"""Canonical IELTS question-group inventory and frozen specialty snapshots.

The imported Cambridge data is intentionally kept source-shaped.  This module
does not invent a second question renderer: it identifies *complete* source
groups, checks whether the existing full-test renderers can display them, and
builds a filtered payload that those same templates consume.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from practice_tables import normalize_practice_tables
from services.practice_library_offline import load_offline_test_ids

TASK_TYPE = "question_type_practice"
SNAPSHOT_VERSION = 1
PACE_EXAM = "exam"
PACE_TRAINING = "training"
VALID_PACES = {PACE_EXAM, PACE_TRAINING}
SUBJECT_LISTENING = "listening"
SUBJECT_READING = "reading"
VALID_SUBJECTS = {SUBJECT_LISTENING, SUBJECT_READING}
CAMBRIDGE_TEST_RE = re.compile(r"^ielts(?P<volume>\d+)_test(?P<test>\d+)(?:_reading)?$")


TYPE_LABELS = {
    "form_completion": "Form Completion",
    "note_completion": "Note Completion",
    "table_completion": "Table Completion",
    "flow_chart_completion": "Flow-chart Completion",
    "sentence_completion": "Sentence Completion",
    "summary_completion": "Summary Completion",
    "multiple_choice_single": "Multiple Choice",
    "multiple_choice_multiple": "Multiple Choice (Multiple Answers)",
    "matching": "Matching",
    "classification": "Classification",
    "map_labelling": "Map Labelling",
    "plan_labelling": "Plan Labelling",
    "diagram_labelling": "Diagram Label Completion",
    "short_answer": "Short-answer Questions",
    "true_false_not_given": "True / False / Not Given",
    "yes_no_not_given": "Yes / No / Not Given",
    "matching_headings": "Matching Headings",
    "matching_information": "Matching Information",
    "matching_features": "Matching Features",
    "matching_sentence_endings": "Matching Sentence Endings",
    "list_selection": "List Selection",
    "unknown": "Unconfirmed",
}

# Keep the canonical English labels above stable for source data, matching and
# historical snapshots.  Student- and teacher-facing pages use these Chinese
# labels so the UI can be translated without changing stored question types.
TYPE_DISPLAY_LABELS = {
    "form_completion": "表单填空题",
    "note_completion": "笔记填空题",
    "table_completion": "表格填空题",
    "flow_chart_completion": "流程图填空题",
    "sentence_completion": "句子填空题",
    "summary_completion": "摘要填空题",
    "multiple_choice_single": "单项选择题",
    "multiple_choice_multiple": "多项选择题",
    "matching": "配对题（通用）",
    "classification": "分类题",
    "map_labelling": "地图标注题",
    "plan_labelling": "平面图标注题",
    "diagram_labelling": "图示标注题",
    "short_answer": "简答题",
    "true_false_not_given": "事实判断题（T / F / NG）",
    "yes_no_not_given": "观点判断题（Y / N / NG）",
    "matching_headings": "段落标题匹配题",
    "matching_information": "段落信息匹配题",
    "matching_features": "特征匹配题（人 / 观点 / 事物）",
    "matching_sentence_endings": "句子结尾匹配题",
    "list_selection": "列表选择题",
    "unknown": "待确认题型",
}

# The student-facing taxonomy deliberately stays broad. The canonical types
# above remain available inside each source group for renderer and scoring
# decisions, while students only choose the categories used by the Cambridge
# catalog UI.
PRACTICE_TYPE_LABELS = {
    "all": "全部",
    "completion": "填空题",
    "single_choice": "单选题",
    "multiple_choice": "多选题",
    "map_group": "地图题",
    "matching_group": "匹配题",
    "judgment": "判断题",
}
PRACTICE_TYPE_ENGLISH_LABELS = {
    "all": "All question types",
    "completion": "Completion",
    "single_choice": "Single choice",
    "multiple_choice": "Multiple choice",
    "map_group": "Map",
    "matching_group": "Matching",
    "judgment": "Judgment",
}
PRACTICE_TYPE_ORDER = {
    SUBJECT_LISTENING: (
        "all",
        "completion",
        "single_choice",
        "multiple_choice",
        "map_group",
        "matching_group",
    ),
    SUBJECT_READING: (
        "all",
        "completion",
        "single_choice",
        "multiple_choice",
        "matching_group",
        "judgment",
    ),
}
PRACTICE_TYPE_MEMBERS = {
    SUBJECT_LISTENING: {
        "completion": frozenset(
            {
                "form_completion",
                "note_completion",
                "table_completion",
                "flow_chart_completion",
                "sentence_completion",
                "summary_completion",
                "short_answer",
            }
        ),
        "single_choice": frozenset({"multiple_choice_single"}),
        "multiple_choice": frozenset({"multiple_choice_multiple"}),
        "map_group": frozenset({"map_labelling", "plan_labelling", "diagram_labelling"}),
        "matching_group": frozenset({"matching", "classification", "list_selection"}),
    },
    SUBJECT_READING: {
        "completion": frozenset(
            {
                "form_completion",
                "note_completion",
                "table_completion",
                "flow_chart_completion",
                "sentence_completion",
                "summary_completion",
                "diagram_labelling",
                "short_answer",
            }
        ),
        "single_choice": frozenset({"multiple_choice_single"}),
        "multiple_choice": frozenset({"multiple_choice_multiple"}),
        "matching_group": frozenset(
            {
                "matching",
                "classification",
                "matching_headings",
                "matching_information",
                "matching_features",
                "matching_sentence_endings",
                "list_selection",
            }
        ),
        "judgment": frozenset({"true_false_not_given", "yes_no_not_given"}),
    },
}


def question_type_display_label(standard_type: str) -> str:
    """Return a Chinese UI label without changing the canonical type code."""

    return PRACTICE_TYPE_LABELS.get(
        standard_type,
        TYPE_DISPLAY_LABELS.get(
            standard_type,
            TYPE_LABELS.get(standard_type, standard_type),
        ),
    )


def practice_type_members(subject: str, practice_type: str) -> frozenset[str]:
    """Return canonical source types represented by one broad UI category."""

    if subject not in VALID_SUBJECTS:
        raise ValueError("invalid_subject")
    if practice_type == "all":
        return frozenset().union(*PRACTICE_TYPE_MEMBERS[subject].values())
    members = PRACTICE_TYPE_MEMBERS[subject].get(practice_type)
    if members is not None:
        return members
    # Backwards compatibility for old snapshots and API callers that still
    # send one canonical type.
    if practice_type in TYPE_LABELS and practice_type != "unknown":
        return frozenset({practice_type})
    raise ValueError("invalid_standard_type")


def broad_practice_type(subject: str, standard_type: str) -> str:
    """Map one canonical source type to its student-facing category."""

    for practice_type in PRACTICE_TYPE_ORDER.get(subject, ()):
        if practice_type != "all" and standard_type in PRACTICE_TYPE_MEMBERS[subject].get(
            practice_type, ()
        ):
            return practice_type
    return "all"


def practice_type_english_label(practice_type: str) -> str:
    return PRACTICE_TYPE_ENGLISH_LABELS.get(
        practice_type,
        TYPE_LABELS.get(practice_type, practice_type),
    )


@dataclass(frozen=True)
class LibraryRoots:
    listening: Path
    reading: Path
    reading_jijing: Path | None = None
    static: Path | None = None
    audio: Path | None = None


def _plain(value) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _instruction(group: dict) -> str:
    return _plain(
        " ".join(str(group.get(key) or "") for key in ("desc", "question_title", "title"))
    ).lower()


def _group_options(group: dict) -> list[dict]:
    options = (group.get("collect_option") or {}).get("list")
    return options if isinstance(options, list) else []


def _questions(group: dict) -> list[dict]:
    questions = group.get("questions")
    return questions if isinstance(questions, list) else []


def canonical_type(group: dict, subject: str) -> tuple[str, str]:
    """Return a stable IELTS type and a source-facing subtype.

    Imported numeric ``type`` values are not globally stable, particularly in
    Reading, so instruction semantics and shared resources take precedence.
    """

    text = _instruction(group)
    image_text = f"{group.get('img_local') or ''} {group.get('img_url') or ''}".lower()
    has_image = bool(image_text.strip())
    options = _group_options(group)
    answer_texts = [str(question.get("answer") or "") for question in _questions(group)]

    if "true" in text and "false" in text and "not given" in text:
        return "true_false_not_given", "judgment"
    if "yes" in text and "no" in text and "not given" in text:
        return "yes_no_not_given", "judgment"
    if "matching headings" in text or "choose the correct heading" in text:
        return "matching_headings", "paragraph-headings"
    if "which paragraph" in text or "contains the following information" in text:
        return "matching_information", "paragraph-information"
    if "match each statement" in text or "match each of the following" in text:
        if "ending" in text:
            return "matching_sentence_endings", "shared-ending-bank"
        return "matching_features", "shared-feature-bank"
    if "sentence ending" in text or "complete each sentence with the correct ending" in text:
        return "matching_sentence_endings", "shared-ending-bank"
    if "matching features" in text:
        return "matching_features", "shared-feature-bank"
    if "matching information" in text:
        return "matching_information", "paragraph-information"

    if "flow-chart" in text or "flow chart" in text or "flowchart" in text:
        return "flow_chart_completion", "structured-completion"
    if "complete the table" in text or (group.get("table") and "complete" in text):
        return "table_completion", "table"
    if "complete the form" in text:
        return "form_completion", "form"
    if "complete the notes" in text or "complete the note" in text:
        return "note_completion", "notes"
    if "complete the summary" in text or "summary below" in text:
        return "summary_completion", "summary"
    if "complete the sentences" in text or "complete each sentence" in text:
        return "sentence_completion", "sentences"

    explicit_image_task = bool(
        re.search(
            r"(?:label|complete|look at)[^.]*(?:\bmap\b|\bplan\b|\bdiagram\b)|"
            r"(?:\bmap\b|\bplan\b|\bdiagram\b)[^.]*(?:below|label)",
            text,
        )
    )
    if "label the chart" in text:
        return "diagram_labelling", "chart-label-bank"
    if has_image or explicit_image_task:
        if re.search(r"\bmap\b", text) or "map" in image_text:
            return "map_labelling", "image-label-bank"
        if re.search(r"\bplan\b", text) or "plan" in image_text:
            return "plan_labelling", "image-label-bank"
        if re.search(r"\bdiagram\b", text) or "diagram" in image_text:
            return "diagram_labelling", "image-label-bank"

    if (
        "short answer" in text
        or "answer the questions" in text
        or (
            "write no more than" in text
            and not group.get("collect")
            and not group.get("table")
            and all(_plain(question.get("title")) for question in _questions(group))
        )
    ):
        return "short_answer", "free-text"
    if "classify" in text or "classification" in text:
        return "classification", "shared-option-bank"

    choose_match = re.search(r"choose\s+(?:the\s+)?(?:correct\s+)?(?:answer|letter|option)", text)
    choose_many = re.search(r"choose\s+(?:two|three|four|five|six|\d+)", text)
    if choose_many or any("," in answer for answer in answer_texts):
        return "multiple_choice_multiple", (
            "shared-stem" if len(_questions(group)) > 1 else "question-options"
        )
    if (
        subject == SUBJECT_READING
        and len(_questions(group)) >= 2
        and all(re.fullmatch(r"[A-Z]", answer.strip().upper()) for answer in answer_texts)
        and not options
        and not any(
            any(
                str(option.get("key") or "").strip().upper() not in {"T", "F", "NG", "Y", "N"}
                for option in question.get("options") or []
            )
            for question in _questions(group)
        )
    ):
        return "matching_information", "paragraph-information-inferred"
    if choose_match or any(question.get("options") for question in _questions(group)):
        return "multiple_choice_single", "question-options"

    if options:
        if any(word in text for word in ("category", "categories", "classify")):
            return "classification", "shared-option-bank"
        if "list" in text and "select" in text:
            return "list_selection", "shared-option-bank"
        return "matching", "shared-option-bank"

    if group.get("collect") or group.get("table"):
        # A completion group can remain publishable even when its source label
        # is vague; the subtype records that human-facing ambiguity.
        return "note_completion", "generic-structured-completion"
    return "unknown", "unclassified"


def renderer_for(group: dict, canonical: str) -> str:
    if canonical in {"map_labelling", "plan_labelling", "diagram_labelling"}:
        return "PracticeRenderers.renderMap / full-test image fallback"
    if canonical.startswith("matching_") or canonical in {
        "matching",
        "classification",
        "list_selection",
    }:
        return "PracticeRenderers.renderMatching"
    if str(group.get("type") or "") == "5" and group.get("collect"):
        return "PracticeRenderers.renderForm"
    if group.get("table"):
        return "PracticeTable.layout + full-test group renderer"
    if group.get("collect"):
        return "PracticeTable.withPlaceholders + full-test group renderer"
    return "full-test questionControl group renderer"


def _question_range(questions: list[dict]) -> str:
    numbers = [
        question.get("number") for question in questions if question.get("number") is not None
    ]
    if not numbers:
        return ""
    return str(numbers[0]) if len(numbers) == 1 else f"{numbers[0]}-{numbers[-1]}"


def _question_marker_ids(group: dict) -> list[str]:
    texts: list[str] = []
    if group.get("collect"):
        texts.append(str(group["collect"]))
    table = group.get("table") or {}
    if isinstance(table, dict):
        texts.append(json.dumps(table.get("content") or [], ensure_ascii=False))
    return re.findall(r"\$(\d+)\$", "\n".join(texts))


def _static_resource_path(static_root: Path | None, value: str) -> Path | None:
    if not static_root or not value:
        return None
    clean = value.split("?", 1)[0].lstrip("/")
    if clean.startswith("static/"):
        clean = clean[len("static/") :]
    return static_root / clean


def validate_group(
    group: dict,
    *,
    subject: str,
    unit: dict,
    canonical: str,
    static_root: Path | None,
    audio_root: Path | None = None,
) -> tuple[str, list[str], list[str], dict]:
    """Return status, blockers, warnings, and resource facts for one group."""

    blockers: list[str] = []
    warnings: list[str] = []
    questions = _questions(group)
    ids = [str(question.get("id") or "") for question in questions]
    numbers = [str(question.get("number") or "") for question in questions]
    answers_present = all(
        bool(str(question.get("answer") or "").strip() or question.get("answers"))
        for question in questions
    )
    if not questions:
        blockers.append("题组没有 questions")
    if any(not value for value in ids) or len(ids) != len(set(ids)):
        blockers.append("题目 ID 缺失或重复")
    if any(not value for value in numbers) or len(numbers) != len(set(numbers)):
        blockers.append("题号缺失或重复")
    if not answers_present:
        blockers.append("正确答案缺失")
    if canonical == "unknown":
        blockers.append("渲染器尚未确认")

    markers = _question_marker_ids(group)
    marker_counts = Counter(markers)
    marker_structured = bool(group.get("collect") or group.get("table"))
    visual_structured = bool(
        group.get("collect") or group.get("table") or group.get("img_local") or group.get("img_url")
    )
    if marker_structured:
        missing_markers = [qid for qid in ids if qid not in marker_counts]
        if missing_markers:
            blockers.append(f"结构题缺少占位符：{','.join(missing_markers[:6])}")
        duplicates = [qid for qid, count in marker_counts.items() if count > 1]
        if duplicates:
            warnings.append(f"占位符重复引用：{','.join(duplicates[:6])}")
        unknown_markers = [qid for qid in marker_counts if qid not in set(ids)]
        if unknown_markers:
            blockers.append(f"占位符关联了题组外 ID：{','.join(unknown_markers[:6])}")
    elif not visual_structured and not any(
        (
            any(_plain(question.get("title")) for question in questions),
            _plain(group.get("title")),
            _plain(group.get("question_title")),
            _plain((group.get("collect_option") or {}).get("title")),
            canonical == "matching_headings" and bool(_group_options(group)),
        )
    ):
        blockers.append("题干丢失或只有孤立输入框")

    needs_options = canonical in {
        "multiple_choice_single",
        "multiple_choice_multiple",
        "matching",
        "classification",
        "list_selection",
        "matching_headings",
        "matching_information",
        "matching_features",
        "matching_sentence_endings",
        "true_false_not_given",
        "yes_no_not_given",
    }
    has_options = bool(_group_options(group)) or all(
        bool(question.get("options")) for question in questions
    )
    implicit_article_options = subject == SUBJECT_READING and canonical in {
        "matching_headings",
        "matching_information",
    }
    if needs_options and not has_options and not implicit_article_options:
        blockers.append("选择/配对题选项缺失")

    image_ref = str(group.get("img_local") or group.get("img_url") or "").strip()
    image_path = _static_resource_path(static_root, image_ref)
    image_exists = bool(image_path and image_path.is_file()) if image_ref else False
    needs_image = canonical in {"map_labelling", "plan_labelling", "diagram_labelling"}
    if needs_image and not image_ref:
        blockers.append("地图、平面图或示意图引用缺失")
    elif needs_image and image_path and not image_exists:
        blockers.append("地图、平面图或示意图文件不存在")

    audio = str(unit.get("audio") or "").strip() if subject == SUBJECT_LISTENING else ""
    effective_audio_root = audio_root or (static_root / "listening" if static_root else None)
    audio_path = effective_audio_root / audio if effective_audio_root and audio else None
    audio_exists = bool(audio_path and audio_path.is_file())
    if subject == SUBJECT_LISTENING and not audio:
        blockers.append("Section 音频引用缺失")
    elif subject == SUBJECT_LISTENING and static_root and not audio_exists:
        blockers.append("Section 音频文件不存在")

    paragraphs = (
        ((unit.get("content") or {}).get("paragraphs") or []) if subject == SUBJECT_READING else []
    )
    has_article = any(
        _plain(paragraph.get("text")) for paragraph in paragraphs if isinstance(paragraph, dict)
    )
    if subject == SUBJECT_READING and not has_article:
        blockers.append("Passage 文章缺失")

    reliable_timestamps = subject == SUBJECT_LISTENING and all(
        isinstance(question.get("start"), (int, float)) and question.get("start") >= 0
        for question in questions
    )
    if subject == SUBJECT_LISTENING and not reliable_timestamps:
        warnings.append("部分题目没有可靠音频时间点")

    status = "blocked" if blockers else "manual_review" if warnings else "publishable"
    return (
        status,
        blockers,
        warnings,
        {
            "has_audio": bool(audio),
            "audio_exists": audio_exists,
            "has_article": has_article,
            "has_image": bool(image_ref),
            "image_exists": image_exists,
            "reliable_audio_timestamps": reliable_timestamps,
        },
    )


def _iter_payload_paths(roots: LibraryRoots, subject: str) -> Iterable[Path]:
    if subject == SUBJECT_LISTENING:
        yield from sorted(roots.listening.glob("*.json"))
        return
    yield from sorted(roots.reading.glob("*.json"))
    if roots.reading_jijing:
        offline_ids = load_offline_test_ids(roots.reading_jijing)
        yield from (
            path
            for path in sorted(roots.reading_jijing.glob("*.json"))
            if path.name != "offline_tests.json" and path.stem not in offline_ids
        )


def _is_test_payload(payload: dict, subject: str) -> bool:
    key = "sections" if subject == SUBJECT_LISTENING else "passages"
    return isinstance(payload.get(key), list)


def build_group_index(roots: LibraryRoots) -> list[dict]:
    rows: list[dict] = []
    for subject in (SUBJECT_LISTENING, SUBJECT_READING):
        unit_key = "sections" if subject == SUBJECT_LISTENING else "passages"
        unit_label = "Section" if subject == SUBJECT_LISTENING else "Passage"
        for path in _iter_payload_paths(roots, subject):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not _is_test_payload(raw, subject):
                continue
            for unit_index, unit in enumerate(raw.get(unit_key) or []):
                for group_index, group in enumerate(unit.get("groups") or []):
                    canonical, subtype = canonical_type(group, subject)
                    questions = _questions(group)
                    source_group_id = str(group.get("group_id") or f"g{group_index + 1}")
                    group_id = f"{subject}:{path.stem}:{unit_index + 1}:{source_group_id}"
                    status, blockers, warnings, resources = validate_group(
                        group,
                        subject=subject,
                        unit=unit,
                        canonical=canonical,
                        static_root=roots.static,
                        audio_root=roots.audio,
                    )
                    rows.append(
                        {
                            "question_group_id": group_id,
                            "subject": subject,
                            "standard_type": canonical,
                            "standard_type_label": TYPE_LABELS[canonical],
                            "standard_type_display_label": question_type_display_label(canonical),
                            "subtype": subtype,
                            "renderer": renderer_for(group, canonical),
                            "source_file": str(path),
                            "source": raw.get("source") or "cambridge",
                            "test_id": raw.get("id") or path.stem,
                            "test_title": raw.get("title") or path.stem,
                            "unit_index": unit_index,
                            "unit_number": unit.get("section")
                            or unit.get("passage")
                            or unit_index + 1,
                            "unit_label": unit_label,
                            "unit_id": unit.get("id") or "",
                            "group_index": group_index,
                            "source_group_id": source_group_id,
                            "original_question_range": _question_range(questions),
                            "question_count": len(questions),
                            "source_numeric_type": group.get("type"),
                            "instruction": group.get("desc") or "",
                            "title": group.get("title") or group.get("question_title") or "",
                            "supports_full_test": status != "blocked",
                            "supports_specialty_practice": status == "publishable",
                            "supports_teacher_push": status == "publishable",
                            "supports_review": status != "blocked",
                            "needs_full_article": subject == SUBJECT_READING,
                            "needs_full_section_audio": subject == SUBJECT_LISTENING,
                            "has_unconfirmed_groups": canonical == "unknown",
                            "has_missing_resources": bool(
                                (resources["has_audio"] and not resources["audio_exists"])
                                or (resources["has_image"] and not resources["image_exists"])
                            ),
                            "safety_status": status,
                            "blockers": blockers,
                            "warnings": warnings,
                            **resources,
                        }
                    )
    return rows


def summarize_inventory(rows: list[dict]) -> dict:
    buckets: dict[tuple[str, str, str, str], dict] = {}
    for row in rows:
        key = (
            row["subject"],
            row["standard_type"],
            row["subtype"],
            row["renderer"],
        )
        bucket = buckets.setdefault(
            key,
            {
                "subject": row["subject"],
                "standard_type": row["standard_type"],
                "standard_type_label": row["standard_type_label"],
                "standard_type_display_label": row["standard_type_display_label"],
                "subtype": row["subtype"],
                "renderer": row["renderer"],
                "group_count": 0,
                "question_count": 0,
                "supports_full_test": True,
                "supports_specialty_practice": True,
                "supports_teacher_push": True,
                "supports_review": True,
                "needs_full_article": False,
                "needs_full_section_audio": False,
                "has_reliable_audio_timestamps": True,
                "unconfirmed_group_count": 0,
                "missing_resource_group_count": 0,
                "blocked_group_count": 0,
                "manual_review_group_count": 0,
                "representative_group_id": row["question_group_id"],
            },
        )
        bucket["group_count"] += 1
        bucket["question_count"] += row["question_count"]
        bucket["supports_full_test"] &= row["supports_full_test"]
        bucket["supports_specialty_practice"] &= row["supports_specialty_practice"]
        bucket["supports_teacher_push"] &= row["supports_teacher_push"]
        bucket["supports_review"] &= row["supports_review"]
        bucket["needs_full_article"] |= row["needs_full_article"]
        bucket["needs_full_section_audio"] |= row["needs_full_section_audio"]
        bucket["has_reliable_audio_timestamps"] &= row["reliable_audio_timestamps"]
        bucket["unconfirmed_group_count"] += int(row["has_unconfirmed_groups"])
        bucket["missing_resource_group_count"] += int(row["has_missing_resources"])
        bucket["blocked_group_count"] += int(row["safety_status"] == "blocked")
        bucket["manual_review_group_count"] += int(row["safety_status"] == "manual_review")
    counts = Counter(row["safety_status"] for row in rows)
    return {
        "schema_version": SNAPSHOT_VERSION,
        "summary": {
            "group_count": len(rows),
            "question_count": sum(row["question_count"] for row in rows),
            "publishable_group_count": counts["publishable"],
            "manual_review_group_count": counts["manual_review"],
            "blocked_group_count": counts["blocked"],
        },
        "types": sorted(
            buckets.values(), key=lambda row: (row["subject"], row["standard_type"], row["subtype"])
        ),
        "groups": rows,
    }


def filter_groups(
    rows: list[dict],
    *,
    subject: str,
    standard_type: str,
    scope: str = "all",
    count: int = 1,
    exclude_group_ids: Iterable[str] = (),
) -> list[dict]:
    allowed_types = practice_type_members(subject, standard_type)
    count = max(1, min(int(count or 1), 20))
    excluded = set(exclude_group_ids)
    candidates = [
        row
        for row in rows
        if row["subject"] == subject
        and row["standard_type"] in allowed_types
        and row["safety_status"] == "publishable"
        and row["question_group_id"] not in excluded
    ]
    clean_scope = _plain(scope)
    candidates = [row for row in candidates if _matches_scope(row, clean_scope)]
    return candidates[:count]


def filter_unit_groups(
    rows: list[dict],
    *,
    subject: str,
    standard_type: str,
    scope: str = "all",
    unit_count: int = 6,
    exclude_group_ids: Iterable[str] = (),
) -> list[dict]:
    """Return every matching group from the first N Sections or Passages."""

    allowed_types = practice_type_members(subject, standard_type)
    limit = max(1, min(int(unit_count or 1), 20))
    excluded = set(exclude_group_ids)
    candidates = [
        row
        for row in rows
        if row["subject"] == subject
        and row["standard_type"] in allowed_types
        and row["safety_status"] == "publishable"
        and row["question_group_id"] not in excluded
    ]
    clean_scope = _plain(scope)
    candidates = [row for row in candidates if _matches_scope(row, clean_scope)]

    selected: list[dict] = []
    unit_keys: list[tuple[str, int]] = []
    for row in candidates:
        unit_key = (row["source_file"], row["unit_index"])
        if unit_key not in unit_keys:
            if len(unit_keys) >= limit:
                break
            unit_keys.append(unit_key)
        selected.append(row)
    return selected


def cambridge_test_numbers(row: dict) -> tuple[int, int] | None:
    """Return Cambridge volume/test numbers for one canonical catalog row."""

    match = CAMBRIDGE_TEST_RE.fullmatch(_plain(row.get("test_id")))
    if not match:
        return None
    return int(match.group("volume")), int(match.group("test"))


def _matches_scope(row: dict, clean_scope: str) -> bool:
    if not clean_scope or clean_scope == "all":
        return True
    numbers = cambridge_test_numbers(row)
    if clean_scope == "cambridge:all":
        return numbers is not None
    if clean_scope.startswith("cambridge:"):
        try:
            volume = int(clean_scope.split(":", 1)[1])
        except ValueError:
            return False
        return bool(numbers and numbers[0] == volume)
    return bool(
        clean_scope in {row["test_id"], row["source"], Path(row["source_file"]).parent.name}
        or clean_scope.lower() in row["test_title"].lower()
    )


def catalog_unit_groups(
    rows: list[dict],
    *,
    subject: str,
    standard_type: str,
    scope: str = "cambridge:all",
) -> list[dict]:
    """Return all safe groups for a browsable Section/Passage catalog.

    The catalog is intentionally not capped at the first N units. Cambridge
    volumes sort newest-first, while tests, units and source groups retain
    their natural order inside each volume.
    """

    allowed_types = practice_type_members(subject, standard_type)
    clean_scope = _plain(scope) or "cambridge:all"
    candidates = [
        row
        for row in rows
        if row["subject"] == subject
        and row["standard_type"] in allowed_types
        and row["safety_status"] == "publishable"
        and _matches_scope(row, clean_scope)
    ]

    def sort_key(row: dict) -> tuple:
        numbers = cambridge_test_numbers(row)
        if numbers:
            volume, test_number = numbers
            return (0, -volume, test_number, row["unit_index"], row["group_index"])
        return (
            1,
            row["test_title"].lower(),
            row["unit_index"],
            row["group_index"],
        )

    return sorted(candidates, key=sort_key)


def _rewrite_markers(value, id_map: dict[str, str]):
    if isinstance(value, list):
        return [_rewrite_markers(item, id_map) for item in value]
    if isinstance(value, dict):
        return {key: _rewrite_markers(item, id_map) for key, item in value.items()}
    if not isinstance(value, str):
        return value
    return re.sub(
        r"\$(\d+)\$", lambda match: f"${id_map.get(match.group(1), match.group(1))}$", value
    )


def _redact_payload(payload: dict) -> dict:
    hidden = {
        "answer",
        "answers",
        "analysis",
        "answer_sentences",
        "central_sentences",
        "locating_words",
        "translation",
        "transcript",
        "scripts",
    }
    if isinstance(payload, list):
        return [
            _redact_payload(item) if isinstance(item, (dict, list)) else item for item in payload
        ]
    if not isinstance(payload, dict):
        return payload
    return {
        key: _redact_payload(value) if isinstance(value, (dict, list)) else value
        for key, value in payload.items()
        if key not in hidden
    }


def build_snapshot(
    selected_rows: list[dict],
    *,
    pace: str,
    standard_type: str,
    roots: LibraryRoots,
) -> dict:
    if pace not in VALID_PACES:
        raise ValueError("invalid_pace")
    if not selected_rows:
        raise ValueError("no_publishable_groups")
    subject = selected_rows[0]["subject"]
    if any(row["subject"] != subject for row in selected_rows):
        raise ValueError("mixed_subjects")
    if any(row["safety_status"] != "publishable" for row in selected_rows):
        raise ValueError("unsafe_group_selected")
    allowed_types = practice_type_members(subject, standard_type)
    if any(row["standard_type"] not in allowed_types for row in selected_rows):
        raise ValueError("unsafe_group_selected")

    source_cache: dict[str, dict] = {}
    grouped: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for row in selected_rows:
        grouped[(row["source_file"], row["unit_index"])].append(row)

    output_units: list[dict] = []
    refs: list[dict] = []
    display_number = 1
    for (source_file, unit_index), unit_rows in grouped.items():
        if source_file not in source_cache:
            source_cache[source_file] = json.loads(Path(source_file).read_text(encoding="utf-8"))
        raw = source_cache[source_file]
        unit_key = "sections" if subject == SUBJECT_LISTENING else "passages"
        source_unit = copy.deepcopy(raw[unit_key][unit_index])
        source_groups = source_unit.get("groups") or []
        selected_groups: list[dict] = []
        for row in sorted(unit_rows, key=lambda item: item["group_index"]):
            group = copy.deepcopy(source_groups[row["group_index"]])
            source_questions = _questions(group)
            combined_answer = (
                str(source_questions[0].get("answer") or "") if source_questions else ""
            )
            if (
                str(group.get("type") or "") == "2"
                and _group_options(group)
                and "," in combined_answer
                and all(
                    str(question.get("answer") or "") == combined_answer
                    for question in source_questions
                )
            ):
                group["response_layout"] = "combined_multi"
                group["max_selections"] = len(source_questions)
            id_map: dict[str, str] = {}
            for question in _questions(group):
                if question.get("options") and "," in str(question.get("answer") or ""):
                    question["response_kind"] = "multiple_choice_multiple"
                    question["max_selections"] = len(
                        [
                            item
                            for item in str(question.get("answer") or "").split(",")
                            if item.strip()
                        ]
                    )
                elif _group_options(group) and str(group.get("type") or "") != "2":
                    question["uses_group_options"] = True
                    question["response_kind"] = "group_select"
                source_id = str(question.get("id") or question.get("number"))
                # Numeric ids keep both templates' placeholder regexes and CSS
                # selectors compatible while remaining unique in one snapshot.
                snapshot_id = str(9_000_000_000 + display_number)
                id_map[source_id] = snapshot_id
                question["source_question_id"] = source_id
                question["source_number"] = question.get("number")
                question["id"] = int(snapshot_id)
                question["number"] = display_number
                display_number += 1
            group = _rewrite_markers(group, id_map)
            group["question_group_id"] = row["question_group_id"]
            group["standard_type"] = row["standard_type"]
            group["standard_type_label"] = row["standard_type_label"]
            group["standard_type_display_label"] = row["standard_type_display_label"]
            group["source_meta"] = {
                "test_id": row["test_id"],
                "test_title": row["test_title"],
                "unit_label": row["unit_label"],
                "unit_number": row["unit_number"],
                "original_question_range": row["original_question_range"],
            }
            selected_groups.append(group)
            refs.append(
                {
                    "question_group_id": row["question_group_id"],
                    "test_id": row["test_id"],
                    "test_title": row["test_title"],
                    "unit_label": row["unit_label"],
                    "unit_number": row["unit_number"],
                    "original_question_range": row["original_question_range"],
                    "standard_type": row["standard_type"],
                    "standard_type_label": row["standard_type_label"],
                    "standard_type_display_label": row["standard_type_display_label"],
                    "renderer": row["renderer"],
                }
            )
        source_unit["groups"] = selected_groups
        source_unit["question_name"] = (
            f"Q{selected_groups[0]['questions'][0]['number']}-{selected_groups[-1]['questions'][-1]['number']}"
        )
        source_unit["question_type"] = list(
            dict.fromkeys(
                question_type_display_label(broad_practice_type(subject, row["standard_type"]))
                for row in unit_rows
            )
        )
        source_unit["source_test_id"] = raw.get("id") or Path(source_file).stem
        output_units.append(source_unit)

    payload_id = f"question_type_{subject}_{hashlib.sha256('|'.join(row['question_group_id'] for row in selected_rows).encode()).hexdigest()[:12]}"
    payload = {
        "id": payload_id,
        "title": f"IELTS {question_type_display_label(standard_type)}专项",
        "source": "question_type_practice",
        "specialty_type": standard_type,
        "sections" if subject == SUBJECT_LISTENING else "passages": output_units,
    }
    payload = normalize_practice_tables(payload)
    canonical = {
        "schema_version": SNAPSHOT_VERSION,
        "task_type": TASK_TYPE,
        "subject": subject,
        "pace": pace,
        "standard_type": standard_type,
        "standard_type_label": practice_type_english_label(standard_type),
        "standard_type_display_label": question_type_display_label(standard_type),
        "group_ids": [row["question_group_id"] for row in selected_rows],
        "group_refs": refs,
        "question_count": display_number - 1,
        "payload": payload,
    }
    encoded = json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    canonical["snapshot_hash"] = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    return canonical


def public_snapshot(snapshot: dict) -> dict:
    """Return the pre-submission payload without any solution or review data."""

    public = copy.deepcopy(snapshot)
    public["payload"] = _redact_payload(public["payload"])
    return public


def snapshot_from_task(task) -> dict | None:
    if getattr(task, "grading_mode", None) != TASK_TYPE:
        return None
    try:
        data = json.loads(task.question_ids or "{}")
    except (TypeError, json.JSONDecodeError):
        return None
    if data.get("task_type") != TASK_TYPE or not isinstance(data.get("payload"), dict):
        return None
    return data


def dump_snapshot(snapshot: dict) -> str:
    return json.dumps(snapshot, ensure_ascii=False, separators=(",", ":"))
