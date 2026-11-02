# Shared helpers for start/stop/status (sourced, not executed).
# Reads IWA_DATA_DIR / IWA_HOST / IWA_PORT / IWA_URL_PREFIX from the environment or the tool's .env.

ENV_FILE="${IWA_ENV_FILE:-$TOOL_DIR/.env}"
read_env() {
  local key="$1" default="$2" value="${!1:-}"
  if [[ -z "$value" && -f "$ENV_FILE" ]]; then
    value="$(grep -E "^(export +)?${key}=" "$ENV_FILE" | tail -n 1 | sed -E "s/^(export +)?${key}=//; s/^[\"']//; s/[\"']$//")"
  fi
  echo "${value:-$default}"
}

DATA_DIR="$(read_env IWA_DATA_DIR "$TOOL_DIR/var")"
HOST="$(read_env IWA_HOST 127.0.0.1)"
PORT="$(read_env IWA_PORT 5055)"
PREFIX="$(read_env IWA_URL_PREFIX "")"
PID_FILE="$DATA_DIR/iwa.pid"
LOG_FILE="$DATA_DIR/iwa.log"
export IWA_HOST="$HOST" IWA_PORT="$PORT" IWA_DATA_DIR="$DATA_DIR"

if [[ -n "${PYTHON:-}" ]]; then
  :
elif [[ -x "$TOOL_DIR/.venv/bin/python" ]]; then
  PYTHON="$TOOL_DIR/.venv/bin/python"
else
  PYTHON="python3"
fi

iwa_url() {
  local host="$HOST"
  [[ "$host" == "0.0.0.0" ]] && host="127.0.0.1"
  local prefix="${PREFIX#/}"
  prefix="${prefix%/}"
  if [[ -n "$prefix" ]]; then
    echo "http://$host:$PORT/$prefix/"
  else
    echo "http://$host:$PORT/"
  fi
}

is_running() {
  [[ -f "$PID_FILE" ]] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null
}
