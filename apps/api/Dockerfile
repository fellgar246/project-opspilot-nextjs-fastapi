FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY apps/api/pyproject.toml apps/api/pyproject.toml
COPY apps/worker/pyproject.toml apps/worker/pyproject.toml
COPY packages/agent/pyproject.toml packages/agent/pyproject.toml
COPY packages/tools/pyproject.toml packages/tools/pyproject.toml
COPY packages/schemas/pyproject.toml packages/schemas/pyproject.toml
COPY packages/telemetry/pyproject.toml packages/telemetry/pyproject.toml

COPY packages packages
COPY apps/api apps/api

RUN uv sync --frozen --package ops-pilot-api --no-dev

FROM python:3.12-slim-bookworm AS runtime

WORKDIR /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/apps/api /app/apps/api
COPY --from=builder /app/packages /app/packages

RUN addgroup --system opspilot && adduser --system --ingroup opspilot opspilot \
    && chown -R opspilot:opspilot /app

WORKDIR /app/apps/api

USER opspilot

EXPOSE 8000

CMD ["uvicorn", "app.main:create_app", "--factory", "--host", "0.0.0.0", "--port", "8000"]
