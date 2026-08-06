from __future__ import annotations

from app.reports.render import render_markdown_export, render_pdf_bytes


def test_markdown_export_includes_cited_references() -> None:
    content = "Fact [[evidence:abc-123]]"
    exported = render_markdown_export(content)
    assert "Cited references" in exported
    assert "evidence" in exported


def test_pdf_export_graceful_without_reportlab() -> None:
    result = render_pdf_bytes("# Title\nBody")
    assert result is None or isinstance(result, bytes)
