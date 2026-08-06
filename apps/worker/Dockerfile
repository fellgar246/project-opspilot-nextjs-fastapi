FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

WORKDIR /app

COPY pyproject.toml uv.lock ./
COPY apps/worker/pyproject.toml apps/worker/pyproject.toml
COPY packages/schemas/pyproject.toml packages/schemas/pyproject.toml
COPY packages/telemetry/pyproject.toml packages/telemetry/pyproject.toml

COPY packages packages
COPY apps/worker apps/worker

RUN uv sync --frozen --package ops-pilot-worker --no-dev

FROM python:3.12-slim-bookworm AS runtime

WORKDIR /app

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/apps/worker /app/apps/worker
COPY --from=builder /app/packages /app/packages

RUN addgroup --system opspilot && adduser --system --ingroup opspilot opspilot \
    && chown -R opspilot:opspilot /app

WORKDIR /app/apps/worker

USER opspilot

CMD ["arq", "worker.main.WorkerSettings"]
