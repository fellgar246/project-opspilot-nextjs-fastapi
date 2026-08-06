#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

if [[ "${RESET_TEST_ONLY:-0}" == "1" ]]; then
  echo "Resetting test environment only (preserving dev volumes)..."
  docker compose --profile minimal down --remove-orphans || true
  echo "Test environment stopped. Dev volumes preserved."
  exit 0
fi

docker compose --profile full down -v --remove-orphans || true
docker volume rm ops-pilot_postgres_data ops-pilot_redis_data 2>/dev/null || true

echo "Local stack volumes removed."
