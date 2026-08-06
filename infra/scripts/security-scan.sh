#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

FAIL=0
EXCEPTIONS="$ROOT/infra/security/exceptions.yaml"

echo "=== Python dependency scan ==="
if command -v pip-audit >/dev/null 2>&1; then
  pip-audit -r <(uv export --no-dev --package ops-pilot-api 2>/dev/null || echo "") || FAIL=1
else
  echo "pip-audit not installed — skipping (install with: uv tool install pip-audit)"
fi

echo "=== JS dependency scan ==="
if command -v pnpm >/dev/null 2>&1; then
  pnpm audit --audit-level high || FAIL=1
else
  echo "pnpm not available — skipping JS audit"
fi

echo "=== Secret scan (working tree) ==="
PATTERNS=(
  'sk-[A-Za-z0-9]{20,}'
  'AKIA[0-9A-Z]{16}'
  'BEGIN (RSA |EC )?PRIVATE KEY'
)
while IFS= read -r file; do
  [[ "$file" == *.example ]] && continue
  [[ "$file" == ./.git/* ]] && continue
  for pattern in "${PATTERNS[@]}"; do
    if grep -Eaq "$pattern" "$file"; then
      echo "Potential secret in $file (pattern: $pattern)"
      FAIL=1
    fi
  done
done < <(git ls-files 2>/dev/null || find . -type f \
  ! -path './.git/*' \
  ! -path './node_modules/*' \
  ! -path './.venv/*' \
  ! -path './apps/web/.next/*')

echo "=== Secret scan (git history, last 50 commits) ==="
if git rev-parse --git-dir >/dev/null 2>&1; then
  for pattern in "${PATTERNS[@]}"; do
    if git log -p -50 2>/dev/null | grep -Eaq "$pattern"; then
      echo "Potential secret in recent git history (pattern: $pattern)"
      FAIL=1
    fi
  done
fi

echo "=== Image vulnerability scan ==="
if command -v trivy >/dev/null 2>&1; then
  docker compose --profile minimal build -q
  for img in ops-pilot-api ops-pilot-worker ops-pilot-web; do
    trivy image --severity HIGH,CRITICAL --exit-code 1 "$img:latest" || FAIL=1
  done
else
  echo "trivy not installed — skipping image scan (install from aquasecurity/trivy)"
fi

if [[ -f "$EXCEPTIONS" ]] && grep -q "exceptions:" "$EXCEPTIONS"; then
  echo "Exceptions file present: $EXCEPTIONS"
fi

if [[ "$FAIL" -ne 0 ]]; then
  echo "security-scan: FAILED"
  exit 1
fi

echo "security-scan: passed"
