"""模考复盘（教师后台）的纯逻辑 helper（不依赖 Flask 请求上下文）。

交卷时已经把逐题判分结果写进 ``MockExamSession.*_results_json``。正常复盘只还原这份快照；
另提供一个窄范围检测器，供路由幂等修复旧版 ``NOT``/``NOT GIVEN`` 控件值造成的历史误判。
除此之外不重新判分。
"""

from __future__ import annotations

import html
import json
import math
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from services.ielts_practice_scoring import grade_reading_test_answers

UTC = timezone.utc  # noqa: UP017 - Python 3.10-compatible replacement.
SHANGHAI = ZoneInfo("Asia/Shanghai")
UNANSWERED_TEXT = "（未作答）"
_WHITESPACE_RE = re.compile(r"\s+")
_PLACEHOLDER_RE = re.compile(r"\$(\d+)\$")
_BREAK_TAG_RE = re.compile(r"<\s*(?:br\s*/?|/p|/div|/li|/tr|/h[1-6])\s*>", re.IGNORECASE)
_OPEN_LIST_ITEM_RE = re.compile(r"<\s*li(?:\s[^>]*)?>", re.IGNORECASE)
_HTML_TAG_RE = re.compile(r"<[^>]+>")


def parse_json_list(blob) -> list:
    """结果 JSON 可能为空 / 脏数据，复盘页不能因此 500。"""
    try:
        data = json.loads(blob or "[]")
    except (TypeError, ValueError):
        return []
    return data if isinstance(data, list) else []


def parse_json_dict(blob) -> dict:
    try:
        data = json.loads(blob or "{}")
    except (TypeError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def build_writing_review_tasks(payload: dict | None) -> list[dict]:
    """给写作复盘补齐可直接渲染的本地题图地址。"""
    if not isinstance(payload, dict):
        return []

    tasks = []
    for raw_task in payload.get("tasks") or []:
        if not isinstance(raw_task, dict):
            continue
        task = dict(raw_task)
        image_path = str(task.get("image") or "").strip().replace("\\", "/")
        parts = [part for part in image_path.split("/") if part]
        if image_path and ".." not in parts:
            if image_path.startswith("/static/"):
                task["image_src"] = image_path
            else:
                image_path = image_path.lstrip("/")
                if not image_path.startswith("writing_tests/"):
                    image_path = f"writing_tests/{image_path}"
                task["image_src"] = f"/static/{image_path}"
        else:
            task["image_src"] = ""
        tasks.append(task)
    return tasks


def has_legacy_not_given_misgrade(results: list) -> bool:
    """识别题库 key=NOT/text=GIVEN 造成的历史误判，不触碰其他历史成绩。"""
    for result in results:
        if not isinstance(result, dict):
            continue
        answer = re.sub(r"[\s_-]+", "", str(result.get("answer") or "").upper())
        value = re.sub(r"[\s_-]+", "", str(result.get("value") or "").upper())
        try:
            awarded = int(result.get("awarded") or 0)
            marks = int(result.get("marks") or 1)
        except (TypeError, ValueError):
            continue
        if answer in {"NG", "NOTGIVEN"} and value == "NOT" and awarded < marks:
            return True
    return False


def repair_legacy_not_given_grade(session, reading_payload: dict | None) -> bool:
    """按保存答案幂等修复旧版 ``NOT``/``NOT GIVEN`` 误判。"""
    saved_results = parse_json_list(session.reading_results_json)
    if not reading_payload or not has_legacy_not_given_misgrade(saved_results):
        return False
    answers = parse_json_dict(session.reading_answers_json)
    if not answers:
        return False
    grade = grade_reading_test_answers(reading_payload, answers)
    session.reading_correct = grade["correct"]
    session.reading_total = grade["total"]
    session.reading_accuracy = grade["accuracy"]
    session.reading_ielts_score = grade["ielts_score"]
    session.reading_results_json = json.dumps(grade["results"], ensure_ascii=False)
    session.reading_wrong_numbers_json = json.dumps(grade["wrong_numbers"], ensure_ascii=False)
    return True


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
    return "\n".join(
        _WHITESPACE_RE.sub(" ", line).strip()
        for line in str(text or "").splitlines()
        if _WHITESPACE_RE.sub(" ", line).strip()
    )


def _plain_text(value, question_labels: dict[str, str] | None = None) -> str:
    """把题库中的轻量 HTML 转成适合后台复盘的纯文本，并保留题号占位。"""
    text = str(value or "")
    labels = question_labels or {}
    text = _PLACEHOLDER_RE.sub(
        lambda match: f"【{labels.get(match.group(1), 'Q' + match.group(1))}】",
        text,
    )
    text = _BREAK_TAG_RE.sub("\n", text)
    text = _OPEN_LIST_ITEM_RE.sub("\n• ", text)
    text = html.unescape(_HTML_TAG_RE.sub("", text))
    lines = [_WHITESPACE_RE.sub(" ", line).strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def _table_text(table, question_labels: dict[str, str]) -> str:
    if not isinstance(table, dict):
        return ""
    rows = []
    for row in table.get("content") or []:
        if not isinstance(row, list):
            continue
        cells = [_plain_text(cell, question_labels) for cell in row]
        if any(cells):
            rows.append(" | ".join(cells))
    title = _plain_text(table.get("title"), question_labels)
    return "\n".join(part for part in [title, *rows] if part)


def _display_options(options) -> list[dict]:
    rows = []
    for option in options or []:
        if not isinstance(option, dict):
            continue
        key = str(option.get("key") or "").strip()
        text = _plain_text(option.get("text"))
        if key or text:
            rows.append({"key": key, "text": text})
    return rows


def _transcript_line(row) -> dict | None:
    if not isinstance(row, dict):
        return None
    text = str(row.get("en") or row.get("text") or "").strip()
    if not text:
        return None
    try:
        start = float(row.get("start") or 0)
    except (TypeError, ValueError):
        start = 0.0
    try:
        end = float(row.get("end") or start)
    except (TypeError, ValueError):
        end = start
    minutes, seconds = divmod(max(0, int(start)), 60)
    return {
        "time": f"{minutes:02d}:{seconds:02d}",
        "text": text,
        "translation": str(row.get("cn") or "").strip(),
        "start": start,
        "end": end,
    }


def _unit_source(container: dict, kind: str) -> dict:
    if kind == "reading":
        content = container.get("content") if isinstance(container.get("content"), dict) else {}
        paragraphs = []
        for paragraph in content.get("paragraphs") or []:
            if not isinstance(paragraph, dict):
                continue
            text = str(paragraph.get("text") or "").strip()
            if text:
                paragraphs.append(
                    {
                        "label": str(paragraph.get("label") or "").strip(),
                        "text": text,
                    }
                )
        return {
            "kind": "reading",
            "title": str(
                content.get("title") or container.get("title") or "Reading Passage"
            ).strip(),
            "paragraphs": paragraphs,
        }

    transcript = []
    for raw_line in container.get("transcript") or []:
        line = _transcript_line(raw_line)
        if line:
            transcript.append(line)
    return {
        "kind": "listening",
        "title": str(
            container.get("source_title") or container.get("title") or "Listening transcript"
        ).strip(),
        "transcript": transcript,
    }


def _reading_evidence(question: dict) -> list[dict]:
    central = question.get("central_sentences")
    if not isinstance(central, dict):
        return []
    sentences = central.get("sentences") or []
    evidence = []
    for sentence in sentences:
        text = sentence.get("sentence") if isinstance(sentence, dict) else sentence
        text = str(text or "").strip()
        if text and text not in {row["text"] for row in evidence}:
            evidence.append({"time": "", "text": text, "translation": ""})
    return evidence


def _listening_evidence(question: dict, source: dict) -> list[dict]:
    timing = question.get("answer_sentences")
    timing = timing if isinstance(timing, dict) else {}
    try:
        start = (
            float(timing.get("start_time")) / 1000
            if timing.get("start_time") is not None
            else float(question.get("start"))
        )
        end = (
            float(timing.get("end_time")) / 1000
            if timing.get("end_time") is not None
            else float(question.get("end"))
        )
    except (TypeError, ValueError):
        return []
    return [
        {key: line[key] for key in ("time", "text", "translation")}
        for line in source.get("transcript") or []
        if line["end"] >= start and line["start"] <= end
    ]


def _question_evidence(question: dict, source: dict, kind: str) -> list[dict]:
    if kind == "reading":
        return _reading_evidence(question)
    return _listening_evidence(question, source)


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
    """构造题号到完整复盘上下文的索引。

    判分结果里只有题号和答案；题干、题目结构、阅读文章和听力原文都必须回原卷查。
    """
    index: dict[str, dict] = {}
    raw_payload = payload if isinstance(payload, dict) else {}
    containers = raw_payload.get("passages" if kind == "reading" else "sections") or []
    if kind != "reading" and not containers and raw_payload.get("groups"):
        containers = [raw_payload]
    units = _payload_units(payload, kind)
    for unit_index, (unit_label, groups) in enumerate(units):
        container = (
            containers[unit_index]
            if unit_index < len(containers) and isinstance(containers[unit_index], dict)
            else {}
        )
        source = _unit_source(container, kind)
        for group_index, group in enumerate(groups):
            group = group if isinstance(group, dict) else {}
            questions = group.get("questions") or group.get("items") or []
            question_labels = {
                str(question.get("id") or question.get("number")): f"Q{question.get('number')}"
                for question in questions
                if isinstance(question, dict)
                and (question.get("id") or question.get("number")) is not None
            }
            prompt = "\n".join(
                part
                for part in (
                    _plain_text(group.get("collect"), question_labels),
                    _table_text(group.get("table"), question_labels),
                )
                if part
            )
            group_options = _display_options((group.get("collect_option") or {}).get("list"))
            image_local = str(group.get("img_local") or "").strip().lstrip("/")
            image_url = str(group.get("img_url") or "").strip()
            meta = {
                "unit_index": unit_index,
                "unit_label": unit_label,
                "group_key": f"{unit_index}-{group_index}",
                "group_title": str(group.get("title") or "").strip(),
                "instruction": _clean_instruction(group.get("desc") or group.get("question_title")),
                "group_prompt": prompt,
                "group_options": group_options,
                "group_image_src": f"/static/{image_local}" if image_local else image_url,
                "source": source,
            }
            for question in questions:
                question = question if isinstance(question, dict) else {}
                qid = question.get("id") or question.get("number")
                if qid is None:
                    continue
                index[str(qid)] = {
                    **meta,
                    "question_stem": _plain_text(question.get("title")),
                    "question_options": _display_options(question.get("options")),
                    "evidence": _question_evidence(question, source, kind),
                    "question_analysis": _clean_instruction(question.get("analysis")),
                }
    return index


def _row_from_result(result: dict, metas: list[dict]) -> dict:
    meta = metas[0] if metas else None
    marks = int(result.get("marks") or 0)
    awarded = int(result.get("awarded") or 0)
    student = str(result.get("value") or "").strip()
    numbers = [str(n) for n in (result.get("numbers") or []) if n is not None]
    label = str(result.get("q") or "").strip() or "、".join(numbers)
    stems = []
    options = []
    evidence = []
    analyses = []
    for item in metas:
        stem = item.get("question_stem") or ""
        if stem and stem not in stems:
            stems.append(stem)
        for option in item.get("question_options") or []:
            if option not in options:
                options.append(option)
        for excerpt in item.get("evidence") or []:
            if excerpt not in evidence:
                evidence.append(excerpt)
        analysis = item.get("question_analysis") or ""
        if analysis and analysis not in analyses:
            analyses.append(analysis)
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
        "question_stem": " / ".join(stems),
        "question_options": options,
        "evidence": evidence,
        "question_analysis": "\n\n".join(analyses),
        "has_context": bool(stems or options or evidence or analyses),
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
        metas = [question_index[i] for i in ids if i in question_index]
        meta = metas[0] if metas else None
        row = _row_from_result(result, metas)

        unit_key = str((meta or {}).get("unit_index", "other"))
        unit = unit_by_key.get(unit_key)
        if unit is None:
            unit = {
                "label": row["unit_label"],
                "groups": [],
                "correct": 0,
                "total": 0,
                "wrong": 0,
                "source": (meta or {}).get("source") or {},
            }
            unit_by_key[unit_key] = unit
            units.append(unit)

        group_key = f"{unit_key}:{(meta or {}).get('group_key', 'other')}"
        group = group_by_key.get(group_key)
        if group is None:
            group = {
                "title": (meta or {}).get("group_title") or "",
                "instruction": (meta or {}).get("instruction") or "",
                "prompt": (meta or {}).get("group_prompt") or "",
                "options": (meta or {}).get("group_options") or [],
                "image_src": (meta or {}).get("group_image_src") or "",
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
