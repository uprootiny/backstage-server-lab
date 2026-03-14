#!/usr/bin/env bash
###############################################################################
# supervisor.sh — resilient process supervisor for Vast.ai web services
#
# Usage:
#   supervisor.sh start_all   — start all services and begin monitoring
#   supervisor.sh stop_all    — stop all services and the monitor loop
#   supervisor.sh status      — print the health of every managed service
#   supervisor.sh monitor     — (internal) runs the periodic health-check loop
###############################################################################
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="/workspace/logs"
SUPERVISOR_LOG="$LOG_DIR/supervisor.log"
CHECK_INTERVAL=30

# PID files
PID_DIR="/tmp"
TENSORBOARD_PID="$PID_DIR/supervisor_tensorboard.pid"
STREAMLIT_PID="$PID_DIR/supervisor_streamlit.pid"
PORTAL_PID="$PID_DIR/supervisor_portal.pid"
MONITOR_PID="$PID_DIR/supervisor_monitor.pid"

# Service log files
TB_LOG="$LOG_DIR/tensorboard_supervisor.log"
ST_LOG="$LOG_DIR/streamlit_supervisor.log"
PT_LOG="$LOG_DIR/portal_supervisor.log"

mkdir -p "$LOG_DIR"

###############################################################################
# Helpers
###############################################################################
log() {
    local msg
    msg="$(date '+%Y-%m-%d %H:%M:%S') $*"
    echo "$msg" >> "$SUPERVISOR_LOG"
    echo "$msg"
}

is_pid_alive() {
    local pid_file="$1"
    if [[ -f "$pid_file" ]]; then
        local pid
        pid=$(<"$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            return 0
        fi
    fi
    return 1
}

kill_pid_file() {
    local pid_file="$1"
    if [[ -f "$pid_file" ]]; then
        local pid
        pid=$(<"$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            kill "$pid" 2>/dev/null || true
            # Give it a moment, then force-kill if still alive
            sleep 2
            kill -0 "$pid" 2>/dev/null && kill -9 "$pid" 2>/dev/null || true
        fi
        rm -f "$pid_file"
    fi
}

health_check() {
    local port="$1"
    local timeout="${2:-5}"
    local http_code
    http_code=$(curl -s -o /dev/null -w '%{http_code}' --max-time "$timeout" "http://127.0.0.1:${port}/" 2>/dev/null) || true
    if [[ "$http_code" == "200" ]]; then
        return 0
    fi
    return 1
}

###############################################################################
# Service: TensorBoard (port 6006)
###############################################################################
start_tensorboard() {
    if is_pid_alive "$TENSORBOARD_PID"; then
        log "[tensorboard] already running (pid $(< "$TENSORBOARD_PID"))"
        return 0
    fi
    log "[tensorboard] starting on port 6006"
    mkdir -p /workspace/logs/rna
    cd "$ROOT_DIR"
    nohup python3 -m tensorboard.main \
        --logdir /workspace/logs/rna \
        --port 6006 \
        --bind_all \
        --reload_interval 10 \
        >> "$TB_LOG" 2>&1 &
    local pid=$!
    echo "$pid" > "$TENSORBOARD_PID"
    log "[tensorboard] started with pid $pid"
}

stop_tensorboard() {
    log "[tensorboard] stopping"
    kill_pid_file "$TENSORBOARD_PID"
    # Also clean up any orphaned tensorboard processes on port 6006
    local orphan
    orphan=$(lsof -ti :6006 2>/dev/null) || true
    if [[ -n "$orphan" ]]; then
        kill $orphan 2>/dev/null || true
    fi
    log "[tensorboard] stopped"
}

###############################################################################
# Service: Streamlit mashup (port 1111)
###############################################################################
start_streamlit() {
    if is_pid_alive "$STREAMLIT_PID"; then
        log "[streamlit] already running (pid $(< "$STREAMLIT_PID"))"
        return 0
    fi
    log "[streamlit] starting on port 1111"
    cd "$ROOT_DIR"
    PYTHONPATH=src nohup python3 -m streamlit run \
        src/labops/kaggle_mashup_app.py \
        --server.port 1111 \
        --server.address 0.0.0.0 \
        --server.headless true \
        >> "$ST_LOG" 2>&1 &
    local pid=$!
    echo "$pid" > "$STREAMLIT_PID"
    log "[streamlit] started with pid $pid"
}

stop_streamlit() {
    log "[streamlit] stopping"
    kill_pid_file "$STREAMLIT_PID"
    local orphan
    orphan=$(lsof -ti :1111 2>/dev/null) || true
    if [[ -n "$orphan" ]]; then
        kill $orphan 2>/dev/null || true
    fi
    log "[streamlit] stopped"
}

###############################################################################
# Service: Portal server (port 8520)
###############################################################################
start_portal() {
    if is_pid_alive "$PORTAL_PID"; then
        log "[portal] already running (pid $(< "$PORTAL_PID"))"
        return 0
    fi
    log "[portal] starting on port 8520"
    cd "$ROOT_DIR"
    nohup python3 web/portal/server.py \
        >> "$PT_LOG" 2>&1 &
    local pid=$!
    echo "$pid" > "$PORTAL_PID"
    log "[portal] started with pid $pid"
}

stop_portal() {
    log "[portal] stopping"
    kill_pid_file "$PORTAL_PID"
    local orphan
    orphan=$(lsof -ti :8520 2>/dev/null) || true
    if [[ -n "$orphan" ]]; then
        kill $orphan 2>/dev/null || true
    fi
    log "[portal] stopped"
}

###############################################################################
# Monitor loop — the heart of the supervisor
###############################################################################
monitor_loop() {
    log "[monitor] health-check loop starting (interval=${CHECK_INTERVAL}s)"
    echo $$ > "$MONITOR_PID"

    while true; do
        # --- TensorBoard ---
        if ! is_pid_alive "$TENSORBOARD_PID"; then
            log "[monitor] tensorboard process not found — restarting"
            start_tensorboard
        elif ! health_check 6006; then
            log "[monitor] tensorboard health check failed (port 6006) — restarting"
            stop_tensorboard
            sleep 1
            start_tensorboard
        fi

        # --- Streamlit ---
        if ! is_pid_alive "$STREAMLIT_PID"; then
            log "[monitor] streamlit process not found — restarting"
            start_streamlit
        elif ! health_check 1111; then
            log "[monitor] streamlit health check failed (port 1111) — restarting"
            stop_streamlit
            sleep 1
            start_streamlit
        fi

        # --- Portal ---
        if ! is_pid_alive "$PORTAL_PID"; then
            log "[monitor] portal process not found — restarting"
            start_portal
        elif ! health_check 8520; then
            log "[monitor] portal health check failed (port 8520) — restarting"
            stop_portal
            sleep 1
            start_portal
        fi

        sleep "$CHECK_INTERVAL"
    done
}

###############################################################################
# Subcommands
###############################################################################
cmd_start_all() {
    log "========== start_all =========="
    start_tensorboard
    start_streamlit
    start_portal

    # Start monitor loop in background if not already running
    if is_pid_alive "$MONITOR_PID"; then
        log "[monitor] already running (pid $(< "$MONITOR_PID"))"
    else
        log "[monitor] launching background monitor"
        nohup bash "$0" monitor >> "$SUPERVISOR_LOG" 2>&1 &
        disown
        log "[monitor] launched (pid $!)"
    fi
    log "start_all complete"
}

cmd_stop_all() {
    log "========== stop_all =========="
    # Stop the monitor first so it doesn't restart services
    if is_pid_alive "$MONITOR_PID"; then
        log "[monitor] stopping monitor loop"
        kill_pid_file "$MONITOR_PID"
    fi
    stop_tensorboard
    stop_streamlit
    stop_portal
    log "stop_all complete"
}

cmd_status() {
    echo "=== Supervisor Status ==="
    echo ""

    # Monitor
    if is_pid_alive "$MONITOR_PID"; then
        echo "  monitor loop : RUNNING (pid $(< "$MONITOR_PID"))"
    else
        echo "  monitor loop : STOPPED"
    fi
    echo ""

    # TensorBoard
    local tb_status="STOPPED"
    local tb_health="n/a"
    if is_pid_alive "$TENSORBOARD_PID"; then
        tb_status="RUNNING (pid $(< "$TENSORBOARD_PID"))"
        if health_check 6006 2; then
            tb_health="HTTP 200 OK"
        else
            tb_health="UNHEALTHY"
        fi
    fi
    echo "  tensorboard  : $tb_status"
    echo "    health     : $tb_health"
    echo ""

    # Streamlit
    local st_status="STOPPED"
    local st_health="n/a"
    if is_pid_alive "$STREAMLIT_PID"; then
        st_status="RUNNING (pid $(< "$STREAMLIT_PID"))"
        if health_check 1111 2; then
            st_health="HTTP 200 OK"
        else
            st_health="UNHEALTHY"
        fi
    fi
    echo "  streamlit    : $st_status"
    echo "    health     : $st_health"
    echo ""

    # Portal
    local pt_status="STOPPED"
    local pt_health="n/a"
    if is_pid_alive "$PORTAL_PID"; then
        pt_status="RUNNING (pid $(< "$PORTAL_PID"))"
        if health_check 8520 2; then
            pt_health="HTTP 200 OK"
        else
            pt_health="UNHEALTHY"
        fi
    fi
    echo "  portal       : $pt_status"
    echo "    health     : $pt_health"
    echo ""
    echo "  log file     : $SUPERVISOR_LOG"
    echo "==========================="
}

###############################################################################
# Main dispatch
###############################################################################
case "${1:-}" in
    start_all)  cmd_start_all ;;
    stop_all)   cmd_stop_all  ;;
    status)     cmd_status    ;;
    monitor)    monitor_loop  ;;
    *)
        echo "Usage: $0 {start_all|stop_all|status}"
        exit 1
        ;;
esac
