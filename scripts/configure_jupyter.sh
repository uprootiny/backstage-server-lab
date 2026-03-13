#!/usr/bin/env bash
set -euo pipefail

mkdir -p "$HOME/.jupyter"
cat > "$HOME/.jupyter/jupyter_lab_config.py" <<'PYCONF'
c.ServerApp.ip = "0.0.0.0"
c.ServerApp.open_browser = False
c.ServerApp.allow_remote_access = True
c.ServerApp.port = 8080
PYCONF

echo "jupyter_configured"
