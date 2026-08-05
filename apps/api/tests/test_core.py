from __future__ import annotations

import logging

import pytest
from app.core.errors import AppError
from app.core.logging import configure_logging
from app.db.session import get_metadata
from app.main import create_app
from httpx import ASGITransport, AsyncClient


def test_configure_logging_sets_json_output(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO")
    logging.getLogger("test").info("hello")
    captured = capsys.readouterr().out
    assert '"message": "hello"' in captured
    assert '"service":' in captured


def test_get_metadata_returns_sqlalchemy_metadata() -> None:
    metadata = get_metadata()
    assert metadata is not None


@pytest.mark.asyncio
async def test_app_error_returns_expected_status(client: AsyncClient) -> None:
    app = create_app()

    @app.get("/boom")
    async def boom() -> None:
        raise AppError("bad request", status_code=400)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as http_client:
        response = await http_client.get("/boom")

    assert response.status_code == 400
    assert response.json()["detail"] == "bad request"
