#!/usr/bin/env bash
# Show whether the standalone trial server is running and healthy.
set -euo pipefail

TOOL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=_common.sh
source "$TOOL_DIR/bin/_common.sh"

if is_running; then
  echo "运行中（PID $(cat "$PID_FILE")）：$(iwa_url)"
  curl -fsS "$(iwa_url)healthz" && echo || echo "健康检查失败，请查看 $LOG_FILE"
else
  echo "未在运行"
  exit 1
fi
