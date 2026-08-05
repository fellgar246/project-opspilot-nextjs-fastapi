from __future__ import annotations

import itertools

import pytest
from app.incidents.models import IncidentStatus
from app.incidents.state_machine import ALLOWED_TRANSITIONS, can_transition


ALL_STATUSES = list(IncidentStatus)


@pytest.mark.parametrize(
    ("current", "target", "is_admin", "expected"),
    [
        *((status, next_status, False, True) for status, next_status in [
            (IncidentStatus.OPEN, IncidentStatus.INVESTIGATING),
            (IncidentStatus.INVESTIGATING, IncidentStatus.MITIGATING),
            (IncidentStatus.MITIGATING, IncidentStatus.MONITORING),
            (IncidentStatus.MONITORING, IncidentStatus.RESOLVED),
            (IncidentStatus.RESOLVED, IncidentStatus.CLOSED),
        ]),
        (IncidentStatus.OPEN, IncidentStatus.CLOSED, False, False),
        (IncidentStatus.OPEN, IncidentStatus.CLOSED, True, True),
        (IncidentStatus.INVESTIGATING, IncidentStatus.CLOSED, True, True),
        (IncidentStatus.CLOSED, IncidentStatus.OPEN, True, False),
        (IncidentStatus.CLOSED, IncidentStatus.CLOSED, True, False),
    ],
)
def test_can_transition(
    current: IncidentStatus,
    target: IncidentStatus,
    is_admin: bool,
    expected: bool,
) -> None:
    assert can_transition(current, target, is_admin=is_admin) is expected


def test_all_combinations_covered() -> None:
    for current in ALL_STATUSES:
        for target in ALL_STATUSES:
            if current == target:
                continue
            expected_normal = target in ALLOWED_TRANSITIONS.get(current, set())
            expected_admin = expected_normal or (
                current != IncidentStatus.CLOSED and target == IncidentStatus.CLOSED
            )
            assert can_transition(current, target, is_admin=False) is expected_normal
            assert can_transition(current, target, is_admin=True) is expected_admin


def test_no_self_transitions() -> None:
    for status in ALL_STATUSES:
        assert can_transition(status, status, is_admin=False) is False
        assert can_transition(status, status, is_admin=True) is False


def test_exhaustive_invalid_normal_transitions() -> None:
    invalid = [
        (current, target)
        for current, target in itertools.product(ALL_STATUSES, ALL_STATUSES)
        if current != target and not can_transition(current, target, is_admin=False)
    ]
    assert len(invalid) > 0
