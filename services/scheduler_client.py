"""Small server-side client for the external scheduler range API."""

from datetime import date

import requests
from flask import current_app


def fetch_range_schedules_by_dates(
    start: date,
    end: date,
    teacher_id=None,
):
    """Fetch schedules for a date range, optionally scoped to one scheduler teacher."""

    base_url = current_app.config.get("SCHEDULER_BASE_URL")
    token = current_app.config.get("SCHEDULER_PUSH_TOKEN")
    if not base_url or not token:
        return None, "scheduler_config_missing"

    params = {"start": start.isoformat(), "end": end.isoformat()}
    if teacher_id is not None:
        params["teacher_id"] = teacher_id

    try:
        response = requests.get(
            f"{base_url}/api/schedules/range",
            headers={"X-Push-Token": token},
            params=params,
            timeout=5,
        )
        if response.status_code != 200:
            current_app.logger.warning(
                "Scheduler range API error: %s %s",
                response.status_code,
                response.text,
            )
            return None, "scheduler_api_error"
        return response.json(), None
    except Exception as exc:  # pragma: no cover - network failure is environment-specific
        current_app.logger.error("Scheduler range API request failed: %s", exc)
        return None, "scheduler_request_failed"


def coerce_schedule_list(payload):
    """Accept the scheduler's current dict/list response shapes."""

    if isinstance(payload, dict):
        return payload.get("schedules") or payload.get("data") or []
    return payload or []
