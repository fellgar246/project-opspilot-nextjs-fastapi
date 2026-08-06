from __future__ import annotations

from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Response
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import require_capability
from app.auth.models import User
from app.auth.policy import Capability
from app.core.errors import AppError
from app.db.session import get_session
from app.incidents.service import require_incident
from app.reports import service as report_service
from app.reports.models import Postmortem
from app.reports.render import render_markdown_export, render_pdf_bytes

router = APIRouter(tags=["reports"])


class PostmortemRead(BaseModel):
    id: str
    incident_id: str
    version: int
    status: str
    content: str
    invalid_references: list[str]
    created_by: str
    created_at: datetime


class PostmortemListResponse(BaseModel):
    items: list[PostmortemRead]


class PostmortemEditRequest(BaseModel):
    content: str = Field(min_length=1)


def _to_read(row: Postmortem) -> PostmortemRead:
    return PostmortemRead(
        id=str(row.id),
        incident_id=str(row.incident_id),
        version=row.version,
        status=row.status,
        content=row.content,
        invalid_references=list(row.invalid_references or []),
        created_by=row.created_by,
        created_at=row.created_at,
    )


@router.get("/incidents/{incident_id}/postmortem", response_model=PostmortemRead)
async def get_postmortem(
    incident_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(require_capability(Capability.READ_INCIDENTS))],
) -> PostmortemRead:
    await require_incident(session, incident_id)
    postmortem = await report_service.get_latest_postmortem(session, incident_id)
    if postmortem is None:
        raise AppError("Postmortem not found", status_code=404)
    return _to_read(postmortem)


@router.get("/incidents/{incident_id}/postmortem/versions", response_model=PostmortemListResponse)
async def list_postmortem_versions(
    incident_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(require_capability(Capability.READ_INCIDENTS))],
) -> PostmortemListResponse:
    await require_incident(session, incident_id)
    rows = await report_service.list_postmortem_versions(session, incident_id)
    return PostmortemListResponse(items=[_to_read(row) for row in rows])


@router.post("/incidents/{incident_id}/postmortem/generate", response_model=PostmortemRead)
async def generate_postmortem(
    incident_id: UUID,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(require_capability(Capability.MANAGE_INVESTIGATION))],
) -> PostmortemRead:
    await require_incident(session, incident_id)
    postmortem = await report_service.generate_postmortem_from_incident(
        session,
        incident_id=incident_id,
    )
    await session.commit()
    return _to_read(postmortem)


@router.patch("/incidents/{incident_id}/postmortem", response_model=PostmortemRead)
async def edit_postmortem(
    incident_id: UUID,
    body: PostmortemEditRequest,
    session: Annotated[AsyncSession, Depends(get_session)],
    actor: Annotated[User, Depends(require_capability(Capability.MANAGE_INVESTIGATION))],
) -> PostmortemRead:
    await require_incident(session, incident_id)
    _ = actor
    postmortem = await report_service.save_postmortem(
        session,
        incident_id=incident_id,
        content=body.content,
        created_by="user",
        regenerate_on_invalid=False,
    )
    await session.commit()
    return _to_read(postmortem)


@router.get("/incidents/{incident_id}/export")
async def export_incident_report(
    incident_id: UUID,
    format: str,
    session: Annotated[AsyncSession, Depends(get_session)],
    _: Annotated[User, Depends(require_capability(Capability.READ_INCIDENTS))],
) -> Response:
    await require_incident(session, incident_id)
    postmortem = await report_service.get_latest_postmortem(session, incident_id)
    if postmortem is None:
        raise AppError("Postmortem not found", status_code=404)

    markdown = render_markdown_export(postmortem.content)
    if format == "md":
        return PlainTextResponse(markdown, media_type="text/markdown")

    if format == "pdf":
        pdf_bytes = render_pdf_bytes(markdown)
        if pdf_bytes is None:
            raise AppError("PDF export unavailable; use format=md", status_code=501)
        return Response(content=pdf_bytes, media_type="application/pdf")

    raise AppError("Unsupported export format", status_code=400)
