"""Web-only IELTS writing model library and typing practice."""

from __future__ import annotations

from datetime import timedelta

from flask import Blueprint, abort, jsonify, redirect, render_template, request, session, url_for
from flask_login import current_user

from models import StudentProfile, User, WritingTypingAttempt, db, utcnow_naive
from services.writing_library import (
    BANDS,
    catalog_summary,
    get_exercise,
    get_mother_topic,
    load_catalog,
    load_mother_topics,
    mother_topic_summary,
    typing_metrics,
)
from services.writing_assignments import (
    RESOURCE_EXERCISE,
    RESOURCE_MOTHER_TOPIC,
    WritingAssignmentError,
    assigned_task,
    complete_task,
    require_student_task,
)

writing_library_bp = Blueprint("writing_library", __name__, url_prefix="/writing")
_STAFF_ROLES = {User.ROLE_ADMIN, User.ROLE_TEACHER, User.ROLE_ASSISTANT}
_CLASSROOM_COOKIE = "classroom_unlocked"


@writing_library_bp.errorhandler(401)
def _api_unauthorized(error):
    if request.path.startswith("/writing/api/"):
        return jsonify(ok=False, error="student_not_verified"), 401
    return error


def _is_staff_mode() -> bool:
    if (
        getattr(current_user, "is_authenticated", False)
        and getattr(current_user, "role", None) in _STAFF_ROLES
    ):
        return True
    return bool(
        session.get("classroom_unlocked")
        or request.cookies.get(_CLASSROOM_COOKIE) == "1"
    )


def _current_student() -> StudentProfile | None:
    if (
        getattr(current_user, "is_authenticated", False)
        and getattr(current_user, "role", None) == User.ROLE_STUDENT
    ):
        profile = StudentProfile.query.filter_by(
            user_id=current_user.id, is_deleted=False
        ).first()
        if profile:
            return profile
        name = (
            getattr(current_user, "display_name", None)
            or getattr(current_user, "username", None)
            or ""
        ).strip()
        if name:
            return StudentProfile.query.filter_by(
                full_name=name, is_deleted=False
            ).first()
    if _is_staff_mode():
        return None
    name = (session.get("practice_student_name") or "").strip()
    if not name:
        return None
    profile = StudentProfile.query.filter_by(full_name=name, is_deleted=False).first()
    if not profile:
        session.pop("practice_student_name", None)
    return profile


def _access_context() -> tuple[StudentProfile | None, bool]:
    student = _current_student()
    return student, _is_staff_mode()


def _assigned_context(
    student: StudentProfile | None,
    *,
    resource_type: str,
    resource_id: str,
) -> dict | None:
    task = assigned_task(
        request.args.get("task_id"),
        student=student,
        resource_type=resource_type,
        resource_id=resource_id,
    )
    if not task:
        return None
    return {
        "id": task.id,
        "status": task.status or "pending",
        "completed": task.status in {"done", "completed", "finished"},
        "date": task.date or "",
    }


def _require_page_access() -> tuple[StudentProfile | None, bool] | None:
    student, staff_mode = _access_context()
    if not student and not staff_mode:
        return None
    return student, staff_mode


def _require_api_access() -> tuple[StudentProfile | None, bool]:
    student, staff_mode = _access_context()
    if not student and not staff_mode:
        abort(401, description="student_not_verified")
    return student, staff_mode


def _attempt_payload(attempt: WritingTypingAttempt) -> dict:
    completed_at = attempt.completed_at or attempt.updated_at
    return {
        "id": attempt.id,
        "exercise_id": attempt.exercise_id,
        "band": attempt.band,
        "status": attempt.status,
        "duration_seconds": attempt.duration_seconds,
        "typed_word_count": attempt.typed_word_count,
        "target_word_count": attempt.target_word_count,
        "speed_wpm": attempt.speed_wpm,
        "accuracy": attempt.accuracy,
        "completed_at": (
            (completed_at + timedelta(hours=8)).strftime("%Y-%m-%d %H:%M")
            if completed_at
            else None
        ),
    }


@writing_library_bp.get("/")
def index():
    access = _require_page_access()
    if access is None:
        return redirect(url_for("practice_library", _anchor="ieltsPractice"))
    student, staff_mode = access
    catalog = load_catalog()
    return render_template(
        "writing/index.html",
        exercises=catalog["exercises"],
        summary=catalog_summary(),
        source_note=catalog["source_note"],
        student=student,
        staff_mode=staff_mode,
    )


@writing_library_bp.get("/topics")
def topics_index():
    access = _require_page_access()
    if access is None:
        return redirect(url_for("practice_library", _anchor="ieltsPractice"))
    student, staff_mode = access
    catalog = load_mother_topics()
    return render_template(
        "writing/topics.html",
        topics=catalog["topics"],
        summary=mother_topic_summary(),
        source_note=catalog["source_note"],
        student=student,
        staff_mode=staff_mode,
    )


@writing_library_bp.get("/topics/<topic_id>")
def topic_detail(topic_id: str):
    access = _require_page_access()
    if access is None:
        return redirect(url_for("practice_library", _anchor="ieltsPractice"))
    topic = get_mother_topic(topic_id)
    if not topic:
        abort(404)
    student, staff_mode = access
    related_exercises = [
        exercise
        for exercise_id in topic["related_exercise_ids"]
        if (exercise := get_exercise(exercise_id))
    ]
    return render_template(
        "writing/topic_detail.html",
        topic=topic,
        bands=BANDS,
        related_exercises=related_exercises,
        student=student,
        staff_mode=staff_mode,
        assigned_task=_assigned_context(
            student,
            resource_type=RESOURCE_MOTHER_TOPIC,
            resource_id=topic["id"],
        ),
    )


@writing_library_bp.get("/<exercise_id>")
def detail(exercise_id: str):
    access = _require_page_access()
    if access is None:
        return redirect(url_for("practice_library", _anchor="ieltsPractice"))
    exercise = get_exercise(exercise_id)
    if not exercise:
        abort(404)
    student, staff_mode = access
    attempts = []
    if student:
        rows = (
            WritingTypingAttempt.query.filter_by(
                student_profile_id=student.id,
                exercise_id=exercise["id"],
                status=WritingTypingAttempt.STATUS_COMPLETED,
            )
            .order_by(WritingTypingAttempt.completed_at.desc())
            .limit(12)
            .all()
        )
        attempts = [_attempt_payload(row) for row in rows]
    return render_template(
        "writing/detail.html",
        exercise=exercise,
        bands=BANDS,
        attempts=attempts,
        student=student,
        staff_mode=staff_mode,
        assigned_task=_assigned_context(
            student,
            resource_type=RESOURCE_EXERCISE,
            resource_id=exercise["id"],
        ),
    )


@writing_library_bp.post("/api/<exercise_id>/typing/start")
def start_typing(exercise_id: str):
    student, staff_mode = _require_api_access()
    exercise = get_exercise(exercise_id)
    if not exercise:
        return jsonify(ok=False, error="exercise_not_found"), 404
    payload = request.get_json(silent=True) or {}
    band = str(payload.get("band") or "")
    if band not in BANDS:
        return jsonify(ok=False, error="invalid_band"), 400
    task_id = payload.get("task_id")
    if task_id and student:
        try:
            require_student_task(
                task_id,
                student=student,
                resource_type=RESOURCE_EXERCISE,
                resource_id=exercise["id"],
            )
        except WritingAssignmentError as exc:
            return jsonify(ok=False, error=str(exc)), 409
    if staff_mode and not student:
        return jsonify(ok=True, client_only=True, attempt_id=None, band=band)

    attempt = WritingTypingAttempt(
        student_profile_id=student.id,
        exercise_id=exercise["id"],
        band=band,
        status=WritingTypingAttempt.STATUS_IN_PROGRESS,
        started_at=utcnow_naive(),
    )
    db.session.add(attempt)
    db.session.commit()
    return jsonify(ok=True, client_only=False, attempt_id=attempt.id, band=band)


@writing_library_bp.post("/api/<exercise_id>/typing/<int:attempt_id>/finish")
def finish_typing(exercise_id: str, attempt_id: int):
    student, _staff_mode = _require_api_access()
    if not student:
        return jsonify(ok=False, error="student_recording_unavailable"), 403
    exercise = get_exercise(exercise_id)
    if not exercise:
        return jsonify(ok=False, error="exercise_not_found"), 404
    attempt = WritingTypingAttempt.query.filter_by(
        id=attempt_id,
        student_profile_id=student.id,
        exercise_id=exercise["id"],
    ).first()
    if not attempt:
        return jsonify(ok=False, error="attempt_not_found"), 404
    payload = request.get_json(silent=True) or {}
    assigned = None
    if payload.get("task_id"):
        try:
            assigned = require_student_task(
                payload["task_id"],
                student=student,
                resource_type=RESOURCE_EXERCISE,
                resource_id=exercise["id"],
            )
        except WritingAssignmentError as exc:
            return jsonify(ok=False, error=str(exc)), 409
    if attempt.status == WritingTypingAttempt.STATUS_COMPLETED:
        if assigned and assigned.status not in {"done", "completed", "finished"}:
            complete_task(
                assigned,
                submitted_at=attempt.completed_at or utcnow_naive(),
                duration_seconds=attempt.duration_seconds,
                accuracy=attempt.accuracy,
                note=f"写作打字完成：Band {attempt.band}，准确率 {attempt.accuracy:.1f}%",
            )
            db.session.commit()
        return jsonify(ok=True, attempt=_attempt_payload(attempt), idempotent=True)

    typed_text = str(payload.get("typed_text") or "")
    if len(typed_text) > 20000:
        return jsonify(ok=False, error="typed_text_too_long"), 413
    selected_band = str(payload.get("band") or attempt.band)
    if selected_band != attempt.band or selected_band not in BANDS:
        return jsonify(ok=False, error="band_mismatch"), 409

    now = utcnow_naive()
    elapsed = max(1, int((now - attempt.started_at).total_seconds()))
    metrics = typing_metrics(
        exercise["essays"][attempt.band]["text"], typed_text, elapsed
    )
    attempt.status = WritingTypingAttempt.STATUS_COMPLETED
    attempt.completed_at = now
    attempt.duration_seconds = metrics["duration_seconds"]
    attempt.typed_text = typed_text
    attempt.typed_word_count = metrics["typed_word_count"]
    attempt.target_word_count = metrics["target_word_count"]
    attempt.speed_wpm = metrics["speed_wpm"]
    attempt.accuracy = metrics["accuracy"]
    if assigned:
        complete_task(
            assigned,
            submitted_at=now,
            duration_seconds=metrics["duration_seconds"],
            accuracy=metrics["accuracy"],
            note=f"写作打字完成：Band {attempt.band}，准确率 {metrics['accuracy']:.1f}%",
        )
    db.session.commit()
    return jsonify(
        ok=True,
        attempt=_attempt_payload(attempt),
        task_completed=bool(assigned),
        idempotent=False,
    )


@writing_library_bp.post("/api/topics/<topic_id>/tasks/<int:task_id>/complete")
def complete_topic_task(topic_id: str, task_id: int):
    student, _staff_mode = _require_api_access()
    if not student:
        return jsonify(ok=False, error="student_recording_unavailable"), 403
    topic = get_mother_topic(topic_id)
    if not topic:
        return jsonify(ok=False, error="topic_not_found"), 404
    try:
        task = require_student_task(
            task_id,
            student=student,
            resource_type=RESOURCE_MOTHER_TOPIC,
            resource_id=topic["id"],
        )
    except WritingAssignmentError as exc:
        return jsonify(ok=False, error=str(exc)), 409
    payload = request.get_json(silent=True) or {}
    try:
        duration_seconds = max(0, min(int(payload.get("duration_seconds") or 0), 14400))
    except (TypeError, ValueError):
        duration_seconds = 0
    now = utcnow_naive()
    complete_task(
        task,
        submitted_at=now,
        duration_seconds=duration_seconds,
        note="已完成大作文母题学习：逻辑链、表达与迁移题",
    )
    db.session.commit()
    return jsonify(ok=True, task={"id": task.id, "status": "done"})
