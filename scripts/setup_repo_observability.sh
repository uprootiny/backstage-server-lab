#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is required" >&2
  exit 2
fi
if ! docker compose version >/dev/null 2>&1; then
  echo "docker compose plugin is required" >&2
  exit 2
fi
if ! docker info >/dev/null 2>&1; then
  echo "docker daemon not accessible from this user; switching to probe-only fallback"
  bash scripts/probe_live_endpoints.sh
  exit 0
fi

if [[ -f .env ]]; then
  set -a
  # shellcheck source=/dev/null
  source .env
  set +a
fi

: "${GITHUB_REPOSITORY:=uprootiny/backstage-server-lab}"

if [[ -z "${GITHUB_TOKEN:-}" ]]; then
  echo "GITHUB_TOKEN is missing; continuing in anonymous mode (reduced rate limits)." >&2
  echo "Recommended scopes when provided: repository metadata, issues, PRs, actions." >&2
fi

mkdir -p logs

echo "starting observability stack for ${GITHUB_REPOSITORY}"
( cd observability && docker compose up -d --remove-orphans )

echo "waiting for endpoints"
for i in {1..30}; do
  p_code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 4 http://127.0.0.1:9090/-/ready || true)"
  g_code="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 4 http://127.0.0.1:3000/api/health || true)"
  if [[ "$p_code" == "200" && "$g_code" == "200" ]]; then
    break
  fi
  sleep 1
done

echo "observability URLs"
echo "- Grafana:    http://127.0.0.1:3000"
echo "- Prometheus: http://127.0.0.1:9090"
echo "- Exporter:   http://127.0.0.1:9171/metrics"

echo "query sanity"
curl -fsS "http://127.0.0.1:9090/api/v1/query?query=github_repo_up" >/dev/null
curl -fsS "http://127.0.0.1:9171/metrics" | rg -n "^github_repo_" | head -n 10 || true

echo "setup_repo_observability=OK"
