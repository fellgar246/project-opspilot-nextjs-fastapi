from __future__ import annotations

from typing import Annotated, Any

from email_validator import EmailNotValidError, validate_email
from pydantic import BaseModel, BeforeValidator, Field

_LOCAL_DEV_DOMAIN_SUFFIX = ".local"


def _validate_app_email(value: Any) -> str:
    """Validate emails, including project seed domains like *.local."""
    email = str(value).strip().lower()
    local_part, separator, domain = email.partition("@")
    if not separator or not local_part or not domain or " " in email or "." not in domain:
        raise ValueError("value is not a valid email address")

    # email-validator rejects IANA special-use names like .local; allow them for local/dev seeds.
    if domain.endswith(_LOCAL_DEV_DOMAIN_SUFFIX):
        return email

    try:
        result = validate_email(
            email,
            check_deliverability=False,
            globally_deliverable=False,
            test_environment=True,
        )
    except EmailNotValidError as exc:
        raise ValueError(str(exc)) from exc
    return result.normalized


AppEmail = Annotated[str, BeforeValidator(_validate_app_email)]


class LoginRequest(BaseModel):
    email: AppEmail
    password: str = Field(min_length=1)


class MeResponse(BaseModel):
    id: str
    email: AppEmail
    display_name: str
    role: str


class TokenPairResponse(BaseModel):
    user: MeResponse
