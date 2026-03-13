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

echo "services_up"
tmux ls
