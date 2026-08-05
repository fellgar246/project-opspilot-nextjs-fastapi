from __future__ import annotations

import uuid
from typing import Annotated, Any

import jwt
from app.auth.models import User
from app.auth.policy import Capability, role_has_capability
from app.auth.security import ACCESS_COOKIE, decode_access_token
from app.core.config import Settings, get_settings
from app.core.errors import AppError
from app.db.session import get_session
from fastapi import Cookie, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

ROUTE_POLICY_ATTR = "__route_policy__"


def _mark_policy(dependency: Any, policy: str) -> Any:
    setattr(dependency, ROUTE_POLICY_ATTR, policy)
    return dependency


async def get_current_user(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    access_token: Annotated[str | None, Cookie(alias=ACCESS_COOKIE)] = None,
) -> User:
    if not access_token:
        raise AppError("Authentication required", status_code=401)
    try:
        payload = decode_access_token(access_token, settings)
    except jwt.PyJWTError as exc:
        raise AppError("Authentication required", status_code=401) from exc

    user_id = uuid.UUID(str(payload["sub"]))
    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise AppError("Authentication required", status_code=401)
    request.state.current_user = user
    return user


def require_authenticated() -> Any:
    async def dependency(user: Annotated[User, Depends(get_current_user)]) -> User:
        return user

    return _mark_policy(dependency, "authenticated")


def require_capability(capability: Capability) -> Any:
    async def dependency(user: Annotated[User, Depends(get_current_user)]) -> User:
        if not role_has_capability(user.role.value, capability):
            raise AppError("Insufficient permissions", status_code=403)
        return user

    return _mark_policy(dependency, capability.value)


def require_not_proposer(proposer_id: uuid.UUID) -> Any:
    async def dependency(user: Annotated[User, Depends(get_current_user)]) -> User:
        if user.id == proposer_id:
            raise AppError("self_approval_forbidden", status_code=403)
        return user

    return _mark_policy(dependency, "not_proposer")
