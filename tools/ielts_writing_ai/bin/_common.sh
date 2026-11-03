# Shared helpers for start/stop/status (sourced, not executed).
# Reads IWA_DATA_DIR / IWA_HOST / IWA_PORT / IWA_URL_PREFIX from the environment or the tool's .env.

ENV_FILE="${IWA_ENV_FILE:-${TOOL_DIR}/.env}"
read_env() {
  local key="$1" default="$2" value="${!1:-}"
  if [[ -z "${value}" && -f "${ENV_FILE}" ]]; then
    value="$(grep -E "^(export +)?${key}=" "${ENV_FILE}" | tail -n 1 | sed -E "s/^(export +)?${key}=//; s/^[\"']//; s/[\"']$//")"
  fi
  echo "${value:-${default}}"
}

DATA_DIR="$(read_env IWA_DATA_DIR "${TOOL_DIR}/var")"
HOST="$(read_env IWA_HOST 127.0.0.1)"
PORT="$(read_env IWA_PORT 5055)"
PREFIX="$(read_env IWA_URL_PREFIX "")"
PID_FILE="${DATA_DIR}/iwa.pid"
LOG_FILE="${DATA_DIR}/iwa.log"
export IWA_HOST="${HOST}" IWA_PORT="${PORT}" IWA_DATA_DIR="${DATA_DIR}"

if [[ -n "${PYTHON:-}" ]]; then
  :
elif [[ -x "${TOOL_DIR}/.venv/bin/python" ]]; then
  PYTHON="${TOOL_DIR}/.venv/bin/python"
else
  PYTHON="python3"
fi

iwa_url() {
  local host="${HOST}"
  [[ "${host}" == "0.0.0.0" ]] && host="127.0.0.1"
  local prefix="${PREFIX#/}"
  prefix="${prefix%/}"
  if [[ -n "${prefix}" ]]; then
    echo "http://${host}:${PORT}/${prefix}/"
  else
    echo "http://${host}:${PORT}/"
  fi
}

# ---------------------------------------------------------------------------
# Instance identity (bash 3.2 compatible: macOS default shell).
#
# The PID file records pid + the process start time (ps lstart) + launch mode.
# A PID is only trusted if the process is alive, its start time matches the
# record, and its command line belongs to this tool. A reused PID fails the
# start-time check, so stop.sh never signals an unrelated process.
# ---------------------------------------------------------------------------
INSTANCE_MARKER="ielts_writing_ai"

proc_start_time() {
  LC_ALL=C ps -o lstart= -p "$1" 2>/dev/null | sed -e 's/^ *//' -e 's/ *$//'
}

proc_command() {
  ps -o command= -p "$1" 2>/dev/null
}

pid_field() {
  # pid_field <key>: read one key=value line from the PID file.
  [[ -f "${PID_FILE}" ]] || return 0
  sed -n "s/^$1=//p" "${PID_FILE}" | head -n 1
}

write_pid_file() {
  # write_pid_file <pid> <mode>
  local started tmp
  started="$(proc_start_time "$1")"
  tmp="${PID_FILE}.tmp.$$"
  printf 'pid=%s\nstarted=%s\nmode=%s\ndata_dir=%s\n' "$1" "${started}" "$2" "${DATA_DIR}" >"${tmp}"
  mv -f "${tmp}" "${PID_FILE}"
}

# Sets INSTANCE_STATE to one of:
#   none      no PID file
#   running   verified instance of this tool (INSTANCE_PID is set)
#   stale     recorded process no longer exists
#   mismatch  PID is alive but start time or command does not match (PID reused)
#   legacy    old PID file without start time; cannot be verified
check_instance() {
  INSTANCE_STATE="none"
  INSTANCE_PID=""
  [[ -f "${PID_FILE}" ]] || return 0
  local pid started actual cmd
  pid="$(pid_field pid)"
  started="$(pid_field started)"
  if [[ -z "${pid}" ]]; then
    pid="$(tr -cd '0-9' <"${PID_FILE}")"
    if [[ -n "${pid}" ]] && kill -0 "${pid}" 2>/dev/null; then
      INSTANCE_STATE="legacy"
      INSTANCE_PID="${pid}"
    else
      INSTANCE_STATE="stale"
    fi
    return 0
  fi
  if ! [[ "${pid}" =~ ^[0-9]+$ ]] || ! kill -0 "${pid}" 2>/dev/null; then
    INSTANCE_STATE="stale"
    return 0
  fi
  INSTANCE_PID="${pid}"
  actual="$(proc_start_time "${pid}")"
  cmd="$(proc_command "${pid}")"
  if [[ -n "${started}" && "${actual}" == "${started}" && "${cmd}" == *"${INSTANCE_MARKER}"* ]]; then
    INSTANCE_STATE="running"
  else
    INSTANCE_STATE="mismatch"
  fi
}

is_running() {
  check_instance
  [[ "${INSTANCE_STATE}" == "running" ]]
}

explain_untrusted_pid() {
  case "${INSTANCE_STATE}" in
    stale) echo "PID 文件记录的进程已不存在，已清理过期 PID 文件。" ;;
    mismatch)
      echo "PID ${INSTANCE_PID} 仍在运行，但启动时间或命令与记录不符（PID 已被其他程序复用），"
      echo "不会向它发送任何信号；已清理过期 PID 文件。"
      ;;
    legacy)
      echo "PID 文件是旧格式（没有启动时间），无法核验 PID ${INSTANCE_PID} 是否属于试用工具，不会自动停止它。"
      echo "请先确认：ps -o pid,lstart,command -p ${INSTANCE_PID}"
      echo "确认是试用工具后手动执行 kill ${INSTANCE_PID}，再删除 ${PID_FILE}。"
      ;;
  esac
}

# ---------------------------------------------------------------------------
# Script-level mutual exclusion for start/stop.
#
# The whole start or stop run happens under an exclusive kernel flock held by
# ctl_lock.py (Python standard library only). Taking it is one atomic system call
# and the kernel releases it when the holder exits - even on SIGKILL - so two
# scripts can never both hold it and there is no stale lock to take over.
# ---------------------------------------------------------------------------
CTL_LOCK_FILE="${DATA_DIR}/iwa.ctl.flock"
CTL_LOCK_TIMEOUT="$(read_env IWA_CTL_LOCK_TIMEOUT 60)"

# Call as: run_under_ctl_lock "$@"  - re-executes the calling script under the lock
# (no-op when already running under it).
run_under_ctl_lock() {
  if [[ "${IWA_CTL_LOCK_HELD:-}" == "${CTL_LOCK_FILE}" ]]; then
    if [[ -d "${DATA_DIR}/iwa.ctl.lock" ]]; then
      rm -rf "${DATA_DIR}/iwa.ctl.lock"  # directory lock left by the previous version
    fi
    return 0
  fi
  mkdir -p "${DATA_DIR}"
  exec "${PYTHON}" -I "${TOOL_DIR}/ctl_lock.py" "${CTL_LOCK_FILE}" "${CTL_LOCK_TIMEOUT}" \
    -- "${BASH}" "${0}" "$@"
}

# Remove the PID file only if it still records the given PID.
remove_pid_file_if_owned() {
  if [[ "$(pid_field pid)" == "$1" ]]; then
    rm -f "${PID_FILE}"
  fi
}
