#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

PATTERNS=(
  'sk-[A-Za-z0-9]{20,}'
  'AKIA[0-9A-Z]{16}'
  'BEGIN (RSA |EC )?PRIVATE KEY'
)

fail=0
while IFS= read -r file; do
  [[ "$file" == *.example ]] && continue
  [[ "$file" == ./.git/* ]] && continue
  for pattern in "${PATTERNS[@]}"; do
    if grep -Eaq "$pattern" "$file"; then
      echo "Potential secret in $file (pattern: $pattern)"
      fail=1
    fi
  done
done < <(git ls-files 2>/dev/null || find . -type f \
  ! -path './.git/*' \
  ! -path './node_modules/*' \
  ! -path './.venv/*' \
  ! -path './apps/web/.next/*')

if [[ "$fail" -ne 0 ]]; then
  exit 1
fi

echo "security-scan: no obvious secrets detected"
