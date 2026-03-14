#!/usr/bin/env bash
# start_tensorboard.sh — Start TensorBoard on port 6006 (Vast maps → external 19448)
set -euo pipefail

LOGDIR="${1:-/workspace/logs/rna}"
PORT=6006
BIND="0.0.0.0"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

mkdir -p "$LOGDIR"

# Kill existing TensorBoard on this port
echo "-> Stopping any existing TensorBoard on port $PORT..."
pkill -f "tensorboard.*--port.*$PORT" 2>/dev/null || true
sleep 1

# Write a demo run if logdir is empty
if [ -z "$(find "$LOGDIR" -name 'events.out.*' 2>/dev/null | head -1)" ]; then
    echo "-> Logdir is empty — writing demo run..."
    PYTHONPATH="$REPO_ROOT/src" python3 "$REPO_ROOT/src/labops/rna_tbx.py" "$LOGDIR"
    echo "   Demo run written to $LOGDIR"
fi

# Launch TensorBoard
echo "-> Starting TensorBoard..."
echo "  logdir : $LOGDIR"
echo "  port   : $PORT  (external -> 19448)"
echo ""

nohup python3 -m tensorboard.main \
    --logdir      "$LOGDIR"   \
    --port        $PORT        \
    --bind_all                 \
    --reload_interval 10       \
    --samples_per_plugin "images=100,scalars=10000,histograms=500" \
    --window_title "RNA 3D Training Lab" \
    > /tmp/tensorboard.log 2>&1 &

TB_PID=$!
echo "  PID    : $TB_PID"
echo "  log    : /tmp/tensorboard.log"

echo -n "  Waiting for TensorBoard to start"
for i in $(seq 1 20); do
    sleep 1
    if curl -sf "http://localhost:$PORT/" > /dev/null 2>&1; then
        echo ""
        echo "OK TensorBoard is up on port $PORT"
        exit 0
    fi
    echo -n "."
done
echo ""
echo "WARNING: TensorBoard did not respond after 20s — check /tmp/tensorboard.log"
tail -20 /tmp/tensorboard.log
exit 1
