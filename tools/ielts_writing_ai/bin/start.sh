#!/usr/bin/env bash
# Start the standalone IELTS writing AI trial server in the background.
# Usage: tools/ielts_writing_ai/bin/start.sh            (Flask threaded server, local)
#        IWA_SERVER=gunicorn tools/ielts_writing_ai/bin/start.sh   (test environment)
set -euo pipefail

TOOL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "$TOOL_DIR/../.." && pwd)"
# shellcheck source=_common.sh
source "$TOOL_DIR/bin/_common.sh"

if is_running; then
  echo "已在运行（PID $(cat "$PID_FILE")），地址 $(iwa_url)"
  exit 0
fi

mkdir -p "$DATA_DIR"
cd "$REPO_ROOT"
"$PYTHON" -m tools.ielts_writing_ai check >/dev/null

if [[ "${IWA_SERVER:-flask}" == "gunicorn" ]]; then
  # -c is mandatory: without it gunicorn would read the main app's gunicorn.conf.py (port 5002).
  nohup "$PYTHON" -m gunicorn -c "$TOOL_DIR/gunicorn.conf.py" >>"$LOG_FILE" 2>&1 &
else
  nohup "$PYTHON" -m tools.ielts_writing_ai serve >>"$LOG_FILE" 2>&1 &
fi
echo $! >"$PID_FILE"

for _ in $(seq 1 40); do
  if curl -fsS "$(iwa_url)healthz" >/dev/null 2>&1; then
    echo "已启动（PID $(cat "$PID_FILE")）：$(iwa_url)"
    echo "日志：$LOG_FILE"
    exit 0
  fi
  if ! is_running; then
    echo "启动失败，最近日志：" >&2
    tail -n 20 "$LOG_FILE" >&2 || true
    rm -f "$PID_FILE"
    exit 1
  fi
  sleep 0.25
done
echo "进程已启动但健康检查未通过，请查看日志：$LOG_FILE" >&2
exit 1
