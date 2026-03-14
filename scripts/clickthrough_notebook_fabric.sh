#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

WORKERS="${WORKERS:-6}"
PLAN="${PLAN:-artifacts/kaggle_parallel/plan.json}"
LEDGER="${LEDGER:-artifacts/kaggle_parallel/ledger.jsonl}"
LOGS_DIR="${LOGS_DIR:-logs/kaggle_parallel}"
EXEC_DIR="${EXEC_DIR:-artifacts/kaggle_parallel/executed}"

mkdir -p "$LOGS_DIR" "$EXEC_DIR"

if [[ -x .venv/bin/python ]]; then
  PY=".venv/bin/python"
else
  PY="python3"
fi

echo "[1/5] pull open notebook repos + artifacts + paramsets"
"$PY" scripts/pull_notebook_sources.py

echo "[2/5] ensure interactive orchestrator notebook exists"
"$PY" scripts/build_interactive_orchestrator_notebook.py

echo "[3/5] dispatch parallel jobs workers=$WORKERS plan=$PLAN"
PYTHONPATH=src "$PY" -m labops.cli kaggle-parallel-dispatch --plan "$PLAN" --workers "$WORKERS" --ledger "$LEDGER" --logs-dir "$LOGS_DIR" --executed-dir "$EXEC_DIR" || true

echo "[4/5] summarize ledger"
PYTHONPATH=src "$PY" -m labops.cli kaggle-parallel-status --ledger "$LEDGER" || true

echo "[5/5] suggest high-VOI reruns"
PYTHONPATH=src "$PY" -m labops.cli kaggle-parallel-reruns --ledger "$LEDGER" --min-voi 0.12 --limit 20 || true

echo "clickthrough_complete plan=$PLAN ledger=$LEDGER"
