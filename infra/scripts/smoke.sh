#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

API_URL="${API_URL:-http://localhost:8000}"
WEB_URL="${WEB_URL:-http://localhost:3000}"

echo "Checking API health at ${API_URL}/health"
api_status="$(curl -s -o /tmp/opspilot-health.json -w "%{http_code}" "${API_URL}/health")"
if [[ "$api_status" != "200" && "$api_status" != "503" ]]; then
  echo "API smoke check failed with HTTP ${api_status}"
  exit 1
fi
python3 - <<'PY'
import json
payload = json.load(open("/tmp/opspilot-health.json"))
assert "status" in payload and "checks" in payload
print("API payload OK:", payload["status"], payload["checks"])
PY

echo "Checking frontend at ${WEB_URL}"
web_status="$(curl -s -o /tmp/opspilot-web.html -w "%{http_code}" "${WEB_URL}")"
if [[ "$web_status" != "200" ]]; then
  echo "Web smoke check failed with HTTP ${web_status}"
  exit 1
fi

if ! grep -q "OpsPilot AI" /tmp/opspilot-web.html; then
  echo "Web page missing expected content"
  exit 1
fi

echo "Smoke checks passed."
