from __future__ import annotations

import time
from typing import Any

import requests
from flask import current_app


def _submit_task(
    appid: str,
    user_id: str,
    warrant_id: str,
    record_id_list: list[str],
) -> tuple[bool, dict[str, Any]]:
    url = str(current_app.config.get("ALIYUN_ORAL_TASK_SUBMIT_URL") or "").strip()
    if not url:
        return False, {"error": "missing_aliyun_oral_submit_url"}
    timeout = float(current_app.config.get("ALIYUN_ORAL_TASK_TIMEOUT") or 12)
    payload = {
        "appid": appid,
        "userid": user_id,
        "warrantid": warrant_id,
        "recordidlist": record_id_list,
    }
    try:
        resp = requests.post(url, json=payload, timeout=timeout)
        resp.raise_for_status()
        raw = resp.json()
    except requests.RequestException as exc:
        return False, {"error": "aliyun_oral_submit_failed", "details": str(exc)}
    except ValueError:
        return False, {"error": "aliyun_oral_submit_invalid_json", "details": resp.text[:500]}
    return True, raw


def _query_task(
    appid: str,
    user_id: str,
    warrant_id: str,
    taskid: str,
) -> tuple[bool, dict[str, Any]]:
    url = str(current_app.config.get("ALIYUN_ORAL_TASK_QUERY_URL") or "").strip()
    if not url:
        return False, {"error": "missing_aliyun_oral_query_url"}
    timeout = float(current_app.config.get("ALIYUN_ORAL_TASK_TIMEOUT") or 12)
    payload = {
        "appid": appid,
        "userid": user_id,
        "warrantid": warrant_id,
        "taskid": taskid,
    }
    try:
        resp = requests.post(url, json=payload, timeout=timeout)
        resp.raise_for_status()
        raw = resp.json()
    except requests.RequestException as exc:
        return False, {"error": "aliyun_oral_query_failed", "details": str(exc)}
    except ValueError:
        return False, {"error": "aliyun_oral_query_invalid_json", "details": resp.text[:500]}
    return True, raw


def _extract_task_id(payload: dict[str, Any]) -> str:
    data = payload.get("data")
    if isinstance(data, dict):
        return str(data.get("taskid") or data.get("task_id") or "").strip()
    return ""


def _extract_status(payload: dict[str, Any]) -> str:
    data = payload.get("data")
    if isinstance(data, dict):
        status = data.get("status") or data.get("taskStatus") or data.get("task_status")
        return str(status or "").strip().upper()
    return ""


def _extract_result(payload: dict[str, Any]) -> dict[str, Any] | None:
    data = payload.get("data")
    if not isinstance(data, dict):
        return None
    for key in ("result", "taskResult", "task_result"):
        value = data.get(key)
        if isinstance(value, dict):
            return value
    return data


def _payload_ok(payload: dict[str, Any]) -> bool:
    code = payload.get("code")
    return code in {0, "0", 200, "200"}


def run_oral_task(
    appid: str,
    user_id: str,
    warrant_id: str,
    record_id_list: list[str],
) -> tuple[bool, dict[str, Any]]:
    ok, submit_payload = _submit_task(
        appid=appid,
        user_id=user_id,
        warrant_id=warrant_id,
        record_id_list=record_id_list,
    )
    if not ok:
        return False, submit_payload
    if not _payload_ok(submit_payload):
        return False, {"error": "aliyun_oral_submit_api_error", "details": submit_payload}

    taskid = _extract_task_id(submit_payload)
    if not taskid:
        return False, {"error": "aliyun_oral_missing_task_id", "details": submit_payload}

    max_wait = int(current_app.config.get("ALIYUN_ORAL_TASK_MAX_WAIT") or 20)
    interval = float(current_app.config.get("ALIYUN_ORAL_TASK_POLL_INTERVAL") or 1.0)
    deadline = time.time() + max_wait
    last_payload: dict[str, Any] | None = None

    while time.time() < deadline:
        ok, query_payload = _query_task(
            appid=appid,
            user_id=user_id,
            warrant_id=warrant_id,
            taskid=taskid,
        )
        if not ok:
            return False, query_payload
        last_payload = query_payload
        if not _payload_ok(query_payload):
            return False, {"error": "aliyun_oral_query_api_error", "details": query_payload}

        status = _extract_status(query_payload)
        if status in {"FAILED", "FAIL", "ERROR"}:
            return False, {"error": "aliyun_oral_task_failed", "details": query_payload}
        if status in {"SUCCESS", "SUCCEEDED", "DONE", "FINISHED"}:
            result = _extract_result(query_payload)
            return True, {
                "taskid": taskid,
                "status": status,
                "result": result if isinstance(result, dict) else {},
                "raw": query_payload,
            }
        time.sleep(interval)

    return False, {"error": "aliyun_oral_task_timeout", "taskid": taskid, "details": last_payload}
