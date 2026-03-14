#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

AUTO_HEAL="${AUTO_HEAL:-0}"
OUT_FILE="${1:-$ROOT_DIR/docs/STACK_DOCTOR_LATEST.md}"
TS="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
PY_BIN="${PY_BIN:-/venv/main/bin/python}"
KAGGLE_BIN="${KAGGLE_BIN:-/venv/main/bin/kaggle}"
if [[ ! -x "$PY_BIN" ]]; then
  PY_BIN="$(command -v python3 || command -v python || true)"
fi
if [[ ! -x "$KAGGLE_BIN" ]]; then
  KAGGLE_BIN="$(command -v kaggle || true)"
fi
PUBLIC_IP="${VAST_PUBLIC_IP:-175.155.64.231}"
MASHUP_PORT="${MASHUP_PORT:-6006}"
TB_PORT="${TB_PORT:-16006}"

mkdir -p "$(dirname "$OUT_FILE")"

have() { command -v "$1" >/dev/null 2>&1; }
http_code() {
  local url="$1"
  local insecure="${2:-0}"
  if [[ "$insecure" == "1" ]]; then
    curl -k -sS -m 6 -o /dev/null -w '%{http_code}' "$url" || true
  else
    curl -sS -m 6 -o /dev/null -w '%{http_code}' "$url" || true
  fi
}

status_row() {
  local name="$1" url="$2" code="$3"
  local state="DOWN"
  if [[ "$code" =~ ^2|3|4 ]]; then
    state="UP"
  fi
  printf '| %s | %s | %s | %s |\n' "$name" "$url" "$state" "$code"
}

if [[ "$AUTO_HEAL" == "1" ]]; then
  bash "$ROOT_DIR/scripts/up.sh" >/tmp/backstage-up.log 2>&1 || true
  bash "$ROOT_DIR/scripts/run_research_library.sh" >/tmp/backstage-lib.log 2>&1 || true
  if [[ -x "$ROOT_DIR/scripts/vast_public_surfaces.sh" ]]; then
    bash "$ROOT_DIR/scripts/vast_public_surfaces.sh" >/tmp/backstage-surfaces.log 2>&1 || true
  fi
fi

# Required pieces
critical_ok=1
req=()
for p in \
  "$ROOT_DIR/src/labops/cli.py" \
  "$ROOT_DIR/src/labops/kaggle_parallel.py" \
  "$ROOT_DIR/src/labops/kaggle_mashup_app.py" \
  "$ROOT_DIR/notebooks/starters/02_rna_3d_training_filled.ipynb" \
  "$ROOT_DIR/artifacts/kaggle_parallel"; do
  if [[ -e "$p" ]]; then
    req+=("ok:$p")
  else
    req+=("missing:$p")
    critical_ok=0
  fi
done

# Service probes
c_mlflow="$(http_code http://127.0.0.1:1111)"
c_tb_local="$(http_code http://127.0.0.1:${TB_PORT})"
c_jupyter="$(http_code https://127.0.0.1:8080 1)"
c_mashup_local="$(http_code http://127.0.0.1:${MASHUP_PORT})"
c_bridge="$(http_code http://127.0.0.1:19999/index.json)"

c_pub_jupyter="$(http_code https://${PUBLIC_IP}:19808 1)"
c_pub_mashup="$(http_code http://${PUBLIC_IP}:19448)"
c_pub_lib="$(http_code http://${PUBLIC_IP}:19121)"
c_pub_sync="$(http_code http://${PUBLIC_IP}:19753)"
c_pub_19842="$(http_code http://${PUBLIC_IP}:19842)"

# Kaggle / harness readiness
kaggle_ok=0
if [[ -x "$KAGGLE_BIN" ]]; then
  if "$KAGGLE_BIN" --help >/dev/null 2>&1; then
    kaggle_ok=1
  fi
fi

python_ok=0
if [[ -x "$PY_BIN" ]]; then
  if PYTHONPATH="$ROOT_DIR/src" "$PY_BIN" -m labops.cli --help >/dev/null 2>&1; then
    python_ok=1
  fi
fi

# Ledger health
ledger="$ROOT_DIR/artifacts/kaggle_parallel/ledger.jsonl"
ledger_lines=0
ok_jobs=0
failed_jobs=0
if [[ -f "$ledger" ]]; then
  ledger_lines="$(wc -l < "$ledger" | tr -d ' ')"
  ok_jobs="$(grep -c '"event": "job_end".*"status": "ok"' "$ledger" || true)"
  failed_jobs="$(grep -c '"event": "job_end".*"status": "failed"' "$ledger" || true)"
fi

# GPU snapshot
gpu_line="unavailable"
if have nvidia-smi; then
  gpu_line="$(nvidia-smi --query-gpu=name,utilization.gpu,memory.used,memory.total --format=csv,noheader | head -1)"
fi

{
  echo "# Stack Doctor"
  echo
  echo "- generated_at: $TS"
  echo "- root: $ROOT_DIR"
  echo "- auto_heal: $AUTO_HEAL"
  echo
  echo "## Required Pieces"
  echo
  echo '```'
  printf '%s\n' "${req[@]}"
  echo '```'
  echo
  echo "## Service Matrix"
  echo
  echo "| Surface | URL | State | HTTP |"
  echo "|---|---|---|---:|"
  status_row "MLflow local" "http://127.0.0.1:1111" "$c_mlflow"
  status_row "TensorBoard local" "http://127.0.0.1:${TB_PORT}" "$c_tb_local"
  status_row "Jupyter local" "https://127.0.0.1:8080" "$c_jupyter"
  status_row "Mashup local" "http://127.0.0.1:${MASHUP_PORT}" "$c_mashup_local"
  status_row "RNA bridge local" "http://127.0.0.1:19999/index.json" "$c_bridge"
  status_row "Jupyter public" "https://${PUBLIC_IP}:19808" "$c_pub_jupyter"
  status_row "Mashup public" "http://${PUBLIC_IP}:19448" "$c_pub_mashup"
  status_row "Research library public" "http://${PUBLIC_IP}:19121" "$c_pub_lib"
  status_row "Syncthing public" "http://${PUBLIC_IP}:19753" "$c_pub_sync"
  status_row "Open 19842 public" "http://${PUBLIC_IP}:19842" "$c_pub_19842"
  echo
  echo "## Harness Readiness"
  echo
  echo "- python_cli_ready: $python_ok"
  echo "- kaggle_cli_ready: $kaggle_ok"
  echo "- ledger_lines: $ledger_lines"
  echo "- job_end_ok: $ok_jobs"
  echo "- job_end_failed: $failed_jobs"
  echo
  echo "## GPU"
  echo
  echo '```'
  echo "$gpu_line"
  echo '```'
} > "$OUT_FILE"

cat "$OUT_FILE"
echo "doctor_report=$OUT_FILE"

if [[ "$critical_ok" != "1" ]]; then
  exit 3
fi
if [[ "$python_ok" != "1" ]]; then
  exit 4
fi
