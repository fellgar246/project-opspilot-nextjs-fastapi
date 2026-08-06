from __future__ import annotations

from app.reports.service import REFERENCE_PATTERN, _strip_invalid_references


def test_reference_pattern_extracts_typed_refs() -> None:
    content = "See [[evidence:abc]] and [[hypothesis:def]]"
    refs = REFERENCE_PATTERN.findall(content)
    assert ("evidence", "abc") in refs
    assert ("hypothesis", "def") in refs


def test_strip_invalid_references() -> None:
    content = "Bad [[evidence:missing]] ok [[incident:1]]"
    stripped = _strip_invalid_references(content, ["evidence:missing"])
    assert "[[evidence:missing]]" not in stripped
    assert "[[incident:1]]" in stripped
