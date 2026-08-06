"""Ensure SQLAlchemy models are registered for Alembic autogenerate."""

from app.approvals.models import Approval, ProposedAction  # noqa: F401
from app.audit.models import AuditEvent  # noqa: F401
from app.auth.models import RefreshToken, User  # noqa: F401
from app.events.models import InvestigationEvent  # noqa: F401
from app.incidents.models import (  # noqa: F401
    Evidence,
    Hypothesis,
    Incident,
    IncidentNote,
    IncidentService,
    IncidentStatusHistory,
    Service,
)
from app.investigation.models import AgentRun  # noqa: F401
from app.retrieval.models import HistoricalIncident, Runbook, RunbookChunk  # noqa: F401
from app.tools.store import ToolCall  # noqa: F401
