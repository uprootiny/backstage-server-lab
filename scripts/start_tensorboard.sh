#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOGDIR="${1:-/workspace/logs/rna}"
PORT="${TB_PORT:-6006}"
HOST="${TB_HOST:-0.0.0.0}"
LOGFILE="${TB_LOGFILE:-${LOGDIR%/}/tensorboard.log}"

if ! mkdir -p "${LOGDIR}" "$(dirname "${LOGFILE}")" 2>/dev/null; then
  LOGDIR="/tmp/rna_tb"
  LOGFILE="${TB_LOGFILE:-/tmp/tensorboard.log}"
  mkdir -p "${LOGDIR}" "$(dirname "${LOGFILE}")"
fi
cd "${ROOT_DIR}"

# Stop prior tensorboard processes on this port.
if command -v lsof >/dev/null 2>&1; then
  PIDS="$(lsof -tiTCP:${PORT} -sTCP:LISTEN 2>/dev/null || true)"
  if [[ -n "${PIDS}" ]]; then
    echo "stopping existing tensorboard on :${PORT} (${PIDS})"
    kill ${PIDS} 2>/dev/null || true
    sleep 1
    for p in ${PIDS}; do
      if kill -0 "$p" 2>/dev/null; then kill -9 "$p" 2>/dev/null || true; fi
    done
  fi
fi

# Seed demo events if logdir is empty.
if [[ -z "$(find "${LOGDIR}" -type f -name 'events.out.tfevents.*' -print -quit)" ]]; then
  echo "logdir empty, writing demo RNA events to ${LOGDIR}"
  uv run python -m labops.rna_tbx --logdir "${LOGDIR}" --run-name "boot_demo"
fi

TB_CMD=""
if uvx --from tensorboard tensorboard --version >/dev/null 2>&1; then
  TB_CMD="uvx --from tensorboard tensorboard"
else
  TB_CMD="uv run tensorboard"
fi

nohup bash -lc "${TB_CMD} \
  --logdir '${LOGDIR}' \
  --host '${HOST}' \
  --port '${PORT}' \
  --reload_interval 10" \
  >"${LOGFILE}" 2>&1 &
TB_PID=$!

echo "tensorboard_started pid=${TB_PID} logdir=${LOGDIR} host=${HOST} port=${PORT}"
echo "tail -f ${LOGFILE}"
