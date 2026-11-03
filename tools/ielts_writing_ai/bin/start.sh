#!/usr/bin/env bash
# Start the standalone IELTS writing AI trial server in the background.
# Usage: tools/ielts_writing_ai/bin/start.sh            (Flask threaded server, local)
#        IWA_SERVER=gunicorn tools/ielts_writing_ai/bin/start.sh   (test environment)
set -euo pipefail

TOOL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REPO_ROOT="$(cd "${TOOL_DIR}/../.." && pwd)"
# shellcheck source=_common.sh
source "${TOOL_DIR}/bin/_common.sh"

run_under_ctl_lock "$@"
check_instance
case "${INSTANCE_STATE}" in
  running)
    echo "已在运行（PID ${INSTANCE_PID}），地址 $(iwa_url)"
    exit 0
    ;;
  stale | mismatch)
    explain_untrusted_pid
    rm -f "${PID_FILE}"
    ;;
  legacy)
    explain_untrusted_pid
    exit 1
    ;;
esac

mkdir -p "${DATA_DIR}"
cd "${REPO_ROOT}"
# The log is always UTF-8, whatever the caller's terminal locale is.
export PYTHONIOENCODING=utf-8
"${PYTHON}" -m tools.ielts_writing_ai check >/dev/null

# The server must not hold the start/stop lock: fd 9 is closed for it (9>&-) and the
# lock variables are removed from its environment.
MODE="${IWA_SERVER:-flask}"
if [[ "${MODE}" == "gunicorn" ]]; then
  # -c is mandatory: without it gunicorn would read the main app's gunicorn.conf.py (port 5002).
  nohup env -u IWA_CTL_LOCK_HELD -u IWA_CTL_LOCK_PID -u IWA_CTL_LOCK_FD \
    "${PYTHON}" -m gunicorn -c "${TOOL_DIR}/gunicorn.conf.py" >>"${LOG_FILE}" 2>&1 9>&- &
else
  MODE="flask"
  nohup env -u IWA_CTL_LOCK_HELD -u IWA_CTL_LOCK_PID -u IWA_CTL_LOCK_FD \
    "${PYTHON}" -m tools.ielts_writing_ai serve >>"${LOG_FILE}" 2>&1 9>&- &
fi
NEW_PID=$!
write_pid_file "${NEW_PID}" "${MODE}"

for _ in $(seq 1 60); do
  # The health answer must come from the process we just started (or its gunicorn
  # worker): another server already on this port must not count as success.
  HEALTH="$(curl -fsS "$(iwa_url)healthz" 2>/dev/null || true)"
  if [[ "${HEALTH}" == *"\"pid\":${NEW_PID},"* || "${HEALTH}" == *"\"ppid\":${NEW_PID},"* ]]; then
    echo "已启动（PID ${NEW_PID}）：$(iwa_url)"
    echo "日志：${LOG_FILE}"
    exit 0
  fi
  if ! kill -0 "${NEW_PID}" 2>/dev/null; then
    echo "启动失败，最近日志：" >&2
    tail -n 20 "${LOG_FILE}" >&2 || true
    remove_pid_file_if_owned "${NEW_PID}"
    exit 1
  fi
  sleep 0.25
done
echo "进程已启动但 15 秒内健康检查未通过（端口 ${PORT} 可能被其他程序占用），请查看日志：${LOG_FILE}" >&2
exit 1
