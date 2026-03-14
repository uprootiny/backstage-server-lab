#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PORT="${RNA_BRIDGE_PORT:-19999}"
ROOT_DATA="${RNA_BRIDGE_ROOT:-$ROOT_DIR/artifacts/rna_predictions}"

mkdir -p "$ROOT_DATA"

if [[ ! -f "$ROOT_DATA/index.json" ]]; then
  cat > "$ROOT_DATA/index.json" <<'JSON'
{
  "predictions": []
}
JSON
fi

tmux has-session -t rna-bridge 2>/dev/null || \
  tmux new-session -d -s rna-bridge \
  "cd '$ROOT_DATA' && python3 -m http.server '$PORT' --bind 0.0.0.0 >> '$ROOT_DIR/logs/rna-bridge.log' 2>&1"

echo "rna_bridge_up root=$ROOT_DATA port=$PORT"
