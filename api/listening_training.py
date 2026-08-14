"""Completion endpoint for assigned listening-review tasks."""

from __future__ import annotations

import json
import secrets
from pathlib import Path

from flask import Blueprint, current_app, jsonify, request
from sqlalchemy.exc import IntegrityError
from werkzeug.utils import secure_filename

from models import ListeningSegmentResult, Task, db
from services.listening_cloze import find_exercise_segment
from services.listening_training import (
    MODE_REVIEW,
    selected_segment_count,
    selected_segment_indices,
    task_training_mode,
    update_task_progress_summary,
)

listening_training_bp = Blueprint("listening_training", __name__)


def _token_from_request() -> str:
    payload = request.get_json(silent=True) or {}
    return str(request.args.get("token") or payload.get("token") or "").strip()


def _load_exercise(task: Task) -> dict | None:
    safe_id = secure_filename(task.listening_exercise_id or "")
    path = Path(current_app.static_folder) / "listening" / f"{safe_id}.json"
    if not safe_id or not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return None
    return payload if isinstance(payload, dict) else None


@listening_training_bp.post(
    "/api/student/listening/task/<int:task_id>/segment/<int:segment_index>/review"
)
def complete_listening_review_segment(task_id: int, segment_index: int):
    """Persist one completion-only segment after listen → reveal."""

    data = request.get_json(silent=True) or {}
    token = _token_from_request()
    if not token:
        return jsonify({"ok": False, "error": "missing_token"}), 400

    task = db.session.get(Task, task_id)
    if not task or not task.listening_exercise_id:
        return jsonify({"ok": False, "error": "task_not_found"}), 404
    if not task.listening_access_token or not secrets.compare_digest(
        task.listening_access_token,
        token,
    ):
        return jsonify({"ok": False, "error": "invalid_token"}), 403
    if task_training_mode(task) != MODE_REVIEW:
        return jsonify({"ok": False, "error": "listening_training_mode_mismatch"}), 409
    if data.get("listened") is not True or data.get("revealed_original") is not True:
        return jsonify({"ok": False, "error": "review_requirements_not_met"}), 400

    selected = set(selected_segment_indices(task) or [])
    if selected and segment_index not in selected:
        return jsonify({"ok": False, "error": "segment_not_assigned"}), 400

    exercise = _load_exercise(task)
    if not exercise:
        return jsonify({"ok": False, "error": "exercise_not_found"}), 404
    segment = find_exercise_segment(exercise, segment_index)
    if not segment:
        return jsonify({"ok": False, "error": "segment_not_found"}), 404

    existing = ListeningSegmentResult.query.filter_by(
        task_id=task.id,
        segment_index=segment_index,
    ).first()
    was_existing = existing is not None
    if existing and existing.training_level != MODE_REVIEW:
        return jsonify({"ok": False, "error": "segment_already_answered"}), 409
    if not existing:
        existing = ListeningSegmentResult(
            task_id=task.id,
            student_name=task.student_name,
            segment_index=segment_index,
            segment_text=str(segment.get("text") or "").strip(),
            hidden_word_indices="[]",
            answers_json="[]",
            correct_words=0,
            total_words=0,
            accuracy=0.0,
            is_completed=True,
            attempt_count=1,
            training_level=MODE_REVIEW,
        )
        db.session.add(existing)
        db.session.flush()

    rows = ListeningSegmentResult.query.filter_by(task_id=task.id).all()
    summary = update_task_progress_summary(
        task,
        rows,
        total_segments=selected_segment_count(task, exercise),
        duration_seconds=data.get("duration_seconds"),
    )
    try:
        db.session.commit()
    except IntegrityError:
        # Two device retries can pass the initial lookup concurrently. The
        # unique task/segment key makes the write safe; return the winner as
        # the same idempotent completion instead of surfacing a 500.
        db.session.rollback()
        existing = ListeningSegmentResult.query.filter_by(
            task_id=task.id,
            segment_index=segment_index,
        ).first()
        if not existing or existing.training_level != MODE_REVIEW:
            raise
        task = db.session.get(Task, task_id)
        summary = {
            "status": task.status,
            "accuracy": task.accuracy,
            "completion_rate": task.completion_rate,
        }
        was_existing = True
    return jsonify(
        {
            "ok": True,
            "already_saved": was_existing,
            "segment": {
                "segment_index": segment_index,
                "segment_text": existing.segment_text,
                "is_completed": True,
                "training_level": MODE_REVIEW,
                "correct_words": 0,
                "total_words": 0,
                "accuracy": 0.0,
                "hidden_word_indices": [],
                "answers": [],
                "results": [],
            },
            "task": {
                "status": summary["status"],
                "accuracy": summary["accuracy"],
                "completion_rate": summary["completion_rate"],
            },
        }
    )
