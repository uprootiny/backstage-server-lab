#!/usr/bin/env bash
set -euo pipefail

cat > "$HOME/.tmux.conf" <<'CONF'
set -g mouse on
set -g history-limit 200000
set -g base-index 1
setw -g pane-base-index 1
set -g status-keys vi
setw -g mode-keys vi
bind r source-file ~/.tmux.conf \; display-message "tmux config reloaded"
CONF

echo "tmux_configured"
