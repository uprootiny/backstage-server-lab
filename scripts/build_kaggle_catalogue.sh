#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SEARCH="${1:-rna}"
LIMIT="${2:-120}"
OUT="${3:-$ROOT_DIR/artifacts/kaggle_catalogue.json}"

# shellcheck disable=SC1091
source "$ROOT_DIR/.venv/bin/activate"
cd "$ROOT_DIR"
labops kaggle-catalogue --search "$SEARCH" --limit "$LIMIT" --out "$OUT"
echo "kaggle_catalogue_ready out=$OUT search=$SEARCH limit=$LIMIT"
