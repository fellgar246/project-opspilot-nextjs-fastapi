#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Created .env from .env.example"
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required. Install from https://docs.astral.sh/uv/"
  exit 1
fi

uv sync --all-packages --all-extras --group dev

if [[ -x node_modules/.bin/pnpm ]]; then
  ./node_modules/.bin/pnpm install
elif command -v pnpm >/dev/null 2>&1; then
  pnpm install
else
  npx --yes pnpm@9 install
fi

echo
echo "Bootstrap complete."
echo "Configure OPENAI_API_KEY in .env when using MODEL_PROVIDER=openai (see ADR-009)."
