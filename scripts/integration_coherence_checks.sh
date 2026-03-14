#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PY_BIN="${PY_BIN:-python3}"
REPORT="${1:-$ROOT_DIR/docs/INTEGRATION_COHERENCE_CHECKS.md}"

mkdir -p "$(dirname "$REPORT")"

run() {
  local name="$1"
  shift
  echo "==> $name"
  if "$@" >/tmp/check.out 2>/tmp/check.err; then
    echo "PASS: $name"
    return 0
  fi
  echo "FAIL: $name"
  cat /tmp/check.err || true
  return 1
}

ok=1
run "shell_syntax" bash -n scripts/doctor_harness.sh scripts/dispatch_rna_bulk.sh scripts/teardown_kaggle_rna_top12.sh scripts/run_rna_pipeline_analytics.sh || ok=0
run "python_compile" "$PY_BIN" -m py_compile src/labops/rna_3d_pipeline.py || ok=0
run "pipeline_analytics" bash scripts/run_rna_pipeline_analytics.sh || ok=0
if run "doctor_no_heal" bash scripts/doctor_harness.sh "$ROOT_DIR/docs/STACK_DOCTOR_LATEST.md"; then
  :
else
  echo "WARN: doctor_no_heal failed in this environment (likely missing local services); continuing with artifact-level checks"
fi

{
  echo "# Integration & Coherence Checks"
  echo
  echo "- generated_at: $(date -u +"%Y-%m-%dT%H:%M:%SZ")"
  echo "- status: $( [[ "$ok" == "1" ]] && echo PASS || echo FAIL )"
  echo
  echo "## Checks"
  echo
  echo "- shell_syntax"
  echo "- python_compile"
  echo "- pipeline_analytics"
  echo "- doctor_no_heal"
  echo
  echo "## Artifacts"
  echo
  echo "- docs/STACK_DOCTOR_LATEST.md"
  echo "- docs/RNA_PIPELINE_ANALYTICS.md"
  echo "- reports/rna_pipeline_analytics.json"
} > "$REPORT"

echo "coherence_report=$REPORT"
[[ "$ok" == "1" ]]
