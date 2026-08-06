from __future__ import annotations

import pytest
from opspilot.tools.execute.execute_simulated_action import assert_simulator_url


def test_simulator_url_guard_rejects_external_host() -> None:
    with pytest.raises(ValueError, match="simulator"):
        assert_simulator_url("https://evil.example.com")


def test_simulator_url_guard_allows_localhost() -> None:
    assert_simulator_url("http://127.0.0.1:8080")
