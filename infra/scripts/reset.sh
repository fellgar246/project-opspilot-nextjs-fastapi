#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

docker compose --profile full down -v --remove-orphans || true
docker volume rm ops-pilot_postgres_data ops-pilot_redis_data 2>/dev/null || true

echo "Local stack volumes removed."
