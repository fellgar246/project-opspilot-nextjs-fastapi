from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from opspilot.agent.providers.base import LLMProvider
from opspilot.agent.retrieval.chunking import ParsedRunbook, parse_runbook_file
from opspilot.agent.retrieval.embeddings import (
    DEFAULT_MODEL_NAME,
    EMBEDDING_DIM,
    embed_texts_batched,
)


@dataclass(frozen=True)
class IngestStats:
    runbooks_processed: int
    runbooks_skipped: int
    chunks_created: int
    incidents_processed: int


@dataclass(frozen=True)
class IngestedChunk:
    runbook_id: str
    title: str
    source_path: str
    version: int
    service_name: str | None
    chunk_index: int
    heading_path: str
    content: str
    embedding: list[float]
    model_name: str


@dataclass(frozen=True)
class IngestedIncident:
    external_id: str
    title: str
    service_name: str
    root_cause: str
    resolution: str
    tags: list[str]
    search_text: str
    embedding: list[float]
    model_name: str


async def load_runbooks_from_dir(
    runbooks_dir: Path,
    provider: LLMProvider,
    *,
    model_name: str = DEFAULT_MODEL_NAME,
    expected_dim: int = EMBEDDING_DIM,
) -> tuple[list[ParsedRunbook], list[IngestedChunk]]:
    files = sorted(runbooks_dir.glob("*.md"))
    parsed = [parse_runbook_file(path) for path in files]
    texts = [chunk.content for rb in parsed for chunk in rb.chunks]
    vectors = await embed_texts_batched(
        provider.embed,
        texts,
        expected_dim=expected_dim,
        model_name=model_name,
    )

    ingested: list[IngestedChunk] = []
    cursor = 0
    for rb in parsed:
        runbook_id = rb.checksum[:32]
        for chunk in rb.chunks:
            ingested.append(
                IngestedChunk(
                    runbook_id=runbook_id,
                    title=rb.title,
                    source_path=rb.source_path,
                    version=1,
                    service_name=rb.service_name,
                    chunk_index=chunk.chunk_index,
                    heading_path=chunk.heading_path,
                    content=chunk.content,
                    embedding=vectors[cursor],
                    model_name=model_name,
                )
            )
            cursor += 1
    return parsed, ingested


async def load_historical_incidents_from_dir(
    incidents_dir: Path,
    provider: LLMProvider,
    *,
    model_name: str = DEFAULT_MODEL_NAME,
    expected_dim: int = EMBEDDING_DIM,
) -> list[IngestedIncident]:
    files = sorted(incidents_dir.glob("*.json"))
    records: list[dict[str, object]] = []
    for path in files:
        records.append(json.loads(path.read_text(encoding="utf-8")))

    texts = [
        f"{rec['title']} {rec['root_cause']} {rec['resolution']} {rec.get('service', '')}"
        for rec in records
    ]
    vectors = await embed_texts_batched(
        provider.embed,
        texts,
        expected_dim=expected_dim,
        model_name=model_name,
    )

    ingested: list[IngestedIncident] = []
    for rec, vector in zip(records, vectors, strict=True):
        ingested.append(
            IngestedIncident(
                external_id=str(rec["incident_id"]),
                title=str(rec["title"]),
                service_name=str(rec.get("service", "unknown")),
                root_cause=str(rec["root_cause"]),
                resolution=str(rec["resolution"]),
                tags=[str(tag) for tag in cast(list[Any], rec.get("tags", []))],
                search_text=texts[len(ingested)],
                embedding=vector,
                model_name=model_name,
            )
        )
    return ingested
