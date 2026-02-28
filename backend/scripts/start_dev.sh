#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
PYTHON_BIN="${PYTHON_BIN:-/home/avishek/.pyenv/versions/meeting-intel/bin/python}"
RQ_BIN="${RQ_BIN:-/home/avishek/.pyenv/versions/meeting-intel/bin/rq}"
HOST="${HOST:-0.0.0.0}"
PORT="${PORT:-8003}"
HEARTBEAT_SECONDS="${HEARTBEAT_SECONDS:-5}"
KILL_EXISTING_WORKERS="${KILL_EXISTING_WORKERS:-0}"

export PYTHONPATH="$BACKEND_DIR"

cleanup() {
  if [[ -n "${MONITOR_PID:-}" ]] && kill -0 "$MONITOR_PID" 2>/dev/null; then
    kill "$MONITOR_PID" 2>/dev/null || true
  fi
  if [[ -n "${UVICORN_PID:-}" ]] && kill -0 "$UVICORN_PID" 2>/dev/null; then
    kill "$UVICORN_PID" 2>/dev/null || true
  fi
  if [[ -n "${WORKER_PID:-}" ]] && kill -0 "$WORKER_PID" 2>/dev/null; then
    kill "$WORKER_PID" 2>/dev/null || true
  fi
}

trap cleanup EXIT INT TERM

cd "$BACKEND_DIR"

echo "[dev] Starting services from: $BACKEND_DIR"

existing_workers="$(pgrep -f 'rq worker default' || true)"
if [[ -n "$existing_workers" ]]; then
  if [[ "$KILL_EXISTING_WORKERS" == "1" ]]; then
    echo "[dev] Stopping existing rq worker(s): $existing_workers"
    pkill -f 'rq worker default' || true
    sleep 1
  else
    echo "[warn] Existing rq worker(s) detected: $existing_workers"
    echo "[warn] This can make job logs appear in another terminal."
    echo "[warn] To auto-stop old workers, run with KILL_EXISTING_WORKERS=1"
  fi
fi

"$RQ_BIN" worker default &
WORKER_PID=$!
echo "[dev] RQ worker PID: $WORKER_PID"

"$PYTHON_BIN" -m uvicorn main:app --host "$HOST" --port "$PORT" --reload &
UVICORN_PID=$!
echo "[dev] Uvicorn PID: $UVICORN_PID"
echo "[dev] API URL: http://$HOST:$PORT"

monitor_loop() {
  while true; do
    sleep "$HEARTBEAT_SECONDS"

    uvicorn_state="up"
    worker_state="up"

    if ! kill -0 "$UVICORN_PID" 2>/dev/null; then
      uvicorn_state="down"
    fi
    if ! kill -0 "$WORKER_PID" 2>/dev/null; then
      worker_state="down"
    fi

    stats="$($RQ_BIN info 2>/dev/null | awk '
      /^default[[:space:]]*\|/ {
        q=$3; gsub(",", "", q)
        e=$4; gsub(",", "", e)
        f=$6; gsub(",", "", f)
        d=$8; gsub(",", "", d)
        printf("queued=%s executing=%s finished=%s failed=%s", q, e, f, d)
      }
      /^[0-9]+ workers,/ {
        printf(" workers_total=%s", $1)
      }
    ')"

    our_worker="down"
    if kill -0 "$WORKER_PID" 2>/dev/null; then
      our_worker="up"
    fi

    if [[ -z "$stats" ]]; then
      stats="queued=? executing=? finished=? failed=? workers_total=?"
    fi

    echo "[heartbeat] uvicorn=$uvicorn_state worker=$worker_state our_worker=$our_worker pid=$WORKER_PID $stats"

    if [[ "$uvicorn_state" == "down" || "$worker_state" == "down" ]]; then
      echo "[alert] One of the processes is down. Stop and restart with: bash backend/scripts/start_dev.sh"
    fi
  done
}

monitor_loop &
MONITOR_PID=$!
echo "[dev] Monitor PID: $MONITOR_PID (interval ${HEARTBEAT_SECONDS}s)"

wait "$UVICORN_PID"
