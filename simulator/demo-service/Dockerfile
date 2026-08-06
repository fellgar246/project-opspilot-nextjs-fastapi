FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY apps/api/pyproject.toml apps/api/pyproject.toml
COPY apps/worker/pyproject.toml apps/worker/pyproject.toml
COPY packages/agent/pyproject.toml packages/agent/pyproject.toml
COPY packages/tools/pyproject.toml packages/tools/pyproject.toml
COPY packages/schemas/pyproject.toml packages/schemas/pyproject.toml
COPY packages/telemetry/pyproject.toml packages/telemetry/pyproject.toml
COPY simulator/demo-service/pyproject.toml simulator/demo-service/pyproject.toml

COPY packages packages
COPY simulator/demo-service simulator/demo-service
COPY simulator/scenarios simulator/scenarios
COPY simulator/data simulator/data

RUN uv sync --frozen --package ops-pilot-simulator --no-dev

FROM python:3.12-slim-bookworm AS runtime

WORKDIR /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    SCENARIOS_DIR=/app/simulator/scenarios \
    DATA_DIR=/app/simulator/data

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/simulator /app/simulator

WORKDIR /app/simulator/demo-service

EXPOSE 8080

CMD ["uvicorn", "demo_service.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8080"]
