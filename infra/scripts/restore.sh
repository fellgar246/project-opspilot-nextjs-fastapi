#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

BACKUP_DIR="${1:?Usage: restore.sh <backup-dir>}"
test -f "$BACKUP_DIR/postgres_data.tar.gz"

echo "Restoring postgres volume from $BACKUP_DIR..."
docker compose --profile minimal stop postgres 2>/dev/null || true
docker run --rm \
  -v ops-pilot_postgres_data:/volume \
  -v "$ROOT/$BACKUP_DIR":/backup:ro \
  alpine sh -c "rm -rf /volume/* && tar xzf /backup/postgres_data.tar.gz -C /volume"

if [[ -f "$BACKUP_DIR/redis_data.tar.gz" ]]; then
  docker run --rm \
    -v ops-pilot_redis_data:/volume \
    -v "$ROOT/$BACKUP_DIR":/backup:ro \
    alpine sh -c "rm -rf /volume/* && tar xzf /backup/redis_data.tar.gz -C /volume"
fi

echo "Restore complete. Start services with: make up"
