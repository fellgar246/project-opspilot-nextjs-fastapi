from __future__ import annotations

import pytest
from opspilot.schemas.evidence import validate_structured_data


@pytest.mark.parametrize(
    ("source_type", "data"),
    [
        ("metric", {"metric_name": "http_errors", "value": 42.0, "unit": "count"}),
        ("log", {"level": "error", "service": "demo-service", "status": 500}),
        (
            "deployment",
            {
                "deployment_id": "dep-1",
                "service": "demo-service",
                "version": "1.2.3",
                "commit_sha": "abc123",
                "deployed_by": "ci",
                "status": "success",
            },
        ),
        ("commit", {"sha": "abc123", "author": "dev", "message": "fix pool size"}),
        ("pull_request", {"number": 42, "title": "Fix pool", "author": "dev"}),
        ("feature_flag", {"key": "new-checkout", "service": "demo-service", "enabled": True}),
        ("runbook", {"runbook_id": "rb-1", "title": "Pool saturation"}),
        (
            "similar_incident",
            {
                "incident_id": "inc-1",
                "title": "Past incident",
                "root_cause": "Pool too small",
                "resolution": "Increased pool size",
            },
        ),
        ("note", {"author": "operator", "tags": ["manual"]}),
    ],
)
def test_validate_structured_data_accepts_valid_payload(source_type: str, data: dict) -> None:
    result = validate_structured_data(source_type, data)
    assert isinstance(result, dict)


def test_validate_structured_data_rejects_invalid_metric() -> None:
    with pytest.raises(ValueError, match="metric_name"):
        validate_structured_data("metric", {"value": 1.0})


def test_validate_structured_data_rejects_unknown_type() -> None:
    with pytest.raises(ValueError, match="Unknown source_type"):
        validate_structured_data("unknown", {})
