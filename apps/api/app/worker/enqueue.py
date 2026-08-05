from __future__ import annotations

from app.core.context import request_id_var


def get_request_id() -> str | None:
    return request_id_var.get()


def enqueue_kwargs() -> dict[str, str]:
    request_id = get_request_id()
    if request_id is None:
        return {}
    return {"request_id": request_id}
