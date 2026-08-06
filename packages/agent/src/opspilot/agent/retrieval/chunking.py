from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RunbookChunkDraft:
    chunk_index: int
    heading_path: str
    content: str


@dataclass(frozen=True)
class ParsedRunbook:
    title: str
    source_path: str
    content: str
    checksum: str
    service_name: str | None
    chunks: list[RunbookChunkDraft]


_HEADER_RE = re.compile(r"^(#{1,6})\s+(.+)$", re.MULTILINE)
_SERVICE_RE = re.compile(r"service[:\s]+([a-zA-Z0-9_-]+)", re.IGNORECASE)


def compute_checksum(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


def parse_runbook_file(
    path: Path, *, min_chars: int = 80, max_chars: int = 800, overlap: int = 80
) -> ParsedRunbook:
    raw = path.read_text(encoding="utf-8")
    title = _extract_title(raw, path)
    service_name = _extract_service_name(raw)
    chunks = chunk_by_headers(raw, min_chars=min_chars, max_chars=max_chars, overlap=overlap)
    return ParsedRunbook(
        title=title,
        source_path=str(path),
        content=raw,
        checksum=compute_checksum(raw),
        service_name=service_name,
        chunks=chunks,
    )


def _extract_title(content: str, path: Path) -> str:
    for line in content.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return path.stem.replace("-", " ").title()


def _extract_service_name(content: str) -> str | None:
    match = _SERVICE_RE.search(content)
    if match:
        return match.group(1)
    return None


def chunk_by_headers(
    content: str,
    *,
    min_chars: int = 80,
    max_chars: int = 800,
    overlap: int = 80,
) -> list[RunbookChunkDraft]:
    sections: list[tuple[str, str]] = []
    current_path: list[str] = []
    current_lines: list[str] = []

    def flush() -> None:
        if not current_lines:
            return
        body = "\n".join(current_lines).strip()
        if body:
            sections.append((" > ".join(current_path) or "(root)", body))

    for line in content.splitlines():
        header_match = _HEADER_RE.match(line)
        if header_match:
            flush()
            level = len(header_match.group(1))
            title = header_match.group(2).strip()
            current_path = current_path[: level - 1] + [title]
            current_lines = [line]
        else:
            current_lines.append(line)
    flush()

    if not sections:
        sections = [("(root)", content.strip())]

    chunks: list[RunbookChunkDraft] = []
    index = 0
    for heading_path, body in sections:
        for piece in _split_with_overlap(
            body, min_chars=min_chars, max_chars=max_chars, overlap=overlap
        ):
            chunks.append(
                RunbookChunkDraft(chunk_index=index, heading_path=heading_path, content=piece)
            )
            index += 1
    return chunks


def _split_with_overlap(
    text: str,
    *,
    min_chars: int,
    max_chars: int,
    overlap: int,
) -> list[str]:
    text = text.strip()
    if len(text) <= max_chars:
        return [text] if text else []

    pieces: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + max_chars)
        if end < len(text):
            split_at = text.rfind("\n\n", start, end)
            if split_at == -1 or split_at - start < min_chars:
                split_at = end
            end = split_at
        piece = text[start:end].strip()
        if piece:
            pieces.append(piece)
        if end >= len(text):
            break
        start = max(0, end - overlap)
    return pieces
