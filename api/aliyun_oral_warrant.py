from __future__ import annotations

import hashlib
import time
from typing import Any

import requests
from flask import current_app


def _md5_hex(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def _build_request_sign(payload: dict[str, Any], app_secret: str) -> str:
    # Official signing rule signs only app_secret + required request fields.
    signing_payload = {
        "appid": payload.get("appid"),
        "timestamp": payload.get("timestamp"),
        "user_id": payload.get("user_id"),
        "user_client_ip": payload.get("user_client_ip"),
        "app_secret": app_secret,
    }
    pairs: list[str] = []
    for key in sorted(signing_payload.keys()):
        value = signing_payload.get(key)
        if value is None:
            continue
        pairs.append(f"{key}={value}")
    signing_source = "&".join(pairs)
    return _md5_hex(signing_source)


def _auth_endpoints() -> list[str]:
    raw = str(current_app.config.get("ALIYUN_ORAL_AUTH_ENDPOINTS") or "")
    return [x.strip() for x in raw.split(",") if x.strip()]


def create_oral_warrant(user_id: str, user_client_ip: str) -> tuple[bool, dict[str, Any]]:
    config = current_app.config
    app_id = (config.get("ALIYUN_ORAL_APP_KEY") or "").strip()
    app_secret = (config.get("ALIYUN_ORAL_APP_SECRET") or "").strip()
    if not app_id or not app_secret:
        return False, {"error": "missing_aliyun_oral_app_credentials"}

    timestamp = str(int(time.time()))
    warrant_available = int(config.get("ALIYUN_ORAL_WARRANT_AVAILABLE") or 7200)
    timeout = float(config.get("ALIYUN_ORAL_AUTH_TIMEOUT") or 10)
    endpoints = _auth_endpoints()
    if not endpoints:
        return False, {"error": "missing_aliyun_oral_auth_endpoint"}

    payload = {
        "appid": app_id,
        "timestamp": timestamp,
        "user_id": user_id,
        "user_client_ip": user_client_ip,
        "warrant_available": warrant_available,
    }
    payload["request_sign"] = _build_request_sign(payload, app_secret)

    last_error: dict[str, Any] | None = None
    for endpoint in endpoints:
        try:
            resp = requests.post(endpoint, data=payload, timeout=timeout)
            resp.raise_for_status()
            raw = resp.json()
        except requests.RequestException as exc:
            last_error = {"error": "aliyun_oral_warrant_request_failed", "endpoint": endpoint, "details": str(exc)}
            continue
        except ValueError:
            last_error = {"error": "aliyun_oral_warrant_invalid_json", "endpoint": endpoint, "details": resp.text[:500]}
            continue

        if raw.get("code") == 0:
            data = raw.get("data") if isinstance(raw.get("data"), dict) else {}
            return True, {
                "warrant_id": data.get("warrant_id"),
                "warrant_available": data.get("warrant_available"),
                "expire_at": data.get("expire_at"),
                "endpoint": endpoint,
                "raw": raw,
            }
        last_error = {"error": "aliyun_oral_warrant_api_error", "endpoint": endpoint, "details": raw}

    return False, last_error or {"error": "aliyun_oral_warrant_unknown_error"}
