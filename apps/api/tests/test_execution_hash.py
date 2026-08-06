from __future__ import annotations

from app.executions.hash import canonical_parameters_hash, execution_idempotency_key


def test_canonical_hash_is_order_independent() -> None:
    first = canonical_parameters_hash({"b": 2, "a": 1})
    second = canonical_parameters_hash({"a": 1, "b": 2})
    assert first == second


def test_parameter_mismatch_detected() -> None:
    approved = canonical_parameters_hash({"service": "demo", "deployment_id": "dep-1"})
    invoked = canonical_parameters_hash({"service": "demo", "deployment_id": "dep-2"})
    assert approved != invoked


def test_idempotency_key_stable() -> None:
    params_hash = canonical_parameters_hash({"x": 1})
    key_a = execution_idempotency_key("approval-1", params_hash)
    key_b = execution_idempotency_key("approval-1", params_hash)
    assert key_a == key_b
