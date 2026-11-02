#!/usr/bin/env bash
# Show whether the standalone trial server is running (verified instance) and healthy.
set -euo pipefail

TOOL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=_common.sh
source "$TOOL_DIR/bin/_common.sh"

check_instance
if [[ "$INSTANCE_STATE" == "running" ]]; then
  echo "运行中（PID $INSTANCE_PID，启动于 $(pid_field started)）：$(iwa_url)"
  curl -fsS "$(iwa_url)healthz" && echo || echo "健康检查失败，请查看 $LOG_FILE"
  exit 0
fi
if [[ "$INSTANCE_STATE" == "none" ]]; then
  echo "未在运行"
else
  echo "未在运行（PID 文件不可信）"
  explain_untrusted_pid | grep -v "已清理" || true
fi
exit 1
