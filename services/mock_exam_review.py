"""模考复盘（教师后台）的纯逻辑 helper（不依赖 Flask 请求上下文）。

交卷时已经把逐题判分结果写进 ``MockExamSession.*_results_json``，教师复盘**不重新判分**，
只把这份结果还原成「按 section / passage 分组的逐题对照表」，外加时间、时长、总分文本。
路由层只做"取会话 → 调这里 → 渲染模板"。
"""

from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

UTC = timezone.utc  # noqa: UP017 - Python 3.10-compatible replacement.
SHANGHAI = ZoneInfo("Asia/Shanghai")
UNANSWERED_TEXT = "（未作答）"
MAX_INSTRUCTION_CHARS = 140
_WHITESPACE_RE = re.compile(r"\s+")


def parse_json_list(blob) -> list:
    """结果 JSON 可能为空 / 脏数据，复盘页不能因此 500。"""
    try:
        data = json.loads(blob or "[]")
    except (TypeError, ValueError):
        return []
    return data if isinstance(data, list) else []


def local_time_text(value: datetime | None, fmt: str = "%Y-%m-%d %H:%M") -> str:
    """库里存的是 naive UTC，教师看到的一律转北京时间。"""
    if not value:
        return ""
    return value.replace(tzinfo=UTC).astimezone(SHANGHAI).strftime(fmt)


def duration_text(seconds) -> str:
    try:
        total = max(0, int(seconds or 0))
    except (TypeError, ValueError):
        total = 0
    return f"{total // 60} 分 {total % 60} 秒"


def overall_band(listening_band, reading_band) -> float | None:
    """两科都判完才有综合分：按雅思口径取 0.5 分档，.25 / .75 一律进位。

    不能用 ``round()``：它在 .5 处取偶，会把 6.25 压成 6.0（应为 6.5）。
    """
    if listening_band is None or reading_band is None:
        return None
    try:
        average = (float(listening_band) + float(reading_band)) / 2
    except (TypeError, ValueError):
        return None
    return math.floor(average * 2 + 0.5) / 2


def _clean_instruction(text) -> str:
    cleaned = _WHITESPACE_RE.sub(" ", str(text or "")).strip()
    if len(cleaned) > MAX_INSTRUCTION_CHARS:
        cleaned = cleaned[: MAX_INSTRUCTION_CHARS - 1] + "…"
    return cleaned


def _payload_units(payload: dict | None, kind: str) -> list[tuple[str, list]]:
    """统一听力 section / 阅读 passage 两种结构：返回 [(单元标题, groups)]。"""
    payload = payload if isinstance(payload, dict) else {}
    if kind == "reading":
        containers = payload.get("passages") or []
        default_prefix = "Passage"
    else:
        containers = payload.get("sections") or []
        if not containers and payload.get("groups"):
            containers = [payload]
        default_prefix = "Section"
    units = []
    for index, container in enumerate(containers):
        container = container if isinstance(container, dict) else {}
        label = f"{default_prefix} {index + 1}"
        title = str(container.get("title") or "").strip()
        # 题库里的 title 常常就是 "Section 1"，重复拼接没有信息量。
        if title and title.lower() != label.lower():
            label = f"{label} · {title}"
        question_range = str(container.get("question_name") or "").strip()
        if question_range and question_range not in label:
            label = f"{label} · {question_range}"
        units.append((label, container.get("groups") or []))
    return units


def build_question_index(payload: dict | None, kind: str) -> dict:
    """{题目 id: {unit_index, unit_label, group_key, group_title, instruction}}。

    判分结果里只有题号和答案，题目归属哪个 section / 题组要回原卷查。
    """
    index: dict[str, dict] = {}
    for unit_index, (unit_label, groups) in enumerate(_payload_units(payload, kind)):
        for group_index, group in enumerate(groups):
            group = group if isinstance(group, dict) else {}
            meta = {
                "unit_index": unit_index,
                "unit_label": unit_label,
                "group_key": f"{unit_index}-{group_index}",
                "group_title": str(group.get("title") or "").strip(),
                "instruction": _clean_instruction(group.get("desc") or group.get("question_title")),
            }
            for question in group.get("questions") or group.get("items") or []:
                question = question if isinstance(question, dict) else {}
                qid = question.get("id") or question.get("number")
                if qid is None:
                    continue
                index[str(qid)] = meta
    return index


def _row_from_result(result: dict, meta: dict | None) -> dict:
    marks = int(result.get("marks") or 0)
    awarded = int(result.get("awarded") or 0)
    student = str(result.get("value") or "").strip()
    numbers = [str(n) for n in (result.get("numbers") or []) if n is not None]
    label = str(result.get("q") or "").strip() or "、".join(numbers)
    return {
        "label": f"Q{label}" if label else "—",
        "student_answer": student or UNANSWERED_TEXT,
        "answered": bool(student),
        "correct_answer": str(result.get("answer") or "").strip() or "—",
        "awarded": awarded,
        "marks": marks,
        "is_correct": bool(marks) and awarded >= marks,
        "is_partial": 0 < awarded < marks,
        "status_label": str(result.get("status_label") or ""),
        "unit_label": (meta or {}).get("unit_label") or "未归类",
    }


def build_review_units(results: list, question_index: dict) -> list[dict]:
    """把逐题结果整理成 [单元 → 题组 → 行]，顺序保持原卷顺序。"""
    units: list[dict] = []
    unit_by_key: dict[str, dict] = {}
    group_by_key: dict[str, dict] = {}

    for result in results:
        if not isinstance(result, dict):
            continue
        ids = [str(i) for i in (result.get("ids") or [])]
        meta = next((question_index[i] for i in ids if i in question_index), None)
        row = _row_from_result(result, meta)

        unit_key = str((meta or {}).get("unit_index", "other"))
        unit = unit_by_key.get(unit_key)
        if unit is None:
            unit = {"label": row["unit_label"], "groups": [], "correct": 0, "total": 0, "wrong": 0}
            unit_by_key[unit_key] = unit
            units.append(unit)

        group_key = f"{unit_key}:{(meta or {}).get('group_key', 'other')}"
        group = group_by_key.get(group_key)
        if group is None:
            group = {
                "title": (meta or {}).get("group_title") or "",
                "instruction": (meta or {}).get("instruction") or "",
                "rows": [],
            }
            group_by_key[group_key] = group
            unit["groups"].append(group)
        group["rows"].append(row)

        unit["total"] += row["marks"]
        unit["correct"] += row["awarded"]
        if not row["is_correct"]:
            unit["wrong"] += 1
    return units


def _section_summary(
    correct, total, accuracy, band, duration_seconds, submitted_at, auto_submitted
):
    return {
        "submitted": bool(submitted_at),
        "submitted_at_text": local_time_text(submitted_at),
        "correct": correct,
        "total": total,
        "accuracy": accuracy,
        "band": band,
        "duration_text": duration_text(duration_seconds),
        "auto_submitted": bool(auto_submitted),
    }


def summarize_session(sess) -> dict:
    """一条会话在教师端的展示口径（成绩列表与复盘页共用）。"""
    listening = _section_summary(
        sess.listening_correct,
        sess.listening_total,
        sess.listening_accuracy,
        sess.listening_ielts_score,
        sess.listening_duration_seconds,
        sess.listening_submitted_at,
        sess.listening_auto_submitted,
    )
    reading = _section_summary(
        sess.reading_correct,
        sess.reading_total,
        sess.reading_accuracy,
        sess.reading_ielts_score,
        sess.reading_duration_seconds,
        sess.reading_submitted_at,
        sess.reading_auto_submitted,
    )
    return {
        "id": sess.id,
        "exam_id": sess.exam_id,
        "student_name": sess.student_name,
        "status": sess.status,
        "status_text": "已交卷" if sess.status == "submitted" else "进行中",
        "current_section": sess.current_section,
        "started_at_text": local_time_text(sess.started_at),
        "finished_at_text": local_time_text(sess.finished_at),
        "listening": listening,
        "reading": reading,
        "writing": {
            "submitted": bool(sess.writing_submitted_at),
            "submitted_at_text": local_time_text(sess.writing_submitted_at),
            "task1_words": sess.writing_task1_words or 0,
            "task2_words": sess.writing_task2_words or 0,
            "duration_text": duration_text(sess.writing_duration_seconds),
            "auto_submitted": bool(sess.writing_auto_submitted),
        },
        "overall_band": overall_band(sess.listening_ielts_score, sess.reading_ielts_score),
    }
