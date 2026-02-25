from __future__ import annotations

import json
import time
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
        "You are an IELTS Speaking evaluator and coach. "
        "Follow official IELTS Speaking descriptors strictly. "
        "Return JSON only with valid syntax. Do not include markdown. "
        "Do not invent facts beyond the student's transcript and provided audio metrics."
    )

    conversation_history = payload.get("conversation_history") or []

    user = {
        "task": "Evaluate IELTS speaking response and provide official-criteria feedback + optimized rewrite. Also respond conversationally as an examiner.",
        "part": part,
        "question": question,
        "transcript": transcript,
        "audio_metrics": audio_metrics,
        "conversation_history": conversation_history,
        "output_schema": {
            "scores": {
                "fluency_coherence": "number",
                "lexical_resource": "number",
                "grammar_range_accuracy": "number",
                "pronunciation": "number",
                "overall": "number"
            },
            "criteria_feedback": {
                "fluency_coherence": {
                    "band": "number",
                    "plus": ["string"],
                    "minus": ["string"],
                    "logic_framework": {
                        "outline_zh": ["string"],
                        "outline_en": ["string"],
                        "upgrade_tips": ["string"]
                    }
                },
                "lexical_resource": {
                    "band": "number",
                    "plus": ["string"],
                    "minus": ["string"],
                    "expression_corrections": [
                        {
                            "original": "string",
                            "native_like": "string",
                            "note": "string"
                        }
                    ],
                    "vocabulary_upgrades": [
                        {
                            "from": "string",
                            "to": ["string", "string"],
                            "usage_note": "string"
                        }
                    ]
                },
                "grammar_range_accuracy": {
                    "band": "number",
                    "plus": ["string"],
                    "minus": ["string"],
                    "sentence_corrections": [
                        {
                            "original": "string",
                            "issue_type": ["grammar|collocation|logic|wording"],
                            "correction": "string",
                            "explain_cn": "string",
                            "severity": "low|mid|high"
                        }
                    ]
                },
                "pronunciation": {
                    "band": "number",
                    "plus": ["string"],
                    "minus": ["string"],
                    "audio_observations": ["string"],
                    "confidence": "low|medium|high",
                    "limitation_note": "string"
                }
            },
            "rewrite_high_band": {
                "target_band": "string",
                "paragraph": "string",
                "logic_tips": ["string"]
            },
            "next_step": ["string"],
            "reply_text": "string (2-3 natural conversational sentences as an IELTS examiner responding to the student. Reference specific things the student said. Be warm and encouraging but honest. Do NOT repeat scores or list corrections here.)",
            "follow_up_question": "string (a single natural IELTS examiner follow-up question. For Part1: a related personal question. For Part2: ask to elaborate on a detail mentioned. For Part3: a deeper discussion question that pushes critical thinking.)"
        },
        "rules": [
            "For Part1: keep the rewrite concise and within 2-4 sentences.",
            "For Part2: include basic info, anecdote, and explanation/feelings; keep clear timeline.",
            "For Part3: include at least two viewpoints with reasons and examples.",
            "Fluency & Coherence must include logic framework coaching, not only score.",
            "Lexical Resource must include Chinese-style expression correction + vocabulary upgrades.",
            "Grammar Range & Accuracy must include sentence-level corrections.",
            "Pronunciation should use audio_metrics when available. If audio_metrics are limited, still give a cautious estimate and include limitation_note.",
            "rewrite_high_band must include one coherent paragraph and logic_tips as bullet points.",
            "logic_tips should be Chinese guidance with key English connectors (for example: When it comes to, If I remember correctly, At first, Then, Finally, As for the reasons why, First of all, What's more).",
            "Keep output concise to avoid truncation: plus/minus each <=2 items; sentence_corrections <=2; expression_corrections <=2; vocabulary_upgrades <=3; logic_tips <=3; next_step <=3.",
            "reply_text must be 2-3 natural sentences like an examiner speaking face-to-face. Reference specific content from the student's transcript. Be warm but constructive. Use English.",
            "follow_up_question must be a single natural question that continues the conversation and is appropriate for the IELTS Part being practiced.",
            "If conversation_history is provided, reference it naturally in reply_text (e.g. acknowledge improvement or recurring issues). follow_up_question should build on the conversation thread. If the student is answering a previous follow-up, evaluate in that context."
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


def _safe_num(value: Any, default: float = 0.0) -> float:
    try:
        return round(float(value), 1)
    except (TypeError, ValueError):
        return default


def _list_of_str(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        if item is None:
            continue
        text = str(item).strip()
        if text:
            result.append(text)
    return result


def _normalize_sentence_feedback(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    result: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        issue_type = item.get("issue_type")
        if isinstance(issue_type, list):
            issue_types = [str(x).strip() for x in issue_type if str(x).strip()]
        elif issue_type:
            issue_types = [str(issue_type).strip()]
        else:
            issue_types = []
        result.append(
            {
                "original": str(item.get("original") or "").strip(),
                "issue_type": issue_types,
                "correction": str(item.get("correction") or "").strip(),
                "explain_cn": str(item.get("explain_cn") or "").strip(),
                "severity": str(item.get("severity") or "").strip() or "mid",
            }
        )
    return [x for x in result if x["original"] or x["correction"]]


def _normalize_native_corrections(items: Any) -> list[dict[str, str]]:
    if not isinstance(items, list):
        return []
    result: list[dict[str, str]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        result.append(
            {
                "original": str(item.get("original") or "").strip(),
                "native_like": str(item.get("native_like") or "").strip(),
                "note": str(item.get("note") or "").strip(),
            }
        )
    return [x for x in result if x["original"] or x["native_like"]]


def _normalize_vocab_upgrades(items: Any) -> list[dict[str, Any]]:
    if not isinstance(items, list):
        return []
    result: list[dict[str, Any]] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        to_value = item.get("to")
        if isinstance(to_value, list):
            to_list = [str(x).strip() for x in to_value if str(x).strip()]
        elif to_value:
            to_list = [str(to_value).strip()]
        else:
            to_list = []
        result.append(
            {
                "from": str(item.get("from") or "").strip(),
                "to": to_list,
                "constraint": str(
                    item.get("constraint") or item.get("usage_note") or ""
                ).strip(),
            }
        )
    return [x for x in result if x["from"] or x["to"]]


def _normalize_result(parsed: Any, target_band: str) -> dict[str, Any]:
    data = parsed if isinstance(parsed, dict) else {}
    raw_scores = data.get("scores") if isinstance(data.get("scores"), dict) else {}
    criteria = (
        data.get("criteria_feedback")
        if isinstance(data.get("criteria_feedback"), dict)
        else {}
    )
    fc = criteria.get("fluency_coherence") if isinstance(criteria.get("fluency_coherence"), dict) else {}
    lr = criteria.get("lexical_resource") if isinstance(criteria.get("lexical_resource"), dict) else {}
    ga = criteria.get("grammar_range_accuracy") if isinstance(criteria.get("grammar_range_accuracy"), dict) else {}
    pr = criteria.get("pronunciation") if isinstance(criteria.get("pronunciation"), dict) else {}

    logic_framework = (
        fc.get("logic_framework")
        if isinstance(fc.get("logic_framework"), dict)
        else {}
    )
    outline_zh = _list_of_str(
        logic_framework.get("outline_zh")
        if logic_framework
        else data.get("logic_outline", {}).get("zh")
        if isinstance(data.get("logic_outline"), dict)
        else []
    )
    outline_en = _list_of_str(
        logic_framework.get("outline_en")
        if logic_framework
        else data.get("logic_outline", {}).get("en")
        if isinstance(data.get("logic_outline"), dict)
        else []
    )

    sentence_feedback = _normalize_sentence_feedback(
        ga.get("sentence_corrections") if ga else data.get("sentence_feedback")
    )
    chinese_style = _normalize_native_corrections(
        lr.get("expression_corrections") if lr else data.get("chinese_style_correction")
    )
    lexical_upgrade = _normalize_vocab_upgrades(
        lr.get("vocabulary_upgrades") if lr else data.get("lexical_upgrade")
    )

    rewrite = (
        data.get("rewrite_high_band")
        if isinstance(data.get("rewrite_high_band"), dict)
        else {}
    )

    scores = {
        "fluency_coherence": _safe_num(
            raw_scores.get("fluency_coherence"), _safe_num(fc.get("band"), 0.0)
        ),
        "lexical_resource": _safe_num(
            raw_scores.get("lexical_resource"), _safe_num(lr.get("band"), 0.0)
        ),
        "grammar_range_accuracy": _safe_num(
            raw_scores.get("grammar_range_accuracy"), _safe_num(ga.get("band"), 0.0)
        ),
        "pronunciation": _safe_num(
            raw_scores.get("pronunciation"), _safe_num(pr.get("band"), 0.0)
        ),
        "overall": _safe_num(raw_scores.get("overall"), 0.0),
    }
    if scores["overall"] == 0.0:
        core = [
            scores["fluency_coherence"],
            scores["lexical_resource"],
            scores["grammar_range_accuracy"],
            scores["pronunciation"],
        ]
        valid = [x for x in core if x > 0]
        if valid:
            scores["overall"] = round(sum(valid) / len(valid), 1)

    criteria_feedback = {
        "fluency_coherence": {
            "band": _safe_num(fc.get("band"), scores["fluency_coherence"]),
            "plus": _list_of_str(fc.get("plus")),
            "minus": _list_of_str(fc.get("minus")),
            "logic_framework": {
                "outline_zh": outline_zh,
                "outline_en": outline_en,
                "upgrade_tips": _list_of_str(logic_framework.get("upgrade_tips")),
            },
        },
        "lexical_resource": {
            "band": _safe_num(lr.get("band"), scores["lexical_resource"]),
            "plus": _list_of_str(lr.get("plus")),
            "minus": _list_of_str(lr.get("minus")),
            "expression_corrections": chinese_style,
            "vocabulary_upgrades": lexical_upgrade,
        },
        "grammar_range_accuracy": {
            "band": _safe_num(ga.get("band"), scores["grammar_range_accuracy"]),
            "plus": _list_of_str(ga.get("plus")),
            "minus": _list_of_str(ga.get("minus")),
            "sentence_corrections": sentence_feedback,
        },
        "pronunciation": {
            "band": _safe_num(pr.get("band"), scores["pronunciation"]),
            "plus": _list_of_str(pr.get("plus")),
            "minus": _list_of_str(pr.get("minus")),
            "audio_observations": _list_of_str(pr.get("audio_observations")),
            "confidence": str(pr.get("confidence") or "low"),
            "limitation_note": str(pr.get("limitation_note") or "").strip(),
        },
    }

    normalized = {
        "scores": scores,
        "criteria_feedback": criteria_feedback,
        "logic_outline": {"zh": outline_zh, "en": outline_en},
        "sentence_feedback": sentence_feedback,
        "chinese_style_correction": chinese_style,
        "lexical_upgrade": lexical_upgrade,
        "rewrite_high_band": {
            "target_band": str(rewrite.get("target_band") or target_band),
            "paragraph": str(rewrite.get("paragraph") or rewrite.get("rewrite") or "").strip(),
            "logic_tips": _list_of_str(rewrite.get("logic_tips")),
        },
        "next_step": _list_of_str(data.get("next_step")),
        "reply_text": str(data.get("reply_text") or "").strip(),
        "follow_up_question": str(data.get("follow_up_question") or "").strip(),
    }
    return normalized


def run_ielts_eval(data: dict[str, Any]) -> tuple[dict[str, Any], int]:
    transcript = data.get("transcript") or data.get("student_answer")
    if not transcript:
        return {"ok": False, "error": "missing_transcript"}, 400

    config = current_app.config
    api_key = config.get("DEEPSEEK_API_KEY")
    if not api_key:
        return {"ok": False, "error": "missing_deepseek_key"}, 500

    base_url = (config.get("DEEPSEEK_API_BASE") or "https://api.deepseek.com").rstrip("/")
    chat_url = (config.get("DEEPSEEK_CHAT_URL") or "").strip() or f"{base_url}/v1/chat/completions"
    model = config.get("DEEPSEEK_MODEL") or "deepseek-chat"
    timeout = float(config.get("DEEPSEEK_TIMEOUT") or 35)
    retries = int(config.get("DEEPSEEK_RETRIES") or 0)

    messages = _build_prompt(data)
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2,
        "max_tokens": 2000,
        "response_format": {"type": "json_object"},
    }

    attempt_plan = [chat_url] * max(1, retries + 1)
    last_error: dict[str, Any] | None = None
    raw: dict[str, Any] | None = None
    final_url = chat_url

    for idx, url in enumerate(attempt_plan):
        final_url = url
        try:
            resp = requests.post(
                url,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=payload,
                timeout=timeout,
            )
        except requests.RequestException as exc:
            last_error = {"error": "deepseek_request_failed", "details": str(exc), "endpoint": url}
            if idx < len(attempt_plan) - 1:
                time.sleep(0.35)
                continue
            return {"ok": False, **last_error}, 502

        if resp.status_code >= 400:
            status_error = {
                "error": "deepseek_http_error",
                "status": resp.status_code,
                "details": resp.text[:600],
                "endpoint": url,
            }
            if resp.status_code in {408, 429, 500, 502, 503, 504} and idx < len(attempt_plan) - 1:
                last_error = status_error
                time.sleep(0.35)
                continue
            return {"ok": False, **status_error}, 502

        try:
            raw = resp.json()
        except ValueError:
            last_error = {
                "error": "deepseek_invalid_json",
                "details": resp.text[:600],
                "endpoint": url,
            }
            if idx < len(attempt_plan) - 1:
                time.sleep(0.35)
                continue
            return {"ok": False, **last_error}, 502
        break

    if raw is None:
        return {"ok": False, **(last_error or {"error": "deepseek_request_failed"})}, 502

    content = (
        raw.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
    )
    ok, parsed = _extract_json(content)
    normalized = _normalize_result(parsed, str(data.get("target_band") or "7.0")) if ok else None
    return {
        "ok": ok,
        "result": normalized if ok else parsed,
        "raw": content if not ok else None,
        "usage": raw.get("usage"),
        "model": raw.get("model", model),
        "endpoint": final_url,
    }, 200


@eval_bp.post("/evaluate")
@require_api_user()
def evaluate_ielts():
    data = request.get_json(silent=True) or {}
    payload, status = run_ielts_eval(data)
    return jsonify(payload), status
