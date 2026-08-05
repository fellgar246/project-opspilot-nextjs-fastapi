from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from app.audit.event_types import AuditEventType
from app.audit.service import record_audit_event
from app.auth.models import RefreshToken, User, UserRole
from app.auth.schemas import MeResponse
from app.auth.security import (
    ACCESS_COOKIE,
    REFRESH_COOKIE,
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    refresh_token_expires_at,
    verify_password,
)
from app.core.config import Settings
from app.core.errors import AppError
from starlette.responses import Response
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession


@dataclass(frozen=True)
class TokenPair:
    access_token: str
    refresh_token: str
    user: User


def user_to_me(user: User) -> MeResponse:
    return MeResponse(
        id=str(user.id),
        email=user.email,
        display_name=user.display_name,
        role=user.role.value,
    )


async def get_user_by_email(session: AsyncSession, email: str) -> User | None:
    normalized = email.strip().lower()
    result = await session.execute(select(User).where(func.lower(User.email) == normalized))
    return result.scalar_one_or_none()


async def authenticate(
    session: AsyncSession,
    *,
    email: str,
    password: str,
) -> User | None:
    user = await get_user_by_email(session, email)
    if user is None or not user.is_active:
        return None
    if not verify_password(user.password_hash, password):
        return None
    return user


async def issue_tokens(session: AsyncSession, user: User, settings: Settings) -> TokenPair:
    access_token = create_access_token(user_id=user.id, role=user.role.value, settings=settings)
    refresh_token = generate_refresh_token()
    family_id = uuid.uuid4()
    session.add(
        RefreshToken(
            user_id=user.id,
            family_id=family_id,
            token_hash=hash_refresh_token(refresh_token),
            expires_at=refresh_token_expires_at(settings),
        )
    )
    await session.flush()
    return TokenPair(access_token=access_token, refresh_token=refresh_token, user=user)


async def rotate_refresh_token(
    session: AsyncSession,
    *,
    refresh_token: str,
    settings: Settings,
    request_id: str | None,
) -> TokenPair:
    token_hash = hash_refresh_token(refresh_token)
    result = await session.execute(
        select(RefreshToken).where(RefreshToken.token_hash == token_hash)
    )
    stored = result.scalar_one_or_none()
    if stored is None or stored.revoked_at is not None:
        raise AppError("Invalid credentials", status_code=401)

    now = datetime.now(UTC)
    if stored.expires_at <= now:
        raise AppError("Invalid credentials", status_code=401)

    if stored.used_at is not None:
        await revoke_token_family(session, stored.family_id)
        await record_audit_event(
            session,
            actor_type="user",
            actor_id=stored.user_id,
            event_type=AuditEventType.AUTH_TOKEN_REUSE_DETECTED,
            entity_type="user",
            entity_id=stored.user_id,
            payload={"family_id": str(stored.family_id)},
            request_id=request_id,
        )
        await session.commit()
        raise AppError("Invalid credentials", status_code=401)

    user_result = await session.execute(select(User).where(User.id == stored.user_id))
    user = user_result.scalar_one()
    if not user.is_active:
        raise AppError("Invalid credentials", status_code=401)

    stored.used_at = now
    new_refresh = generate_refresh_token()
    session.add(
        RefreshToken(
            user_id=user.id,
            family_id=stored.family_id,
            token_hash=hash_refresh_token(new_refresh),
            expires_at=refresh_token_expires_at(settings),
        )
    )
    access_token = create_access_token(user_id=user.id, role=user.role.value, settings=settings)
    await session.flush()
    return TokenPair(access_token=access_token, refresh_token=new_refresh, user=user)


async def revoke_token_family(session: AsyncSession, family_id: uuid.UUID) -> None:
    now = datetime.now(UTC)
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=now)
    )


def set_auth_cookies(response: Response, token_pair: TokenPair, settings: Settings) -> None:
    secure = settings.auth_cookie_secure or settings.app_env != "local"
    response.set_cookie(
        key=ACCESS_COOKIE,
        value=token_pair.access_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=settings.jwt_access_ttl_seconds,
        path="/",
    )
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=token_pair.refresh_token,
        httponly=True,
        secure=secure,
        samesite="lax",
        max_age=settings.jwt_refresh_ttl_seconds,
        path="/",
    )


def clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(key=ACCESS_COOKIE, path="/")
    response.delete_cookie(key=REFRESH_COOKIE, path="/")


async def seed_user_if_missing(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    display_name: str,
    role: UserRole,
) -> bool:
    existing = await get_user_by_email(session, email)
    if existing is not None:
        return False
    session.add(
        User(
            email=email.strip().lower(),
            display_name=display_name,
            role=role,
            password_hash=hash_password(password),
            is_active=True,
        )
    )
    return True
