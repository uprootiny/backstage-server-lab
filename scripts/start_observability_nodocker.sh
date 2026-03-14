#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

OBS_ROOT="${OBS_ROOT:-/workspace/.bsl-observability}"
EXPORTER_PORT="${EXPORTER_PORT:-19171}"
PROM_PORT="${PROM_PORT:-19390}"
GRAFANA_PORT="${GRAFANA_PORT:-19300}"
GRAFANA_ADMIN_USER="${GRAFANA_ADMIN_USER:-admin}"
GRAFANA_ADMIN_PASSWORD="${GRAFANA_ADMIN_PASSWORD:-admin}"
GRAFANA_VERSION="${GRAFANA_VERSION:-11.1.4}"
PROM_VERSION="${PROM_VERSION:-2.53.0}"

mkdir -p "$OBS_ROOT"/{bin,run,logs,prometheus/data,grafana/data,grafana/provisioning/datasources,grafana/provisioning/dashboards,grafana/dashboards}

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    echo "missing required command: $1" >&2
    exit 2
  fi
}

require_cmd curl
require_cmd tar

if ! command -v uv >/dev/null 2>&1; then
  echo "uv not found; installing via official installer"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

download_prometheus() {
  local arch="linux-amd64"
  local tarball="prometheus-${PROM_VERSION}.${arch}.tar.gz"
  local url="https://github.com/prometheus/prometheus/releases/download/v${PROM_VERSION}/${tarball}"
  local dest="$OBS_ROOT/bin/$tarball"
  if [[ ! -x "$OBS_ROOT/bin/prometheus-${PROM_VERSION}.${arch}/prometheus" ]]; then
    echo "downloading prometheus ${PROM_VERSION}"
    curl -fL "$url" -o "$dest"
    tar -xzf "$dest" -C "$OBS_ROOT/bin"
  fi
  echo "$OBS_ROOT/bin/prometheus-${PROM_VERSION}.${arch}/prometheus"
}

download_grafana() {
  local arch="linux-amd64"
  local tarball="grafana-${GRAFANA_VERSION}.${arch}.tar.gz"
  local url="https://dl.grafana.com/oss/release/${tarball}"
  local dest="$OBS_ROOT/bin/$tarball"
  if [[ ! -x "$OBS_ROOT/bin/grafana-v${GRAFANA_VERSION}/bin/grafana-server" ]]; then
    echo "downloading grafana ${GRAFANA_VERSION}"
    curl -fL "$url" -o "$dest"
    tar -xzf "$dest" -C "$OBS_ROOT/bin"
  fi
  echo "$OBS_ROOT/bin/grafana-v${GRAFANA_VERSION}/bin/grafana-server"
}

PROM_BIN="$(download_prometheus)"
GRAFANA_BIN="$(download_grafana)"

cat > "$OBS_ROOT/prometheus/prometheus.yml" <<EOF
global:
  scrape_interval: 30s
  evaluation_interval: 30s

scrape_configs:
  - job_name: github_exporter
    static_configs:
      - targets: ["127.0.0.1:${EXPORTER_PORT}"]
EOF

cat > "$OBS_ROOT/grafana/provisioning/datasources/prometheus.yml" <<EOF
apiVersion: 1
datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://127.0.0.1:${PROM_PORT}
    isDefault: true
    editable: false
EOF

cat > "$OBS_ROOT/grafana/provisioning/dashboards/dashboards.yml" <<EOF
apiVersion: 1
providers:
  - name: BackstageRepoObservability
    orgId: 1
    folder: Backstage Repo
    type: file
    disableDeletion: false
    editable: true
    options:
      path: ${OBS_ROOT}/grafana/dashboards
EOF

cp -f observability/grafana/dashboards/*.json "$OBS_ROOT/grafana/dashboards/"

cat > "$OBS_ROOT/grafana/grafana.ini" <<EOF
[server]
http_addr = 0.0.0.0
http_port = ${GRAFANA_PORT}

[security]
admin_user = ${GRAFANA_ADMIN_USER}
admin_password = ${GRAFANA_ADMIN_PASSWORD}

[users]
allow_sign_up = false

[paths]
data = ${OBS_ROOT}/grafana/data
provisioning = ${OBS_ROOT}/grafana/provisioning
EOF

pkill -f 'github_exporter.py' || true
pkill -f 'prometheus.*bsl-observability' || true
pkill -f 'grafana-server.*bsl-observability' || true

echo "starting github exporter on :${EXPORTER_PORT}"
nohup env GITHUB_EXPORTER_PORT="${EXPORTER_PORT}" \
  GITHUB_REPOSITORY="${GITHUB_REPOSITORY:-uprootiny/backstage-server-lab}" \
  uv run --with requests --with prometheus-client \
  observability/github_exporter.py \
  > "$OBS_ROOT/logs/github_exporter.log" 2>&1 &
echo $! > "$OBS_ROOT/run/github_exporter.pid"

echo "starting prometheus on :${PROM_PORT}"
nohup "$PROM_BIN" \
  --config.file="$OBS_ROOT/prometheus/prometheus.yml" \
  --storage.tsdb.path="$OBS_ROOT/prometheus/data" \
  --web.listen-address="0.0.0.0:${PROM_PORT}" \
  > "$OBS_ROOT/logs/prometheus.log" 2>&1 &
echo $! > "$OBS_ROOT/run/prometheus.pid"

echo "starting grafana on :${GRAFANA_PORT}"
nohup "$GRAFANA_BIN" \
  --homepath="$(dirname "$(dirname "$GRAFANA_BIN")")" \
  --config="$OBS_ROOT/grafana/grafana.ini" \
  > "$OBS_ROOT/logs/grafana.log" 2>&1 &
echo $! > "$OBS_ROOT/run/grafana.pid"

sleep 6

echo "health checks"
echo "  exporter: $(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:${EXPORTER_PORT}/metrics" || true)"
echo "  prometheus: $(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:${PROM_PORT}/-/ready" || true)"
echo "  grafana: $(curl -s -o /dev/null -w '%{http_code}' "http://127.0.0.1:${GRAFANA_PORT}/api/health" || true)"
echo "grafana_url=http://127.0.0.1:${GRAFANA_PORT}"
echo "public_hint=http://175.155.64.231:${GRAFANA_PORT}"
