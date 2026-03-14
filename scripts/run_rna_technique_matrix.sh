#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

CONFIG_PATH="${CONFIG_PATH:-$ROOT_DIR/configs/rna_technique_matrix.yaml}"
PLAN_PATH="${PLAN_PATH:-$ROOT_DIR/artifacts/kaggle_parallel/plan_rna_technique_matrix.json}"
MANIFEST_PATH="${MANIFEST_PATH:-$ROOT_DIR/artifacts/kaggle_parallel/rna_technique_matrix_manifest.json}"
LEDGER_PATH="${LEDGER_PATH:-$ROOT_DIR/artifacts/kaggle_parallel/ledger.jsonl}"
LOGS_DIR="${LOGS_DIR:-$ROOT_DIR/logs/kaggle_parallel}"
EXEC_DIR="${EXEC_DIR:-$ROOT_DIR/artifacts/kaggle_parallel/executed}"
REPORT_JSON="${REPORT_JSON:-$ROOT_DIR/reports/rna_technique_matrix_validation.json}"
REPORT_MD="${REPORT_MD:-$ROOT_DIR/docs/RNA_TECHNIQUE_MATRIX_VALIDATION.md}"
MAX_JOBS="${MAX_JOBS:-20}"
WORKERS="${WORKERS:-3}"
NOTEBOOK_OVERRIDES="${NOTEBOOK_OVERRIDES:-}"

mkdir -p "$(dirname "$PLAN_PATH")" "$LOGS_DIR" "$EXEC_DIR" "$(dirname "$REPORT_JSON")" "$(dirname "$REPORT_MD")"

build_cmd=(
  uv run python scripts/build_rna_technique_matrix_plan.py
  --config "$CONFIG_PATH"
  --out-plan "$PLAN_PATH"
  --out-manifest "$MANIFEST_PATH"
  --max-jobs "$MAX_JOBS"
)

if [[ -n "$NOTEBOOK_OVERRIDES" ]]; then
  IFS=',' read -r -a override_items <<< "$NOTEBOOK_OVERRIDES"
  for item in "${override_items[@]}"; do
    [[ -n "$item" ]] || continue
    build_cmd+=(--notebook-override "$item")
  done
fi

"${build_cmd[@]}"

uv run labops kaggle-parallel-dispatch \
  --plan "$PLAN_PATH" \
  --workers "$WORKERS" \
  --ledger "$LEDGER_PATH" \
  --logs-dir "$LOGS_DIR" \
  --executed-dir "$EXEC_DIR"

uv run python scripts/validate_rna_technique_matrix.py \
  --plan "$PLAN_PATH" \
  --ledger "$LEDGER_PATH" \
  --out-json "$REPORT_JSON" \
  --out-md "$REPORT_MD"

uv run labops kaggle-parallel-status --ledger "$LEDGER_PATH"

echo "rna_technique_matrix_done plan=$PLAN_PATH report=$REPORT_JSON"
