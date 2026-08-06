from __future__ import annotations

from demo_service.clock import clock


async def test_list_scenarios(client) -> None:
    response = await client.get("/sim/scenarios")
    assert response.status_code == 200
    ids = {item["id"] for item in response.json()}
    assert len(ids) >= 7
    assert "SCN-003-db-pool-exhaustion" in ids


async def test_activate_ramp_up_and_deactivate(client, app) -> None:
    clock.reset()
    activate = await client.post(
        "/sim/scenarios/SCN-003-db-pool-exhaustion/activate",
        json={"seed": 7, "mode": "live"},
    )
    assert activate.status_code == 200
    assert activate.json()["id"] == "SCN-003-db-pool-exhaustion"

    # Before ramp completes, intensity should be partial.
    state_early = (await client.get("/sim/state")).json()
    assert state_early["active"]
    assert state_early["effects"]["pool_saturation"] < 0.95

    await client.post("/sim/clock", json={"advance_seconds": 180})
    state_late = (await client.get("/sim/state")).json()
    assert state_late["effects"]["pool_saturation"] >= 0.9
    assert state_late["effects"]["external_error_rate"] > 0  # noise signal present

    await client.post("/sim/scenarios/SCN-003-db-pool-exhaustion/deactivate")
    state_down = (await client.get("/sim/state")).json()
    assert "SCN-003-db-pool-exhaustion" not in [a["id"] for a in state_down["active"]]


async def test_multiple_scenarios_active(client) -> None:
    clock.reset()
    await client.post("/sim/scenarios/SCN-001-missing-env/activate", json={"seed": 1})
    await client.post("/sim/scenarios/SCN-004-external-dependency/activate", json={"seed": 2})
    state = (await client.get("/sim/state")).json()
    active_ids = {a["id"] for a in state["active"]}
    assert "SCN-001-missing-env" in active_ids
    assert "SCN-004-external-dependency" in active_ids


async def test_replay_mode_skips_ramp(client) -> None:
    clock.reset()
    await client.post(
        "/sim/scenarios/SCN-003-db-pool-exhaustion/activate",
        json={"seed": 1, "mode": "replay"},
    )
    state = (await client.get("/sim/state")).json()
    assert state["mode"] == "replay"
    assert state["effects"]["pool_saturation"] >= 0.9


async def test_reproducibility_same_seed(client, app) -> None:
    clock.reset()
    await client.post("/sim/reset")
    await client.post(
        "/sim/scenarios/SCN-002-n-plus-one/activate",
        json={"seed": 99, "mode": "live"},
    )
    await client.post("/sim/clock", json={"advance_seconds": 120})
    effects_a = (await client.get("/sim/state")).json()["effects"]

    await client.post("/sim/reset")
    clock.reset()
    await client.post(
        "/sim/scenarios/SCN-002-n-plus-one/activate",
        json={"seed": 99, "mode": "live"},
    )
    await client.post("/sim/clock", json={"advance_seconds": 120})
    effects_b = (await client.get("/sim/state")).json()["effects"]

    tolerance = app.state.settings.reproducibility_tolerance
    assert abs(effects_a["latency_multiplier"] - effects_b["latency_multiplier"]) <= tolerance
    assert effects_a["n_plus_one_queries"] == effects_b["n_plus_one_queries"]


async def test_each_scenario_has_noise_signal(client) -> None:
    scenarios = (await client.get("/sim/scenarios")).json()
    for scenario in scenarios:
        notes = [s.get("note") for s in scenario["signals"] if s.get("note")]
        assert notes, f"{scenario['id']} missing correlated non-causal noise note"
