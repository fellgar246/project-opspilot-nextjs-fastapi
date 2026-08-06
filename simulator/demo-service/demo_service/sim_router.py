from __future__ import annotations

from typing import Any, Literal, cast

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel, Field

router = APIRouter(prefix="/sim")


class ActivateBody(BaseModel):
    seed: int = 42
    mode: Literal["live", "replay"] = "live"


class ClockBody(BaseModel):
    advance_seconds: float | None = None
    offset_seconds: float | None = None


class FlagBody(BaseModel):
    enabled: bool
    rollout_percentage: float = Field(ge=0, le=100)
    updated_by: str = "operator"


def _require_internal_auth(request: Request, authorization: str | None) -> None:
    expected = request.app.state.settings.internal_auth_token
    if authorization != f"Bearer {expected}":
        raise HTTPException(status_code=401, detail="Missing or invalid internal authorization")


@router.get("/scenarios")
async def list_scenarios(request: Request) -> list[dict[str, Any]]:
    engine = request.app.state.engine
    return [s.model_dump() for s in engine.list_scenarios()]


@router.get("/state")
async def get_state(request: Request) -> dict[str, Any]:
    return cast(dict[str, Any], request.app.state.engine.state())


@router.post("/scenarios/{scenario_id}/activate")
async def activate_scenario(
    scenario_id: str,
    body: ActivateBody,
    request: Request,
) -> dict[str, Any]:
    engine = request.app.state.engine
    try:
        active = engine.activate(scenario_id, seed=body.seed, mode=body.mode)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown scenario: {scenario_id}") from exc
    return cast(dict[str, Any], active.model_dump())


@router.post("/scenarios/{scenario_id}/deactivate")
async def deactivate_scenario(scenario_id: str, request: Request) -> dict[str, str]:
    request.app.state.engine.deactivate(scenario_id)
    return {"status": "deactivating", "scenario_id": scenario_id}


@router.post("/reset")
async def reset_simulator(request: Request) -> dict[str, str]:
    request.app.state.engine.reset()
    return {"status": "reset"}


@router.get("/clock")
async def get_clock(request: Request) -> dict[str, Any]:
    state = cast(dict[str, Any], request.app.state.engine.state())
    return cast(dict[str, Any], state["clock"])


@router.post("/clock")
async def set_clock(body: ClockBody, request: Request) -> dict[str, Any]:
    from demo_service.clock import clock

    if body.offset_seconds is not None:
        clock.set_offset(body.offset_seconds)
    elif body.advance_seconds is not None:
        clock.advance(body.advance_seconds)
    else:
        raise HTTPException(status_code=400, detail="Provide advance_seconds or offset_seconds")
    return {
        "now": clock.now(),
        "now_iso": clock.now_iso(),
        "offset_seconds": clock.offset_seconds,
    }


@router.get("/deployments")
async def list_deployments(
    request: Request,
    service: str | None = None,
    from_ts: float | None = None,
    to_ts: float | None = None,
) -> list[dict[str, Any]]:
    return cast(
        list[dict[str, Any]],
        request.app.state.engine.deployments.list(service=service, from_ts=from_ts, to_ts=to_ts),
    )


@router.get("/feature-flags")
async def list_flags(request: Request, service: str | None = None) -> list[dict[str, Any]]:
    return cast(list[dict[str, Any]], request.app.state.engine.flags.list(service=service))


@router.post("/deployments/{deployment_id}/rollback")
async def rollback_deployment(
    deployment_id: str,
    request: Request,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    _require_internal_auth(request, authorization)
    engine = request.app.state.engine
    try:
        rollback = engine.deployments.rollback(deployment_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="deployment not found") from exc

    # Revert scenario signals tied to this deployment.
    for active in list(engine.state()["active"]):
        if active.get("deployment_id") == deployment_id:
            engine.deactivate(active["id"])
    return cast(dict[str, Any], rollback)


@router.post("/feature-flags/{key}")
async def mutate_flag(
    key: str,
    body: FlagBody,
    request: Request,
    authorization: str | None = Header(default=None),
) -> dict[str, Any]:
    _require_internal_auth(request, authorization)
    settings = request.app.state.settings
    record = request.app.state.engine.flags.upsert(
        key=key,
        service=settings.service_name,
        enabled=body.enabled,
        rollout_percentage=body.rollout_percentage,
        updated_by=body.updated_by,
    )
    # Turning off a bad flag deactivates the feature-flag scenario if active.
    if key == "new-checkout-flow" and not body.enabled:
        request.app.state.engine.deactivate("SCN-006-bad-feature-flag")
    return cast(dict[str, Any], record)
