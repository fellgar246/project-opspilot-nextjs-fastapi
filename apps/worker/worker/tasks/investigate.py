from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime

from app.incidents.models import HypothesisStatus
from app.incidents.service import create_hypothesis
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


async def investigate_incident(ctx: dict[str, object], agent_run_id: str) -> dict[str, str]:
    settings = get_worker_settings()
    run_id = uuid.UUID(agent_run_id)
    engine = create_async_engine(database_url_async(str(settings.database_url)))
    session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

    async with session_factory() as session:
        agent_run = await session.get(AgentRun, run_id)
        if agent_run is None:
            logger.error("agent_run_not_found", extra={"agent_run_id": agent_run_id})
            return {"status": "not_found"}

        if agent_run.status == AgentRunStatus.PAUSED:
            return {"status": "paused"}

        agent_run.status = AgentRunStatus.RUNNING
        if agent_run.started_at is None:
            agent_run.started_at = datetime.now(UTC)
        await session.commit()

        incident = await load_incident_context(session, agent_run.incident_id)
        retrieval_store = SqlRetrievalStore(session)
        registry = build_default_registry(retrieval_store=retrieval_store)
        persistence = SqlAlchemyToolPersistence(session)
        publisher = WorkerEventPublisher(
            session,
            incident_id=agent_run.incident_id,
            agent_run_id=agent_run.id,
        )
        gateway = ToolGateway(registry, persistence, event_publisher=publisher)
        provider = create_provider()

        checkpointer = await create_postgres_checkpointer(str(settings.database_url))

        async def pause_checker() -> bool:
            async with session_factory() as check_session:
                row = await check_session.get(AgentRun, run_id)
                return row is not None and row.status == AgentRunStatus.PAUSED

        approval_store = SqlApprovalStore(session)

        try:
            final_state = await run_investigation(
                provider=provider,
                gateway=gateway,
                checkpointer=checkpointer,
                incident=incident,
                agent_run_id=run_id,
                graph_thread_id=agent_run.graph_thread_id,
                pause_checker=pause_checker,
                approval_store=approval_store,
                event_publisher=publisher,
            )
        except Exception as exc:
            logger.exception("investigation_failed", extra={"agent_run_id": agent_run_id})
            agent_run.status = AgentRunStatus.FAILED
            agent_run.error = str(exc)
            agent_run.completed_at = datetime.now(UTC)
            await session.commit()
            return {"status": "failed"}

        if final_state.get("investigation_status") == "awaiting_approval":
            agent_run.status = AgentRunStatus.AWAITING_APPROVAL
            await session.commit()
            await engine.dispose()
            return {"status": "awaiting_approval"}

        for hypothesis in final_state.get("hypotheses") or []:
            status = (
                HypothesisStatus.REJECTED
                if hypothesis.get("status") == "rejected"
                else HypothesisStatus.PROPOSED
            )
            await create_hypothesis(
                session,
                incident_id=agent_run.incident_id,
                statement=hypothesis["statement"],
                confidence=hypothesis["confidence"],
                supporting_evidence=[uuid.UUID(item) for item in hypothesis["supporting_evidence"]],
                contradicting_evidence=[
                    uuid.UUID(item) for item in hypothesis.get("contradicting_evidence", [])
                ],
                status=status,
                confidence_breakdown=hypothesis.get("confidence_breakdown"),
                grounding=hypothesis.get("grounding"),
                critic_verdict=hypothesis.get("critic_verdict"),
                assumptions=hypothesis.get("assumptions"),
                missing_evidence=hypothesis.get("missing_evidence"),
                rejection_reason=hypothesis.get("rejection_reason"),
                hypothesis_type=hypothesis.get("hypothesis_type"),
            )

        await finalize_agent_run(session, agent_run, final_state=final_state)
        await session.commit()

    await engine.dispose()
    return {"status": final_state.get("investigation_status", "completed")}
