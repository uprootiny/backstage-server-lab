#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HYP_ID="${1:-hypothesis-demo}"

cd "$ROOT_DIR"
source .venv/bin/activate

labops formulate \
  --hypothesis-id "$HYP_ID" \
  --statement "Parameter wiggle improves score without destabilizing validation" \
  --question "Which variant maximizes score under validation threshold?" \
  --voi-prior 0.72 \
  --kaggle-ref "playground-series" \
  --paper-ref "https://arxiv.org/abs/2107.03374" || true

labops run-bench --hypothesis-id "$HYP_ID" --config configs/validation_bench.yaml --workers 3
labops validate --min-metric 0.70
labops graph --out artifacts/thesis_graph.json
labops list
