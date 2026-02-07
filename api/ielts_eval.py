from __future__ import annotations

import json
from typing import Any

import requests
from flask import Blueprint, current_app, jsonify, request

from .auth_utils import require_api_user


eval_bp = Blueprint("ielts_eval", __name__, url_prefix="/api/v1/ielts")


def _build_prompt(payload: dict[str, Any]) -> list[dict[str, str]]:
    part = payload.get("part") or "Part1"
    question = payload.get("question") or ""
    transcript = payload.get("transcript") or ""
    audio_metrics = payload.get("audio_metrics") or {}
    target_band = payload.get("target_band") or "7.0"
    part2_topic = payload.get("part2_topic") or payload.get("topic_type") or ""

    system = (
        "You are an IELTS Speaking evaluator. Follow IELTS band descriptors strictly. "
        "Return JSON only, no extra text. Output fields exactly as specified. "
        "Do not invent facts beyond the student's answer. Keep feedback concise and actionable."
    )

    user = {
        "task": "Evaluate IELTS speaking response and provide feedback.",
        "part": part,
        "question": question,
        "transcript": transcript,
        "audio_metrics": audio_metrics,
        "output_schema": {
            "scores": {
                "fluency_coherence": "number",
                "lexical_resource": "number",
                "grammar_range_accuracy": "number",
                "pronunciation": "number",
                "overall": "number"
            },
            "strengths": ["string"],
            "improvements": ["string"],
            "sentence_feedback": [
                {
                    "original": "string",
                    "issue_type": ["grammar|collocation|logic|wording|chinese_style"],
                    "correction": "string",
                    "explain_cn": "string",
                    "severity": "low|mid|high"
                }
            ],
            "chinese_style_correction": [
                {
                    "original": "string",
                    "native_like": "string",
                    "note": "string"
                }
            ],
            "lexical_upgrade": [
                {
                    "from": "string",
                    "to": ["string", "string"],
                    "constraint": "string"
                }
            ],
            "logic_outline": {
                "zh": ["string"],
                "en": ["string"]
            },
            "rewrite_high_band": {
                "target_band": "string",
                "paragraph": "string",
                "logic_tips": ["string"]
            },
            "grading_notes": ["string"]
        },
        "rules": [
            "For Part1: keep the rewrite concise and within 2-4 sentences.",
            "For Part2: include basic info, anecdote, and explanation/feelings; keep clear timeline.",
            "For Part3: include at least two viewpoints with reasons and examples.",
            "logic_outline must be bilingual (Chinese + English) and reflect the student's content.",
            "rewrite_high_band must include one coherent paragraph and logic_tips as bullet points.",
            "logic_tips should use Chinese explanations and include key English connectors (for example: When it comes to, If I remember correctly, At first, Then, Finally, As for the reasons why, First of all, What's more).",
            "Focus on logic and structure in feedback and rewrite."
        ],
        "part2_frameworks": {
            "person_place": [
                "Basic info (opening; who the person is; relationship)",
                "Anecdote (how you know them; at first/then/finally; one-sentence feeling)",
                "Explanation/Feelings (why impressed; first of all/what's more)"
            ],
            "object_concrete": [
                "Basic info (what it is; where it came from; what it looks like)",
                "Anecdote (how/when you got it; first time using it; how it helped)",
                "Explanation (emotional value; why it is important)"
            ],
            "object_abstract": [
                "Basic info (what it is; how you first came across it; why it intrigued you)",
                "Anecdote (learning experience; what you learned; who you shared with)",
                "Explanation (why you are interested; real-life value)"
            ],
            "storyline": [
                "Story start (when/where/who)",
                "Story development (details/obstacle)",
                "Story climax (key turning point)",
                "Ending/feelings (result and reflection)"
            ]
        },
        "part2_topic_hint": part2_topic,
        "target_band": target_band
    }

    return [
        {"role": "system", "content": system},
        {"role": "user", "content": json.dumps(user, ensure_ascii=False)},
    ]


def _extract_json(text: str) -> tuple[bool, Any]:
    text = text.strip()
    if not text:
        return False, {"error": "empty_response"}

    try:
        return True, json.loads(text)
    except json.JSONDecodeError:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return False, {"raw_text": text}

    try:
        return True, json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return False, {"raw_text": text}


def run_ielts_eval(data: dict[str, Any]) -> tuple[dict[str, Any], int]:
    transcript = data.get("transcript") or data.get("student_answer")
    if not transcript:
        return {"ok": False, "error": "missing_transcript"}, 400

    config = current_app.config
    api_key = config.get("DEEPSEEK_API_KEY")
    if not api_key:
        return {"ok": False, "error": "missing_deepseek_key"}, 500

    base_url = (config.get("DEEPSEEK_API_BASE") or "https://api.deepseek.com").rstrip("/")
    chat_url = config.get("DEEPSEEK_CHAT_URL") or f"{base_url}/v1/chat/completions"
    model = config.get("DEEPSEEK_MODEL") or "deepseek-chat"
    timeout = float(config.get("DEEPSEEK_TIMEOUT") or 30)

    messages = _build_prompt(data)
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 1400,
    }

    try:
        resp = requests.post(
            chat_url,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=timeout,
        )
    except requests.RequestException as exc:
        return {"ok": False, "error": "deepseek_request_failed", "details": str(exc)}, 502

    if resp.status_code >= 400:
        return {
            "ok": False,
            "error": "deepseek_http_error",
            "status": resp.status_code,
            "details": resp.text,
        }, 502

    raw = resp.json()
    content = (
        raw.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
    )
    ok, parsed = _extract_json(content)
    return {
        "ok": ok,
        "result": parsed,
        "raw": content if not ok else None,
        "usage": raw.get("usage"),
        "model": raw.get("model", model),
    }, 200


@eval_bp.post("/evaluate")
@require_api_user()
def evaluate_ielts():
    data = request.get_json(silent=True) or {}
    payload, status = run_ielts_eval(data)
    return jsonify(payload), status
