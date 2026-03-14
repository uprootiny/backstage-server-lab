#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PRED_FILE="${1:-}"
RUN_ID="${2:-run-$(date -u +%Y%m%dT%H%M%SZ)}"
SEQUENCE="${3:-unknown}"
MODEL="${4:-unknown}"
HOST_BASE="${RNA_BRIDGE_PUBLIC_BASE:-http://127.0.0.1:${RNA_BRIDGE_PORT:-19999}}"
ROOT_DATA="${RNA_BRIDGE_ROOT:-$ROOT_DIR/artifacts/rna_predictions}"
INDEX="$ROOT_DATA/index.json"

if [[ -z "$PRED_FILE" ]]; then
  echo "usage: $0 <prediction.pdb> [run_id] [sequence] [model]"
  exit 2
fi

mkdir -p "$ROOT_DATA/$RUN_ID"
cp "$PRED_FILE" "$ROOT_DATA/$RUN_ID/prediction.pdb"

if [[ ! -f "$INDEX" ]]; then
  printf '{\n  "predictions": []\n}\n' > "$INDEX"
fi

ts="$(date -u +"%Y-%m-%dT%H:%M:%SZ")"
url="$HOST_BASE/$RUN_ID/prediction.pdb"

tmp="$(mktemp)"
jq \
  --arg run_id "$RUN_ID" \
  --arg sequence "$SEQUENCE" \
  --arg model "$MODEL" \
  --arg url "$url" \
  --arg created_at "$ts" \
  '.predictions += [{
    "run_id": $run_id,
    "sequence": $sequence,
    "model": $model,
    "pdb_url": $url,
    "created_at": $created_at
  }]' \
  "$INDEX" > "$tmp"
mv "$tmp" "$INDEX"

echo "rna_prediction_registered run_id=$RUN_ID pdb_url=$url index=$INDEX"
