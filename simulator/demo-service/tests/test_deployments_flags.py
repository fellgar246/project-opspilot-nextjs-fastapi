from __future__ import annotations

from demo_service.clock import clock


async def test_activation_registers_deployment(client) -> None:
    clock.reset()
    await client.post("/sim/reset")
    before = clock.now()
    await client.post(
        "/sim/scenarios/SCN-007-post-deploy-regression/activate",
        json={"seed": 3},
    )
    deployments = (await client.get("/sim/deployments", params={"service": "demo-service"})).json()
    assert deployments
    latest = deployments[0]
    assert latest["version"] == "v2.16.0"
    # Deploy precedes degradation start (offset_seconds = -120).
    assert latest["deployed_at"] < before + 1


async def test_deployments_range_filter(client, app) -> None:
    store = app.state.engine.deployments
    store.add(
        service="demo-service",
        version="v0.0.1",
        commit_sha="abc",
        deployed_at=100.0,
    )
    store.add(
        service="demo-service",
        version="v0.0.2",
        commit_sha="def",
        deployed_at=200.0,
    )
    response = await client.get(
        "/sim/deployments",
        params={"service": "demo-service", "from_ts": 150, "to_ts": 250},
    )
    versions = {d["version"] for d in response.json()}
    assert "v0.0.2" in versions
    assert "v0.0.1" not in versions


async def test_rollback_requires_auth(client) -> None:
    clock.reset()
    activate = await client.post(
        "/sim/scenarios/SCN-003-db-pool-exhaustion/activate",
        json={"seed": 1},
    )
    dep_id = activate.json()["deployment_id"]
    unauthorized = await client.post(f"/sim/deployments/{dep_id}/rollback")
    assert unauthorized.status_code == 401

    authorized = await client.post(
        f"/sim/deployments/{dep_id}/rollback",
        headers={"Authorization": "Bearer test-token"},
    )
    assert authorized.status_code == 200
    assert authorized.json()["changelog"].startswith("Rollback")


async def test_flag_mutation_requires_auth(client) -> None:
    denied = await client.post(
        "/sim/feature-flags/new-checkout-flow",
        json={"enabled": True, "rollout_percentage": 100},
    )
    assert denied.status_code == 401

    ok = await client.post(
        "/sim/feature-flags/new-checkout-flow",
        json={"enabled": False, "rollout_percentage": 0},
        headers={"Authorization": "Bearer test-token"},
    )
    assert ok.status_code == 200
    assert ok.json()["enabled"] is False


async def test_clock_advance(client) -> None:
    clock.reset()
    before = (await client.get("/sim/clock")).json()["offset_seconds"]
    after = (await client.post("/sim/clock", json={"advance_seconds": 30})).json()
    assert after["offset_seconds"] == before + 30
