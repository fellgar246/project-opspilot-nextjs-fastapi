from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class MeResponse(BaseModel):
    id: str
    email: EmailStr
    display_name: str
    role: str


class TokenPairResponse(BaseModel):
    user: MeResponse
