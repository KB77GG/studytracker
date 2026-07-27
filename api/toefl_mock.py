"""Thin HTTP layer for the TOEFL mock flow described by the v2 spec."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from flask import (
    Blueprint,
    current_app,
    jsonify,
    render_template,
    request,
    session,
)
from flask_login import current_user

from models import (
    StudentProfile,
    ToeflMockAttempt,
    ToeflMockResponse,
    User,
    db,
)
from services.toefl_mock_v2 import (
    PackageNotFoundError,
    PackageReleaseBlockedError,
    catalog,
    definition,
    parse_sections,
    require_attempt_allowed,
    route_module_two,
    score_responses,
)

toefl_mock_bp = Blueprint("toefl_mock", __name__)
MAX_RECORDING_BYTES = 20 * 1024 * 1024


def _json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def _load_json_text(value: str | None, fallback: Any) -> Any:
    try:
        return json.loads(value or "")
    except (json.JSONDecodeError, TypeError):
        return fallback


def _current_student() -> StudentProfile | None:
    if not getattr(current_user, "is_authenticated", False):
        return None
    if getattr(current_user, "role", None) != User.ROLE_STUDENT:
        return None
    return StudentProfile.query.filter_by(
        user_id=current_user.id,
        is_deleted=False,
    ).first()


def _actor_key() -> str:
    profile = _current_student()
    if profile:
        return f"student:{profile.id}"
    actor = str(session.get("toefl_mock_actor") or "").strip()
    if not actor:
        actor = f"preview:{uuid.uuid4().hex}"
        session["toefl_mock_actor"] = actor
    return actor


def _safe_return_to(value: Any) -> str:
    target = str(value or "").strip()
    if target.startswith("/") and not target.startswith("//"):
        return target
    return "/toefl/mock"


def _is_staff() -> bool:
    return bool(
        getattr(current_user, "is_authenticated", False)
        and getattr(current_user, "role", None)
        in {User.ROLE_ADMIN, User.ROLE_TEACHER, User.ROLE_ASSISTANT}
    )


def _owned_attempt(attempt_id: str) -> ToeflMockAttempt | None:
    attempt = db.session.get(ToeflMockAttempt, attempt_id)
    if not attempt:
        return None
    if _is_staff() or attempt.actor_key == _actor_key():
        return attempt
    return None


def _response_map(attempt: ToeflMockAttempt) -> dict[str, Any]:
    return {
        row.question_id: _load_json_text(row.response_json, None)
        for row in attempt.responses
    }


def _attempt_definition(attempt: ToeflMockAttempt) -> dict[str, Any]:
    return definition(
        attempt.exam_id,
        _load_json_text(attempt.sections_json, []),
    )


def _question_map(attempt: ToeflMockAttempt) -> dict[str, dict[str, Any]]:
    return {
        item["id"]: item
        for item in _attempt_definition(attempt)["questions"]
    }


def _serialize_attempt(attempt: ToeflMockAttempt) -> dict[str, Any]:
    return {
        "id": attempt.id,
        "exam_id": attempt.exam_id,
        "sections": _load_json_text(attempt.sections_json, []),
        "status": attempt.status,
        "preview": attempt.is_preview,
        "current_phase": attempt.current_phase,
        "remaining_seconds": attempt.remaining_seconds,
        "state": _load_json_text(attempt.state_json, {}),
        "routes": _load_json_text(attempt.routes_json, {}),
        "responses": _response_map(attempt),
        "started_at": attempt.started_at.isoformat() if attempt.started_at else None,
        "updated_at": attempt.updated_at.isoformat() if attempt.updated_at else None,
        "completed_at": (
            attempt.completed_at.isoformat() if attempt.completed_at else None
        ),
    }


def _upsert_response(
    attempt: ToeflMockAttempt,
    question_id: str,
    response_value: Any,
    recording_token: str | None = None,
) -> ToeflMockResponse:
    row = ToeflMockResponse.query.filter_by(
        attempt_id=attempt.id,
        question_id=question_id,
    ).first()
    if not row:
        row = ToeflMockResponse(
            attempt_id=attempt.id,
            question_id=question_id,
        )
        db.session.add(row)
    row.response_json = _json_text(response_value)
    if recording_token is not None:
        row.recording_token = recording_token
    return row


@toefl_mock_bp.errorhandler(PackageNotFoundError)
def _package_not_found(exc):
    return jsonify({"error": "test_not_found", "message": str(exc)}), 404


@toefl_mock_bp.errorhandler(PackageReleaseBlockedError)
def _package_blocked(exc):
    return jsonify({"error": "release_blocked", "message": str(exc)}), 409


@toefl_mock_bp.get("/toefl/mock")
def mock_catalog():
    return render_template("toefl/mock_index.html", exams=catalog())


@toefl_mock_bp.get("/toefl/mock/<test_id>")
def mock_exam(test_id: str):
    selected = request.args.get("sections")
    payload = definition(test_id, selected)
    preview = request.args.get("preview") == "1"
    return render_template(
        "toefl/mock_exam.html",
        definition=payload,
        preview=preview,
        return_to=_safe_return_to(request.args.get("returnTo")),
    )


@toefl_mock_bp.get("/api/toefl/tests/<test_id>/definition")
def test_definition(test_id: str):
    return jsonify(definition(test_id, request.args.get("sections")))


@toefl_mock_bp.post("/api/toefl/attempts/start")
def start_attempt():
    payload = request.get_json(silent=True) or {}
    sections = parse_sections(payload.get("sections"))
    mock_definition = definition(str(payload.get("testId") or ""), sections)
    preview = bool(payload.get("preview"))
    require_attempt_allowed(mock_definition, preview)
    first_phase = mock_definition["phases"][0] if mock_definition["phases"] else {}
    profile = _current_student()
    attempt = ToeflMockAttempt(
        id=str(uuid.uuid4()),
        student_id=profile.id if profile else None,
        actor_key=_actor_key(),
        exam_id=mock_definition["test"]["id"],
        sections_json=_json_text(sections),
        is_preview=preview,
        current_phase=first_phase.get("id"),
        remaining_seconds=first_phase.get("duration_seconds"),
        state_json=_json_text(
            {
                "phaseIndex": 0,
                "questionIndex": 0,
                "returnTo": _safe_return_to(payload.get("returnTo")),
            }
        ),
        routes_json="{}",
    )
    db.session.add(attempt)
    db.session.commit()
    return jsonify({"attempt": _serialize_attempt(attempt)}), 201


@toefl_mock_bp.post("/api/toefl/responses")
def save_response():
    payload = request.get_json(silent=True) or {}
    attempt = _owned_attempt(str(payload.get("attemptId") or ""))
    if not attempt:
        return jsonify({"error": "attempt_not_found"}), 404
    if attempt.status != "in_progress":
        return jsonify({"error": "attempt_closed"}), 409
    question_id = str(payload.get("questionId") or "").strip()
    if not question_id.startswith(f"{attempt.exam_id}:"):
        return jsonify({"error": "question_not_in_attempt"}), 400
    if question_id not in _question_map(attempt):
        return jsonify({"error": "question_not_in_attempt"}), 400
    _upsert_response(attempt, question_id, payload.get("response"))
    db.session.commit()
    return jsonify({"saved": True, "questionId": question_id})


@toefl_mock_bp.post("/api/toefl/recordings")
def save_recording():
    attempt = _owned_attempt(str(request.form.get("attemptId") or ""))
    if not attempt:
        return jsonify({"error": "attempt_not_found"}), 404
    if attempt.status != "in_progress":
        return jsonify({"error": "attempt_closed"}), 409
    question_id = str(request.form.get("questionId") or "").strip()
    upload = request.files.get("audio")
    question = _question_map(attempt).get(question_id)
    if not question or question.get("response_type") != "recording" or not upload:
        return jsonify({"error": "invalid_recording_request"}), 400
    payload = upload.read(MAX_RECORDING_BYTES + 1)
    if len(payload) > MAX_RECORDING_BYTES:
        return jsonify({"error": "recording_too_large"}), 413
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in {".webm", ".wav", ".mp3", ".m4a", ".ogg"}:
        suffix = ".webm"
    relative = Path("toefl_mock") / attempt.id / f"{uuid.uuid4().hex}{suffix}"
    target = Path(current_app.config["UPLOAD_FOLDER"]) / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    token = relative.as_posix()
    _upsert_response(attempt, question_id, {"recorded": True}, token)
    db.session.commit()
    return jsonify({"saved": True, "recordingToken": token})


@toefl_mock_bp.post("/api/toefl/attempts/<attempt_id>/route-m2")
def route_m2(attempt_id: str):
    attempt = _owned_attempt(attempt_id)
    if not attempt:
        return jsonify({"error": "attempt_not_found"}), 404
    payload = request.get_json(silent=True) or {}
    subject = str(payload.get("subject") or "").lower()
    if subject not in {"reading", "listening"}:
        return jsonify({"error": "invalid_adaptive_subject"}), 400
    route = route_module_two(attempt.exam_id, subject, _response_map(attempt))
    routes = _load_json_text(attempt.routes_json, {})
    routes[subject] = route
    attempt.routes_json = _json_text(routes)
    db.session.commit()
    return jsonify(route)


@toefl_mock_bp.get("/api/toefl/attempts/<attempt_id>/resume")
def resume_attempt(attempt_id: str):
    attempt = _owned_attempt(attempt_id)
    if not attempt:
        return jsonify({"error": "attempt_not_found"}), 404
    return jsonify(
        {
            "attempt": _serialize_attempt(attempt),
            "definition": definition(
                attempt.exam_id,
                _load_json_text(attempt.sections_json, []),
            ),
        }
    )


@toefl_mock_bp.route(
    "/api/toefl/attempts/<attempt_id>/state", methods=["GET", "PUT"]
)
def attempt_state(attempt_id: str):
    attempt = _owned_attempt(attempt_id)
    if not attempt:
        return jsonify({"error": "attempt_not_found"}), 404
    if request.method == "GET":
        return jsonify({"attempt": _serialize_attempt(attempt)})
    if attempt.status != "in_progress":
        return jsonify({"error": "attempt_closed"}), 409
    payload = request.get_json(silent=True) or {}
    if "state" in payload and isinstance(payload["state"], dict):
        previous = _load_json_text(attempt.state_json, {})
        incoming = payload["state"]
        for key in ("phaseIndex", "groupIndex", "questionIndex"):
            if key in incoming:
                try:
                    previous[key] = max(0, int(incoming[key]))
                except (TypeError, ValueError):
                    return jsonify({"error": "invalid_attempt_state"}), 400
        if "returnTo" in incoming:
            previous["returnTo"] = _safe_return_to(incoming["returnTo"])
        attempt.state_json = _json_text(previous)
    if "currentPhase" in payload:
        phase_id = str(payload["currentPhase"] or "").strip()
        allowed_phases = {
            item["id"] for item in _attempt_definition(attempt)["phases"]
        }
        if phase_id not in allowed_phases:
            return jsonify({"error": "invalid_current_phase"}), 400
        attempt.current_phase = phase_id
    if "remainingSeconds" in payload:
        value = payload["remainingSeconds"]
        try:
            attempt.remaining_seconds = (
                max(0, int(value)) if value is not None else None
            )
        except (TypeError, ValueError):
            return jsonify({"error": "invalid_remaining_seconds"}), 400
    db.session.commit()
    return jsonify({"attempt": _serialize_attempt(attempt)})


@toefl_mock_bp.post("/api/toefl/attempts/<attempt_id>/complete")
def complete_attempt(attempt_id: str):
    attempt = _owned_attempt(attempt_id)
    if not attempt:
        return jsonify({"error": "attempt_not_found"}), 404
    if attempt.status != "completed":
        attempt.status = "completed"
        attempt.completed_at = datetime.now(UTC).replace(tzinfo=None)
        db.session.commit()
    return jsonify({"attempt": _serialize_attempt(attempt)})


@toefl_mock_bp.get("/api/toefl/attempts/<attempt_id>/report")
def attempt_report(attempt_id: str):
    attempt = _owned_attempt(attempt_id)
    if not attempt:
        return jsonify({"error": "attempt_not_found"}), 404
    mock_definition = definition(
        attempt.exam_id,
        _load_json_text(attempt.sections_json, []),
    )
    responses = _response_map(attempt)
    score = score_responses(
        attempt.exam_id,
        responses,
        question_ids={item["id"] for item in mock_definition["questions"]},
    )
    manual_total = sum(
        item.get("grading_status") == "manual"
        for item in mock_definition["questions"]
    )
    return jsonify(
        {
            "attemptId": attempt.id,
            "status": attempt.status,
            "preview": attempt.is_preview,
            "objective": {
                key: score[key]
                for key in ("correct", "auto_total", "answered", "accuracy")
            },
            "manual": {
                "total": manual_total,
                "submitted": sum(
                    item["id"] in responses
                    for item in mock_definition["questions"]
                    if item.get("grading_status") == "manual"
                ),
                "status": "pending_teacher_review" if manual_total else "none",
            },
            "routes": _load_json_text(attempt.routes_json, {}),
            "release": mock_definition["release"],
        }
    )
