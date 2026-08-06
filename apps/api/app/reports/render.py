from __future__ import annotations

import re

from app.reports.service import REFERENCE_PATTERN


def render_markdown_export(content: str) -> str:
    cited = REFERENCE_PATTERN.findall(content)
    appendix_lines = ["", "## Cited references", ""]
    seen: set[str] = set()
    for kind, ref_id in cited:
        key = f"{kind}:{ref_id}"
        if key in seen:
            continue
        seen.add(key)
        appendix_lines.append(f"- `{kind}` → `{ref_id}`")
    return content + "\n".join(appendix_lines)


def render_pdf_bytes(content: str) -> bytes | None:
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
        import io

        buffer = io.BytesIO()
        pdf = canvas.Canvas(buffer, pagesize=letter)
        text = pdf.beginText(40, 750)
        for line in content.splitlines()[:120]:
            text.textLine(line[:100])
        pdf.drawText(text)
        pdf.showPage()
        pdf.save()
        return buffer.getvalue()
    except ImportError:
        return None
