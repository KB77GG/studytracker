from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import uuid
from typing import Any
from urllib.parse import urlparse

import requests
from flask import current_app


def _is_enabled() -> bool:
    value = str(current_app.config.get("TENCENT_SOE_ENABLED") or "0").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _hmac_sha256(key: bytes, msg: str) -> bytes:
    return hmac.new(key, msg.encode("utf-8"), hashlib.sha256).digest()


def _tc3_sign(
    secret_id: str,
    secret_key: str,
    service: str,
    host: str,
    action: str,
    version: str,
    region: str,
    payload: dict[str, Any],
) -> tuple[dict[str, str], str]:
    timestamp = int(time.time())
    date = time.strftime("%Y-%m-%d", time.gmtime(timestamp))
    algorithm = "TC3-HMAC-SHA256"
    http_request_method = "POST"
    canonical_uri = "/"
    canonical_querystring = ""
    ct = "application/json; charset=utf-8"

    canonical_headers = f"content-type:{ct}\nhost:{host}\n"
    signed_headers = "content-type;host"
    payload_str = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    hashed_payload = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()
    canonical_request = "\n".join(
        [
            http_request_method,
            canonical_uri,
            canonical_querystring,
            canonical_headers,
            signed_headers,
            hashed_payload,
        ]
    )

    credential_scope = f"{date}/{service}/tc3_request"
    string_to_sign = "\n".join(
        [
            algorithm,
            str(timestamp),
            credential_scope,
            hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
        ]
    )

    secret_date = _hmac_sha256(("TC3" + secret_key).encode("utf-8"), date)
    secret_service = _hmac_sha256(secret_date, service)
    secret_signing = _hmac_sha256(secret_service, "tc3_request")
    signature = hmac.new(secret_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()

    authorization = (
        f"{algorithm} Credential={secret_id}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )

    headers = {
        "Authorization": authorization,
        "Content-Type": ct,
        "Host": host,
        "X-TC-Action": action,
        "X-TC-Timestamp": str(timestamp),
        "X-TC-Version": version,
    }
    if region:
        headers["X-TC-Region"] = region
    return headers, payload_str


def _voice_file_type_from_url(audio_url: str) -> int:
    path = (urlparse(audio_url).path or "").lower()
    if path.endswith(".pcm"):
        return 1
    if path.endswith(".wav"):
        return 2
    if path.endswith(".mp3"):
        return 3
    if path.endswith(".speex") or path.endswith(".spx"):
        return 4
    return 3


def _download_audio(audio_url: str, timeout: float, max_bytes: int) -> tuple[bool, dict[str, Any]]:
    try:
        resp = requests.get(audio_url, timeout=timeout)
        resp.raise_for_status()
    except requests.RequestException as exc:
        return False, {"error": "tencent_audio_download_failed", "details": str(exc)}

    audio_bytes = resp.content or b""
    if not audio_bytes:
        return False, {"error": "tencent_audio_empty"}
    if len(audio_bytes) > max_bytes:
        return False, {
            "error": "tencent_audio_too_large",
            "size_bytes": len(audio_bytes),
            "max_bytes": max_bytes,
        }

    return True, {"audio_bytes": audio_bytes, "size_bytes": len(audio_bytes)}


def _mode_by_length(ref_text: str) -> int:
    words = [x for x in ref_text.strip().split() if x]
    if len(words) <= 16:
        return 1  # word/sentence
    return 2  # paragraph


def evaluate_pronunciation(audio_url: str, ref_text: str) -> tuple[bool, dict[str, Any]]:
    if not _is_enabled():
        return False, {"error": "tencent_soe_disabled"}

    config = current_app.config
    secret_id = (config.get("TENCENT_SECRET_ID") or "").strip()
    secret_key = (config.get("TENCENT_SECRET_KEY") or "").strip()
    if not secret_id or not secret_key:
        return False, {"error": "missing_tencent_soe_secret"}

    host = (config.get("TENCENT_SOE_ENDPOINT") or "soe.tencentcloudapi.com").strip()
    version = (config.get("TENCENT_SOE_VERSION") or "2018-07-24").strip()
    region = (config.get("TENCENT_SOE_REGION") or "").strip()
    app_id = str(config.get("TENCENT_SOE_APP_ID") or "").strip()
    timeout = float(config.get("TENCENT_SOE_TIMEOUT") or 20)
    max_bytes = int(config.get("TENCENT_SOE_MAX_AUDIO_BYTES") or 980000)
    score_coeff = float(config.get("TENCENT_SOE_SCORE_COEFF") or 4.0)

    ok, downloaded = _download_audio(audio_url, timeout=timeout, max_bytes=max_bytes)
    if not ok:
        return False, downloaded

    audio_bytes = downloaded["audio_bytes"]
    base64_audio = base64.b64encode(audio_bytes).decode("utf-8")

    payload: dict[str, Any] = {
        "SeqId": 1,
        "IsEnd": 1,
        "VoiceFileType": _voice_file_type_from_url(audio_url),
        "UserVoiceData": base64_audio,
        "SessionId": uuid.uuid4().hex,
        "RefText": (ref_text or "").strip(),
        "EvalMode": _mode_by_length(ref_text),
        "ScoreCoeff": score_coeff,
        "ServerType": 0,  # English
        "WorkMode": 1,  # one-shot
    }
    if app_id:
        try:
            payload["SoeAppId"] = int(app_id)
        except ValueError:
            payload["SoeAppId"] = app_id

    headers, payload_str = _tc3_sign(
        secret_id=secret_id,
        secret_key=secret_key,
        service="soe",
        host=host,
        action="TransmitOralProcessWithInit",
        version=version,
        region=region,
        payload=payload,
    )

    try:
        resp = requests.post(
            f"https://{host}",
            headers=headers,
            data=payload_str.encode("utf-8"),
            timeout=timeout,
        )
    except requests.RequestException as exc:
        return False, {"error": "tencent_soe_request_failed", "details": str(exc)}

    if resp.status_code >= 400:
        return False, {
            "error": "tencent_soe_http_error",
            "status": resp.status_code,
            "details": resp.text[:600],
        }

    try:
        raw = resp.json()
    except ValueError:
        return False, {"error": "tencent_soe_invalid_json", "details": resp.text[:600]}

    response = raw.get("Response") if isinstance(raw, dict) else None
    if not isinstance(response, dict):
        return False, {"error": "tencent_soe_bad_response", "details": raw}

    if isinstance(response.get("Error"), dict):
        err = response["Error"]
        return False, {
            "error": "tencent_soe_api_error",
            "code": err.get("Code"),
            "message": err.get("Message"),
            "request_id": response.get("RequestId"),
        }

    suggested_score = float(response.get("SuggestedScore") or 0.0)
    band = round(max(0.0, min(9.0, suggested_score * 9.0 / 100.0)), 1)

    return True, {
        "engine": "tencent_soe",
        "request_id": response.get("RequestId"),
        "session_id": response.get("SessionId"),
        "pron_accuracy": response.get("PronAccuracy"),
        "pron_fluency": response.get("PronFluency"),
        "pron_completion": response.get("PronCompletion"),
        "words": response.get("Words"),
        "suggested_score_100": suggested_score,
        "band_9": band,
        "audio_size_bytes": downloaded.get("size_bytes"),
    }
