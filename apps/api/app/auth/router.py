from __future__ import annotations

from typing import Annotated

from app.audit.event_types import AuditEventType
from app.audit.service import record_audit_event
from app.auth.dependencies import require_authenticated
from app.auth.models import User
from app.auth.rate_limit import check_auth_rate_limit, record_rate_limited
from app.auth.schemas import LoginRequest, MeResponse, TokenPairResponse
from app.auth.security import REFRESH_COOKIE
from app.auth.service import (
    authenticate,
    clear_auth_cookies,
    issue_tokens,
    rotate_refresh_token,
    set_auth_cookies,
    user_to_me,
)
from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.core.redis import get_redis
from app.db.session import get_session
from fastapi import APIRouter, Cookie, Depends, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(prefix="/auth", tags=["auth"])


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client is None:
        return "unknown"
    return request.client.host


@router.post("/login", response_model=TokenPairResponse)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenPairResponse:
    ip_address = _client_ip(request)
    request_id = getattr(request.state, "request_id", None)
    redis = get_redis()
    try:
        await check_auth_rate_limit(
            redis=redis,
            settings=settings,
            ip_address=ip_address,
            email=body.email,
        )
    except AppError:
        await record_rate_limited(
            session,
            email=body.email,
            ip_address=ip_address,
            request_id=request_id,
        )
        raise

    user = await authenticate(session, email=body.email, password=body.password)
    if user is None:
        await record_audit_event(
            session,
            actor_type="system",
            actor_id=None,
            event_type=AuditEventType.AUTH_LOGIN_FAILED,
            entity_type="auth",
            entity_id=None,
            payload={"email": body.email},
            request_id=request_id,
        )
        await session.commit()
        raise AppError("Invalid credentials", status_code=401)

    token_pair = await issue_tokens(session, user, settings)
    await record_audit_event(
        session,
        actor_type="user",
        actor_id=user.id,
        event_type=AuditEventType.AUTH_LOGIN_SUCCEEDED,
        entity_type="user",
        entity_id=user.id,
        payload={"email": user.email},
        request_id=request_id,
    )
    await session.commit()
    set_auth_cookies(response, token_pair, settings)
    return TokenPairResponse(user=user_to_me(user))


@router.post("/refresh", response_model=TokenPairResponse)
async def refresh(
    request: Request,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    refresh_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None,
) -> TokenPairResponse:
    if refresh_token is None:
        raise AppError("Authentication required", status_code=401)
    request_id = getattr(request.state, "request_id", None)
    token_pair = await rotate_refresh_token(
        session,
        refresh_token=refresh_token,
        settings=settings,
        request_id=request_id,
    )
    await session.commit()
    set_auth_cookies(response, token_pair, settings)
    return TokenPairResponse(user=user_to_me(token_pair.user))


@router.get("/me", response_model=MeResponse)
async def me(user: Annotated[User, Depends(require_authenticated())]) -> MeResponse:
    return user_to_me(user)


@router.post("/logout")
async def logout(
    response: Response,
    _: Annotated[User, Depends(require_authenticated())],
) -> dict[str, str]:
    clear_auth_cookies(response)
    return {"detail": "Logged out"}
