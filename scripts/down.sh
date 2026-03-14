#!/usr/bin/env bash
set -euo pipefail

tmux kill-session -t mlflow 2>/dev/null || true
tmux kill-session -t tensorboard 2>/dev/null || true
tmux kill-session -t kaggle-mashup 2>/dev/null || true
tmux kill-session -t rna-bridge 2>/dev/null || true
tmux kill-session -t rna-workbench 2>/dev/null || true
echo "services_down"
