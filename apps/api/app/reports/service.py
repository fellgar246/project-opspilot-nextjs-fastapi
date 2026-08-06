from __future__ import annotations

import re
import uuid

from app.audit.event_types import AuditEventType
from app.audit.service import record_audit_event
from app.events.bus import publish_event
from app.events.models import InvestigationEventType
from app.incidents.models import Evidence, Hypothesis
from app.incidents.timeline import assemble_timeline
from app.reports.models import Postmortem, PostmortemStatus
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

REFERENCE_PATTERN = re.compile(r"\[\[(evidence|hypothesis|action|timeline|incident):([^\]]+)\]\]")


async def validate_references(
    session: AsyncSession,
    *,
    incident_id: uuid.UUID,
    content: str,
) -> list[str]:
    invalid: list[str] = []
    for kind, ref_id in REFERENCE_PATTERN.findall(content):
        if kind == "incident":
            if ref_id != str(incident_id):
                invalid.append(f"{kind}:{ref_id}")
            continue
        if kind == "timeline":
            timeline = await assemble_timeline(session, incident_id)
            if not any(str(entry.id) == ref_id for entry in timeline):
                invalid.append(f"{kind}:{ref_id}")
            continue
        try:
            parsed = uuid.UUID(ref_id)
        except ValueError:
            invalid.append(f"{kind}:{ref_id}")
            continue
        if kind == "evidence":
            row = await session.get(Evidence, parsed)
            if row is None or row.incident_id != incident_id:
                invalid.append(f"{kind}:{ref_id}")
        elif kind == "hypothesis":
            row = await session.get(Hypothesis, parsed)
            if row is None or row.incident_id != incident_id:
                invalid.append(f"{kind}:{ref_id}")
        elif kind == "action":
            from app.approvals.models import ProposedAction

            row = await session.get(ProposedAction, parsed)
            if row is None or row.incident_id != incident_id:
                invalid.append(f"{kind}:{ref_id}")
    return invalid


async def _next_version(session: AsyncSession, incident_id: uuid.UUID) -> int:
    result = await session.execute(
        select(func.coalesce(func.max(Postmortem.version), 0)).where(
            Postmortem.incident_id == incident_id
        )
    )
    current = int(result.scalar_one())
    return current + 1


async def save_postmortem(
    session: AsyncSession,
    *,
    incident_id: uuid.UUID,
    content: str,
    created_by: str = "agent",
    regenerate_on_invalid: bool = True,
) -> Postmortem:
    invalid = await validate_references(session, incident_id=incident_id, content=content)
    status = PostmortemStatus.DRAFT
    final_content = content

    if invalid and regenerate_on_invalid:
        stripped = _strip_invalid_references(content, invalid)
        invalid = await validate_references(session, incident_id=incident_id, content=stripped)
        final_content = stripped

    if invalid:
        status = PostmortemStatus.DRAFT_WITH_WARNINGS

    version = await _next_version(session, incident_id)
    postmortem = Postmortem(
        id=uuid.uuid4(),
        incident_id=incident_id,
        version=version,
        status=status.value,
        content=final_content,
        invalid_references=invalid,
        created_by=created_by,
    )
    session.add(postmortem)
    await session.flush()

    await publish_event(
        session,
        incident_id=incident_id,
        agent_run_id=None,
        event_type=InvestigationEventType.POSTMORTEM_GENERATED,
        payload={"postmortem_id": str(postmortem.id), "version": version, "status": status.value},
    )
    await record_audit_event(
        session,
        actor_type=created_by if created_by in {"user", "agent"} else "agent",
        actor_id=postmortem.id,
        event_type=AuditEventType.POSTMORTEM_GENERATED,
        entity_type="postmortem",
        entity_id=postmortem.id,
        payload={
            "incident_id": str(incident_id),
            "version": version,
            "invalid_references": invalid,
        },
    )
    return postmortem


def _strip_invalid_references(content: str, invalid: list[str]) -> str:
    result = content
    for ref in invalid:
        kind, ref_id = ref.split(":", 1)
        result = result.replace(f"[[{kind}:{ref_id}]]", "")
    return result


async def get_latest_postmortem(
    session: AsyncSession,
    incident_id: uuid.UUID,
) -> Postmortem | None:
    result = await session.execute(
        select(Postmortem)
        .where(Postmortem.incident_id == incident_id)
        .order_by(Postmortem.version.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def list_postmortem_versions(
    session: AsyncSession,
    incident_id: uuid.UUID,
) -> list[Postmortem]:
    result = await session.execute(
        select(Postmortem)
        .where(Postmortem.incident_id == incident_id)
        .order_by(Postmortem.version.desc())
    )
    return list(result.scalars().all())


async def generate_postmortem_from_incident(
    session: AsyncSession,
    *,
    incident_id: uuid.UUID,
) -> Postmortem:
    from app.incidents.service import require_incident

    incident = await require_incident(session, incident_id)
    timeline = await assemble_timeline(session, incident_id)
    lines = [
        f"# Postmortem: {incident.title}",
        "",
        "## Executive summary",
        incident.description,
        "",
        "## Timeline",
    ]
    for entry in timeline:
        lines.append(f"- {entry.occurred_at.isoformat()}: {entry.title} [[timeline:{entry.id}]]")

    lines.extend(["", "## Root cause", "See investigation hypotheses for details."])
    content = "\n".join(lines)
    return await save_postmortem(session, incident_id=incident_id, content=content)
