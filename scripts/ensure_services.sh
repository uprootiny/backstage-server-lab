#!/usr/bin/env bash
###############################################################################
# ensure_services.sh — idempotent entry-point for cron / onstart.sh
#
# Safe to call repeatedly.  If the supervisor monitor is already running it
# does nothing; otherwise it launches everything via supervisor.sh start_all.
#
# Cron example (every 5 minutes):
#   */5 * * * * /workspace/backstage-server-lab/scripts/ensure_services.sh >> /workspace/logs/ensure_services.log 2>&1
#
# onstart.sh example:
#   bash /workspace/backstage-server-lab/scripts/ensure_services.sh
###############################################################################
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SUPERVISOR="$SCRIPT_DIR/supervisor.sh"
MONITOR_PID="/tmp/supervisor_monitor.pid"
LOG="/workspace/logs/supervisor.log"

mkdir -p /workspace/logs

timestamp() { date '+%Y-%m-%d %H:%M:%S'; }

# Check whether the monitor loop is already alive
monitor_running=false
if [[ -f "$MONITOR_PID" ]]; then
    pid=$(<"$MONITOR_PID")
    if kill -0 "$pid" 2>/dev/null; then
        monitor_running=true
    fi
fi

if $monitor_running; then
    echo "$(timestamp) [ensure] supervisor monitor already running (pid $pid) — nothing to do" | tee -a "$LOG"
else
    echo "$(timestamp) [ensure] supervisor monitor not detected — starting all services" | tee -a "$LOG"
    bash "$SUPERVISOR" start_all
fi
