#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="/workspace/backstage-server-lab"
LOG_DIR="${REPO_DIR}/logs"
mkdir -p "$LOG_DIR"

if [[ ! -d "$REPO_DIR/.git" ]]; then
  git clone https://github.com/uprootiny/backstage-server-lab.git "$REPO_DIR" >>"$LOG_DIR/onstart.log" 2>&1 || true
fi

cd "$REPO_DIR"
git fetch origin main >>"$LOG_DIR/onstart.log" 2>&1 || true
git checkout main >>"$LOG_DIR/onstart.log" 2>&1 || true
git pull --ff-only >>"$LOG_DIR/onstart.log" 2>&1 || true

if [[ ! -d .venv ]]; then
  bash scripts/bootstrap.sh >>"$LOG_DIR/onstart.log" 2>&1 || true
fi

# Keep the tri-surface runtime online by default
bash scripts/up.sh >>"$LOG_DIR/onstart.log" 2>&1 || true

# Optional observatory on 19842 (uses system venv on vast image)
pkill -f "streamlit run src/labops/kaggle_mashup_app.py" || true
nohup /venv/main/bin/python -m streamlit run src/labops/kaggle_mashup_app.py \
  --server.port 19842 --server.address 0.0.0.0 --server.headless true \
  >>"$LOG_DIR/observatory.log" 2>&1 &

# Write one typed operator event if CLI is available
if [[ -x .venv/bin/python ]]; then
  .venv/bin/python - <<'PY' || true
from datetime import datetime, timezone
from pathlib import Path
import json
p = Path("artifacts/operator_events.jsonl")
p.parent.mkdir(parents=True, exist_ok=True)
row = {
    "ts": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00","Z"),
    "kind": "infra.info",
    "source": "vast.onstart",
    "message": "onstart completed",
    "severity": "info",
    "run_id": ""
}
with p.open("a", encoding="utf-8") as f:
    f.write(json.dumps(row, ensure_ascii=True) + "\\n")
PY
fi
