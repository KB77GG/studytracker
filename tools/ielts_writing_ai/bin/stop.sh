#!/usr/bin/env bash
# Stop the standalone trial server started by start.sh (only that PID, never the main app).
set -euo pipefail

TOOL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=_common.sh
source "$TOOL_DIR/bin/_common.sh"

if ! is_running; then
  echo "未在运行"
  rm -f "$PID_FILE"
  exit 0
fi

PID="$(cat "$PID_FILE")"
kill -TERM "$PID"
for _ in $(seq 1 40); do
  if ! kill -0 "$PID" 2>/dev/null; then
    rm -f "$PID_FILE"
    echo "已停止（PID $PID）"
    exit 0
  fi
  sleep 0.25
done
echo "10 秒内未退出，强制结束 PID $PID"
kill -KILL "$PID" 2>/dev/null || true
rm -f "$PID_FILE"
