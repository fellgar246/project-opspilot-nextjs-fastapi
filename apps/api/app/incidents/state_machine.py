from __future__ import annotations

from app.incidents.models import IncidentStatus

ALLOWED_TRANSITIONS: dict[IncidentStatus, set[IncidentStatus]] = {
    IncidentStatus.OPEN: {IncidentStatus.INVESTIGATING},
    IncidentStatus.INVESTIGATING: {IncidentStatus.MITIGATING},
    IncidentStatus.MITIGATING: {IncidentStatus.MONITORING},
    IncidentStatus.MONITORING: {IncidentStatus.RESOLVED},
    IncidentStatus.RESOLVED: {IncidentStatus.CLOSED},
    IncidentStatus.CLOSED: {IncidentStatus.INVESTIGATING},
}

ADMIN_CLOSE_FROM: frozenset[IncidentStatus] = frozenset(
    status for status in IncidentStatus if status != IncidentStatus.CLOSED
)


def allowed_transitions(
    current: IncidentStatus,
    *,
    is_admin: bool = False,
) -> set[IncidentStatus]:
    transitions = set(ALLOWED_TRANSITIONS.get(current, set()))
    if is_admin and current != IncidentStatus.CLOSED:
        transitions.add(IncidentStatus.CLOSED)
    return transitions


def can_transition(
    current: IncidentStatus,
    target: IncidentStatus,
    *,
    is_admin: bool = False,
) -> bool:
    return target in allowed_transitions(current, is_admin=is_admin)
