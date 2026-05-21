"""Qwen client for vocabulary enrichment generation."""

from __future__ import annotations

import json
import os
import re
import time
from typing import Any

import requests
from flask import current_app


QWEN_CHAT_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"

SYSTEM_PROMPT = """你是 TOEFL/IELTS 词汇教学专家。请为英语学习者生成词汇增强信息。

要求：
1. core_meaning_zh 必须是简洁核心义，不照搬冗长释义。
2. usage_pattern 写常见搭配或句型；无明显搭配时写自然常用语境。
3. example_en 写 12-22 个英文词，自然地道，适合 TOEFL/IELTS 或通用学习语境。
4. example_zh 是准确流畅的中文翻译。
5. usage_note 只在多义词、易混词、搭配限制或考试常用法需要说明时填写；普通词可为空字符串。
6. needs_review 对高风险词、短语、不确定内容返回 true，否则 false。

只输出合法 JSON，不要输出 Markdown。JSON 格式：
{
  "items": [
    {
      "id": 123,
      "core_meaning_zh": "...",
      "usage_pattern": "...",
      "example_en": "...",
      "example_zh": "...",
      "usage_note": "...",
      "needs_review": false
    }
  ]
}
"""


def _config_value(key: str, default: str | None = None) -> str | None:
    try:
        value = current_app.config.get(key)
    except RuntimeError:
        value = None
    return value or os.environ.get(key) or default


def _chat_url() -> str:
    base = (_config_value("ALIYUN_QWEN_CHAT_URL") or "").strip()
    if base:
        return base
    return QWEN_CHAT_URL


def _model(default: str = "qwen3-max-2026-01-23") -> str:
    return (_config_value("ALIYUN_QWEN_MODEL", default) or default).strip()


def _api_key() -> str | None:
    return _config_value("ALIYUN_API_KEY")


def _word_tokens(text: str) -> list[str]:
    return [t.lower() for t in re.findall(r"[A-Za-z]+", text or "") if len(t) >= 3]


def _looks_like_single_word(text: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z]+(?:'[A-Za-z]+)?", (text or "").strip()))


def _has_reasonable_word_match(word: str, example: str) -> bool:
    """Best-effort check; failure means review, not automatic discard."""
    clean_word = (word or "").strip().lower()
    clean_example = (example or "").strip().lower()
    if not clean_word or not clean_example:
        return False

    example_tokens = set(_word_tokens(clean_example))
    if _looks_like_single_word(clean_word):
        base = clean_word.rstrip(".")
        variants = {
            base,
            f"{base}s",
            f"{base}es",
            f"{base}ed",
            f"{base}d",
            f"{base}ing",
        }
        if base.endswith("y") and len(base) > 1:
            variants.add(f"{base[:-1]}ies")
        if base.endswith("e") and len(base) > 1:
            variants.add(f"{base[:-1]}ing")
        return bool(example_tokens.intersection(variants))

    phrase_tokens = _word_tokens(clean_word)
    if not phrase_tokens:
        return True
    required = phrase_tokens[:2] if len(phrase_tokens) > 2 else phrase_tokens
    return any(token in example_tokens for token in required)


def _strip_json_fence(content: str) -> str:
    text = (content or "").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _parse_qwen_json(content: str) -> dict[str, Any]:
    text = _strip_json_fence(content)
    return json.loads(text)


def _normalize_result(raw: dict[str, Any], by_id: dict[int, dict[str, Any]], model: str) -> dict[str, Any] | None:
    try:
        word_id = int(raw.get("id"))
    except (TypeError, ValueError):
        return None
    source = by_id.get(word_id)
    if not source:
        return None

    needs_review = raw.get("needs_review")
    if isinstance(needs_review, str):
        needs_review = needs_review.strip().lower() in {"1", "true", "yes", "需要", "是"}
    else:
        needs_review = bool(needs_review)

    result = {
        "id": word_id,
        "core_meaning_zh": str(raw.get("core_meaning_zh") or "").strip(),
        "usage_pattern": str(raw.get("usage_pattern") or "").strip(),
        "example_en": str(raw.get("example_en") or "").strip(),
        "example_zh": str(raw.get("example_zh") or "").strip(),
        "usage_note": str(raw.get("usage_note") or "").strip(),
        "needs_review": needs_review,
        "model": model,
    }
    if not _has_reasonable_word_match(source.get("word", ""), result["example_en"]):
        result["needs_review"] = True
    return result


def _build_user_prompt(items: list[dict[str, Any]]) -> str:
    payload = [
        {
            "id": item.get("id"),
            "word": item.get("word") or "",
            "translation": item.get("translation") or "",
            "phonetic": item.get("phonetic") or "",
        }
        for item in items
    ]
    return (
        "请为以下词条生成词汇增强信息。必须保持 id 不变，返回 items 数组，"
        "items 数量必须和输入一致。\n\n"
        + json.dumps(payload, ensure_ascii=False)
    )


def generate_vocab_enrichment(
    items: list[dict[str, Any]],
    *,
    model: str | None = None,
    timeout: float = 90,
    max_retries: int = 2,
) -> list[dict[str, Any]]:
    """Generate enrichment rows for a batch of vocabulary items.

    Each input item should contain id, word, translation, and optionally phonetic.
    Returns normalized result dicts. Raises RuntimeError after all retries fail.
    """
    clean_items = [
        item for item in items
        if item.get("id") is not None and str(item.get("word") or "").strip()
    ]
    if not clean_items:
        return []

    api_key = _api_key()
    if not api_key:
        raise RuntimeError("missing_aliyun_api_key")

    model_name = (model or _model()).strip()
    by_id = {int(item["id"]): item for item in clean_items}
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_prompt(clean_items)},
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
        "enable_thinking": False,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    last_error: Exception | None = None
    for attempt in range(max_retries + 1):
        try:
            resp = requests.post(_chat_url(), headers=headers, json=payload, timeout=timeout)
            resp.raise_for_status()
            data = resp.json()
            content = data["choices"][0]["message"]["content"]
            parsed = _parse_qwen_json(content)
            raw_items = parsed.get("items")
            if not isinstance(raw_items, list):
                raise RuntimeError("qwen_response_missing_items")
            results = [
                normalized for normalized in (
                    _normalize_result(raw, by_id, model_name)
                    for raw in raw_items
                    if isinstance(raw, dict)
                )
                if normalized is not None
            ]
            if not results:
                raise RuntimeError("qwen_response_no_valid_items")
            return results
        except Exception as exc:
            last_error = exc
            if attempt < max_retries:
                time.sleep(1.5 * (attempt + 1))

    raise RuntimeError(f"qwen_vocab_generation_failed: {last_error}")


def generate_word_enrichment(
    word: str,
    translation: str,
    *,
    word_id: int = 0,
    phonetic: str | None = None,
    model: str | None = None,
    timeout: float = 60,
    max_retries: int = 2,
) -> dict[str, Any] | None:
    """Generate enrichment for a single word. Returns None if Qwen fails."""
    try:
        results = generate_vocab_enrichment(
            [{
                "id": word_id or 1,
                "word": word,
                "translation": translation,
                "phonetic": phonetic or "",
            }],
            model=model,
            timeout=timeout,
            max_retries=max_retries,
        )
    except RuntimeError:
        return None
    return results[0] if results else None
