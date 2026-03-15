#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HYP_ID="${1:-hypothesis-demo}"

export PATH="$HOME/.local/bin:$PATH"
cd "$ROOT_DIR"
source .venv/bin/activate

labops formulate \
  "Parameter wiggle improves score without destabilizing validation" \
  "Which variant maximizes score under validation threshold?" \
  --hypothesis-id "$HYP_ID" \
  --voi-prior 0.72 \
  --kaggle-ref "playground-series" \
  --paper-ref "https://arxiv.org/abs/2107.03374" || true

labops run-bench "$HYP_ID" --config configs/validation_bench.yaml --workers 3
labops validate --min-metric 0.70
labops graph --out artifacts/thesis_graph.json
labops list
