#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if ! docker info >/dev/null 2>&1; then
  echo "docker daemon not accessible from this user; nothing to stop"
  exit 0
fi
cd "$ROOT_DIR/observability"
docker compose down
