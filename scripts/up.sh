#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT_DIR/.venv/bin/activate"

mkdir -p "$ROOT_DIR/logs"

tmux has-session -t mlflow 2>/dev/null || \
  tmux new-session -d -s mlflow \
  "cd $ROOT_DIR && source .venv/bin/activate && mlflow server --host 0.0.0.0 --port 1111 --backend-store-uri sqlite:///$ROOT_DIR/mlflow.db --default-artifact-root $ROOT_DIR/artifacts >> $ROOT_DIR/logs/mlflow.log 2>&1"

tmux has-session -t tensorboard 2>/dev/null || \
  tmux new-session -d -s tensorboard \
  "cd $ROOT_DIR && source .venv/bin/activate && tensorboard --logdir $ROOT_DIR/artifacts --host 0.0.0.0 --port 6006 >> $ROOT_DIR/logs/tensorboard.log 2>&1"

if [[ "${START_KAGGLE_MASHUP:-0}" == "1" ]]; then
  tmux has-session -t kaggle-mashup 2>/dev/null || \
    tmux new-session -d -s kaggle-mashup \
    "cd $ROOT_DIR && source .venv/bin/activate && streamlit run src/labops/kaggle_mashup_app.py --server.port 8511 --server.address 0.0.0.0 >> $ROOT_DIR/logs/kaggle-mashup.log 2>&1"
fi

if [[ "${START_RNA_BRIDGE:-1}" == "1" ]]; then
  bash "$ROOT_DIR/scripts/start_rna_artifact_bridge.sh"
fi

echo "services_up"
tmux ls
