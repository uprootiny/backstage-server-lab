#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_FILE="${1:-$ROOT_DIR/docs/CONNECTION_DOCTOR.md}"
mkdir -p "$(dirname "$OUT_FILE")"

ts="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"

check_http() {
  local url="$1"
  local code
  code="$(curl -sS -L -o /dev/null -w "%{http_code}" --max-time 12 "$url" || true)"
  if [[ -z "$code" || "$code" == "000" ]]; then
    echo "DOWN"
  elif [[ "$code" =~ ^2|3|4 ]]; then
    echo "UP($code)"
  else
    echo "DOWN($code)"
  fi
}

append_row() {
  local name="$1"
  local url="$2"
  local status="$3"
  printf "| %s | %s | %s |\n" "$name" "$url" "$status" >> "$OUT_FILE"
}

{
  echo "# Connection Doctor"
  echo
  echo "- generated_at: $ts"
  echo "- root: $ROOT_DIR"
  echo
  echo "## Local Endpoints"
  echo
  echo "| Surface | URL | Status |"
  echo "|---|---|---|"
} > "$OUT_FILE"

append_row "MLflow" "http://127.0.0.1:1111" "$(check_http "http://127.0.0.1:1111")"
append_row "TensorBoard" "http://127.0.0.1:6006" "$(check_http "http://127.0.0.1:6006")"
append_row "Kaggle Mashup" "http://127.0.0.1:8511" "$(check_http "http://127.0.0.1:8511")"
append_row "RNA Artifact Bridge" "http://127.0.0.1:19999" "$(check_http "http://127.0.0.1:19999")"

{
  echo
  echo "## Public/Tunnel Endpoints (optional)"
  echo
  echo "| Surface | URL | Status |"
  echo "|---|---|---|"
} >> "$OUT_FILE"

if [[ -n "${MLFLOW_PUBLIC_URL:-}" ]]; then
  append_row "MLflow public" "$MLFLOW_PUBLIC_URL" "$(check_http "$MLFLOW_PUBLIC_URL")"
else
  append_row "MLflow public" "(unset MLFLOW_PUBLIC_URL)" "SKIPPED"
fi
if [[ -n "${TENSORBOARD_PUBLIC_URL:-}" ]]; then
  append_row "TensorBoard public" "$TENSORBOARD_PUBLIC_URL" "$(check_http "$TENSORBOARD_PUBLIC_URL")"
else
  append_row "TensorBoard public" "(unset TENSORBOARD_PUBLIC_URL)" "SKIPPED"
fi
if [[ -n "${JUPYTER_PUBLIC_URL:-}" ]]; then
  append_row "Jupyter public" "$JUPYTER_PUBLIC_URL" "$(check_http "$JUPYTER_PUBLIC_URL")"
else
  append_row "Jupyter public" "(unset JUPYTER_PUBLIC_URL)" "SKIPPED"
fi
if [[ -n "${KAGGLE_MASHUP_PUBLIC_URL:-}" ]]; then
  append_row "Kaggle Mashup public" "$KAGGLE_MASHUP_PUBLIC_URL" "$(check_http "$KAGGLE_MASHUP_PUBLIC_URL")"
else
  append_row "Kaggle Mashup public" "(unset KAGGLE_MASHUP_PUBLIC_URL)" "SKIPPED"
fi
if [[ -n "${RNA_BRIDGE_PUBLIC_URL:-}" ]]; then
  append_row "RNA Bridge public" "$RNA_BRIDGE_PUBLIC_URL" "$(check_http "$RNA_BRIDGE_PUBLIC_URL")"
else
  append_row "RNA Bridge public" "(unset RNA_BRIDGE_PUBLIC_URL)" "SKIPPED"
fi

{
  echo
  echo "## Service Sessions"
  echo
  echo '```'
  tmux ls 2>&1 || true
  echo '```'
  echo
  echo "## Listening Ports Snapshot"
  echo
  echo '```'
  ss -ltn 2>/dev/null | awk 'NR==1 || /:1111|:6006|:8080|:8511|:19999/'
  echo '```'
} >> "$OUT_FILE"

echo "connection_doctor_report=$OUT_FILE"
