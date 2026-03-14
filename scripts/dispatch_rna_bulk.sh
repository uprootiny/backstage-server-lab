#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PY_BIN="${PY_BIN:-/venv/main/bin/python}"
if [[ ! -x "$PY_BIN" ]]; then
  PY_BIN="$(command -v python3 || command -v python || true)"
fi
WORKERS="${WORKERS:-4}"
JOBS="${JOBS:-36}"
TIMEOUT_MIN="${TIMEOUT_MIN:-35}"
PROFILE="${PROFILE:-rna_bulk_methodical}"
PLAN_PATH="${PLAN_PATH:-$ROOT_DIR/artifacts/kaggle_parallel/plan_bulk_methodical.json}"
LEDGER="${LEDGER:-$ROOT_DIR/artifacts/kaggle_parallel/ledger.jsonl}"
LOGS_DIR="${LOGS_DIR:-$ROOT_DIR/logs/kaggle_parallel}"
EXEC_DIR="${EXEC_DIR:-$ROOT_DIR/artifacts/kaggle_parallel/executed}"

mkdir -p "$(dirname "$PLAN_PATH")" "$LOGS_DIR" "$EXEC_DIR"

NOTEBOOKS=(
  "notebooks/starters/01_rna_eda_baseline.ipynb"
  "notebooks/starters/02_rna_3d_training_stub.ipynb"
  "notebooks/starters/02_rna_3d_training_filled.ipynb"
  "notebooks/starters/03_rna_eval_workbench_bridge.ipynb"
  "notebooks/starters/04_interactive_pipeline_orchestrator.ipynb"
  "notebooks/kaggle/sigmaborov-top1/stanford-rna-3d-folding-top-1-solution.local.ipynb"
)

usable=()
for nb in "${NOTEBOOKS[@]}"; do
  [[ -f "$ROOT_DIR/$nb" ]] && usable+=("$nb")
done
if [[ "${#usable[@]}" -eq 0 ]]; then
  echo "no_notebooks_found"
  exit 2
fi

ts="$(date -u +%Y%m%dT%H%M%SZ)"
USABLE_NOTEBOOKS_JSON="$("$PY_BIN" -c 'import json,sys; print(json.dumps(sys.argv[1:]))' "${usable[@]}")"

# Build deterministic plan JSON via python
USABLE_NOTEBOOKS_JSON="$USABLE_NOTEBOOKS_JSON" PYTHONPATH="$ROOT_DIR/src" "$PY_BIN" - <<PY
import json
import os
from pathlib import Path

usable = json.loads(os.environ["USABLE_NOTEBOOKS_JSON"])
plan_path = Path("$PLAN_PATH")
ts = "$ts"
jobs = []
for i in range(int("$JOBS")):
    nb = usable[i % len(usable)]
    jid = f"bulk-{ts}-{i+1:03d}"
    jobs.append({
        "id": jid,
        "notebook": nb,
        "timeout_min": int("$TIMEOUT_MIN"),
        "expected_improvement": round(0.12 + 0.01 * (i % 9), 3),
        "uncertainty": round(0.55 + 0.02 * (i % 5), 3),
        "importance": round(0.82 + 0.01 * (i % 7), 3),
        "tags": ["bulk", "methodical", "rna", "vast"]
    })
plan = {
    "profile": "$PROFILE",
    "retries": {"max_attempts": 2, "backoff_sec": 4},
    "jobs": jobs
}
plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
print(f"plan_written={plan_path} jobs={len(jobs)} notebooks={len(usable)}")
PY

PYTHONPATH="$ROOT_DIR/src" "$PY_BIN" -m labops.cli kaggle-parallel-dispatch \
  --plan "$PLAN_PATH" \
  --workers "$WORKERS" \
  --ledger "$LEDGER" \
  --logs-dir "$LOGS_DIR" \
  --executed-dir "$EXEC_DIR"

PYTHONPATH="$ROOT_DIR/src" "$PY_BIN" -m labops.cli kaggle-parallel-status --ledger "$LEDGER"

echo "bulk_dispatch_done plan=$PLAN_PATH workers=$WORKERS jobs=$JOBS"
