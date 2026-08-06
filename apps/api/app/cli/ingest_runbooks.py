from __future__ import annotations

import asyncio
import uuid
from pathlib import Path

from app.core.config import ROOT_DIR, get_settings
from app.retrieval.models import HistoricalIncident, Runbook, RunbookChunk
from app.retrieval.store import resolve_service_id
from opspilot.agent.retrieval.chunking import parse_runbook_file
from opspilot.agent.retrieval.embeddings import (
    DEFAULT_MODEL_NAME,
    EMBEDDING_DIM,
    embed_texts_batched,
)
from opspilot.agent.retrieval.ingest import load_historical_incidents_from_dir
from opspilot.agent.runner import create_provider
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


async def ingest_runbooks(session: AsyncSession, *, repo_root: Path) -> dict[str, int]:
    runbooks_dir = repo_root / "simulator/data/runbooks"
    incidents_dir = repo_root / "datasets/incidents"
    provider = create_provider()
    model_name = DEFAULT_MODEL_NAME

    processed = skipped = chunks_created = incidents_processed = 0
    for path in sorted(runbooks_dir.glob("*.md")):
        parsed = parse_runbook_file(path)
        existing = await session.scalar(
            select(Runbook).where(Runbook.checksum == parsed.checksum, Runbook.is_current.is_(True))
        )
        if existing is not None:
            skipped += 1
            continue

        prior = await session.scalar(
            select(Runbook).where(Runbook.source_path == parsed.source_path)
        )
        version = 1 if prior is None else prior.version + 1
        if prior is not None:
            prior.is_current = False

        service_id = await resolve_service_id(session, parsed.service_name)
        runbook = Runbook(
            id=uuid.uuid4(),
            service_id=service_id,
            title=parsed.title,
            content=parsed.content,
            version=version,
            source_path=parsed.source_path,
            checksum=parsed.checksum,
            is_current=True,
        )
        session.add(runbook)
        await session.flush()

        texts = [chunk.content for chunk in parsed.chunks]
        vectors = await embed_texts_batched(
            provider.embed,
            texts,
            expected_dim=EMBEDDING_DIM,
            model_name=model_name,
        )
        for chunk, vector in zip(parsed.chunks, vectors, strict=True):
            session.add(
                RunbookChunk(
                    id=uuid.uuid4(),
                    runbook_id=runbook.id,
                    chunk_index=chunk.chunk_index,
                    heading_path=chunk.heading_path,
                    content=chunk.content,
                    embedding=vector,
                    model_name=model_name,
                )
            )
            chunks_created += 1
        processed += 1

    incidents = await load_historical_incidents_from_dir(incidents_dir, provider)
    await session.execute(delete(HistoricalIncident))
    for incident in incidents:
        session.add(
            HistoricalIncident(
                id=uuid.uuid4(),
                external_id=incident.external_id,
                title=incident.title,
                service_name=incident.service_name,
                root_cause=incident.root_cause,
                resolution=incident.resolution,
                tags=incident.tags,
                search_text=incident.search_text,
                embedding=incident.embedding,
                model_name=incident.model_name,
            )
        )
        incidents_processed += 1

    await session.commit()
    return {
        "runbooks_processed": processed,
        "runbooks_skipped": skipped,
        "chunks_created": chunks_created,
        "incidents_processed": incidents_processed,
    }


def main() -> None:
    settings = get_settings()
    repo_root = ROOT_DIR

    def _database_url_async(url: str) -> str:
        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+asyncpg://", 1)
        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+asyncpg://", 1)
        return url

    async def _run() -> None:
        engine = create_async_engine(_database_url_async(str(settings.database_url)))
        session_factory = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
        async with session_factory() as session:
            stats = await ingest_runbooks(session, repo_root=repo_root)
            print(stats)
        await engine.dispose()

    asyncio.run(_run())


if __name__ == "__main__":
    main()
