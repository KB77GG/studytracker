"""Question-group specialty practice on the existing Task/PlanItem workflow."""

from __future__ import annotations

import hashlib
import json
import os
from datetime import date, datetime, timedelta
from functools import lru_cache
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from flask import (
    Blueprint,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from flask_login import current_user, login_required

from models import QuestionTypePracticeAttempt, StudentProfile, Task, User, db
from services.ielts_practice_scoring import (
    grade_listening_test_answers,
    grade_reading_test_answers,
)
from services.practice_navigation import safe_local_target
from services.question_type_assignments import (
    assignment_url,
    complete_assignment_plan_item,
    create_assignment,
)
from services.question_type_practice import (
    PACE_EXAM,
    PRACTICE_TYPE_ORDER,
    SUBJECT_LISTENING,
    TASK_TYPE,
    LibraryRoots,
    broad_practice_type,
    build_group_index,
    build_snapshot,
    cambridge_test_numbers,
    catalog_unit_groups,
    filter_groups,
    filter_unit_groups,
    practice_type_members,
    public_snapshot,
    question_type_display_label,
    snapshot_from_task,
)
from services.task_assignment_duplicates import (
    begin_assignment_transaction,
    normalize_idempotency_key,
    staff_task_payload,
    validate_publish_conflicts,
    write_repeat_audit,
)

question_type_practice_bp = Blueprint("question_type_practice", __name__)
_PROJECT_ROOT = Path(__file__).resolve().parents[1]
_STAFF_ROLES = {User.ROLE_ADMIN, User.ROLE_TEACHER, User.ROLE_ASSISTANT}
_LISTENING_REVIEW_SECONDS = 120


def _navigation_args() -> dict[str, str]:
    values: dict[str, str] = {}
    for key in ("practice_return", "practice_exit"):
        value = safe_local_target(request.args.get(key), "")
        if value:
            values[key] = value
    for key in ("practice_source", "practice_identity"):
        value = str(request.args.get(key) or "").strip()
        if value and len(value) <= 40 and value.replace("_", "").isalnum():
            values[key] = value
    return values


def _with_navigation(url: str) -> str:
    values = _navigation_args()
    if not values:
        return url
    parts = urlsplit(url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query.update(values)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def _task_result_url(task_id: int, token: str) -> str:
    return url_for(
        "question_type_practice.task_result",
        task_id=task_id,
        token=token,
        **_navigation_args(),
    )


def _roots() -> LibraryRoots:
    configured_audio = os.environ.get("STUDYTRACKER_AUDIO_ROOT", "").strip()
    return LibraryRoots(
        listening=_PROJECT_ROOT / "static/listening_tests",
        reading=_PROJECT_ROOT / "static/reading_tests",
        static=_PROJECT_ROOT / "static",
        audio=Path(configured_audio) if configured_audio else _PROJECT_ROOT / "static/listening",
    )


@lru_cache(maxsize=1)
def _library_rows() -> tuple[dict, ...]:
    return tuple(build_group_index(_roots()))


def _is_staff() -> bool:
    return bool(
        getattr(current_user, "is_authenticated", False)
        and getattr(current_user, "role", None) in _STAFF_ROLES
    )


def _current_student() -> StudentProfile | None:
    if (
        getattr(current_user, "is_authenticated", False)
        and getattr(current_user, "role", None) == User.ROLE_STUDENT
    ):
        profile = StudentProfile.query.filter_by(user_id=current_user.id, is_deleted=False).first()
        if profile:
            return profile
        name = (current_user.display_name or current_user.username or "").strip()
        if name:
            return StudentProfile.query.filter_by(full_name=name, is_deleted=False).first()
    if _is_staff():
        return None
    name = (session.get("practice_student_name") or "").strip()
    return (
        StudentProfile.query.filter_by(full_name=name, is_deleted=False).first() if name else None
    )


def _self_creator(profile: StudentProfile) -> int | None:
    if profile.primary_teacher_id:
        return profile.primary_teacher_id
    owner = User.query.filter(User.role.in_(_STAFF_ROLES)).order_by(User.id.asc()).first()
    if owner:
        return owner.id
    return profile.user_id


def _json_object(value) -> dict:
    if isinstance(value, dict):
        return value
    try:
        parsed = json.loads(value or "{}")
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _type_summaries(subject: str | None = None) -> list[dict]:
    subjects = (subject,) if subject else tuple(PRACTICE_TYPE_ORDER)
    summaries: list[dict] = []
    for current_subject in subjects:
        publishable = [
            row
            for row in _library_rows()
            if row["subject"] == current_subject and row["safety_status"] == "publishable"
        ]
        for practice_type in PRACTICE_TYPE_ORDER.get(current_subject, ()):
            members = practice_type_members(current_subject, practice_type)
            rows = [row for row in publishable if row["standard_type"] in members]
            volumes: list[dict] = []
            for volume in sorted(
                {
                    numbers[0]
                    for row in rows
                    if (numbers := cambridge_test_numbers(row)) is not None
                },
                reverse=True,
            ):
                volume_rows = [
                    row
                    for row in rows
                    if (numbers := cambridge_test_numbers(row)) is not None and numbers[0] == volume
                ]
                volumes.append(
                    {
                        "value": f"cambridge:{volume}",
                        "volume": volume,
                        "label": f"剑雅{volume}",
                        "test_count": len({row["test_id"] for row in volume_rows}),
                        "unit_count": len(
                            {(row["test_id"], row["unit_index"]) for row in volume_rows}
                        ),
                    }
                )
            summaries.append(
                {
                    "subject": current_subject,
                    "standard_type": practice_type,
                    "label": question_type_display_label(practice_type),
                    "group_count": len(rows),
                    "unit_count": len({(row["test_id"], row["unit_index"]) for row in rows}),
                    "question_count": sum(row["question_count"] for row in rows),
                    "tests": sorted({row["test_id"] for row in rows}),
                    "cambridge_volumes": volumes,
                }
            )
    return summaries


def _selected_rows(data: dict) -> list[dict]:
    subject = str(data.get("subject") or "").strip()
    standard_type = str(data.get("standard_type") or "").strip()
    allowed_types = practice_type_members(subject, standard_type)
    explicit_ids = data.get("group_ids") or []
    if explicit_ids:
        wanted = list(dict.fromkeys(str(value) for value in explicit_ids))
        index = {row["question_group_id"]: row for row in _library_rows()}
        selected = [index[value] for value in wanted if value in index]
        if len(selected) != len(wanted):
            raise ValueError("group_not_found")
        if any(
            row["subject"] != subject
            or row["standard_type"] not in allowed_types
            or row["safety_status"] != "publishable"
            for row in selected
        ):
            raise ValueError("unsafe_group_selected")
        return selected
    if data.get("unit_count") not in (None, ""):
        return filter_unit_groups(
            list(_library_rows()),
            subject=subject,
            standard_type=standard_type,
            scope=str(data.get("scope") or "all"),
            unit_count=data.get("unit_count") or 1,
            exclude_group_ids=data.get("exclude_group_ids") or [],
        )
    return filter_groups(
        list(_library_rows()),
        subject=subject,
        standard_type=standard_type,
        scope=str(data.get("scope") or "all"),
        count=data.get("count") or 1,
        exclude_group_ids=data.get("exclude_group_ids") or [],
    )


def _selection_snapshot(data: dict) -> tuple[list[dict], dict]:
    pace = str(data.get("pace") or "training").strip()
    standard_type = str(data.get("standard_type") or "").strip()
    selected = _selected_rows(data)
    if not data.get("group_ids") and data.get("unit_count") in (None, ""):
        requested = max(1, min(int(data.get("count") or 1), 20))
        if len(selected) < requested:
            raise ValueError(f"insufficient_question_groups:{requested - len(selected)}")
    snapshot = build_snapshot(
        selected,
        pace=pace,
        standard_type=standard_type,
        roots=_roots(),
    )
    return selected, snapshot


def _preview_row(row: dict) -> dict:
    keys = (
        "question_group_id",
        "subject",
        "test_id",
        "test_title",
        "unit_label",
        "unit_number",
        "original_question_range",
        "standard_type",
        "standard_type_label",
        "standard_type_display_label",
        "subtype",
        "question_count",
        "renderer",
        "has_audio",
        "has_article",
        "has_image",
        "reliable_audio_timestamps",
        "safety_status",
        "blockers",
        "warnings",
    )
    payload = {key: row[key] for key in keys}
    payload["practice_type"] = broad_practice_type(row["subject"], row["standard_type"])
    payload["practice_type_label"] = question_type_display_label(payload["practice_type"])
    return payload


def _catalog_units(rows: list[dict]) -> list[dict]:
    units: dict[tuple[str, int], dict] = {}
    for row in rows:
        key = (row["test_id"], row["unit_index"])
        numbers = cambridge_test_numbers(row)
        unit = units.setdefault(
            key,
            {
                "key": f'{row["test_id"]}:{row["unit_index"]}',
                "test_id": row["test_id"],
                "test_title": row["test_title"],
                "volume": numbers[0] if numbers else None,
                "test_number": numbers[1] if numbers else None,
                "unit_label": row["unit_label"],
                "unit_number": row["unit_number"],
                "ranges": [],
                "practice_type_labels": [],
                "group_ids": [],
                "group_count": 0,
                "question_count": 0,
                "has_audio": False,
                "has_article": False,
                "has_image": False,
            },
        )
        unit["ranges"].append(row["original_question_range"])
        label = question_type_display_label(
            broad_practice_type(row["subject"], row["standard_type"])
        )
        if label not in unit["practice_type_labels"]:
            unit["practice_type_labels"].append(label)
        unit["group_ids"].append(row["question_group_id"])
        unit["group_count"] += 1
        unit["question_count"] += row["question_count"]
        unit["has_audio"] |= row["has_audio"]
        unit["has_article"] |= row["has_article"]
        unit["has_image"] |= row["has_image"]
    return list(units.values())


def _task_with_token(task_id: int, token: str) -> tuple[Task | None, dict | None]:
    task = db.session.get(Task, task_id)
    snapshot = snapshot_from_task(task) if task else None
    expected = (task.listening_access_token or task.reading_access_token) if task else None
    if not task or not snapshot or not token or token != expected:
        return None, None
    return task, snapshot


def _attempt(task: Task, snapshot: dict) -> QuestionTypePracticeAttempt:
    row = QuestionTypePracticeAttempt.query.filter_by(task_id=task.id).first()
    if row:
        if row.snapshot_hash != snapshot["snapshot_hash"]:
            raise ValueError("snapshot_changed")
        return row
    row = QuestionTypePracticeAttempt(
        task_id=task.id,
        student_name=task.student_name,
        subject=snapshot["subject"],
        standard_type=snapshot["standard_type"],
        pace=snapshot["pace"],
        snapshot_hash=snapshot["snapshot_hash"],
        status=QuestionTypePracticeAttempt.STATUS_PENDING,
        answers_json="{}",
    )
    db.session.add(row)
    db.session.flush()
    return row


def _start_non_listening_exam(attempt: QuestionTypePracticeAttempt, task: Task) -> None:
    if attempt.started_at:
        return
    attempt.started_at = datetime.utcnow()
    attempt.status = QuestionTypePracticeAttempt.STATUS_IN_PROGRESS
    task.status = "progress"
    if attempt.pace == PACE_EXAM:
        attempt.deadline_at = attempt.started_at + timedelta(
            minutes=max(1, int(task.planned_minutes or 20))
        )


def _expired(attempt: QuestionTypePracticeAttempt, now: datetime | None = None) -> bool:
    return bool(attempt.deadline_at and (now or datetime.utcnow()) >= attempt.deadline_at)


def _question_group_map(snapshot: dict) -> dict[str, str]:
    mapping: dict[str, str] = {}
    unit_key = "sections" if snapshot["subject"] == SUBJECT_LISTENING else "passages"
    for unit in snapshot["payload"].get(unit_key) or []:
        for group in unit.get("groups") or []:
            for question in group.get("questions") or []:
                mapping[str(question.get("id"))] = group["question_group_id"]
    return mapping


def _grade(snapshot: dict, answers: dict) -> dict:
    grader = (
        grade_listening_test_answers
        if snapshot["subject"] == SUBJECT_LISTENING
        else grade_reading_test_answers
    )
    return grader(snapshot["payload"], answers)


def _finalize(
    task: Task,
    snapshot: dict,
    attempt: QuestionTypePracticeAttempt,
    answers: dict,
    duration_seconds: int | None = None,
) -> dict:
    if attempt.submitted_at:
        return _json_object(attempt.results_json)
    grade = _grade(snapshot, answers)
    submitted_at = datetime.utcnow()
    group_map = _question_group_map(snapshot)
    wrong_group_ids: list[str] = []
    answered_marks = 0
    for result in grade.get("results") or []:
        if str(result.get("value") or "").strip():
            answered_marks += int(result.get("marks") or 1)
        if result.get("status") != "correct":
            ids = result.get("ids") or [result.get("id")]
            for question_id in ids:
                group_id = group_map.get(str(question_id))
                if group_id and group_id not in wrong_group_ids:
                    wrong_group_ids.append(group_id)
    elapsed = max(
        0,
        (
            int(duration_seconds)
            if duration_seconds is not None
            else int((submitted_at - (attempt.started_at or submitted_at)).total_seconds())
        ),
    )
    total = int(grade.get("total") or 0)
    attempt.status = QuestionTypePracticeAttempt.STATUS_SUBMITTED
    attempt.answers_json = json.dumps(answers, ensure_ascii=False)
    attempt.results_json = json.dumps(grade, ensure_ascii=False)
    attempt.wrong_group_ids_json = json.dumps(wrong_group_ids, ensure_ascii=False)
    attempt.submitted_at = submitted_at
    attempt.correct_count = int(grade.get("correct") or 0)
    attempt.total_count = total
    attempt.accuracy = float(grade.get("accuracy") or 0.0)
    attempt.duration_seconds = elapsed
    task.status = "done"
    task.accuracy = attempt.accuracy
    task.completion_rate = round(answered_marks * 100.0 / total, 1) if total else 0.0
    task.actual_seconds = max(int(task.actual_seconds or 0), elapsed)
    task.student_submitted = True
    task.submitted_at = submitted_at
    task.ended_at = submitted_at
    task.student_note = f"专项完成：{attempt.correct_count}/{total}，正确率 {attempt.accuracy:.1f}%"
    complete_assignment_plan_item(task, submitted_at=submitted_at)
    db.session.commit()
    return grade


def _attempt_payload(attempt: QuestionTypePracticeAttempt) -> dict:
    return {
        "status": attempt.status,
        "answers": _json_object(attempt.answers_json),
        "started_at": attempt.started_at.isoformat() + "Z" if attempt.started_at else None,
        "deadline_at": attempt.deadline_at.isoformat() + "Z" if attempt.deadline_at else None,
        "submitted_at": attempt.submitted_at.isoformat() + "Z" if attempt.submitted_at else None,
    }


def _notify_assignment(profile: StudentProfile, task: Task) -> None:
    openid = profile.user.wechat_openid if profile.user and profile.user.wechat_openid else None
    if not openid:
        return
    try:
        from api.wechat import send_subscribe_message

        send_subscribe_message(
            openid,
            current_app.config.get("WECHAT_TASK_TEMPLATE_ID", ""),
            {
                "thing1": {"value": (task.detail or "IELTS 题型专项")[:20]},
                "time2": {"value": f"{task.date} 08:00"},
                "time3": {"value": f"{task.date} 23:59"},
                "thing4": {"value": "题型专项"},
            },
        )
    except Exception as exc:  # Notification failure must not roll back assignment publication.
        current_app.logger.warning("Question-type assignment notification failed: %s", exc)


@question_type_practice_bp.get("/practice/question-types")
def student_index():
    return render_template(
        "question_type_practice/student_index.html",
        student=_current_student(),
        type_summaries=_type_summaries(),
    )


@question_type_practice_bp.get("/tasks/question-types")
@login_required
def teacher_index():
    if not _is_staff():
        return redirect(url_for("question_type_practice.student_index"))
    # Keep old bookmarks alive while making the unified task drawer the one
    # teacher-facing assignment entry point.
    return redirect("/tasks?source=question_type#taskForm")


@question_type_practice_bp.get("/api/question-type-practice/inventory")
def inventory_api():
    subject = (request.args.get("subject") or "").strip() or None
    payload = {"ok": True, "types": _type_summaries(subject)}
    if request.args.get("include_groups") == "1" and _is_staff():
        payload["groups"] = [_preview_row(row) for row in _library_rows()]
    return jsonify(payload)


@question_type_practice_bp.post("/api/question-type-practice/preview")
def preview_api():
    if not (_is_staff() or _current_student()):
        return jsonify(ok=False, error="student_not_verified"), 401
    try:
        selected, snapshot = _selection_snapshot(request.get_json(silent=True) or {})
    except ValueError as exc:
        return jsonify(ok=False, error=str(exc)), 400
    return jsonify(
        ok=True,
        selection={
            "subject": snapshot["subject"],
            "standard_type": snapshot["standard_type"],
            "pace": snapshot["pace"],
            "snapshot_hash": snapshot["snapshot_hash"],
            "question_count": snapshot["question_count"],
        },
        groups=[_preview_row(row) for row in selected],
    )


@question_type_practice_bp.post("/api/question-type-practice/catalog")
def catalog_api():
    if not (_is_staff() or _current_student()):
        return jsonify(ok=False, error="student_not_verified"), 401
    data = request.get_json(silent=True) or {}
    try:
        rows = catalog_unit_groups(
            list(_library_rows()),
            subject=str(data.get("subject") or ""),
            standard_type=str(data.get("standard_type") or ""),
            scope=str(data.get("scope") or "cambridge:all"),
        )
    except ValueError as exc:
        return jsonify(ok=False, error=str(exc)), 400
    units = _catalog_units(rows)
    return jsonify(
        ok=True,
        units=units,
        summary={
            "volume_count": len({row["volume"] for row in units if row["volume"] is not None}),
            "test_count": len({row["test_id"] for row in units}),
            "unit_count": len(units),
            "group_count": sum(row["group_count"] for row in units),
            "question_count": sum(row["question_count"] for row in units),
        },
    )


def _assignment_inputs(data: dict, snapshot: dict) -> tuple[str, int, str]:
    due_date = str(data.get("due_date") or date.today().isoformat())
    default_minutes = 20 if snapshot["subject"] == SUBJECT_LISTENING else 25
    planned_minutes = max(1, min(int(data.get("planned_minutes") or default_minutes), 180))
    return due_date, planned_minutes, str(data.get("note") or "").strip()


def _exclude_groups_for_students(data: dict, names: list[str]) -> dict:
    """Exclude the union of previously assigned groups for a batch."""

    if data.get("group_ids"):
        return data
    subject = str(data.get("subject") or "").strip()
    standard_type = str(data.get("standard_type") or "").strip()
    if not subject or not standard_type or not names:
        return data
    excluded: set[str] = set()
    history = Task.query.filter(Task.student_name.in_(names)).all()
    for task in history:
        snapshot = snapshot_from_task(task) if task else None
        if snapshot and snapshot.get("subject") == subject and snapshot.get("standard_type") == standard_type:
            excluded.update(str(group_id) for group_id in snapshot.get("group_ids") or [])
    excluded.update(str(group_id) for group_id in data.get("exclude_group_ids") or [])
    if not excluded:
        return data
    return {**data, "exclude_group_ids": sorted(excluded)}


@question_type_practice_bp.post("/api/question-type-practice/assign")
@login_required
def assign_api():
    if not _is_staff():
        return jsonify(ok=False, error="forbidden"), 403
    data = request.get_json(silent=True) or {}
    names = list(
        dict.fromkeys(
            str(name).strip() for name in data.get("student_names") or [] if str(name).strip()
        )
    )
    profiles = StudentProfile.query.filter(
        StudentProfile.full_name.in_(names), StudentProfile.is_deleted.is_(False)
    ).order_by(StudentProfile.id.asc()).all()
    if not names or len(profiles) != len(names):
        return jsonify(ok=False, error="student_not_found"), 400
    try:
        data = _exclude_groups_for_students(data, names)
        _selected, snapshot = _selection_snapshot(data)
        due_date, minutes, note = _assignment_inputs(data, snapshot)
        # The first publish request from the unified drawer always carries a
        # key.  A deterministic fallback preserves idempotency for older API
        # clients that have not added it yet.
        raw_key = normalize_idempotency_key(data.get("idempotency_key"))
        if not raw_key:
            fingerprint = json.dumps(
                {
                    "names": names,
                    "subject": snapshot["subject"],
                    "standard_type": snapshot["standard_type"],
                    "groups": snapshot["group_ids"],
                    "due_date": due_date,
                    "minutes": minutes,
                    "note": note,
                },
                sort_keys=True,
                ensure_ascii=False,
            ).encode("utf-8")
            raw_key = "legacy-" + hashlib.sha256(fingerprint).hexdigest()[:48]
        per_student_keys = {
            profile.id: hashlib.sha256(f"{raw_key}:{profile.id}".encode()).hexdigest()
            for profile in profiles
        }
        begin_assignment_transaction()
        existing = Task.query.filter(
            Task.assignment_idempotency_key.in_(list(per_student_keys.values()))
        ).all()
        if existing:
            if len(existing) == len(profiles):
                return jsonify(
                        ok=True,
                        idempotent=True,
                        tasks=[staff_task_payload(task) for task in sorted(existing, key=lambda row: row.id)],
                )
            db.session.rollback()
            return jsonify(ok=False, error="idempotency_key_reused"), 409

        duplicate_result = validate_publish_conflicts(
            names,
            {**data, "source": "question_type", "group_ids": snapshot["group_ids"]},
            force_repeat=bool(data.get("force_repeat")),
            force_reason=str(data.get("force_reason") or ""),
            confirmed=bool(data.get("confirm_repeat")),
        )
        if not duplicate_result["can_publish"]:
            db.session.rollback()
            return jsonify(ok=False, **duplicate_result), 409
        tasks = [
            create_assignment(
                profile=profile,
                snapshot=snapshot,
                creator_id=current_user.id,
                due_date=due_date,
                planned_minutes=minutes,
                note=note,
                idempotency_key=per_student_keys[profile.id],
            )
            for profile in profiles
        ]
        if duplicate_result.get("forced"):
            write_repeat_audit(
                tasks,
                actor_id=current_user.id,
                reason=str(data.get("force_reason") or ""),
                source_task_ids_by_student={
                    row["student_name"]: row.get("source_task_ids", [])
                    for row in duplicate_result.get("students", [])
                },
            )
        db.session.commit()
    except (TypeError, ValueError) as exc:
        db.session.rollback()
        return jsonify(ok=False, error=str(exc)), 400
    except Exception as exc:
        # A unique-key race is a safe retry response; all other failures keep
        # the transaction atomic and remain server errors for observability.
        db.session.rollback()
        if "unique" in str(exc).lower() and "assignment_idempotency" in str(exc).lower():
            return jsonify(ok=False, error="idempotency_key_reused"), 409
        raise
    for profile, task in zip(profiles, tasks, strict=True):
        _notify_assignment(profile, task)
    return jsonify(
        ok=True,
        tasks=[
            staff_task_payload(task) for task in tasks
        ],
    )


@question_type_practice_bp.post("/api/question-type-practice/self")
def self_assign_api():
    profile = _current_student()
    if not profile:
        return jsonify(ok=False, error="student_not_verified"), 401
    creator_id = _self_creator(profile)
    if not creator_id:
        return jsonify(ok=False, error="assignment_owner_missing"), 409
    data = request.get_json(silent=True) or {}
    try:
        _selected, snapshot = _selection_snapshot(data)
        due_date, minutes, note = _assignment_inputs(data, snapshot)
        task = create_assignment(
            profile=profile,
            snapshot=snapshot,
            creator_id=creator_id,
            due_date=due_date,
            planned_minutes=minutes,
            note=note or "学生自主题型专项",
        )
        db.session.commit()
    except (TypeError, ValueError) as exc:
        db.session.rollback()
        return jsonify(ok=False, error=str(exc)), 400
    return jsonify(ok=True, task={"id": task.id, "url": assignment_url(task)})


def _practice_context(
    task: Task, snapshot: dict, attempt: QuestionTypePracticeAttempt, token: str
) -> dict:
    base = f"/api/question-type-practice/task/{task.id}"
    query = "?" + urlencode({"token": token, **_navigation_args()})
    result_url = _task_result_url(task.id, token)
    return {
        "task_id": task.id,
        "task_type": TASK_TYPE,
        "subject": snapshot["subject"],
        "pace": snapshot["pace"],
        "draft_url": f"{base}/draft{query}",
        "submit_url": f"{base}/submit{query}",
        "submission_url": result_url,
        "result_url": result_url,
        "exit_url": url_for("practice_library"),
        # The live task and /result page render the same frozen paper. Keep
        # browser-local highlights under one stable, token-free task scope.
        "highlight_path": url_for(
            "question_type_practice.task_page", task_id=task.id
        ),
    }


def _review_practice_context(
    task: Task, snapshot: dict, attempt: QuestionTypePracticeAttempt, token: str
) -> dict:
    context = _practice_context(task, snapshot, attempt, token)
    context["draft_url"] = None
    context["read_only"] = True
    context["initial_review"] = {
        "answers": _json_object(attempt.answers_json),
        "result": _json_object(attempt.results_json),
    }
    return context


def _exam_context(
    task: Task, snapshot: dict, attempt: QuestionTypePracticeAttempt, token: str
) -> dict:
    context = _practice_context(task, snapshot, attempt, token)
    base = f"/api/question-type-practice/task/{task.id}"
    context.update(
        {
            "exam_id": f"question-type-{task.id}",
            "exam_name": task.detail or "IELTS 题型专项",
            "session_token": token,
            "student_name": task.student_name,
            "section": snapshot["subject"],
            "section_label": "Listening" if snapshot["subject"] == SUBJECT_LISTENING else "Reading",
            "minutes": int(task.planned_minutes or 20),
            "started_at": attempt.started_at.isoformat() + "Z" if attempt.started_at else None,
            "deadline_at": attempt.deadline_at.isoformat() + "Z" if attempt.deadline_at else None,
            "start_url": (
                f"{base}/start?token={token}" if snapshot["subject"] == SUBJECT_LISTENING else None
            ),
            "audio_complete_url": (
                f"{base}/audio-complete?token={token}"
                if snapshot["subject"] == SUBJECT_LISTENING
                else None
            ),
            "next_url": context["result_url"],
        }
    )
    return context


@question_type_practice_bp.get("/practice/question-types/task/<int:task_id>")
def task_page(task_id: int):
    token = (request.args.get("token") or "").strip()
    task, snapshot = _task_with_token(task_id, token)
    if not task or not snapshot:
        return "题型专项任务不存在或链接无效", 404
    attempt = _attempt(task, snapshot)
    if attempt.submitted_at:
        return redirect(_task_result_url(task.id, token))
    if snapshot["pace"] != PACE_EXAM or snapshot["subject"] != SUBJECT_LISTENING:
        _start_non_listening_exam(attempt, task)
        db.session.commit()
    context = _practice_context(task, snapshot, attempt, token)
    template = (
        "listening/test_practice.html"
        if snapshot["subject"] == SUBJECT_LISTENING
        else "reading/test_practice.html"
    )
    return render_template(
        template,
        test=public_snapshot(snapshot)["payload"],
        practice_context=context,
        exam_context=(
            _exam_context(task, snapshot, attempt, token) if snapshot["pace"] == PACE_EXAM else None
        ),
        practice_source=TASK_TYPE,
        practice_source_ref=str(task.id),
    )


@question_type_practice_bp.route(
    "/api/question-type-practice/task/<int:task_id>/draft", methods=["GET", "PUT"]
)
def task_draft(task_id: int):
    token = (request.args.get("token") or "").strip()
    task, snapshot = _task_with_token(task_id, token)
    if not task or not snapshot:
        return jsonify(ok=False, error="task_not_found"), 404
    attempt = _attempt(task, snapshot)
    if attempt.submitted_at:
        return (
            jsonify(
                ok=False,
                error="already_submitted",
                submitted=True,
                next_url=_task_result_url(task.id, token),
            ),
            409,
        )
    if request.method == "GET":
        return jsonify(ok=True, **_attempt_payload(attempt))
    if _expired(attempt):
        grade = _finalize(task, snapshot, attempt, _json_object(attempt.answers_json))
        return (
            jsonify(
                ok=False,
                error="time_expired",
                submitted=True,
                result=grade,
                next_url=_task_result_url(task.id, token),
            ),
            409,
        )
    answers = (request.get_json(silent=True) or {}).get("answers")
    if not isinstance(answers, dict) or len(answers) > 2000:
        return jsonify(ok=False, error="invalid_answers"), 400
    attempt.answers_json = json.dumps(answers, ensure_ascii=False)
    if not attempt.started_at and snapshot["pace"] != PACE_EXAM:
        _start_non_listening_exam(attempt, task)
    db.session.commit()
    return jsonify(
        ok=True,
        saved_at=datetime.utcnow().isoformat() + "Z",
        deadline_at=attempt.deadline_at.isoformat() + "Z" if attempt.deadline_at else None,
    )


@question_type_practice_bp.post("/api/question-type-practice/task/<int:task_id>/start")
def task_start(task_id: int):
    token = (request.args.get("token") or "").strip()
    task, snapshot = _task_with_token(task_id, token)
    if not task or not snapshot:
        return jsonify(ok=False, error="task_not_found"), 404
    attempt = _attempt(task, snapshot)
    if attempt.submitted_at:
        return jsonify(ok=False, error="already_submitted"), 409
    if not attempt.started_at:
        duration = float((request.get_json(silent=True) or {}).get("audio_duration_seconds") or 0)
        duration = max(60.0, min(duration, 4 * 60 * 60))
        attempt.started_at = datetime.utcnow()
        attempt.deadline_at = attempt.started_at + timedelta(
            seconds=duration + _LISTENING_REVIEW_SECONDS
        )
        attempt.status = QuestionTypePracticeAttempt.STATUS_IN_PROGRESS
        task.status = "progress"
        db.session.commit()
    return jsonify(
        ok=True,
        started_at=attempt.started_at.isoformat() + "Z",
        deadline_at=attempt.deadline_at.isoformat() + "Z",
    )


@question_type_practice_bp.post("/api/question-type-practice/task/<int:task_id>/audio-complete")
def task_audio_complete(task_id: int):
    token = (request.args.get("token") or "").strip()
    task, snapshot = _task_with_token(task_id, token)
    if not task or not snapshot:
        return jsonify(ok=False, error="task_not_found"), 404
    attempt = _attempt(task, snapshot)
    if not attempt.started_at or attempt.submitted_at:
        return jsonify(ok=False, error="task_not_active"), 409
    review_deadline = datetime.utcnow() + timedelta(seconds=_LISTENING_REVIEW_SECONDS)
    if not attempt.deadline_at or review_deadline < attempt.deadline_at:
        attempt.deadline_at = review_deadline
        db.session.commit()
    return jsonify(ok=True, deadline_at=attempt.deadline_at.isoformat() + "Z")


@question_type_practice_bp.post("/api/question-type-practice/task/<int:task_id>/submit")
def task_submit(task_id: int):
    token = (request.args.get("token") or "").strip()
    task, snapshot = _task_with_token(task_id, token)
    if not task or not snapshot:
        return jsonify(ok=False, error="task_not_found"), 404
    attempt = _attempt(task, snapshot)
    if attempt.submitted_at:
        return jsonify(
            ok=True,
            synced=True,
            result=_json_object(attempt.results_json),
            next_url=_task_result_url(task.id, token),
        )
    data = request.get_json(silent=True) or {}
    incoming = data.get("answers") if isinstance(data.get("answers"), dict) else {}
    answers = _json_object(attempt.answers_json) if _expired(attempt) else incoming
    if not attempt.started_at:
        _start_non_listening_exam(attempt, task)
    grade = _finalize(task, snapshot, attempt, answers, data.get("duration_seconds"))
    return jsonify(
        ok=True,
        synced=True,
        result=grade,
        next_url=_task_result_url(task.id, token),
    )


def _result_rows(snapshot: dict, attempt: QuestionTypePracticeAttempt) -> list[dict]:
    group_map = _question_group_map(snapshot)
    refs = {row["question_group_id"]: row for row in snapshot["group_refs"]}
    rows = []
    for result in _json_object(attempt.results_json).get("results") or []:
        ids = result.get("ids") or [result.get("id")]
        group_id = next(
            (group_map.get(str(value)) for value in ids if group_map.get(str(value))), ""
        )
        source = dict(refs.get(group_id, {}))
        source["standard_type_display_label"] = question_type_display_label(
            source.get("standard_type", snapshot["standard_type"])
        )
        source["practice_type_display_label"] = question_type_display_label(
            broad_practice_type(
                snapshot["subject"],
                source.get("standard_type", snapshot["standard_type"]),
            )
        )
        rows.append({**result, "question_group_id": group_id, "source": source})
    return rows


@question_type_practice_bp.get("/practice/question-types/task/<int:task_id>/result")
def task_result(task_id: int):
    token = (request.args.get("token") or "").strip()
    task, snapshot = _task_with_token(task_id, token)
    if not task or not snapshot:
        return "题型专项任务不存在或链接无效", 404
    attempt = QuestionTypePracticeAttempt.query.filter_by(task_id=task.id).first()
    if not attempt or not attempt.submitted_at:
        return redirect(
            _with_navigation(
                assignment_url(task) or url_for("question_type_practice.student_index")
            )
        )
    template = (
        "listening/test_practice.html"
        if snapshot["subject"] == SUBJECT_LISTENING
        else "reading/test_practice.html"
    )
    return render_template(
        template,
        test=public_snapshot(snapshot)["payload"],
        practice_context=_review_practice_context(task, snapshot, attempt, token),
        exam_context=None,
        practice_source=TASK_TYPE,
        practice_source_ref=str(task.id),
    )


@question_type_practice_bp.get("/tasks/question-types/<int:task_id>/result")
@login_required
def teacher_result(task_id: int):
    if not _is_staff():
        return redirect(url_for("question_type_practice.student_index"))
    task = db.session.get(Task, task_id)
    snapshot = snapshot_from_task(task) if task else None
    attempt = QuestionTypePracticeAttempt.query.filter_by(task_id=task_id).first() if task else None
    if not task or not snapshot or not attempt:
        return "结果不存在", 404
    return render_template(
        "question_type_practice/result.html",
        task=task,
        snapshot=snapshot,
        type_label=question_type_display_label(snapshot["standard_type"]),
        attempt=attempt,
        rows=_result_rows(snapshot, attempt),
        staff_mode=True,
    )


@question_type_practice_bp.post("/api/question-type-practice/task/<int:task_id>/repush")
@login_required
def repush_api(task_id: int):
    if not _is_staff():
        return jsonify(ok=False, error="forbidden"), 403
    task = db.session.get(Task, task_id)
    snapshot = snapshot_from_task(task) if task else None
    attempt = QuestionTypePracticeAttempt.query.filter_by(task_id=task_id).first() if task else None
    if not task or not snapshot or not attempt or not attempt.submitted_at:
        return jsonify(ok=False, error="result_not_found"), 404
    data = request.get_json(silent=True) or {}
    mode = str(data.get("mode") or "wrong").strip()
    names = data.get("student_names") or [task.student_name]
    names = list(dict.fromkeys(str(name).strip() for name in names if str(name).strip()))
    selection = {
        "subject": snapshot["subject"],
        "standard_type": snapshot["standard_type"],
        "pace": str(data.get("pace") or snapshot["pace"]),
    }
    if mode == "wrong":
        wrong_group_ids = json.loads(attempt.wrong_group_ids_json or "[]")
        if not isinstance(wrong_group_ids, list) or not wrong_group_ids:
            return jsonify(ok=False, error="wrong_groups_empty"), 400
        source_group_ids = {str(group_id) for group_id in snapshot.get("group_ids") or []}
        wrong_group_ids = [str(group_id) for group_id in wrong_group_ids]
        if any(group_id not in source_group_ids for group_id in wrong_group_ids):
            return jsonify(ok=False, error="wrong_groups_not_in_source"), 400
        selection["group_ids"] = wrong_group_ids
    elif mode == "same_type_new":
        selection.update(
            {
                "count": len(snapshot["group_ids"]),
                "exclude_group_ids": snapshot["group_ids"],
                "scope": data.get("scope") or "all",
            }
        )
    else:
        return jsonify(ok=False, error="invalid_repush_mode"), 400
    selection = _exclude_groups_for_students(selection, names)
    profiles = StudentProfile.query.filter(
        StudentProfile.full_name.in_(names), StudentProfile.is_deleted.is_(False)
    ).order_by(StudentProfile.id.asc()).all()
    if not names or len(profiles) != len(names):
        return jsonify(ok=False, error="student_not_found"), 400
    try:
        _selected, new_snapshot = _selection_snapshot(selection)
        due_date, minutes, note = _assignment_inputs(data, new_snapshot)
        raw_key = normalize_idempotency_key(data.get("idempotency_key"))
        if not raw_key:
            fingerprint = json.dumps(
                {
                    "source_task_id": task_id,
                    "mode": mode,
                    "names": names,
                    "groups": new_snapshot["group_ids"],
                    "due_date": due_date,
                },
                sort_keys=True,
                ensure_ascii=False,
            ).encode("utf-8")
            raw_key = "repush-" + hashlib.sha256(fingerprint).hexdigest()[:48]
        per_student_keys = {
            profile.id: hashlib.sha256(f"{raw_key}:{profile.id}".encode()).hexdigest()
            for profile in profiles
        }
        begin_assignment_transaction()
        existing = Task.query.filter(
            Task.assignment_idempotency_key.in_(list(per_student_keys.values()))
        ).all()
        if existing:
            if len(existing) == len(profiles):
                return jsonify(
                    ok=True,
                    idempotent=True,
                    tasks=[
                        staff_task_payload(row) for row in sorted(existing, key=lambda row: row.id)
                    ],
                )
            db.session.rollback()
            return jsonify(ok=False, error="idempotency_key_reused"), 409
        tasks = [
            create_assignment(
                profile=profile,
                snapshot=new_snapshot,
                creator_id=current_user.id,
                due_date=due_date,
                planned_minutes=minutes,
                note=note or ("错题重练" if mode == "wrong" else "同题型新题"),
                idempotency_key=per_student_keys[profile.id],
            )
            for profile in profiles
        ]
        for row in tasks:
            metadata = _json_object(row.plan_item.resource_metadata)
            metadata.update(
                {
                    "retraining_mode": "wrong_answer_retrain" if mode == "wrong" else "same_type_new",
                    "source_task_id": task_id,
                    "source_task_ids": [task_id],
                }
            )
            row.plan_item.resource_metadata = json.dumps(metadata, ensure_ascii=False)
        write_repeat_audit(
            tasks,
            actor_id=current_user.id,
            reason=note or ("错题完整组复训" if mode == "wrong" else "同题型新题"),
            source_task_id=task_id,
            mode="wrong_answer_retrain" if mode == "wrong" else "same_type_new",
        )
        db.session.commit()
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        db.session.rollback()
        return jsonify(ok=False, error=str(exc)), 400
    return jsonify(
        ok=True,
        tasks=[
            staff_task_payload(row) for row in tasks
        ],
    )
