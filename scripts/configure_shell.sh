#!/usr/bin/env bash
set -euo pipefail

BASHRC="$HOME/.bashrc"
BLOCK_START="# >>> backstage-server-lab >>>"
BLOCK_END="# <<< backstage-server-lab <<<"

if ! grep -q "$BLOCK_START" "$BASHRC" 2>/dev/null; then
  cat >> "$BASHRC" <<'RC'
# >>> backstage-server-lab >>>
export PATH="$HOME/.local/bin:$HOME/.local/share/mise/shims:$PATH"
alias ll='ls -alF'
alias gs='git status -sb'
alias venv='source .venv/bin/activate'
# <<< backstage-server-lab <<<
RC
fi

echo "shell_configured"
