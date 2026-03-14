#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

KAGGLE_BIN="${KAGGLE_BIN:-/venv/main/bin/kaggle}"
if [[ ! -x "$KAGGLE_BIN" ]]; then
  KAGGLE_BIN="$(command -v kaggle || true)"
fi
QUERY="${QUERY:-stanford rna 3d folding}"
TOP_N="${TOP_N:-12}"
OUT_DIR="${OUT_DIR:-$ROOT_DIR/notebooks/kaggle/live_teardown}"
OUT_MD="${OUT_MD:-$ROOT_DIR/docs/KAGGLE_RNA_TOP12_TEARDOWN.md}"
OUT_JSON="${OUT_JSON:-$ROOT_DIR/docs/KAGGLE_RNA_TOP12_TEARDOWN.json}"

mkdir -p "$OUT_DIR" "$(dirname "$OUT_MD")"

if [[ ! -x "$KAGGLE_BIN" ]]; then
  echo "missing_kaggle_cli bin=$KAGGLE_BIN"
  exit 2
fi

list_txt="$(mktemp)"
"$KAGGLE_BIN" kernels list -s "$QUERY" --page-size 30 > "$list_txt"

# Collect top refs by list order (already sorted by votes/recency in Kaggle listing).
mapfile -t refs < <(awk 'NR>2 && $1 !~ /^-+$/ {print $1}' "$list_txt" | head -n "$TOP_N")

if [[ "${#refs[@]}" -eq 0 ]]; then
  echo "no_refs_found query=$QUERY"
  exit 3
fi

for ref in "${refs[@]}"; do
  slug="${ref//\//__}"
  target="$OUT_DIR/$slug"
  mkdir -p "$target"
  "$KAGGLE_BIN" kernels pull "$ref" -p "$target" >/tmp/kpull.log 2>&1 || true
  if [[ ! -f "$target/${ref##*/}.ipynb" ]]; then
    # fallback if notebook filename differs
    ls "$target"/*.ipynb >/dev/null 2>&1 || true
  fi
done

TOP_N="$TOP_N" OUT_DIR="$OUT_DIR" OUT_MD="$OUT_MD" OUT_JSON="$OUT_JSON" /venv/main/bin/python - <<'PY'
import json
import os
from pathlib import Path

out_dir = Path(os.environ["OUT_DIR"])
out_md = Path(os.environ["OUT_MD"])
out_json = Path(os.environ["OUT_JSON"])

def analyze_ipynb(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    cells = data.get("cells", [])
    code_cells = [c for c in cells if c.get("cell_type") == "code"]
    md_cells = [c for c in cells if c.get("cell_type") == "markdown"]
    src = "\n".join("".join(c.get("source", [])) for c in code_cells)
    imports = []
    for k in ["torch", "tensorflow", "jax", "numpy", "pandas", "matplotlib", "plotly", "sklearn", "xgboost", "lightgbm", "viennarna", "ribonanza", "protenix", "rhofold"]:
        if k in src.lower():
            imports.append(k)
    return {
        "path": str(path),
        "cells": len(cells),
        "code_cells": len(code_cells),
        "markdown_cells": len(md_cells),
        "has_submission": "submission" in src.lower(),
        "has_inference": "inference" in src.lower(),
        "imports": imports,
        "lines_code": sum(len("".join(c.get("source", [])).splitlines()) for c in code_cells),
    }

rows = []
for d in sorted(out_dir.iterdir()):
    if not d.is_dir():
        continue
    for ipynb in d.glob("*.ipynb"):
        rows.append(analyze_ipynb(ipynb))

rows = sorted(rows, key=lambda r: (r["has_submission"], r["has_inference"], r["code_cells"], r["lines_code"]), reverse=True)
out_json.write_text(json.dumps(rows, indent=2), encoding="utf-8")

lines = []
lines.append("# Kaggle RNA Top-12 Teardown")
lines.append("")
lines.append("| Notebook | Code cells | LOC(code) | Inference | Submission | Imports |")
lines.append("|---|---:|---:|---|---|---|")
for r in rows:
    name = Path(r["path"]).parent.name
    lines.append(f"| `{name}` | {r['code_cells']} | {r['lines_code']} | {'yes' if r['has_inference'] else 'no'} | {'yes' if r['has_submission'] else 'no'} | {', '.join(r['imports']) or '-'} |")

lines.append("")
lines.append("## Operational Summary")
if rows:
    inf = sum(1 for r in rows if r["has_inference"])
    sub = sum(1 for r in rows if r["has_submission"])
    avg_code = sum(r["code_cells"] for r in rows) / len(rows)
    lines.append(f"- notebooks_analyzed: {len(rows)}")
    lines.append(f"- inference_notebooks: {inf}")
    lines.append(f"- submission_notebooks: {sub}")
    lines.append(f"- avg_code_cells: {avg_code:.1f}")
    lines.append("- recommendation: prioritize notebooks with both inference+submission and heavy RNA-specific imports for reproduction queue.")

out_md.write_text("\n".join(lines) + "\n", encoding="utf-8")
print(f"teardown_md={out_md}")
print(f"teardown_json={out_json}")
print(f"notebooks_analyzed={len(rows)}")
PY

echo "teardown_done query=$QUERY top_n=$TOP_N"
