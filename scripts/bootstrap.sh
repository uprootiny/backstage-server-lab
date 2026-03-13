#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="$HOME/.local/bin:$PATH"

have() { command -v "$1" >/dev/null 2>&1; }

if have apt-get; then
  sudo apt-get update -y >/dev/null || true
  sudo DEBIAN_FRONTEND=noninteractive apt-get install -y tmux git rsync curl jq htop tree >/dev/null || true
fi

if ! have mise; then
  curl https://mise.run | sh
fi
export PATH="$HOME/.local/bin:$HOME/.local/share/mise/shims:$PATH"

if ! have uv; then
  curl -LsSf https://astral.sh/uv/install.sh | sh
  export PATH="$HOME/.local/bin:$PATH"
fi

cd "$ROOT_DIR"
mise install || true

if [[ ! -d .venv ]]; then
  uv venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
uv pip install -e .[dev]

bash scripts/configure_tmux.sh
bash scripts/configure_jupyter.sh
bash scripts/configure_shell.sh

mkdir -p artifacts/checkpoints artifacts/models logs data tmp

echo "bootstrap_complete root=$ROOT_DIR"
