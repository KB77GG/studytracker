"""Stable resource identity and duplicate checks for teacher assignments.

The legacy task page has several resource pickers.  This module keeps their
identity rules in one place so the browser preview and the publish endpoint
make the same decision.  It intentionally returns only staff-safe metadata:
task ids, dates, statuses, and the overlapping unit ids/ranges.  Access tokens,
answers, and other student secrets never leave this service.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from typing import Any

from sqlalchemy import text

from models import AuditLogEntry, Task, db

STATUS_LABELS = {
    "pending": "未开始",
    "progress": "进行中",
    "in_progress": "进行中",
    "submitted": "待批改",
    "done": "已完成",
    "completed": "已完成",
    "finished": "已完成",
}

_KEY_RE = re.compile(r"[^A-Za-z0-9_.:-]+")


def _text(value: Any) -> str:
    return str(value or "").strip()


def _json(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(value or "")
    except (TypeError, ValueError, json.JSONDecodeError):
        return None


def _ids(value: Any) -> set[str] | None:
    """Normalize an explicit selected-unit list.

    ``None`` means the picker represents the whole resource (or did not send
    enough information to enumerate units).  An empty list is treated as
    whole-resource too, matching the legacy form's "nothing checked means all"
    contract.
    """

    parsed = _json(value)
    if isinstance(parsed, dict):
        parsed = parsed.get("question_ids") or parsed.get("ids")
    if not isinstance(parsed, (list, tuple, set)):
        return None
    values = {_text(item) for item in parsed if _text(item)}
    return values or None


def _number(value: Any, default: int | None = None) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _range_units(start: Any, end: Any) -> tuple[int, int] | None:
    first = _number(start, 1)
    last = _number(end)
    if first is None:
        return None
    if last is None:
        # An open range is not safe to compare as a precise range.  It is kept
        # as a wildcard by the caller instead of being mislabelled as unique.
        return None
    first, last = sorted((max(1, first), max(1, last)))
    return first, last


def _identity(
    *,
    kind: str,
    base: tuple[Any, ...],
    units: set[str] | None = None,
    range_value: tuple[int, int] | None = None,
    label: str = "",
) -> dict[str, Any]:
    certain = bool(kind != "unknown" and all(base))
    if kind in {"dictation", "speaking"} and range_value is None:
        certain = False
    return {
        "kind": kind,
        "base": tuple("" if value is None else str(value) for value in base),
        "units": set(units) if units else None,
        "range": range_value,
        "label": label or kind,
        "certain": certain,
    }


def _question_type_identity(payload: dict[str, Any]) -> dict[str, Any]:
    subject = _text(payload.get("subject"))
    standard_type = _text(payload.get("standard_type"))
    groups = payload.get("group_ids")
    if not groups and isinstance(payload.get("snapshot"), dict):
        groups = payload["snapshot"].get("group_ids")
    ids = _ids(groups)
    return _identity(
        kind="question_type",
        base=(subject, standard_type),
        units=ids,
        label=f"{subject}/{standard_type} 题组" if subject and standard_type else "题型专项",
    )


def resource_identity_from_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Build an identity from a unified form or JSON publish payload."""

    payload = payload or {}
    source = _text(payload.get("source") or payload.get("task_source")).lower()
    grading_mode = _text(payload.get("grading_mode")).lower()
    if source in {"question_type", "question-type", "question_type_practice"} or grading_mode == "question_type_practice":
        return _question_type_identity(payload)

    writing_type = _text(payload.get("writing_resource_type"))
    writing_id = _text(payload.get("writing_resource_id"))
    if writing_type in {"exercise", "mother_topic"} and writing_id:
        label = "写作真题" if writing_type == "exercise" else "大作文母题"
        return _identity(
            kind="writing",
            base=(writing_type, writing_id),
            label=f"{label} {writing_id}",
        )

    listening_id = _text(payload.get("listening_exercise_id"))
    resource_type = _text(payload.get("listening_resource_type")) or "intensive"
    if listening_id:
        section = _number(
            payload.get("listening_section_number")
            or payload.get("section_number")
        )
        selected = _ids(payload.get("question_ids") or payload.get("selected_question_ids"))
        if selected and section:
            selected = {f"section:{section}:q:{item}" for item in selected}
        elif section:
            selected = {f"section:{section}"}
        return _identity(
            kind="listening",
            base=(resource_type, listening_id),
            units=selected,
            label=f"听力 {listening_id}" + (f" Section {section}" if section else " 整套"),
        )

    reading_id = _text(payload.get("reading_test_id"))
    if reading_id:
        passage = _number(
            payload.get("reading_passage_number")
            or payload.get("passage_number")
        )
        selected = _ids(payload.get("question_ids") or payload.get("selected_question_ids"))
        if selected and passage:
            selected = {f"passage:{passage}:q:{item}" for item in selected}
        elif passage:
            selected = {f"passage:{passage}"}
        return _identity(
            kind="reading",
            base=(reading_id,),
            units=selected,
            label=f"阅读 {reading_id}" + (f" Passage {passage}" if passage else " 整套"),
        )

    dictation_id = payload.get("dictation_book_id")
    if dictation_id:
        range_value = _range_units(
            payload.get("dictation_word_start") or payload.get("word_start") or 1,
            payload.get("dictation_word_end") or payload.get("word_end"),
        )
        return _identity(
            kind="dictation",
            base=(dictation_id,),
            range_value=range_value,
            label=f"听写词书 {dictation_id}",
        )

    speaking_id = payload.get("speaking_book_id")
    if speaking_id:
        range_value = _range_units(
            payload.get("speaking_phrase_start") or payload.get("phrase_start") or 1,
            payload.get("speaking_phrase_end") or payload.get("phrase_end"),
        )
        return _identity(
            kind="speaking",
            base=(speaking_id,),
            range_value=range_value,
            label=f"口语素材 {speaking_id}",
        )

    material_id = payload.get("material_id")
    if material_id and not _text(material_id).startswith(("dictation-", "speaking-")):
        material_range = _range_units(
            payload.get("question_range_start") or payload.get("dictation_word_start"),
            payload.get("question_range_end") or payload.get("dictation_word_end"),
        )
        return _identity(
            kind="material",
            base=(material_id,),
            units=_ids(payload.get("question_ids") or payload.get("selected_question_ids")),
            range_value=material_range,
            label=f"材料 {material_id}",
        )

    # Free-form text has no stable question identity.  It must never be
    # advertised as "未布置" because doing so would create a false guarantee.
    return _identity(kind="unknown", base=(source,), label="无法自动判断")


def resource_identity_from_task(task: Task) -> dict[str, Any]:
    if task.grading_mode == "question_type_practice":
        snapshot = _json(task.question_ids) or {}
        return _question_type_identity(snapshot if isinstance(snapshot, dict) else {})

    if task.grading_mode == "writing_practice":
        snapshot = _json(task.question_ids) or {}
        return resource_identity_from_payload(
            snapshot if isinstance(snapshot, dict) else {}
        )

    if task.listening_exercise_id:
        section = None
        metadata = _json(task.question_ids)
        if isinstance(metadata, dict):
            section = metadata.get("listening_section_number")
        return resource_identity_from_payload(
            {
                "listening_exercise_id": task.listening_exercise_id,
                "listening_resource_type": task.listening_resource_type,
                "listening_section_number": section,
                "question_ids": task.question_ids,
            }
        )
    if task.reading_test_id:
        return resource_identity_from_payload(
            {
                "reading_test_id": task.reading_test_id,
                "reading_passage_number": task.reading_passage_number,
                "question_ids": task.question_ids,
            }
        )
    if task.dictation_book_id:
        return resource_identity_from_payload(
            {
                "dictation_book_id": task.dictation_book_id,
                "dictation_word_start": task.dictation_word_start,
                "dictation_word_end": task.dictation_word_end,
            }
        )
    if task.speaking_book_id:
        return resource_identity_from_payload(
            {
                "speaking_book_id": task.speaking_book_id,
                "speaking_phrase_start": task.speaking_phrase_start,
                "speaking_phrase_end": task.speaking_phrase_end,
            }
        )
    if task.material_id:
        return resource_identity_from_payload(
            {
                "material_id": task.material_id,
                "question_ids": task.question_ids,
                "question_range_start": task.dictation_word_start,
                "question_range_end": task.dictation_word_end,
            }
        )
    return _identity(kind="unknown", base=(task.category or "",), label="无法自动判断")


def _overlap(
    wanted: dict[str, Any], existing: dict[str, Any]
) -> tuple[str, list[str], bool] | None:
    if not wanted["certain"] or not existing["certain"]:
        return None
    if wanted["kind"] != existing["kind"] or wanted["base"] != existing["base"]:
        return None

    if wanted["range"] or existing["range"]:
        if not wanted["range"] or not existing["range"]:
            return "partial", [], False
        left = max(wanted["range"][0], existing["range"][0])
        right = min(wanted["range"][1], existing["range"][1])
        if left > right:
            return None
        exact = wanted["range"] == existing["range"]
        return ("exact" if exact else "partial", [f"{left}-{right}"], exact)

    wanted_units = wanted.get("units")
    existing_units = existing.get("units")
    if wanted_units is None and existing_units is None:
        return "exact", [], True
    if wanted_units is None or existing_units is None:
        return "partial", sorted(existing_units or wanted_units or []), False
    common = sorted(wanted_units & existing_units)
    if not common:
        return None
    exact = wanted_units == existing_units
    return ("exact" if exact else "partial", common, exact)


def normalized_status(task: Task) -> str:
    value = _text(task.status).lower() or "pending"
    return value if value in STATUS_LABELS else "pending"


def _safe_task_link(task: Task) -> str:
    # Staff review routes are token-free.  Never use assignment_url here.
    return f"/tasks/{int(task.id)}/review"


def _match_payload(task: Task, overlap: tuple[str, list[str], bool]) -> dict[str, Any]:
    overlap_type, units, _exact = overlap
    status = normalized_status(task)
    return {
        "task_id": task.id,
        "assigned_date": task.date.isoformat() if hasattr(task.date, "isoformat") else task.date,
        "status": status,
        "status_label": STATUS_LABELS.get(status, "未开始"),
        "overlap_type": overlap_type,
        "overlap_units": units,
        "overlap_label": "、".join(units) if units else "完整资源",
        "view_url": _safe_task_link(task),
    }


def staff_task_payload(task: Task) -> dict[str, Any]:
    """Return the smallest safe representation of a task for staff APIs."""

    return {
        "id": int(task.id),
        "student_name": _text(task.student_name),
        "status": normalized_status(task),
        "review_url": _safe_task_link(task),
    }


def _student_result(name: str, matches: list[dict[str, Any]], identity: dict[str, Any]) -> dict[str, Any]:
    if not identity["certain"]:
        return {
            "student_name": name,
            "status": "unable_to_determine",
            "status_label": "无法自动判断",
            "matches": [],
            "can_publish": True,
            "requires_confirmation": False,
        }
    if not matches:
        return {
            "student_name": name,
            "status": "not_assigned",
            "status_label": "未布置",
            "matches": [],
            "can_publish": True,
            "requires_confirmation": False,
        }
    blocking = any(
        row["overlap_type"] == "exact" and row["status"] in {"pending", "progress", "in_progress"}
        for row in matches
    )
    return {
        "student_name": name,
        "status": "partial_overlap" if any(row["overlap_type"] == "partial" for row in matches) else "assigned",
        "status_label": "部分题目重复" if any(row["overlap_type"] == "partial" for row in matches) else "已布置",
        "matches": matches,
        "can_publish": not blocking,
        "requires_confirmation": True,
        "blocking": blocking,
        "source_task_ids": sorted({int(row["task_id"]) for row in matches}),
    }


def _question_type_units(identity: dict[str, Any], payload: dict[str, Any]) -> list[dict[str, str]]:
    """Return every requested Question Group as a staff-safe render unit.

    The duplicate query must describe units that have no history as well as
    units that do.  Labels are optional display metadata from the picker and
    never participate in the stable identity calculation.
    """

    if identity["kind"] != "question_type":
        return []
    labels = payload.get("unit_labels") or {}
    if not isinstance(labels, dict):
        labels = {}
    return [
        {
            "id": str(unit_id),
            "label": _text(labels.get(str(unit_id))) or str(unit_id),
        }
        for unit_id in sorted(identity.get("units") or ())
    ]


def _question_type_matrix_rows(
    student: dict[str, Any], units: list[dict[str, str]]
) -> list[dict[str, Any]]:
    """Expand task-level matches into exactly one row per student × group."""

    rows: list[dict[str, Any]] = []
    matches = student.get("matches") or []
    for unit in units:
        unit_id = unit["id"]
        unit_matches = [
            match for match in matches if unit_id in (match.get("overlap_units") or [])
        ]
        match = unit_matches[0] if unit_matches else None
        if match:
            rows.append(
                {
                    "student_name": student["student_name"],
                    "unit_id": unit_id,
                    "unit_label": unit["label"],
                    "status": match["status"],
                    "status_label": match["status_label"],
                    # The task-level match can be partial because the batch
                    # contains other groups.  At this atomic Question Group
                    # row, a matching group is an exact duplicate.
                    "overlap_type": "exact",
                    "overlap_units": [unit_id],
                    "match": match,
                }
            )
        else:
            rows.append(
                {
                    "student_name": student["student_name"],
                    "unit_id": unit_id,
                    "unit_label": unit["label"],
                    "status": "not_assigned",
                    "status_label": "未布置",
                    "overlap_type": None,
                    "overlap_units": [],
                    "match": None,
                }
            )
    return rows


def check_duplicate_assignments(
    student_names: Iterable[str], payload: dict[str, Any], *, tasks: Iterable[Task] | None = None
) -> dict[str, Any]:
    """Batch-load history once and return student × resource decisions."""

    names = list(dict.fromkeys(_text(name) for name in student_names if _text(name)))
    identity = resource_identity_from_payload(payload)
    history = list(tasks) if tasks is not None else (
        Task.query.filter(Task.student_name.in_(names)).order_by(Task.date.desc(), Task.id.desc()).all()
        if names
        else []
    )
    by_student: dict[str, list[Task]] = {name: [] for name in names}
    for task in history:
        by_student.setdefault(task.student_name, []).append(task)

    results = []
    for name in names:
        matches: list[dict[str, Any]] = []
        for task in by_student.get(name, []):
            overlap = _overlap(identity, resource_identity_from_task(task))
            if overlap:
                match = _match_payload(task, overlap)
                match["kind"] = identity["kind"]
                matches.append(match)
        results.append(_student_result(name, matches, identity))

    blocking = any(row.get("blocking") for row in results)
    warnings = any(row.get("matches") for row in results)
    question_type_units = _question_type_units(identity, payload)
    matrix_rows: list[dict[str, Any]] = []
    for student in results:
        if question_type_units:
            student["matrix_rows"] = _question_type_matrix_rows(student, question_type_units)
            matrix_rows.extend(student["matrix_rows"])

    response = {
        "resource": {
            "kind": identity["kind"],
            "label": identity["label"],
            "certain": identity["certain"],
        },
        "students": results,
        "blocking": blocking,
        "has_history": warnings,
        "requires_confirmation": bool(warnings),
        "can_publish": not blocking,
    }
    if identity["kind"] == "question_type":
        response["resource"]["units"] = question_type_units
        response["matrix_rows"] = matrix_rows
    for row in results:
        row.setdefault("source_task_ids", sorted({int(match["task_id"]) for match in row.get("matches", [])}))
    if identity["kind"] == "question_type":
        used: set[str] = set()
        for task in history:
            existing = resource_identity_from_task(task)
            if existing["kind"] == identity["kind"] and existing["base"] == identity["base"]:
                used.update(existing.get("units") or ())
        response["excluded_group_ids"] = sorted(used)
    return response


def validate_publish_conflicts(
    student_names: Iterable[str],
    payload: dict[str, Any],
    *,
    force_repeat: bool = False,
    force_reason: str = "",
    confirmed: bool = False,
    tasks: Iterable[Task] | None = None,
) -> dict[str, Any]:
    """Apply publish policy after the browser preview.

    Completed/partial history is publishable only after explicit repeat
    confirmation and a reason. Wrong-answer repush is handled by its
    separately verified endpoint and is never a client-supplied exemption.
    """

    result = check_duplicate_assignments(student_names, payload, tasks=tasks)
    reason = _text(force_reason)
    explicit_repeat = bool(force_repeat and confirmed and len(reason) >= 2)
    if result["blocking"] and not explicit_repeat:
        result["can_publish"] = False
        result["error"] = "duplicate_assignment_conflict"
        result["reason_required"] = True
        return result
    if result["has_history"]:
        if not force_repeat or not confirmed or len(reason) < 2:
            result["can_publish"] = False
            result["error"] = "duplicate_assignment_conflict"
            result["reason_required"] = True
            return result
    result["can_publish"] = True
    result["forced"] = bool(result["has_history"])
    return result


def normalize_idempotency_key(value: Any) -> str:
    value = _KEY_RE.sub("-", _text(value))[:128].strip("-_.:")
    return value


def stable_assignment_key(
    raw_key: Any,
    *,
    namespace: str,
    student_names: Iterable[str],
    payload: dict[str, Any],
) -> str:
    """Normalize a browser key, with a deterministic legacy-client fallback."""

    normalized = normalize_idempotency_key(raw_key)
    if normalized:
        return normalized
    fingerprint = json.dumps(
        {
            "namespace": namespace,
            "students": list(student_names),
            "payload": payload,
        },
        sort_keys=True,
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")
    return f"{namespace}-" + hashlib.sha256(fingerprint).hexdigest()[:48]


def build_legacy_duplicate_payload(
    *,
    source: str,
    material_id: int | None,
    question_ids: Any,
    dictation_book_id: int | None,
    dictation_word_start: int,
    dictation_word_end: int | None,
    speaking_book_id: int | None,
    speaking_phrase_start: int,
    speaking_phrase_end: int | None,
    listening_exercise_id: str | None,
    listening_resource_type: str | None,
    reading_test_id: str | None,
    reading_passage_number: int | None,
    writing_resource_type: str | None = None,
    writing_resource_id: str | None = None,
) -> dict[str, Any]:
    """Normalize the legacy form's resource fields for history and publish."""

    listening_section = None
    if listening_exercise_id and question_ids:
        metadata = _json(question_ids)
        if isinstance(metadata, dict):
            listening_section = metadata.get("listening_section_number")
    return {
        "source": source,
        "task_source": source,
        "material_id": material_id,
        "question_ids": question_ids,
        "dictation_book_id": dictation_book_id,
        "dictation_word_start": dictation_word_start,
        "dictation_word_end": dictation_word_end,
        "speaking_book_id": speaking_book_id,
        "speaking_phrase_start": speaking_phrase_start,
        "speaking_phrase_end": speaking_phrase_end,
        "listening_exercise_id": listening_exercise_id,
        "listening_resource_type": listening_resource_type,
        "listening_section_number": listening_section,
        "reading_test_id": reading_test_id,
        "reading_passage_number": reading_passage_number,
        "writing_resource_type": writing_resource_type,
        "writing_resource_id": writing_resource_id,
    }


def duplicate_conflict_payload(result: dict[str, Any]) -> dict[str, Any]:
    """Return the stable, staff-safe JSON body for a duplicate conflict."""

    return {"ok": False, **result, "error": "duplicate_assignment_conflict"}


def legacy_assignment_preflight(
    student_name: str,
    payload: dict[str, Any],
    *,
    raw_key: Any,
    force_repeat: bool,
    force_reason: str,
    confirmed: bool,
) -> tuple[str, Task | None, dict[str, Any]]:
    """Lock, dedupe and re-check one legacy assignment before its insert."""

    key = stable_assignment_key(
        raw_key,
        namespace="legacy-task",
        student_names=[student_name],
        payload=payload,
    )
    begin_assignment_transaction()
    existing = Task.query.filter_by(assignment_idempotency_key=key).first()
    if existing:
        return key, existing, {"can_publish": True, "idempotent": True}
    result = validate_publish_conflicts(
        [student_name],
        payload,
        force_repeat=force_repeat,
        force_reason=force_reason,
        confirmed=confirmed,
    )
    return key, None, result


def begin_assignment_transaction() -> None:
    """Take the SQLite writer lock before the history check and inserts.

    PostgreSQL/MySQL use their normal transaction isolation.  SQLite is the
    local/production deployment used by this project and otherwise permits
    two request handlers to pass the same read-before-write check.
    """

    if db.engine.dialect.name == "sqlite":
        db.session.rollback()
        db.session.execute(text("BEGIN IMMEDIATE"))


def write_repeat_audit(
    tasks: Iterable[Task],
    *,
    actor_id: int | None,
    reason: str,
    source_task_id: int | None = None,
    source_task_ids_by_student: dict[str, Iterable[int]] | None = None,
    mode: str = "force_repeat",
) -> None:
    for task in tasks:
        source_ids = list(source_task_ids_by_student.get(_text(task.student_name), ()) if source_task_ids_by_student else ())
        if source_task_id and int(source_task_id) not in source_ids:
            source_ids.append(int(source_task_id))
        source_ids = sorted(set(source_ids))
        payload = {
            "mode": mode,
            "reason": _text(reason)[:500],
            "source_task_ids": source_ids,
            "source_task_id": source_ids[0] if source_ids else None,
        }
        db.session.add(
            AuditLogEntry(
                entity_type="task",
                entity_id=task.id,
                action="create",
                field="assignment_repeat",
                new_value="true",
                actor_id=actor_id,
                metadata_payload=payload,
            )
        )
