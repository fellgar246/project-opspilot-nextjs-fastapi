#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

echo "=== SPEC-10 verify pipeline ==="

echo "[1/10] Isolated dependencies"
docker compose --profile minimal up -d postgres redis
sleep 3

echo "[2/10] Migrate"
docker compose --profile minimal run --rm api alembic upgrade head

echo "[3/10] Backend tests"
make test

echo "[4/10] Evaluation regression"
EVAL_SMOKE=true make eval

echo "[5/10] Build images"
make build

echo "[6/10] Security scan"
make security-scan

echo "[7/10] Stack smoke"
docker compose --profile minimal up -d api worker web
sleep 5
make smoke

echo "[8/10] Scenario seed check"
test -d datasets/evaluations
test "$(find datasets/evaluations -name '*.yaml' | wc -l | tr -d ' ')" -ge 1

echo "[9/10] Reports directory"
mkdir -p reports
test -d reports

echo "[10/10] Teardown test environment"
docker compose --profile minimal down --remove-orphans

echo "verify: all gates passed"
