from __future__ import annotations

from app.auth.dependencies import ROUTE_POLICY_ATTR
from fastapi import FastAPI
from fastapi.dependencies.models import Dependant
from fastapi.routing import APIRoute

PUBLIC_ROUTE_PATHS: set[tuple[str, str]] = {
    ("GET", "/health"),
    ("GET", "/metrics"),
    ("POST", "/api/v1/auth/login"),
    ("POST", "/api/v1/auth/refresh"),
}


def _dependency_has_policy(dependant: Dependant) -> bool:
    if dependant.call is not None and hasattr(dependant.call, ROUTE_POLICY_ATTR):
        return True
    return any(_dependency_has_policy(sub) for sub in dependant.dependencies)


def route_has_policy(route: APIRoute) -> bool:
    return _dependency_has_policy(route.dependant)


def collect_unprotected_routes(app: FastAPI) -> list[str]:
    missing: list[str] = []
    for route in app.routes:
        if not isinstance(route, APIRoute):
            continue
        methods = route.methods or set()
        if any((method, route.path) in PUBLIC_ROUTE_PATHS for method in methods):
            continue
        if not route_has_policy(route):
            missing.append(f"{','.join(sorted(methods))} {route.path}")
    return missing
