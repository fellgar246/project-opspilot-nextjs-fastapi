from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from app.approvals import service as approval_service
from app.approvals.models import Approval, ApprovalDecision
from app.investigation.models import AgentRun, AgentRunStatus
from app.investigation.service import finalize_agent_run, load_incident_context
from app.retrieval.store import SqlRetrievalStore
from app.tools.store import SqlAlchemyToolPersistence
from opspilot.agent.graph.checkpointer import create_postgres_checkpointer
from opspilot.agent.runner import create_provider, run_investigation
from opspilot.tools.bootstrap import build_default_registry
from opspilot.tools.gateway import ToolGateway
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from worker.adapters import SqlApprovalStore, WorkerEventPublisher
from worker.config import get_worker_settings
from worker.db import database_url_async

logger = logging.getLogger(__name__)


async def resume_investigation(ctx: dict[str, object], approval_id: str, resume_value: dict) -> dict[str, str]:
    settings = get_worker_settings()
    approval_uuid = uuid.UUID(approval_id)
    engine = create_async_engine(database_url_async(str(settings.database_url)))
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with session_factory() as session:
        approval = await session.get(Approval, approval_uuid)
        if approval is None:
            return {"status": "not_found"}
        if approval.decision == ApprovalDecision.PENDING:
            return {"status": "still_pending"}

        agent_run = await session.get(AgentRun, approval.agent_run_id)
        if agent_run is None:
            return {"status": "agent_run_not_found"}

        agent_run.status = AgentRunStatus.RUNNING
        await session.commit()

        incident = await load_incident_context(session, agent_run.incident_id)
        retrieval_store = SqlRetrievalStore(session)
        registry = build_default_registry(retrieval_store=retrieval_store)
        persistence = SqlAlchemyToolPersistence(session)
        gateway = ToolGateway(registry, persistence)
        provider = create_provider()
        checkpointer = await create_postgres_checkpointer(str(settings.database_url))
        approval_store = SqlApprovalStore(session)
        publisher = WorkerEventPublisher(
            session,
            incident_id=agent_run.incident_id,
            agent_run_id=agent_run.id,
        )

        try:
            final_state = await run_investigation(
                provider=provider,
                gateway=gateway,
                checkpointer=checkpointer,
                incident=incident,
                agent_run_id=agent_run.id,
                graph_thread_id=agent_run.graph_thread_id,
                approval_store=approval_store,
                event_publisher=publisher,
                resume_value=resume_value,
            )
        except Exception as exc:
            logger.exception("resume_investigation_failed", extra={"approval_id": approval_id})
            agent_run.status = AgentRunStatus.FAILED
            agent_run.error = str(exc)
            agent_run.completed_at = datetime.now(UTC)
            await session.commit()
            return {"status": "failed"}

        await finalize_agent_run(session, agent_run, final_state=final_state)
        await session.commit()

    await engine.dispose()
    return {"status": final_state.get("investigation_status", "completed")}


async def expire_pending_approvals(ctx: dict[str, object]) -> dict[str, int]:
    settings = get_worker_settings()
    engine = create_async_engine(database_url_async(str(settings.database_url)))
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
    expired_count = 0

    async with session_factory() as session:
        from sqlalchemy import select

        result = await session.execute(
            select(Approval).where(Approval.decision == ApprovalDecision.PENDING)
        )
        approvals = list(result.scalars().all())
        for approval in approvals:
            if await approval_service.expire_approval(session, approval):
                expired_count += 1
        await session.commit()

    await engine.dispose()
    return {"expired": expired_count}
