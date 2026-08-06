#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"
COMPOSE="docker compose"
BACKUP_DIR="${1:-backups/$(date +%Y%m%d-%H%M%S)}"
mkdir -p "$BACKUP_DIR"

echo "Backing up postgres volume..."
docker run --rm \
  -v ops-pilot_postgres_data:/volume:ro \
  -v "$ROOT/$BACKUP_DIR":/backup \
  alpine tar czf /backup/postgres_data.tar.gz -C /volume .

echo "Backing up redis volume..."
docker run --rm \
  -v ops-pilot_redis_data:/volume:ro \
  -v "$ROOT/$BACKUP_DIR":/backup \
  alpine tar czf /backup/redis_data.tar.gz -C /volume .

echo "Backup saved to $BACKUP_DIR"
