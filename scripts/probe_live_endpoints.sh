#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_FILE="${1:-$ROOT_DIR/docs/LIVE_ENDPOINTS.md}"
mkdir -p "$(dirname "$OUT_FILE")"

if [[ -f "$ROOT_DIR/.env" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "$ROOT_DIR/.env"
  set +a
fi

ts="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

DEFAULT_URLS=(
  "Grafana Local|http://127.0.0.1:3000"
  "Prometheus Local|http://127.0.0.1:9090/-/ready"
  "GitHub Exporter Local|http://127.0.0.1:9171/metrics"
  "MLflow Local|http://127.0.0.1:1111"
  "TensorBoard Local|http://127.0.0.1:6006"
  "Kaggle Mashup Local|http://127.0.0.1:8511"
  "RNA Bridge Local|http://127.0.0.1:19999/index.json"
  "RNA Workbench Local|http://127.0.0.1:8522/rna_workbench.html"
  "Grafana Remote|http://173.212.203.211:19300"
  "Vast Jupyter Port|https://175.155.64.231:19808"
  "Vast Portal Tunnel|https://broadband-petroleum-camera-clear.trycloudflare.com/#/apps"
  "Vast Jupyter Tunnel|https://alignment-vacations-abilities-conclusion.trycloudflare.com"
  "Vast TensorBoard Tunnel|https://consistency-personnel-draft-ordering.trycloudflare.com"
  "Vast Syncthing Tunnel|https://luther-identification-room-export.trycloudflare.com"
)

if [[ -n "${EXTRA_ENDPOINTS:-}" ]]; then
  while IFS= read -r line; do
    [[ -n "$line" ]] && DEFAULT_URLS+=("$line")
  done <<< "$EXTRA_ENDPOINTS"
fi

check_url() {
  local url="$1"
  local code
  local t
  local proto
  proto="$(printf '%s' "$url" | cut -d: -f1)"
  if [[ "$proto" == "https" ]]; then
    read -r code t < <(curl -k -sS -L --max-time 12 -o /dev/null -w "%{http_code} %{time_total}" "$url" || echo "000 0")
  else
    read -r code t < <(curl -sS -L --max-time 12 -o /dev/null -w "%{http_code} %{time_total}" "$url" || echo "000 0")
  fi
  if [[ "$code" == "000" ]]; then
    echo "DOWN|$code|$t"
  elif [[ "$code" =~ ^2|3|4 ]]; then
    echo "UP|$code|$t"
  else
    echo "DOWN|$code|$t"
  fi
}

{
  echo "# Live Endpoints"
  echo
  echo "- generated_at: $ts"
  echo
  echo "| Surface | URL | Status | HTTP | Latency(s) |"
  echo "|---|---|---|---:|---:|"
} > "$OUT_FILE"

for entry in "${DEFAULT_URLS[@]}"; do
  name="${entry%%|*}"
  url="${entry#*|}"
  status_raw="$(check_url "$url")"
  state="${status_raw%%|*}"
  rem="${status_raw#*|}"
  code="${rem%%|*}"
  lat="${rem#*|}"
  printf '| %s | %s | %s | %s | %s |\n' "$name" "$url" "$state" "$code" "$lat" >> "$OUT_FILE"
done

{
  echo
  echo "## Reachability"
  echo
  echo '```'
  ping -c 2 -W 2 173.212.203.211 2>&1 || true
  ping -c 2 -W 2 175.155.64.231 2>&1 || true
  echo '```'
  echo
  echo "## SSH checks"
  echo
  echo '```'
  ssh -o BatchMode=yes -o ConnectTimeout=6 root@175.155.64.231 'echo ssh_ok' 2>&1 || true
  ssh -o BatchMode=yes -o ConnectTimeout=6 root@173.212.203.211 'echo ssh_ok' 2>&1 || true
  echo '```'
} >> "$OUT_FILE"

echo "live_endpoints_report=$OUT_FILE"
cat "$OUT_FILE"
