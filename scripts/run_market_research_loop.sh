#!/usr/bin/env bash
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="${WEALTHPULSE_REPO_DIR:-$(cd "$SCRIPT_DIR/.." && pwd)}"
LOG_ROOT="${LOGS_DIR:-$REPO_DIR/storage/logs}"
LOG_DIR="$LOG_ROOT/runtime"
LOG_FILE="$LOG_DIR/openai_research_loop.log"
RUNNER="$SCRIPT_DIR/run_market_research.sh"
INTERVAL_SECONDS="${WEALTHPULSE_RESEARCH_LOOP_INTERVAL_SECONDS:-60}"
CLOSED_INTERVAL_SECONDS="${WEALTHPULSE_RESEARCH_CLOSED_INTERVAL_SECONDS:-600}"
MARKET="${WEALTHPULSE_RESEARCH_MARKET:-KOSPI}"
FAIL_STOP_MARKER="${WEALTHPULSE_RESEARCH_FAIL_STOP_MARKER:-/tmp/wealthpulse-research-loop.fail-stopped}"
ACTIVE_CHILD_PID=""

mkdir -p "$LOG_DIR"
exec > >(tee -a "$LOG_FILE") 2>&1

shutdown() {
  local child_pid="${ACTIVE_CHILD_PID:-}"

  trap - TERM INT
  if [[ -n "$child_pid" ]]; then
    kill -TERM -- "-$child_pid" 2>/dev/null || true
    wait "$child_pid" 2>/dev/null || true
  fi
  ACTIVE_CHILD_PID=""
  printf '[%s] wealthpulse-research-loop stop reason=signal\n' "$(date --iso-8601=seconds)"
  exit 0
}

run_tracked() {
  setsid "$@" &
  ACTIVE_CHILD_PID=$!
  wait "$ACTIVE_CHILD_PID"
  local status=$?
  ACTIVE_CHILD_PID=""
  return "$status"
}

fail_stopped() {
  local reason="$1"
  local exit_code="${2:-1}"

  printf '%s\n' "$reason" > "$FAIL_STOP_MARKER"
  printf '[%s] wealthpulse-research-loop fail_stopped reason=%s exit_code=%s marker=%s\n' \
    "$(date --iso-8601=seconds)" "$reason" "$exit_code" "$FAIL_STOP_MARKER"

  while true; do
    run_tracked sleep 86400 || true
  done
}

trap shutdown TERM INT
rm -f "$FAIL_STOP_MARKER"

case "$INTERVAL_SECONDS" in
  ""|*[!0-9]*)
    printf '[%s] wealthpulse-research-loop failed reason=invalid_interval interval=%s\n' "$(date --iso-8601=seconds)" "$INTERVAL_SECONDS"
    fail_stopped "invalid_interval" 1
    ;;
esac

case "$CLOSED_INTERVAL_SECONDS" in
  ""|*[!0-9]*)
    printf '[%s] wealthpulse-research-loop failed reason=invalid_closed_interval interval=%s\n' "$(date --iso-8601=seconds)" "$CLOSED_INTERVAL_SECONDS"
    fail_stopped "invalid_closed_interval" 1
    ;;
esac

if (( INTERVAL_SECONDS < 1 || CLOSED_INTERVAL_SECONDS < 1 )); then
  printf '[%s] wealthpulse-research-loop failed reason=invalid_interval interval=%s closed_interval=%s\n' "$(date --iso-8601=seconds)" "$INTERVAL_SECONDS" "$CLOSED_INTERVAL_SECONDS"
  fail_stopped "invalid_interval" 1
fi

if [[ -n "${WEALTHPULSE_PYTHON_BIN:-}" ]]; then
  PYTHON_BIN="$WEALTHPULSE_PYTHON_BIN"
elif [[ -x "$REPO_DIR/.venv/bin/python" ]]; then
  PYTHON_BIN="$REPO_DIR/.venv/bin/python"
else
  PYTHON_BIN="python"
fi

if [[ ! -x "$RUNNER" ]]; then
  printf '[%s] wealthpulse-research-loop failed reason=runner_not_executable path=%s\n' "$(date --iso-8601=seconds)" "$RUNNER"
  fail_stopped "runner_not_executable" 1
fi

cd "$REPO_DIR"

market_status() {
  "$PYTHON_BIN" - "$MARKET" <<'PY'
import json
import sys
from pathlib import Path

repo = Path.cwd()
sys.path.insert(0, str(repo / "apps/api"))

from config.market_calendar import get_market_local_dt, is_market_open, is_market_trading_day

market = sys.argv[1]
local_dt = get_market_local_dt(market)
payload = {
    "market": market,
    "local_time": local_dt.isoformat(timespec="seconds"),
    "trading_day": is_market_trading_day(market, local_dt),
    "open": is_market_open(market, local_dt),
}
print(json.dumps(payload, ensure_ascii=False))
PY
}

printf '[%s] wealthpulse-research-loop start repo=%s market=%s interval_seconds=%s closed_interval_seconds=%s python_bin=%s\n' \
  "$(date --iso-8601=seconds)" "$REPO_DIR" "$MARKET" "$INTERVAL_SECONDS" "$CLOSED_INTERVAL_SECONDS" "$PYTHON_BIN"

while true; do
  set +e
  status_payload="$(market_status)"
  status_code=$?
  set -e

  if [[ "$status_code" != "0" ]]; then
    printf '[%s] wealthpulse-research-loop failed reason=market_calendar_error exit_code=%s\n' "$(date --iso-8601=seconds)" "$status_code"
    fail_stopped "market_calendar_error" "$status_code"
  fi

  market_open="$("$PYTHON_BIN" - "$status_payload" <<'PY'
import json
import sys
payload = json.loads(sys.argv[1])
print("1" if payload.get("open") else "0")
PY
)"

  if [[ "$market_open" != "1" ]]; then
    printf '[%s] wealthpulse-research-loop idle reason=market_closed status=%s sleep_seconds=%s\n' "$(date --iso-8601=seconds)" "$status_payload" "$CLOSED_INTERVAL_SECONDS"
    run_tracked sleep "$CLOSED_INTERVAL_SECONDS"
    continue
  fi

  printf '[%s] wealthpulse-research-loop iteration_start\n' "$(date --iso-8601=seconds)"

  set +e
  run_tracked "$RUNNER"
  status=$?
  set -e

  printf '[%s] wealthpulse-research-loop iteration_finish exit_code=%s\n' "$(date --iso-8601=seconds)" "$status"
  if [[ "$status" != "0" ]]; then
    printf '[%s] wealthpulse-research-loop failed reason=runner_failed exit_code=%s\n' "$(date --iso-8601=seconds)" "$status"
    fail_stopped "runner_failed" "$status"
  fi

  run_tracked sleep "$INTERVAL_SECONDS"
done
