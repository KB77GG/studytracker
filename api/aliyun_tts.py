from __future__ import annotations

from typing import Any

import requests
from flask import current_app


def _dashscope_host() -> str:
    config = current_app.config
    host = (config.get("ALIYUN_ASR_HOST") or "").strip()
    if host:
        return host.replace("https://", "").replace("http://", "").strip("/")
    region = (config.get("ALIYUN_ASR_REGION") or "cn-beijing").lower()
    if region.startswith("cn"):
        return "dashscope.aliyuncs.com"
    return "dashscope-intl.aliyuncs.com"


def synthesize_text(text: str) -> tuple[bool, dict[str, Any]]:
    config = current_app.config
    api_key = config.get("ALIYUN_API_KEY")
    if not api_key:
        return False, {"error": "missing_aliyun_api_key"}

    model = config.get("ALIYUN_TTS_MODEL", "qwen3-tts-flash")
    voice = config.get("ALIYUN_TTS_VOICE", "Cherry")
    language_type = config.get("ALIYUN_TTS_LANGUAGE", "English")

    host = _dashscope_host()
    url = f"https://{host}/api/v1/services/aigc/multimodal-generation/generation"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "input": {
            "text": text,
            "voice": voice,
            "language_type": language_type,
        },
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=20)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        return False, {"error": "tts_submit_failed", "details": str(exc)}

    audio_url = data.get("output", {}).get("audio", {}).get("url")
    if not audio_url:
        return False, {"error": "tts_missing_audio_url", "details": data}

    try:
        audio_resp = requests.get(audio_url, timeout=20)
        audio_resp.raise_for_status()
    except requests.RequestException as exc:
        return False, {"error": "tts_fetch_failed", "details": str(exc)}

    return True, {"audio_bytes": audio_resp.content, "audio_url": audio_url}
