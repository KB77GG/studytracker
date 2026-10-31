"""Validated, notification-free resource adapters for scheduled assignments."""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
from datetime import date
from functools import lru_cache
from pathlib import Path

from flask import current_app
from sqlalchemy import func
from werkzeug.utils import secure_filename

from api.listening_series import parse_intensive_id
from models import (
    DictationBook,
    DictationWord,
    PlanItem,
    StudyPlan,
    Task,
    db,
    utcnow_naive,
)
from services.dictation_assignment_range import dictation_range_error
from services.listening_training import TRAINING_MODE_OPTIONS, VALID_TRAINING_MODES
from services.practice_library_offline import load_offline_test_ids
from services.question_type_assignments import assignment_title, create_assignment
from services.question_type_practice import (
    PRACTICE_TYPE_ORDER,
    LibraryRoots,
    build_group_index,
    build_snapshot,
    canonical_type,
    practice_type_members,
    question_type_display_label,
    snapshot_from_task,
    validate_group,
)
from services.task_assignment_duplicates import resource_identity_from_payload

KINDS = frozenset(
    {"question_type", "reading_passage", "listening_test", "intensive", "dictation"}
)
GOALS = frozenset({"reading", "writing", "listening", "comprehensive"})
DICTATION_MODES = frozenset({"audio_to_en", "zh_to_en", "en_to_zh", "spelling_drill"})


def _root():
    return Path(
        current_app.config.get("TASK_PLANNER_ROOT")
        or Path(__file__).resolve().parents[1]
    )


def _roots():
    root = _root()
    audio = current_app.config.get("TASK_PLANNER_AUDIO_ROOT")
    if not audio and not current_app.config.get("TASK_PLANNER_ROOT"):
        audio = os.environ.get("STUDYTRACKER_AUDIO_ROOT")
    return LibraryRoots(
        listening=root / "static/listening_tests",
        reading=root / "static/reading_tests",
        reading_jijing=root / "static/reading_jijing",
        static=root / "static",
        audio=Path(audio) if audio else root / "static/listening",
    )


def _digest(value):
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode()).hexdigest()


def _integer(value, label, minimum=1, maximum=None):
    if isinstance(value, bool) or not str(value).isdigit():
        raise ValueError(f"{label}必须是整数")
    number = int(value)
    if number < minimum or (maximum is not None and number > maximum):
        raise ValueError(f"{label}超出允许范围")
    return number


def _json_file(directory, resource_id):
    if not resource_id or secure_filename(resource_id) != resource_id:
        raise ValueError("资源标识无效")
    path = directory / f"{resource_id}.json"
    if path.resolve().parent != directory.resolve():
        raise ValueError("资源标识无效")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError("所选资源不存在或不可读取") from exc
    if not isinstance(payload, dict) or payload.get("hidden_from_catalog"):
        raise ValueError("所选资源已下线")
    return payload


def _library_signature(roots):
    result = []
    for directory in (roots.listening, roots.reading, roots.reading_jijing):
        for path in sorted(directory.glob("*.json")):
            stat = path.stat()
            result.append((str(path), stat.st_mtime_ns, stat.st_size))
    # Detect an added/deleted local audio file without reading its contents.
    if roots.audio.exists():
        result.append((str(roots.audio), roots.audio.stat().st_mtime_ns, 0))
    return tuple(result)


@lru_cache(maxsize=4)
def _cached_groups(paths, signature):
    del signature
    roots = LibraryRoots(**{key: Path(value) for key, value in paths})
    available = {}
    result = []
    for row in build_group_index(roots):
        path = Path(row["source_file"])
        if path not in available:
            try:
                _json_file(path.parent, path.stem)
                available[path] = path.stem not in load_offline_test_ids(path.parent)
            except ValueError:
                available[path] = False
        if available[path]:
            result.append(row)
    return tuple(result)


def _groups():
    roots = _roots()
    paths = tuple(
        (key, str(getattr(roots, key)))
        for key in ("listening", "reading", "reading_jijing", "static", "audio")
    )
    return _cached_groups(paths, _library_signature(roots))


def _question_catalog(filters):
    subject = str(filters.get("subject") or "reading")
    if subject not in PRACTICE_TYPE_ORDER:
        raise ValueError("请选择阅读或听力")
    standard_type = str(filters.get("standard_type") or "all")
    allowed = practice_type_members(subject, standard_type)
    items = []
    for row in _groups():
        if (
            row["subject"] != subject
            or row["standard_type"] not in allowed
            or row["safety_status"] != "publishable"
        ):
            continue
        label = f"{row['test_title']} · {row['unit_label']} {row['unit_number']} · {row['original_question_range']} · {row['standard_type_display_label']}"
        items.append(
            {
                "id": row["question_group_id"],
                "label": label,
                "test_id": row["test_id"],
                "test_title": row["test_title"],
                "unit_label": row["unit_label"],
                "unit_number": row["unit_number"],
                "range": row["original_question_range"],
                "standard_type": row["standard_type"],
                "question_count": row["question_count"],
                "selection": {
                    "subject": subject,
                    "standard_type": standard_type,
                    "group_ids": [row["question_group_id"]],
                    "pace": "training",
                },
            }
        )
    return items, {
        "types": [
            {"id": key, "label": question_type_display_label(key)}
            for key in PRACTICE_TYPE_ORDER[subject]
        ]
    }


def _reading_payload(test_id):
    if not test_id or secure_filename(test_id) != test_id:
        raise ValueError("阅读资源标识无效")
    roots = _roots()
    for directory in (roots.reading, roots.reading_jijing):
        if test_id in load_offline_test_ids(directory):
            raise ValueError("所选篇章已下线")
        if (directory / f"{test_id}.json").is_file():
            payload = _json_file(directory, test_id)
            if not isinstance(payload.get("passages"), list):
                raise ValueError("所选资源不是阅读练习")
            return payload
    raise ValueError("所选阅读练习不存在")


def _reading_catalog():
    items, seen = [], set()
    roots = _roots()
    for directory in (roots.reading, roots.reading_jijing):
        for path in sorted(directory.glob("*.json")):
            if path.stem in seen:
                continue
            seen.add(path.stem)
            try:
                payload = _reading_payload(path.stem)
            except ValueError:
                continue
            for index, passage in enumerate(payload["passages"], 1):
                number = int(passage.get("passage") or index)
                if not passage.get("groups"):
                    continue
                selection = {"test_id": path.stem, "passage_number": number}
                items.append(
                    {
                        "id": f"{path.stem}:{number}",
                        "label": f"{payload.get('title') or path.stem} · Passage {number}",
                        "test_id": path.stem,
                        "passage_number": number,
                        "selection": selection,
                    }
                )
    return items, {}


def _listening_payload(test_id):
    roots = _roots()
    if test_id in load_offline_test_ids(roots.listening):
        raise ValueError("所选听力已下线")
    payload = _json_file(roots.listening, test_id)
    sections = payload.get("sections")
    if not isinstance(sections, list) or not sections:
        raise ValueError("所选资源没有听力 Section")
    numbers = []
    for section in sections:
        if not isinstance(section, dict):
            raise ValueError("听力 Section 数据无效")
        numbers.append(_integer(section.get("section"), "Section 序号", maximum=4))
    if len(numbers) != len(set(numbers)):
        raise ValueError("听力 Section 序号重复")
    return payload


def _listening_section_questions(section):
    """Validate whole-section playback without requiring question timestamps."""
    roots = _roots()
    audio = str(section.get("audio") or "").strip()
    audio_root = roots.audio.resolve()
    candidate = (audio_root / audio).resolve()
    if (
        not audio
        or Path(audio).is_absolute()
        or not candidate.is_relative_to(audio_root)
        or not candidate.is_file()
    ):
        raise ValueError("听力 Section 音频不可用")
    groups = section.get("groups")
    if not isinstance(groups, list) or not groups:
        raise ValueError("所选听力 Section 没有题目")
    questions = []
    for group in groups:
        if (
            not isinstance(group, dict)
            or not isinstance(group.get("questions"), list)
            or any(not isinstance(row, dict) for row in group["questions"])
        ):
            raise ValueError("听力题组数据无效")
        canonical, _subtype = canonical_type(group, "listening")
        _status, blockers, _warnings, _assets = validate_group(
            group,
            subject="listening",
            unit=section,
            canonical=canonical,
            static_root=roots.static,
            audio_root=roots.audio,
        )
        # Whole-section playback remains valid without per-question cue points.
        if blockers:
            raise ValueError("所选听力题组暂不可布置")
        questions.extend(group["questions"])
    ids = [str(row.get("id")) for row in questions]
    numbers = [_integer(row.get("number"), "听力题号") for row in questions]
    if len(ids) != len(set(ids)) or len(numbers) != len(set(numbers)):
        raise ValueError("听力 Section 题目 ID 或题号重复")
    return numbers


def _complete_listening_test(sections):
    return set(sections) == {1, 2, 3, 4} and sorted(
        number for numbers in sections.values() for number in numbers
    ) == list(range(1, 41))


def _listening_catalog(filters):
    scope = str(filters.get("scope") or "all")
    if scope not in {"all", "test", "section"}:
        raise ValueError("请选择整套 Test 或 Section")
    items = []
    paths = sorted(
        _roots().listening.glob("*.json"),
        key=lambda path: [
            int(part) if part.isdigit() else part
            for part in re.split(r"(\d+)", path.stem)
        ],
    )
    for path in paths:
        try:
            source = _listening_payload(path.stem)
        except ValueError:
            continue
        valid = []
        for section in sorted(source["sections"], key=lambda row: int(row["section"])):
            try:
                numbers = _listening_section_questions(section)
            except ValueError:
                continue
            valid.append((int(section["section"]), numbers))
        options = []
        if scope != "section" and _complete_listening_test(dict(valid)):
            options.append((None, 40))
        if scope != "test":
            options.extend((number, len(numbers)) for number, numbers in valid)
        for number, count in options:
            label = f"Section {number}" if number is not None else "整套 Test"
            items.append(
                {
                    "id": f"{path.stem}:{number if number is not None else 'all'}",
                    "label": f"{source.get('title') or path.stem} · {label}",
                    "test_id": path.stem,
                    "section_number": number,
                    "question_count": count,
                    "selection": {"test_id": path.stem, "section_number": number},
                }
            )
    return items, {}


def _intensive_payload(exercise_id):
    if not parse_intensive_id(exercise_id):
        raise ValueError("请选择已注册的精听资源")
    payload = _json_file(_root() / "static/listening", exercise_id)
    audio = str(payload.get("audio") or "")
    audio_root = _roots().audio.resolve()
    candidate = (audio_root / audio).resolve()
    if not audio or candidate.parent != audio_root or not candidate.is_file():
        raise ValueError("精听音频不可用")
    return payload


def _intensive_catalog():
    items = []
    for path in sorted((_root() / "static/listening").glob("*.json")):
        try:
            payload = _intensive_payload(path.stem)
        except ValueError:
            continue
        count = sum(
            len(part.get("segments") or []) for part in payload.get("parts") or []
        )
        if count:
            items.append(
                {
                    "id": path.stem,
                    "label": payload.get("title") or path.stem,
                    "segment_count": count,
                    "selection": {"exercise_id": path.stem, "training_mode": "system"},
                }
            )
    return items, {
        "training_modes": [
            {"id": row["key"], "label": row["label"]} for row in TRAINING_MODE_OPTIONS
        ]
    }


def _dictation_catalog():
    items = []
    books = (
        DictationBook.query.filter_by(is_deleted=False, is_active=True)
        .order_by(DictationBook.title)
        .all()
    )
    stats = {
        book_id: (count, last)
        for book_id, count, last in db.session.query(
            DictationWord.book_id,
            func.count(DictationWord.id),
            func.max(DictationWord.sequence),
        ).group_by(DictationWord.book_id)
    }
    for book in books:
        count, last = stats.get(book.id, (0, 0))
        if not count:
            continue
        goal = (
            book.default_vocabulary_goal
            if book.default_vocabulary_goal in GOALS
            else "reading"
        )
        items.append(
            {
                "id": book.id,
                "label": book.title,
                "word_count": count,
                "last_sequence": last,
                "selection": {
                    "book_id": book.id,
                    "word_start": 1,
                    "word_end": last,
                    "vocabulary_goal": goal,
                    "dictation_mode": "audio_to_en",
                    "dictation_order": "sequence",
                },
            }
        )
    return items, {}


def catalog(kind, filters=None):
    """Bounded staff picker output with no answers or arbitrary file paths."""
    filters = dict(filters or {})
    if kind not in KINDS:
        raise ValueError("暂不支持此任务类型")
    limit = _integer(filters.get("limit", 50), "每页数量", maximum=100)
    offset = _integer(filters.get("offset", 0), "偏移量", minimum=0)
    if kind == "question_type":
        items, extra = _question_catalog(filters)
    elif kind == "listening_test":
        items, extra = _listening_catalog(filters)
    else:
        items, extra = {
            "reading_passage": _reading_catalog,
            "intensive": _intensive_catalog,
            "dictation": _dictation_catalog,
        }[kind]()
    query = str(filters.get("query") or "").strip().casefold()
    if query:
        items = [
            row
            for row in items
            if query in str(row["label"]).casefold()
            or query in str(row["id"]).casefold()
        ]
    return {
        "items": items[offset : offset + limit],
        "total": len(items),
        "limit": limit,
        "offset": offset,
        "types": [],
        **extra,
    }


def _prepare_question(payload):
    subject, standard_type = (
        str(payload.get("subject") or ""),
        str(payload.get("standard_type") or ""),
    )
    allowed = practice_type_members(subject, standard_type)
    ids = payload.get("group_ids")
    if (
        not isinstance(ids, list)
        or not 1 <= len(ids) <= 20
        or any(not isinstance(value, str) for value in ids)
    ):
        raise ValueError("请明确选择1至20个完整题组")
    if len(ids) != len(set(ids)):
        raise ValueError("所选题组重复")
    index = {row["question_group_id"]: row for row in _groups()}
    selected = [index.get(value) for value in ids]
    if any(
        row is None
        or row["subject"] != subject
        or row["standard_type"] not in allowed
        or row["safety_status"] != "publishable"
        for row in selected
    ):
        raise ValueError("所选题组不存在、题型不符或暂不可布置")
    # The directory signature caches enumeration only. Validate selected assets
    # again so removed audio/images cannot be accepted from a stale catalog.
    roots = _roots()
    for row in selected:
        path = Path(row["source_file"])
        source = _json_file(path.parent, path.stem)
        units = source["sections" if subject == "listening" else "passages"]
        unit = units[row["unit_index"]]
        group = unit["groups"][row["group_index"]]
        status, _blockers, _warnings, _assets = validate_group(
            group,
            subject=subject,
            unit=unit,
            canonical=row["standard_type"],
            static_root=roots.static,
            audio_root=roots.audio,
        )
        if status != "publishable":
            raise ValueError("所选题组资源已变化或不可布置")
    pace = str(payload.get("pace") or "training")
    snapshot = build_snapshot(
        selected, pace=pace, standard_type=standard_type, roots=_roots()
    )
    selection = {
        "subject": subject,
        "standard_type": standard_type,
        "group_ids": ids,
        "pace": pace,
    }
    coverage = [
        {
            "subject": subject,
            "test_id": row["test_id"],
            "unit_number": int(row["unit_number"]),
            "group_id": row["question_group_id"],
        }
        for row in selected
    ]
    return {
        "title": assignment_title(snapshot),
        "selection": selection,
        "snapshot": snapshot,
        "content_hash": snapshot["snapshot_hash"],
        "coverage_units": coverage,
        "duplicate_payload": {"source": "question_type", **selection},
    }


def _prepare_reading(payload):
    test_id = str(payload.get("test_id") or "").strip()
    number = _integer(payload.get("passage_number"), "篇章序号")
    source = _reading_payload(test_id)
    matches = [
        row
        for index, row in enumerate(source["passages"], 1)
        if int(row.get("passage") or index) == number
    ]
    if len(matches) != 1 or not matches[0].get("groups"):
        raise ValueError("所选篇章不存在或没有题目")
    return {
        "title": f"{source.get('title') or test_id} Passage {number}",
        "selection": {"test_id": test_id, "passage_number": number},
        "content_hash": _digest(source),
        "metadata": {"source": source.get("source")},
        "coverage_units": [
            {
                "subject": "reading",
                "test_id": source.get("id") or test_id,
                "unit_number": number,
                "whole": True,
            }
        ],
        "duplicate_payload": {
            "source": "reading",
            "reading_test_id": test_id,
            "reading_passage_number": number,
        },
    }


def _prepare_listening(payload):
    test_id = str(payload.get("test_id") or "").strip()
    value = payload.get("section_number")
    number = None if value in (None, "") else _integer(value, "Section 序号", maximum=4)
    source = _listening_payload(test_id)
    selected = [
        section
        for section in source["sections"]
        if number is None or int(section["section"]) == number
    ]
    if not selected:
        raise ValueError("所选听力 Section 不存在")
    selected.sort(key=lambda row: int(row["section"]))
    ranges = [
        {
            "section_number": int(section["section"]),
            "question_numbers": _listening_section_questions(section),
        }
        for section in selected
    ]
    if number is None and not _complete_listening_test(
        {row["section_number"]: row["question_numbers"] for row in ranges}
    ):
        raise ValueError("整套听力须包含 Section 1–4 及完整的第1–40题，请改选 Section")
    label = f"Section {number}" if number is not None else "整套 Test"
    return {
        "title": f"{source.get('title') or test_id} · {label}",
        "selection": {"test_id": test_id, "section_number": number},
        "content_hash": _digest(source),
        "metadata": {
            "question_ranges": ranges,
            "question_count": sum(len(row["question_numbers"]) for row in ranges),
        },
        "coverage_units": [
            {
                "subject": "listening",
                "test_id": source.get("id") or test_id,
                "unit_number": row["section_number"],
                "whole": True,
            }
            for row in ranges
        ],
        "duplicate_payload": {
            "source": "listening",
            "listening_resource_type": "cambridge_test",
            "listening_exercise_id": test_id,
            "listening_section_number": number,
        },
    }


def _prepare_intensive(payload):
    exercise_id = str(payload.get("exercise_id") or "").strip()
    source = _intensive_payload(exercise_id)
    mode = str(payload.get("training_mode") or "system")
    if mode not in VALID_TRAINING_MODES:
        raise ValueError("精听训练方式无效")
    count = sum(len(part.get("segments") or []) for part in source.get("parts") or [])
    if not count:
        raise ValueError("所选精听没有可练习句子")
    return {
        "title": source.get("title") or exercise_id,
        "selection": {"exercise_id": exercise_id, "training_mode": mode},
        "content_hash": _digest(source),
        "metadata": {"segment_count": count},
        "coverage_units": [],
        "duplicate_payload": {
            "source": "listening",
            "listening_exercise_id": exercise_id,
            "listening_resource_type": "intensive",
        },
    }


def _prepare_dictation(payload):
    book_id = _integer(payload.get("book_id"), "词书ID")
    book = db.session.get(DictationBook, book_id)
    if not book or book.is_deleted or not book.is_active:
        raise ValueError("词书不存在或已停用")
    start, end = (
        _integer(payload.get("word_start"), "起始词序"),
        _integer(payload.get("word_end"), "结束词序"),
    )
    error = dictation_range_error(book_id, start, end)
    if error:
        raise ValueError(error)
    goal = str(payload.get("vocabulary_goal") or "")
    mode, order = (
        str(payload.get("dictation_mode") or "audio_to_en"),
        str(payload.get("dictation_order") or "sequence"),
    )
    if (
        goal not in GOALS
        or mode not in DICTATION_MODES
        or order not in {"sequence", "random"}
    ):
        raise ValueError("请选择有效的词汇目标和训练方式")
    words = (
        DictationWord.query.filter(
            DictationWord.book_id == book_id, DictationWord.sequence.between(start, end)
        )
        .order_by(DictationWord.sequence, DictationWord.id)
        .all()
    )
    if len(words) > 1200:
        raise ValueError("单次词汇任务最多1200词，请缩小范围")
    columns = (
        "id",
        "sequence",
        "word",
        "translation",
        "accepted_answers",
        "sense_id",
        "core_meaning_zh",
        "example_en",
        "example_zh",
        "usage_pattern",
    )
    frozen = [{key: getattr(word, key) for key in columns} for word in words]
    selection = {
        "book_id": book_id,
        "word_start": start,
        "word_end": end,
        "vocabulary_goal": goal,
        "dictation_mode": mode,
        "dictation_order": order,
    }
    return {
        "title": f"{book.title} · 第{start}–{end}词",
        "selection": selection,
        "content_hash": _digest(frozen),
        "metadata": {"word_count": len(words), "word_ids": [row.id for row in words]},
        "coverage_units": [],
        "duplicate_payload": {
            "source": "material",
            "dictation_book_id": book_id,
            "dictation_word_start": start,
            "dictation_word_end": end,
        },
    }


def prepare_resource(kind, payload):
    """Construct trusted metadata from selection; client snapshots are ignored."""
    if kind not in KINDS or not isinstance(payload, dict):
        raise ValueError("任务类型或选择内容无效")
    adapters = {
        "question_type": _prepare_question,
        "reading_passage": _prepare_reading,
        "listening_test": _prepare_listening,
        "intensive": _prepare_intensive,
        "dictation": _prepare_dictation,
    }
    prepared = {"kind": kind, **adapters[kind](payload)}
    prepared["prepared_hash"] = _digest(prepared)
    return prepared


def revalidate_resource(prepared):
    """Reject changed or unavailable resources, never silently choose other work."""
    if not isinstance(prepared, dict):
        raise ValueError("任务资源快照无效")
    saved = dict(prepared)
    stored_hash = saved.pop("prepared_hash", None)
    if not stored_hash or _digest(saved) != stored_hash:
        raise ValueError("任务资源快照损坏，请重新选题")
    current = prepare_resource(prepared.get("kind"), prepared.get("selection"))
    if current["prepared_hash"] != stored_hash:
        raise ValueError("资源内容已变化，请重新预览并确认")
    return current


def _coverage_overlap(first, second):
    for left in first:
        for right in second:
            if left.get("subject") != right.get("subject") or left.get(
                "test_id"
            ) != right.get("test_id"):
                continue
            if (
                left.get("unit_number")
                and right.get("unit_number")
                and left["unit_number"] != right["unit_number"]
            ):
                continue
            if (
                left.get("whole")
                or right.get("whole")
                or left.get("group_id") == right.get("group_id")
            ):
                return True
    return False


def resource_overlap(first, second):
    """Overlap for two trusted planner records, including whole-vs-specialty work."""
    if _coverage_overlap(
        first.get("coverage_units", []), second.get("coverage_units", [])
    ):
        return True
    a = resource_identity_from_payload(first.get("duplicate_payload"))
    b = resource_identity_from_payload(second.get("duplicate_payload"))
    if (
        not a["certain"]
        or not b["certain"]
        or a["kind"] != b["kind"]
        or a["base"] != b["base"]
    ):
        return False
    if a["range"] and b["range"]:
        return max(a["range"][0], b["range"][0]) <= min(a["range"][1], b["range"][1])
    return not a["units"] or not b["units"] or bool(a["units"] & b["units"])


def overlaps_task(prepared, task):
    """Only cross-kind overlaps; normal same-kind policy remains in the caller."""
    if task.cancelled_at or task.status == Task.STATUS_CANCELLED:
        return False
    if (
        prepared["kind"] == "question_type"
        and task.reading_test_id
        and task.grading_mode != "question_type_practice"
    ):
        try:
            test_id = (
                _reading_payload(task.reading_test_id).get("id") or task.reading_test_id
            )
        except ValueError:
            test_id = task.reading_test_id
        other = [
            {
                "subject": "reading",
                "test_id": test_id,
                "unit_number": task.reading_passage_number,
                "whole": True,
            }
        ]
    elif (
        prepared["kind"] == "question_type"
        and task.listening_resource_type == "cambridge_test"
        and task.listening_exercise_id
    ):
        try:
            test_id = (
                _listening_payload(task.listening_exercise_id).get("id")
                or task.listening_exercise_id
            )
        except ValueError:
            test_id = task.listening_exercise_id
        try:
            scope = json.loads(task.question_ids or "{}")
        except (ValueError, TypeError):
            scope = {}
        try:
            number = _integer(
                scope.get("listening_section_number"), "Section 序号", maximum=4
            )
        except (AttributeError, ValueError):
            number = None
        other = [
            {
                "subject": "listening",
                "test_id": test_id,
                "unit_number": number,
                "whole": True,
            }
        ]
    elif (
        prepared["kind"] in {"reading_passage", "listening_test"}
        and task.grading_mode == "question_type_practice"
    ):
        snapshot = snapshot_from_task(task) or {}
        other = []
        for ref in snapshot.get("group_refs") or []:
            other.append(
                {
                    "subject": snapshot.get("subject"),
                    "test_id": ref.get("test_id"),
                    "unit_number": ref.get("unit_number"),
                    "group_id": ref.get("question_group_id"),
                }
            )
    else:
        return False
    return _coverage_overlap(prepared.get("coverage_units", []), other)


def _plan(profile, due, creator_id):
    plan = StudyPlan.query.filter_by(student_id=profile.id, plan_date=due).first()
    if plan and (plan.is_deleted or plan.status != StudyPlan.STATUS_PUBLISHED):
        raise ValueError("该日期已有未发布、锁定或删除的学习计划")
    if not plan:
        plan = StudyPlan(
            student_id=profile.id,
            plan_date=due,
            status=StudyPlan.STATUS_PUBLISHED,
            created_by=creator_id,
            published_by=creator_id,
            published_at=utcnow_naive(),
        )
        db.session.add(plan)
        db.session.flush()
    return plan


def create_resource_task(
    profile, prepared, creator_id, due_date, planned_minutes, note, idempotency_key
):
    """Flush Task + PlanItem only. Caller owns transaction, dedupe and notification policy."""
    prepared = revalidate_resource(prepared)
    due = date.fromisoformat(str(due_date))
    minutes = _integer(planned_minutes, "计划用时", maximum=180)
    if not idempotency_key or len(str(idempotency_key)) > 128:
        raise ValueError("任务布置标识无效")
    if profile.is_deleted:
        raise ValueError("学生档案已停用")
    note = str(note or "")[:200]
    plan = _plan(profile, due, creator_id)
    if prepared["kind"] == "question_type":
        return create_assignment(
            profile=profile,
            snapshot=prepared["snapshot"],
            creator_id=creator_id,
            due_date=due.isoformat(),
            planned_minutes=minutes,
            note=note,
            idempotency_key=idempotency_key,
        )
    selection = prepared["selection"]
    token = secrets.token_urlsafe(24)
    if prepared["kind"] == "reading_passage":
        resource_type, resource_id, module, name = (
            "cambridge_reading_test",
            selection["test_id"],
            "阅读",
            "篇章练习",
        )
        fields = {
            "reading_test_id": resource_id,
            "reading_passage_number": selection["passage_number"],
            "reading_access_token": token,
            "grading_mode": "reading_test",
        }
        metadata = {
            "reading_test_id": resource_id,
            "reading_passage_number": selection["passage_number"],
            "question_ids": None,
            "grading_mode": "reading_test",
        }
        category = (
            "雅思-阅读-ZYZ"
            if prepared["metadata"].get("source") == "idictation_reading_jijing"
            else "雅思-阅读-整套"
        )
    elif prepared["kind"] == "listening_test":
        number = selection["section_number"]
        resource_type, resource_id, module, name = (
            "cambridge_listening_test",
            selection["test_id"],
            "听力",
            "Section 练习" if number is not None else "整套练习",
        )
        fields = {
            "listening_resource_type": "cambridge_test",
            "listening_exercise_id": resource_id,
            "listening_access_token": token,
            "question_ids": (
                json.dumps({"listening_section_number": number})
                if number is not None
                else None
            ),
            "grading_mode": "image",
        }
        metadata = {
            "listening_section_number": number,
            **prepared["metadata"],
        }
        category = "雅思-听力-整套"
    elif prepared["kind"] == "intensive":
        resource_type, resource_id, module, name = (
            "intensive_listening",
            selection["exercise_id"],
            "听力",
            "精听",
        )
        fields = {
            "listening_resource_type": "intensive",
            "listening_exercise_id": resource_id,
            "listening_training_mode": selection["training_mode"],
            "listening_access_token": token,
            "grading_mode": "image",
        }
        metadata = {"listening_training_mode": selection["training_mode"]}
        category = (
            "托福-听力-精听"
            if "TOEFL" in prepared["title"].upper() or "托福" in prepared["title"]
            else "雅思-听力-精听"
        )
    else:
        resource_type, resource_id, module, name, token = (
            "dictation",
            f"dictation_book:{selection['book_id']}",
            "词汇",
            "词汇学习",
            None,
        )
        fields = {
            "dictation_book_id": selection["book_id"],
            "dictation_word_start": selection["word_start"],
            "dictation_word_end": selection["word_end"],
            "vocabulary_goal": selection["vocabulary_goal"],
            "dictation_mode": selection["dictation_mode"],
            "dictation_order": selection["dictation_order"],
            "grading_mode": "material",
        }
        metadata = {
            key: value
            for key, value in fields.items()
            if key not in {"dictation_book_id", "grading_mode"}
        }
        category = "词汇学习"
    order = (
        db.session.query(func.max(PlanItem.order_index))
        .filter(PlanItem.plan_id == plan.id)
        .scalar()
        or 0
    )
    item = PlanItem(
        plan=plan,
        exam_system="托福" if category.startswith("托福") else "雅思",
        module=module,
        task_name=name,
        custom_title=prepared["title"][:128],
        instructions=note,
        order_index=order + 1,
        resource_type=resource_type,
        resource_id=resource_id,
        access_token=token,
        resource_metadata=json.dumps(metadata, ensure_ascii=False),
        planned_minutes=minutes,
        student_status=PlanItem.STUDENT_PENDING,
        review_status=PlanItem.REVIEW_PENDING,
    )
    db.session.add(item)
    db.session.flush()
    task = Task(
        date=due.isoformat(),
        student_name=profile.full_name,
        category=category,
        detail=prepared["title"][:200],
        status="pending",
        note=note,
        created_by=creator_id,
        plan_item_id=item.id,
        planned_minutes=minutes,
        assignment_idempotency_key=idempotency_key,
        **fields,
    )
    db.session.add(task)
    db.session.flush()
    return task
