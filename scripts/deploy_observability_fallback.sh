#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

MODE="${1:-auto}"

have_local() {
  command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1
}

run_local() {
  echo "deploy mode: local"
  bash scripts/setup_repo_observability.sh
  bash scripts/probe_live_endpoints.sh
}

run_vast() {
  if [[ -z "${VAST_HOST:-}" ]]; then
    echo "VAST_HOST not set; cannot deploy remote" >&2
    return 1
  fi
  echo "deploy mode: vast ($VAST_HOST)"
  rsync -az --delete --exclude '.git' ./ "$VAST_HOST:/workspace/backstage-server-lab/"
  ssh "$VAST_HOST" 'cd /workspace/backstage-server-lab && bash scripts/setup_repo_observability.sh && bash scripts/probe_live_endpoints.sh'
}

run_actions() {
  if ! command -v gh >/dev/null 2>&1; then
    echo "gh CLI not found; cannot dispatch actions fallback" >&2
    return 1
  fi
  echo "deploy mode: github-actions"
  gh workflow run observability-smoke.yml --ref main
  echo "triggered workflow observability-smoke.yml"
}

case "$MODE" in
  local)
    run_local
    ;;
  vast)
    run_vast
    ;;
  actions)
    run_actions
    ;;
  auto)
    if have_local; then
      run_local
    elif [[ -n "${VAST_HOST:-}" ]]; then
      run_vast
    else
      run_actions
    fi
    ;;
  *)
    echo "usage: $0 [auto|local|vast|actions]" >&2
    exit 2
    ;;
esac
