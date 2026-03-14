#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${RNA_WORKBENCH_PORT:-8522}"
WEB_ROOT="$ROOT_DIR/web"

if [[ ! -f "$WEB_ROOT/rna_workbench.html" ]]; then
  echo "missing $WEB_ROOT/rna_workbench.html"
  exit 1
fi

tmux has-session -t rna-workbench 2>/dev/null || \
  tmux new-session -d -s rna-workbench \
  "cd '$WEB_ROOT' && python3 -m http.server '$PORT' --bind 0.0.0.0 >> '$ROOT_DIR/logs/rna-workbench.log' 2>&1"

echo "rna_workbench_up url=http://127.0.0.1:$PORT/rna_workbench.html"
