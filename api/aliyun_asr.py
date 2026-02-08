from __future__ import annotations

import time
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


def _submit_task(api_key: str, model: str, file_url: str) -> tuple[str | None, dict[str, Any]]:
    host = _dashscope_host()
    url = f"https://{host}/api/v1/services/audio/asr/transcription"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-DashScope-Async": "enable",
    }
    payload = {
        "model": model,
        "input": {"file_urls": [file_url]},
        "parameters": {"channel_id": [0]},
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    data = resp.json()
    task_id = (
        data.get("output", {}).get("task_id")
        or data.get("task_id")
        or data.get("output", {}).get("taskId")
    )
    return task_id, data


def _query_task(api_key: str, task_id: str) -> dict[str, Any]:
    host = _dashscope_host()
    url = f"https://{host}/api/v1/tasks/{task_id}"
    headers = {"Authorization": f"Bearer {api_key}"}
    resp = requests.post(url, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _fetch_transcript(transcription_url: str) -> dict[str, Any]:
    resp = requests.get(transcription_url, timeout=30)
    resp.raise_for_status()
    return resp.json()


def _extract_text(payload: dict[str, Any]) -> str:
    transcripts = payload.get("transcripts") or []
    parts: list[str] = []
    for item in transcripts:
        text = item.get("text") or item.get("transcript") or ""
        if text:
            parts.append(text)
    if parts:
        return " ".join(parts).strip()

    sentences = payload.get("sentences") or []
    if sentences:
        sentence_text = " ".join(
            [s.get("text", "") for s in sentences if s.get("text")]
        ).strip()
        if sentence_text:
            return sentence_text

    return payload.get("text", "") or ""


def transcribe_audio_url(file_url: str) -> tuple[bool, dict[str, Any]]:
    config = current_app.config
    api_key = config.get("ALIYUN_API_KEY")
    if not api_key:
        return False, {"error": "missing_aliyun_api_key"}

    model = config.get("ALIYUN_ASR_MODEL", "paraformer-v2")
    max_wait = int(config.get("ALIYUN_ASR_MAX_WAIT", 45))
    poll_interval = float(config.get("ALIYUN_ASR_POLL_INTERVAL", 1.0))

    try:
        task_id, submit_payload = _submit_task(api_key, model, file_url)
    except requests.RequestException as exc:
        return False, {"error": "asr_submit_failed", "details": str(exc)}

    if not task_id:
        return False, {"error": "asr_missing_task_id", "details": submit_payload}

    deadline = time.time() + max_wait
    last_payload: dict[str, Any] | None = None

    while time.time() < deadline:
        try:
            status_payload = _query_task(api_key, task_id)
        except requests.RequestException as exc:
            return False, {"error": "asr_query_failed", "details": str(exc)}

        last_payload = status_payload
        output = status_payload.get("output", {})
        task_status = output.get("task_status") or status_payload.get("task_status")

        if task_status in {"FAILED", "CANCELLED", "CANCELED"}:
            return False, {
                "error": "asr_task_failed",
                "task_status": task_status,
                "details": status_payload,
            }

        if task_status == "SUCCEEDED":
            results = output.get("results") or []
            success_result = None
            for item in results:
                if item.get("subtask_status") == "SUCCEEDED":
                    success_result = item
                    break
            if not success_result and results:
                success_result = results[0]

            transcription_url = (success_result or {}).get("transcription_url")
            if not transcription_url:
                return False, {
                    "error": "asr_missing_transcription_url",
                    "details": status_payload,
                }

            try:
                transcript_payload = _fetch_transcript(transcription_url)
            except requests.RequestException as exc:
                return False, {"error": "asr_fetch_transcript_failed", "details": str(exc)}

            text = _extract_text(transcript_payload)
            return True, {
                "task_id": task_id,
                "model": model,
                "transcript": text,
                "transcript_raw": transcript_payload,
                "transcription_url": transcription_url,
                "usage": status_payload.get("usage"),
            }

        time.sleep(poll_interval)

    return False, {"error": "asr_timeout", "details": last_payload, "task_id": task_id}
