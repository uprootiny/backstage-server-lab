#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"
source .venv/bin/activate

streamlit run src/labops/kaggle_mashup_app.py --server.port 8511 --server.address 0.0.0.0
