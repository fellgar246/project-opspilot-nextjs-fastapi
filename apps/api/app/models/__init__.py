"""Ensure SQLAlchemy models are registered for Alembic autogenerate."""

from app.audit.models import AuditEvent  # noqa: F401
from app.auth.models import RefreshToken, User  # noqa: F401
