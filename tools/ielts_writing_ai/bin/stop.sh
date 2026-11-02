#!/usr/bin/env bash
# Stop the standalone trial server started by start.sh.
# Only a verified instance (same PID, same start time, this tool's command line) is signalled.
set -euo pipefail

TOOL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=_common.sh
source "$TOOL_DIR/bin/_common.sh"

check_instance
case "$INSTANCE_STATE" in
  none)
    echo "未在运行"
    exit 0
    ;;
  stale)
    explain_untrusted_pid
    rm -f "$PID_FILE"
    exit 0
    ;;
  mismatch)
    explain_untrusted_pid
    rm -f "$PID_FILE"
    exit 1
    ;;
  legacy)
    explain_untrusted_pid
    exit 1
    ;;
esac

PID="$INSTANCE_PID"
kill -TERM "$PID"
for _ in $(seq 1 40); do
  if ! kill -0 "$PID" 2>/dev/null; then
    rm -f "$PID_FILE"
    echo "已停止（PID $PID）"
    exit 0
  fi
  sleep 0.25
done

# Re-verify before escalating: never SIGKILL a PID that is no longer our instance.
check_instance
if [[ "$INSTANCE_STATE" == "running" && "$INSTANCE_PID" == "$PID" ]]; then
  echo "10 秒内未退出，强制结束 PID $PID"
  kill -KILL "$PID" 2>/dev/null || true
fi
rm -f "$PID_FILE"
