"""Shared Pydantic schemas."""

from opspilot.schemas.evidence import (
    SourceType,
    validate_structured_data,
)

__all__ = ["SourceType", "validate_structured_data"]
