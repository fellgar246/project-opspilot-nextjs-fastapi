#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

echo "=== OpsPilot Demo Story ==="
echo "1. Health check"
curl -sf http://127.0.0.1:8000/health | python -m json.tool

echo "2. Seed simulator scenario SCN-001 (replay mode)"
curl -sf -X POST "http://127.0.0.1:8080/sim/scenarios/SCN-001-missing-env/activate" \
  -H "Content-Type: application/json" \
  -d '{"seed": 42, "mode": "replay"}' | python -m json.tool

echo "3. Run evaluation smoke gate"
EVAL_SMOKE=true make eval

echo "4. Demo complete — open http://localhost:3000/evaluations for Evaluation Lab"
echo "   Login: admin credentials from .env (SEED_ADMIN_EMAIL / SEED_ADMIN_PASSWORD)"
