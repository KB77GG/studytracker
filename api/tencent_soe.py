from __future__ import annotations

import base64
import hashlib
import hmac
import json
import random
import re
import ssl
import time
import uuid
from typing import Any
from urllib.parse import quote, urlparse

import requests
import websocket
from flask import current_app


SOE_WS_HOST = "soe.cloud.tencent.com"
SOE_WS_PATH = "/soe/api"


def _is_enabled() -> bool:
    value = str(current_app.config.get("TENCENT_SOE_ENABLED") or "0").strip().lower()
    return value in {"1", "true", "yes", "on"}


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


def _voice_format_from_url(audio_url: str) -> int:
    path = (urlparse(audio_url).path or "").lower()
    if path.endswith(".pcm"):
        return 0
    if path.endswith(".wav"):
        return 1
    if path.endswith(".speex") or path.endswith(".spx"):
        return 4
    return 2


def _mode_by_length(ref_text: str) -> int:
    words = [x for x in re.split(r"\s+", ref_text.strip()) if x]
    if len(words) <= 1:
        return 0
    if len(words) <= 30:
        return 1
    return 2


def _score_100(value: Any) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    if 0 <= score <= 1:
        score *= 100
    return round(max(0.0, min(100.0, score)), 1)


def _normalize_ref_text(ref_text: str) -> str:
    text = re.sub(r"\s+", " ", (ref_text or "").strip())
    text = re.sub(
        r"^(?:[A-Z][A-Z .'-]{0,24}|Man|Woman|Male|Female|Speaker\s*\d+)\s*:\s*",
        "",
        text,
        flags=re.IGNORECASE,
    ).strip()
    return text or (ref_text or "").strip()


def _build_ws_url(
    app_id: str,
    secret_key: str,
    params: dict[str, Any],
    host: str,
) -> str:
    ordered = sorted((key, str(value)) for key, value in params.items())
    sign_query = "&".join(f"{key}={value}" for key, value in ordered)
    sign_text = f"{host}{SOE_WS_PATH}/{app_id}?{sign_query}"
    signature = base64.b64encode(
        hmac.new(secret_key.encode("utf-8"), sign_text.encode("utf-8"), hashlib.sha1).digest()
    ).decode("utf-8")
    query = "&".join(
        f"{quote(key, safe='')}={quote(value, safe='')}"
        for key, value in ordered
    )
    return (
        f"wss://{host}{SOE_WS_PATH}/{quote(app_id, safe='')}?"
        f"{query}&signature={quote(signature, safe='')}"
    )


def _json_message(message: Any) -> dict[str, Any]:
    if isinstance(message, bytes):
        message = message.decode("utf-8", errors="replace")
    if not isinstance(message, str):
        return {"code": -1, "message": "invalid websocket message"}
    try:
        parsed = json.loads(message)
    except ValueError:
        return {"code": -1, "message": "invalid websocket json", "raw": message[:300]}
    return parsed if isinstance(parsed, dict) else {"code": -1, "message": "invalid websocket payload"}


def _websocket_sslopt(verify: bool) -> dict[str, Any]:
    if not verify:
        return {"cert_reqs": ssl.CERT_NONE}
    try:
        import certifi

        return {"ca_certs": certifi.where()}
    except Exception:
        return {}


def _extract_number(payload: dict[str, Any], raw: str, key: str) -> float:
    value = payload.get(key)
    if value is not None:
        return _score_100(value)
    match = re.search(rf"\b{re.escape(key)}\s*:\s*(-?\d+(?:\.\d+)?)", raw)
    return _score_100(match.group(1)) if match else 0.0


def _parse_words_from_result(raw: str) -> list[dict[str, Any]]:
    words_match = re.search(r"\bWords\s*:\s*\[(.*?)]\s+SentenceId\b", raw, flags=re.S)
    if not words_match:
        return []
    words_text = words_match.group(1)
    words: list[dict[str, Any]] = []
    for part in re.split(r"(?=\bMbtm\s*:)", words_text):
        accuracy = re.search(r"\bPronAccuracy\s*:\s*(-?\d+(?:\.\d+)?)", part)
        if not accuracy:
            continue
        fluency = re.search(r"\bPronFluency\s*:\s*(-?\d+(?:\.\d+)?)", part)
        word = re.search(r"(?:\bReferenceWord\s*:\s*)?\bWord\s*:\s*([^\s\]}]+)", part)
        words.append({
            "Word": word.group(1) if word else "",
            "PronAccuracy": _score_100(accuracy.group(1)),
            "PronFluency": _score_100(fluency.group(1)) if fluency else 0.0,
        })
    return words


def _normalize_word_items(raw_words: list[Any]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for raw in raw_words:
        if not isinstance(raw, dict):
            continue
        reference = raw.get("ReferenceWord")
        label = (
            raw.get("Word")
            or raw.get("word")
            or raw.get("Text")
            or raw.get("text")
            or (reference.get("Word") if isinstance(reference, dict) else None)
            or (reference.get("word") if isinstance(reference, dict) else None)
            or ""
        )
        normalized.append({
            **raw,
            "Word": str(label).strip(),
            "PronAccuracy": _score_100(
                raw.get("PronAccuracy")
                if raw.get("PronAccuracy") is not None
                else raw.get("pronAccuracy")
            ),
            "PronFluency": _score_100(
                raw.get("PronFluency")
                if raw.get("PronFluency") is not None
                else raw.get("pronFluency")
            ),
        })
    return normalized


def _positive_scores(items: list[dict[str, Any]], key: str) -> list[float]:
    scores: list[float] = []
    for item in items:
        try:
            value = float(item.get(key) or 0)
        except (TypeError, ValueError):
            continue
        if value > 0:
            scores.append(value)
    return scores


def _parse_soe_result(result: Any) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    if isinstance(result, dict):
        payload = result
        raw = json.dumps(result, ensure_ascii=False)
    else:
        raw = str(result or "")
        try:
            loaded = json.loads(raw)
            if isinstance(loaded, dict):
                payload = loaded
        except ValueError:
            payload = {}

    words = payload.get("Words") if isinstance(payload.get("Words"), list) else []
    if not words:
        words = _parse_words_from_result(raw)
    else:
        words = _normalize_word_items(words)

    pron_accuracy = _extract_number(payload, raw, "PronAccuracy")
    pron_fluency = _extract_number(payload, raw, "PronFluency")
    pron_completion = _extract_number(payload, raw, "PronCompletion")
    suggested_score = _extract_number(payload, raw, "SuggestedScore")

    if words and pron_accuracy <= 0:
        valid = _positive_scores(words, "PronAccuracy")
        if valid:
            pron_accuracy = round(sum(valid) / len(valid), 1)
    if words and pron_fluency <= 0:
        valid = _positive_scores(words, "PronFluency")
        if valid:
            pron_fluency = round(sum(valid) / len(valid), 1)

    return {
        "pron_accuracy": pron_accuracy,
        "pron_fluency": pron_fluency,
        "pron_completion": pron_completion,
        "suggested_score_100": suggested_score,
        "words": words if isinstance(words, list) else [],
    }


def evaluate_pronunciation(audio_url: str, ref_text: str) -> tuple[bool, dict[str, Any]]:
    if not _is_enabled():
        return False, {"error": "tencent_soe_disabled"}

    config = current_app.config
    secret_id = (config.get("TENCENT_SECRET_ID") or "").strip()
    secret_key = (config.get("TENCENT_SECRET_KEY") or "").strip()
    app_id = str(config.get("TENCENT_SOE_APP_ID") or "").strip()
    if not secret_id or not secret_key:
        return False, {"error": "missing_tencent_soe_secret"}
    if not app_id:
        return False, {"error": "missing_tencent_soe_app_id"}

    timeout = float(config.get("TENCENT_SOE_TIMEOUT") or 20)
    max_bytes = int(config.get("TENCENT_SOE_MAX_AUDIO_BYTES") or 980000)
    score_coeff = float(config.get("TENCENT_SOE_SCORE_COEFF") or 4.0)
    engine_type = (config.get("TENCENT_SOE_ENGINE_MODEL_TYPE") or "16k_en").strip()
    host = (config.get("TENCENT_SOE_WS_HOST") or SOE_WS_HOST).strip()
    ssl_verify = str(config.get("TENCENT_SOE_SSL_VERIFY") or "1").strip().lower() not in {"0", "false", "no", "off"}
    ref_text_clean = _normalize_ref_text(ref_text)
    if not ref_text_clean:
        return False, {"error": "tencent_soe_empty_ref_text"}

    ok, downloaded = _download_audio(audio_url, timeout=timeout, max_bytes=max_bytes)
    if not ok:
        return False, downloaded

    audio_bytes = downloaded["audio_bytes"]
    voice_id = str(uuid.uuid4())
    now = int(time.time())
    params: dict[str, Any] = {
        "eval_mode": _mode_by_length(ref_text_clean),
        "expired": now + 24 * 60 * 60,
        "nonce": random.randint(1, 9999999999),
        "rec_mode": 1,
        "ref_text": ref_text_clean,
        "score_coeff": score_coeff,
        "secretid": secret_id,
        "sentence_info_enabled": 1,
        "server_engine_type": engine_type,
        "text_mode": 0,
        "timestamp": now,
        "voice_format": _voice_format_from_url(audio_url),
        "voice_id": voice_id,
    }
    url = _build_ws_url(
        app_id=app_id,
        secret_key=secret_key,
        params=params,
        host=host,
    )

    ws = None
    last_result: Any = None
    final_message: dict[str, Any] | None = None
    try:
        ws = websocket.create_connection(
            url,
            timeout=timeout,
            sslopt=_websocket_sslopt(ssl_verify),
        )
        handshake = _json_message(ws.recv())
        if int(handshake.get("code") or 0) != 0:
            return False, {
                "error": "tencent_soe_api_error",
                "code": handshake.get("code"),
                "message": handshake.get("message"),
                "voice_id": handshake.get("voice_id") or voice_id,
            }

        ws.send_binary(audio_bytes)
        ws.send(json.dumps({"type": "end"}))

        deadline = time.time() + timeout
        while time.time() < deadline:
            message = _json_message(ws.recv())
            if int(message.get("code") or 0) != 0:
                return False, {
                    "error": "tencent_soe_api_error",
                    "code": message.get("code"),
                    "message": message.get("message"),
                    "voice_id": message.get("voice_id") or voice_id,
                    "message_id": message.get("message_id"),
                }
            if message.get("result") is not None:
                last_result = message.get("result")
            if int(message.get("final") or 0) == 1:
                final_message = message
                break
    except websocket.WebSocketTimeoutException as exc:
        return False, {"error": "tencent_soe_timeout", "details": str(exc)}
    except websocket.WebSocketException as exc:
        return False, {"error": "tencent_soe_request_failed", "details": str(exc)}
    except Exception as exc:
        return False, {"error": "tencent_soe_request_failed", "details": str(exc)}
    finally:
        if ws is not None:
            try:
                ws.close()
            except Exception:
                pass

    if last_result is None:
        return False, {
            "error": "tencent_soe_no_result",
            "voice_id": voice_id,
            "message": "口语评测未返回评分结果",
        }

    parsed = _parse_soe_result(last_result)
    suggested_score = float(parsed.get("suggested_score_100") or 0.0)
    band = round(max(0.0, min(9.0, suggested_score * 9.0 / 100.0)), 1)

    return True, {
        "engine": "tencent_soe_new",
        "request_id": (final_message or {}).get("message_id"),
        "session_id": voice_id,
        "pron_accuracy": parsed.get("pron_accuracy", 0.0),
        "pron_fluency": parsed.get("pron_fluency", 0.0),
        "pron_completion": parsed.get("pron_completion", 0.0),
        "words": parsed.get("words") or [],
        "suggested_score_100": suggested_score,
        "band_9": band,
        "audio_size_bytes": downloaded.get("size_bytes"),
    }
