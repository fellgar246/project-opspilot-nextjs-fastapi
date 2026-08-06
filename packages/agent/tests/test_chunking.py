from __future__ import annotations

from pathlib import Path

from opspilot.agent.retrieval.chunking import chunk_by_headers, parse_runbook_file


def test_chunk_by_headers_respects_structure() -> None:
    content = "# Root\n\nIntro\n\n## Step 1\n\nDo thing\n\n## Step 2\n\nDo other"
    chunks = chunk_by_headers(content, min_chars=10, max_chars=200, overlap=10)
    assert len(chunks) >= 2
    assert any("Step 1" in chunk.heading_path for chunk in chunks)


def test_parse_real_runbook() -> None:
    root = Path(__file__).resolve().parents[3]
    path = root / "simulator/data/runbooks/RB-001-missing-env.md"
    parsed = parse_runbook_file(path)
    assert parsed.title
    assert parsed.checksum
    assert parsed.chunks
