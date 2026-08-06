from __future__ import annotations

import uuid
from typing import Any
from uuid import UUID

from app.reports import service as report_service
from sqlalchemy.ext.asyncio import AsyncSession


class SqlPostmortemStore:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save_generated(
        self,
        *,
        incident_id: UUID,
        content: str,
    ) -> dict[str, Any]:
        postmortem = await report_service.save_postmortem(
            self.session,
            incident_id=incident_id,
            content=content,
            created_by="agent",
        )
        return {
            "id": str(postmortem.id),
            "status": postmortem.status,
            "version": postmortem.version,
        }
