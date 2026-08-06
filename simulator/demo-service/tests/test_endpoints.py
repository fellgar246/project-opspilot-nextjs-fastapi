from __future__ import annotations


async def test_health(client) -> None:
    response = await client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


async def test_catalog_checkout_orders(client) -> None:
    catalog = await client.get("/catalog")
    assert catalog.status_code == 200
    assert "items" in catalog.json()

    checkout = await client.post("/checkout", json={})
    assert checkout.status_code in {200, 500, 503}

    orders = await client.get("/orders/ord-1001")
    assert orders.status_code in {200, 500, 503}


async def test_metrics_prometheus_format(client) -> None:
    # Generate some traffic first.
    await client.get("/catalog")
    response = await client.get("/metrics")
    assert response.status_code == 200
    body = response.text
    assert "http_requests_total" in body
    assert "http_request_duration_seconds" in body
    assert "db_pool_connections_in_use" in body
    assert "db_pool_wait_seconds" in body
    assert "external_dependency_errors_total" in body
    assert "process_resident_memory_bytes" in body
