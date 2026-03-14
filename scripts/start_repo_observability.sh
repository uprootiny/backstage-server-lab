#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if ! docker info >/dev/null 2>&1; then
  echo "docker daemon not accessible from this user; probe-only fallback"
  bash "$ROOT_DIR/scripts/probe_live_endpoints.sh"
  exit 0
fi
cd "$ROOT_DIR/observability"
docker compose up -d --remove-orphans

echo "Grafana: http://127.0.0.1:3000"
echo "Prometheus: http://127.0.0.1:9090"
echo "Exporter: http://127.0.0.1:9171/metrics"
