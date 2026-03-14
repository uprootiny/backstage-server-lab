#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "usage: bash scripts/munch_csv_dataset.sh <signed_csv_url> [out_dir]" >&2
  exit 2
fi

URL="$1"
OUT_DIR="${2:-artifacts/datasets}"
mkdir -p "$OUT_DIR"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
CSV_PATH="$OUT_DIR/dataset_${STAMP}.csv"
META_PATH="$OUT_DIR/dataset_${STAMP}.json"

curl -L --fail --retry 3 --retry-delay 1 "$URL" -o "$CSV_PATH"

uv run python - <<PY
import hashlib, json
from pathlib import Path
import pandas as pd

csv_path = Path("$CSV_PATH")
meta_path = Path("$META_PATH")

df = pd.read_csv(csv_path)
sha = hashlib.sha256(csv_path.read_bytes()).hexdigest()
meta = {
    "path": str(csv_path),
    "rows": int(len(df)),
    "columns": [str(c) for c in df.columns.tolist()],
    "dtypes": {str(k): str(v) for k, v in df.dtypes.to_dict().items()},
    "head": df.head(5).to_dict(orient="records"),
    "sha256": sha,
}
meta_path.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
print(json.dumps({"csv": str(csv_path), "meta": str(meta_path), "rows": meta["rows"]}, indent=2))
PY
