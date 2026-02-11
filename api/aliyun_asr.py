from __future__ import annotations

import re
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


def _safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _collect_sentence_segments(payload: dict[str, Any]) -> list[tuple[float, float]]:
    segments: list[tuple[float, float]] = []
    sentences = payload.get("sentences") or []
    raw_pairs: list[tuple[float, float]] = []
    for sentence in sentences:
        if not isinstance(sentence, dict):
            continue
        start = (
            _safe_float(sentence.get("begin_time"))
            or _safe_float(sentence.get("beginTime"))
            or _safe_float(sentence.get("start_time"))
            or _safe_float(sentence.get("startTime"))
            or _safe_float(sentence.get("start"))
        )
        end = (
            _safe_float(sentence.get("end_time"))
            or _safe_float(sentence.get("endTime"))
            or _safe_float(sentence.get("stop_time"))
            or _safe_float(sentence.get("stopTime"))
            or _safe_float(sentence.get("end"))
        )
        if start is None or end is None:
            continue
        if end < start:
            start, end = end, start
        raw_pairs.append((start, end))

    if not raw_pairs:
        return segments

    max_value = max(max(start, end) for start, end in raw_pairs)
    # DashScope payloads usually use ms. If all values are very small, treat as seconds.
    scale = 1000.0 if max_value <= 600 else 1.0
    for start, end in raw_pairs:
        segments.append((start * scale, end * scale))
    segments.sort(key=lambda x: x[0])
    return segments


def _collect_confidence_scores(payload: Any, depth: int = 0) -> list[float]:
    if depth > 6:
        return []

    scores: list[float] = []
    if isinstance(payload, dict):
        for key in ("confidence", "confidence_score", "prob", "probability", "score"):
            value = _safe_float(payload.get(key))
            if value is None:
                continue
            if 0 <= value <= 1:
                scores.append(value)
            elif 1 < value <= 100:
                scores.append(value / 100.0)

        for key in ("words", "tokens", "sentences", "phrases", "transcripts"):
            nested = payload.get(key)
            if nested is not None:
                scores.extend(_collect_confidence_scores(nested, depth + 1))
    elif isinstance(payload, list):
        for item in payload[:500]:
            scores.extend(_collect_confidence_scores(item, depth + 1))

    return scores


def _estimate_audio_metrics(transcript_payload: dict[str, Any], transcript_text: str) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    segments = _collect_sentence_segments(transcript_payload)

    duration_ms = (
        _safe_float(transcript_payload.get("duration"))
        or _safe_float(transcript_payload.get("duration_ms"))
        or _safe_float(transcript_payload.get("audio_duration"))
    )
    if duration_ms is not None and duration_ms < 600:
        duration_ms *= 1000.0
    if duration_ms is None and segments:
        duration_ms = max(0.0, segments[-1][1] - segments[0][0])

    if duration_ms is not None:
        metrics["duration_ms"] = round(duration_ms)
        metrics["duration_sec"] = round(duration_ms / 1000.0, 2)

    words = re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?|\d+", transcript_text or "")
    word_count = len(words)
    if word_count == 0 and transcript_text:
        compact = (transcript_text or "").strip().replace(" ", "")
        if compact:
            word_count = len(compact)
    metrics["word_count"] = word_count

    if duration_ms and duration_ms > 0 and word_count > 0:
        wpm = word_count / (duration_ms / 60000.0)
        metrics["speech_rate_wpm"] = round(wpm, 1)

    if len(segments) >= 2:
        pauses: list[float] = []
        for i in range(1, len(segments)):
            gap = segments[i][0] - segments[i - 1][1]
            if gap > 200:
                pauses.append(gap)
        if pauses:
            metrics["pause_count"] = len(pauses)
            metrics["long_pause_count"] = sum(1 for x in pauses if x >= 1200)
            metrics["avg_pause_ms"] = round(sum(pauses) / len(pauses))
            metrics["max_pause_ms"] = round(max(pauses))
            if duration_ms and duration_ms > 0:
                silence_ratio = min(1.0, sum(pauses) / duration_ms)
                metrics["silence_ratio"] = round(silence_ratio, 3)

    confidence_scores = _collect_confidence_scores(transcript_payload)
    if confidence_scores:
        avg_conf = sum(confidence_scores) / len(confidence_scores)
        metrics["asr_confidence"] = round(avg_conf, 3)
        metrics["asr_confidence_samples"] = len(confidence_scores)

    return metrics


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
            audio_metrics = _estimate_audio_metrics(transcript_payload, text)
            return True, {
                "task_id": task_id,
                "model": model,
                "transcript": text,
                "transcript_raw": transcript_payload,
                "transcription_url": transcription_url,
                "audio_metrics": audio_metrics,
                "usage": status_payload.get("usage"),
            }

        time.sleep(poll_interval)

    return False, {"error": "asr_timeout", "details": last_payload, "task_id": task_id}
