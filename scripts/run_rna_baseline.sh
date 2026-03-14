#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

PLAN_PATH="${PLAN_PATH:-$ROOT_DIR/artifacts/kaggle_parallel/plan_rna_baseline.json}"
LEDGER_PATH="${LEDGER_PATH:-$ROOT_DIR/artifacts/kaggle_parallel/ledger.jsonl}"
LOGS_DIR="${LOGS_DIR:-$ROOT_DIR/logs/kaggle_parallel}"
EXEC_DIR="${EXEC_DIR:-$ROOT_DIR/artifacts/kaggle_parallel/executed}"
WORKERS="${WORKERS:-1}"
TIMEOUT_MIN="${TIMEOUT_MIN:-35}"
REPORT_MD="${REPORT_MD:-$ROOT_DIR/docs/RNA_BASELINE_RUN.md}"
REPORT_JSON="${REPORT_JSON:-$ROOT_DIR/reports/rna_baseline_run.json}"

mkdir -p "$(dirname "$PLAN_PATH")" "$LOGS_DIR" "$EXEC_DIR" "$(dirname "$REPORT_MD")" "$(dirname "$REPORT_JSON")"

TOP_NOTEBOOK="notebooks/kaggle/sigmaborov-top1/stanford-rna-3d-folding-top-1-solution.local.ipynb"
SAFE_NOTEBOOK="notebooks/starters/02_rna_3d_training_filled.ipynb"

if [[ ! -f "$TOP_NOTEBOOK" ]]; then
  echo "missing baseline notebook: $TOP_NOTEBOOK" >&2
  exit 2
fi

cat > "$PLAN_PATH" <<JSON
{
  "profile": "rna_baseline_protenix_anchor",
  "retries": {"max_attempts": 2, "backoff_sec": 4},
  "jobs": [
    {
      "id": "baseline-top1",
      "notebook": "${TOP_NOTEBOOK}",
      "timeout_min": ${TIMEOUT_MIN},
      "expected_improvement": 0.30,
      "uncertainty": 0.40,
      "importance": 0.95,
      "tags": ["baseline", "protenix_anchor", "kaggle_top1", "rna_3d"]
    },
    {
      "id": "baseline-sanity",
      "notebook": "${SAFE_NOTEBOOK}",
      "timeout_min": ${TIMEOUT_MIN},
      "expected_improvement": 0.08,
      "uncertainty": 0.20,
      "importance": 0.80,
      "tags": ["baseline", "sanity", "rna_3d"]
    }
  ]
}
JSON

uv run labops kaggle-parallel-dispatch \
  --plan "$PLAN_PATH" \
  --workers "$WORKERS" \
  --ledger "$LEDGER_PATH" \
  --logs-dir "$LOGS_DIR" \
  --executed-dir "$EXEC_DIR"

uv run python - <<'PY' "$LEDGER_PATH" "$REPORT_JSON" "$REPORT_MD" "$PLAN_PATH"
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ledger_path = Path(sys.argv[1])
report_json = Path(sys.argv[2])
report_md = Path(sys.argv[3])
plan_path = Path(sys.argv[4])

rows = [json.loads(x) for x in ledger_path.read_text().splitlines() if x.strip()]
run_end = [r for r in rows if r.get("event") == "run_end"][-1]
run_id = run_end["run_id"]
jobs = [r for r in rows if r.get("run_id") == run_id and r.get("event") == "job_end"]
ok = sum(1 for r in jobs if r.get("status") == "ok")
failed = len(jobs) - ok
payload = {
    "generated_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    "kind": "rna_baseline_run",
    "run_id": run_id,
    "plan": str(plan_path),
    "job_end_count": len(jobs),
    "ok": ok,
    "failed": failed,
    "jobs": jobs,
}
report_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

lines = [
    "# RNA Baseline Run",
    "",
    f"- generated_at: {payload['generated_at']}",
    f"- run_id: `{run_id}`",
    f"- plan: `{plan_path}`",
    f"- job_end_count: {len(jobs)}",
    f"- ok: {ok}",
    f"- failed: {failed}",
    "",
    "## Jobs",
    "",
    "| Job ID | Status | Seconds | Log |",
    "|---|---|---:|---|",
]
for j in jobs:
    lines.append(
        f"| `{j.get('job_id','')}` | `{j.get('status','')}` | {float(j.get('seconds',0.0)):.2f} | `{j.get('log','')}` |"
    )
report_md.write_text("\n".join(lines) + "\n", encoding="utf-8")

print(f"baseline_report_json={report_json}")
print(f"baseline_report_md={report_md}")
print(f"baseline_run_id={run_id}")
PY
