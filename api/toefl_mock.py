"""Thin HTTP layer for the TOEFL mock flow described by the v2 spec."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from flask import (
    Blueprint,
    current_app,
    jsonify,
    render_template,
    request,
    send_file,
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
from services import toefl_mock_review as review_workflow
from services.toefl_mock_v2 import (
    PackageNotFoundError,
    PackageReleaseBlockedError,
    definition,
    parse_sections,
    public_catalog,
    require_attempt_allowed,
    route_module_two,
    validate_navigation_state,
    validate_response_value,
)
from services.web_privacy import no_store

toefl_mock_bp = Blueprint("toefl_mock", __name__)
MAX_RECORDING_BYTES = 20 * 1024 * 1024
MIN_RECORDING_DURATION_MS = 250
RECORDING_DURATION_TOLERANCE_MS = 2000
RECORDING_SUFFIXES = {
    ".webm": "audio/webm",
    ".wav": "audio/wav",
    ".mp3": "audio/mpeg",
    ".m4a": "audio/mp4",
    ".ogg": "audio/ogg",
}


def _recording_root() -> Path:
    configured = current_app.config.get("TOEFL_MOCK_RECORDING_FOLDER")
    root = Path(
        configured
        or (Path(current_app.root_path) / "private_uploads" / "toefl_mock")
    )
    root = root.resolve()
    public_root = Path(current_app.config["UPLOAD_FOLDER"]).resolve()
    try:
        root.relative_to(public_root)
    except ValueError:
        return root
    raise RuntimeError(
        "TOEFL_MOCK_RECORDING_FOLDER must be outside the public UPLOAD_FOLDER"
    )


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
    parsed = urlsplit(target)
    if (
        target.startswith("/")
        and not target.startswith("//")
        and not parsed.scheme
        and not parsed.netloc
        and "\\" not in target
        and not any(ord(char) < 32 for char in target)
    ):
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
    mock_definition = _attempt_definition(attempt)
    _refresh_server_clock(attempt, mock_definition)
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


def _utcnow_naive() -> datetime:
    # Production still runs Python 3.10, where datetime.UTC is unavailable.
    return datetime.now(timezone.utc).replace(tzinfo=None)  # noqa: UP017


def _state(attempt: ToeflMockAttempt) -> dict[str, Any]:
    value = _load_json_text(attempt.state_json, {})
    return value if isinstance(value, dict) else {}


def _phase_indices(attempt: ToeflMockAttempt) -> tuple[int, int]:
    current = _state(attempt)
    try:
        return max(0, int(current.get("phaseIndex", 0))), max(
            0, int(current.get("groupIndex", 0))
        )
    except (TypeError, ValueError):
        return 0, 0


def _phase_started_at(state: dict[str, Any], fallback: datetime) -> datetime:
    value = state.get("phaseStartedAt")
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if parsed.tzinfo:
                return parsed.astimezone(timezone.utc).replace(  # noqa: UP017
                    tzinfo=None
                )
            return parsed
        except ValueError:
            pass
    return fallback


def _refresh_server_clock(
    attempt: ToeflMockAttempt, mock_definition: dict[str, Any]
) -> int | None:
    phase_index, _ = _phase_indices(attempt)
    phases = mock_definition.get("phases", [])
    if not 0 <= phase_index < len(phases):
        return attempt.remaining_seconds
    phase = phases[phase_index]
    duration = phase.get("duration_seconds")
    if duration is None:
        attempt.remaining_seconds = None
        return None
    state = _state(attempt)
    started = _phase_started_at(state, attempt.started_at or _utcnow_naive())
    elapsed = max(0, int((_utcnow_naive() - started).total_seconds()))
    computed = max(0, int(duration) - elapsed)
    stored = attempt.remaining_seconds
    attempt.remaining_seconds = min(
        computed, int(stored) if stored is not None else int(duration)
    )
    return attempt.remaining_seconds


def _phase_timer_snapshots(state: dict[str, Any]) -> dict[str, int | None]:
    snapshots = state.get("phaseTimers")
    if not isinstance(snapshots, dict):
        return {}
    return {
        str(phase_id): value
        for phase_id, value in snapshots.items()
        if isinstance(phase_id, str) and (isinstance(value, int) or value is None)
    }


def _save_phase_timer_snapshot(
    state: dict[str, Any], phase_id: str, remaining_seconds: int | None
) -> None:
    snapshots = _phase_timer_snapshots(state)
    snapshots[phase_id] = remaining_seconds
    state["phaseTimers"] = snapshots


def _validated_audio_state(
    attempt: ToeflMockAttempt,
    mock_definition: dict[str, Any],
    value: Any,
) -> tuple[dict[str, dict[str, bool]] | None, tuple[dict[str, str], int] | None]:
    if not isinstance(value, dict):
        return None, ({"error": "audio_state_invalid"}, 400)
    allowed_audio_ids = {
        phase.get("id")
        for phase in mock_definition.get("phases", [])
        if phase.get("section") == "listening"
    }
    allowed_audio_ids.update(
        group.get("id")
        for group in mock_definition.get("groups", [])
        if group.get("subject") == "listening"
        and (group.get("stimulus") or {}).get("format") == "audio"
        and (group.get("stimulus") or {}).get("playback_scope") == "group"
    )
    allowed_fields = {"ready", "skipped", "played"}
    validated: dict[str, dict[str, bool]] = {}
    if len(value) > len(allowed_audio_ids):
        return None, ({"error": "audio_state_invalid"}, 400)
    for audio_id, state in value.items():
        if audio_id not in allowed_audio_ids or not isinstance(state, dict):
            return None, ({"error": "audio_state_invalid"}, 400)
        if set(state) - allowed_fields:
            return None, ({"error": "audio_state_invalid"}, 400)
        if any(not isinstance(item, bool) for item in state.values()):
            return None, ({"error": "audio_state_invalid"}, 400)
        if state.get("skipped") and not attempt.is_preview:
            return None, ({"error": "audio_skip_preview_only"}, 409)
        validated[audio_id] = {
            key: state[key] for key in allowed_fields if key in state
        }
    return validated, None


def _question_phase_index(
    mock_definition: dict[str, Any], question_id: str
) -> int | None:
    for index, phase in enumerate(mock_definition.get("phases", [])):
        if question_id in phase.get("question_ids", []):
            return index
    return None


def _start_permission(preview: bool) -> tuple[dict[str, Any], int] | None:
    authenticated = bool(getattr(current_user, "is_authenticated", False))
    role = getattr(current_user, "role", None)
    if not preview and not authenticated:
        return {"error": "login_required", "message": "正式模考需要学生账号"}, 401
    if authenticated and role not in {
        User.ROLE_STUDENT,
        User.ROLE_ADMIN,
        User.ROLE_TEACHER,
        User.ROLE_ASSISTANT,
    }:
        return {"error": "forbidden", "message": "当前账号无权开始 TOEFL 模考"}, 403
    if not preview and role != User.ROLE_STUDENT:
        return {"error": "student_required", "message": "正式模考只对学生账号开放"}, 403
    return None


def _require_current_phase_question(
    attempt: ToeflMockAttempt, question_id: str
) -> tuple[dict[str, Any] | None, tuple[dict[str, Any], int] | None]:
    mock_definition = _attempt_definition(attempt)
    question = _question_map(attempt).get(question_id)
    if not question:
        return None, ({"error": "question_not_in_attempt"}, 400)
    current_phase, _ = _phase_indices(attempt)
    question_phase = _question_phase_index(mock_definition, question_id)
    if question_phase is None or question_phase != current_phase:
        return None, ({"error": "question_not_current"}, 409)
    return question, None


@toefl_mock_bp.errorhandler(PackageNotFoundError)
def _package_not_found(exc):
    return jsonify({"error": "test_not_found", "message": str(exc)}), 404


@toefl_mock_bp.errorhandler(PackageReleaseBlockedError)
def _package_blocked(exc):
    return jsonify({"error": "release_blocked", "message": str(exc)}), 409


@toefl_mock_bp.errorhandler(ValueError)
def _invalid_request(exc):
    return jsonify({"error": "invalid_request", "message": str(exc)}), 400


@toefl_mock_bp.get("/toefl/mock")
def mock_catalog():
    return render_template("toefl/mock_index.html", exams=public_catalog())


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
    preview = payload.get("preview") is True
    device_check = payload.get("deviceCheck")
    if not isinstance(device_check, dict):
        device_check = {}
    permission_error = _start_permission(preview)
    if permission_error:
        body, status = permission_error
        return jsonify(body), status
    if "speaking" in sections and device_check.get("microphone") != "passed":
        return jsonify(
            {
                "error": "microphone_check_required",
                "message": "开始包含 Speaking 的模考前必须完成麦克风测试",
            }
        ), 409
    require_attempt_allowed(mock_definition, preview)
    first_phase = mock_definition["phases"][0] if mock_definition["phases"] else {}
    profile = _current_student()
    now = _utcnow_naive()
    initial_state = {
        "phaseIndex": 0,
        "groupIndex": 0,
        "questionIndex": 0,
        "returnTo": _safe_return_to(payload.get("returnTo")),
        "phaseStartedAt": now.isoformat() + "Z",
        "phaseTimers": {
            first_phase.get("id"): first_phase.get("duration_seconds")
        },
        "deviceCheck": device_check,
    }
    attempt = ToeflMockAttempt(
        id=str(uuid.uuid4()),
        student_id=profile.id if profile else None,
        actor_key=_actor_key(),
        exam_id=mock_definition["test"]["id"],
        sections_json=_json_text(sections),
        is_preview=preview,
        current_phase=first_phase.get("id"),
        remaining_seconds=first_phase.get("duration_seconds"),
        state_json=_json_text(initial_state),
        routes_json="{}",
        started_at=now,
        updated_at=now,
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
    question, error = _require_current_phase_question(attempt, question_id)
    if error:
        return jsonify(error[0]), error[1]
    if not question.get("available", True):
        return jsonify(
            {
                "error": "question_blocked",
                "message": "该题来源不完整，不能作答或进入判分分母",
            }
        ), 409
    response_error = validate_response_value(question, payload.get("response"))
    if response_error:
        return jsonify({"error": response_error}), 400
    mock_definition = _attempt_definition(attempt)
    if _refresh_server_clock(attempt, mock_definition) == 0 and (
        mock_definition["phases"][_phase_indices(attempt)[0]].get("duration_seconds") is not None
    ):
        return jsonify({"error": "phase_expired"}), 409
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
    question, error = _require_current_phase_question(attempt, question_id)
    if error:
        return jsonify(error[0]), error[1]
    if (
        not question
        or question.get("response_type") != "recording"
        or not question.get("available", True)
        or not upload
    ):
        return jsonify({"error": "invalid_recording_request"}), 400
    mock_definition = _attempt_definition(attempt)
    phase_index, group_index = _phase_indices(attempt)
    phase = mock_definition["phases"][phase_index]
    current_group_ids = phase.get("group_ids", [])
    if (
        not 0 <= group_index < len(current_group_ids)
        or question.get("group_id") != current_group_ids[group_index]
    ):
        return jsonify({"error": "question_not_current"}), 409
    existing = ToeflMockResponse.query.filter_by(
        attempt_id=attempt.id,
        question_id=question_id,
    ).first()
    maximum_takes = (question.get("input_config") or {}).get(
        "maximum_takes_test_mode"
    )
    if (
        not attempt.is_preview
        and maximum_takes == 1
        and existing
        and existing.recording_token
    ):
        return jsonify({"error": "recording_take_limit_reached"}), 409
    try:
        duration_ms = int(request.form.get("durationMs") or 0)
    except (TypeError, ValueError):
        return jsonify({"error": "recording_duration_invalid"}), 400
    response_seconds = (question.get("input_config") or {}).get(
        "response_seconds"
    )
    if not isinstance(response_seconds, (int, float)) or response_seconds <= 0:
        return jsonify({"error": "recording_timing_unavailable"}), 409
    maximum_duration_ms = (
        int(response_seconds * 1000) + RECORDING_DURATION_TOLERANCE_MS
    )
    if (
        duration_ms < MIN_RECORDING_DURATION_MS
        or duration_ms > maximum_duration_ms
    ):
        return jsonify({"error": "recording_duration_invalid"}), 400
    if _refresh_server_clock(attempt, mock_definition) == 0:
        return jsonify({"error": "phase_expired"}), 409
    payload = upload.read(MAX_RECORDING_BYTES + 1)
    if not payload:
        return jsonify({"error": "recording_empty"}), 400
    if len(payload) > MAX_RECORDING_BYTES:
        return jsonify({"error": "recording_too_large"}), 413
    allowed_mime = {
        "audio/webm",
        "audio/wav",
        "audio/x-wav",
        "audio/mpeg",
        "audio/mp4",
        "audio/ogg",
        "video/webm",
    }
    suffix = Path(upload.filename or "").suffix.lower()
    if upload.mimetype and upload.mimetype not in allowed_mime and not (
        upload.mimetype == "application/octet-stream"
        and suffix in {".webm", ".wav", ".mp3", ".m4a", ".ogg"}
    ):
        return jsonify({"error": "recording_type_invalid"}), 400
    if suffix not in {".webm", ".wav", ".mp3", ".m4a", ".ogg"}:
        suffix = ".webm"
    relative = Path(attempt.id) / f"{uuid.uuid4().hex}{suffix}"
    target = _recording_root() / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(payload)
    token = relative.as_posix()
    recording_id = uuid.uuid4().hex
    _upsert_response(
        attempt,
        question_id,
        {
            "recorded": True,
            "recordingId": recording_id,
            "durationMs": duration_ms,
            "mimeType": upload.mimetype or "application/octet-stream",
        },
        token,
    )
    db.session.commit()
    return jsonify({"saved": True, "recordingId": recording_id, "durationMs": duration_ms})


@toefl_mock_bp.post("/api/toefl/attempts/<attempt_id>/route-m2")
def route_m2(attempt_id: str):
    attempt = _owned_attempt(attempt_id)
    if not attempt:
        return jsonify({"error": "attempt_not_found"}), 404
    if attempt.status != "in_progress":
        return jsonify({"error": "attempt_closed"}), 409
    payload = request.get_json(silent=True) or {}
    subject = str(payload.get("subject") or "").lower()
    if subject not in {"reading", "listening"}:
        return jsonify({"error": "invalid_adaptive_subject"}), 400
    routes = _load_json_text(attempt.routes_json, {})
    if subject in routes:
        return jsonify(routes[subject])
    mock_definition = _attempt_definition(attempt)
    current_phase, _ = _phase_indices(attempt)
    if not 0 <= current_phase < len(mock_definition["phases"]):
        return jsonify({"error": "invalid_server_state"}), 409
    phase = mock_definition["phases"][current_phase]
    if phase.get("section") != subject or phase.get("module") != "m1":
        return jsonify({"error": "m1_not_current"}), 409
    if _phase_indices(attempt)[1] != len(phase.get("group_ids", [])) - 1:
        return jsonify({"error": "m1_not_complete"}), 409
    route = route_module_two(attempt.exam_id, subject, _response_map(attempt))
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
        _refresh_server_clock(attempt, _attempt_definition(attempt))
        return jsonify({"attempt": _serialize_attempt(attempt)})
    if attempt.status != "in_progress":
        return jsonify({"error": "attempt_closed"}), 409
    payload = request.get_json(silent=True) or {}
    mock_definition = _attempt_definition(attempt)
    previous = _state(attempt)
    current_phase, current_group = _phase_indices(attempt)
    incoming = payload.get("state") if isinstance(payload.get("state"), dict) else {}
    try:
        target_phase = int(incoming.get("phaseIndex", current_phase))
        target_group = int(incoming.get("groupIndex", current_group))
    except (TypeError, ValueError):
        return jsonify({"error": "invalid_attempt_state"}), 400
    error = validate_navigation_state(
        mock_definition, current_phase, current_group, target_phase, target_group
    )
    if error:
        status = 409 if error in {
            "invalid_navigation_jump",
            "back_navigation_disabled",
        } else 400
        return jsonify({"error": error}), status
    current_phase_definition = mock_definition["phases"][current_phase]
    target_phase_definition = mock_definition["phases"][target_phase]
    if (
        target_phase != current_phase
        and current_phase_definition.get("adaptive_checkpoint")
        and target_phase_definition.get("section") == current_phase_definition.get("section")
        and target_phase_definition.get("module") == "m2"
        and current_phase_definition.get("section") not in _load_json_text(attempt.routes_json, {})
    ):
        return jsonify({"error": "m2_route_required"}), 409
    target_phase_id = mock_definition["phases"][target_phase]["id"]
    if "currentPhase" in payload and str(payload["currentPhase"] or "") != target_phase_id:
        return jsonify({"error": "invalid_current_phase"}), 400
    if "audio" in incoming:
        audio_state, audio_error = _validated_audio_state(
            attempt, mock_definition, incoming["audio"]
        )
        if audio_error:
            return jsonify(audio_error[0]), audio_error[1]
        previous["audio"] = audio_state
    if "returnTo" in incoming:
        previous["returnTo"] = _safe_return_to(incoming["returnTo"])
    previous["phaseIndex"] = target_phase
    previous["groupIndex"] = target_group
    if "questionIndex" in incoming:
        try:
            previous["questionIndex"] = max(0, int(incoming["questionIndex"]))
        except (TypeError, ValueError):
            return jsonify({"error": "invalid_attempt_state"}), 400
    phase_changed = target_phase != current_phase
    if phase_changed:
        current_phase_id = current_phase_definition["id"]
        _refresh_server_clock(attempt, mock_definition)
        _save_phase_timer_snapshot(
            previous, current_phase_id, attempt.remaining_seconds
        )
        target_phase_id = target_phase_definition["id"]
        snapshots = _phase_timer_snapshots(previous)
        if target_phase_id in snapshots:
            target_remaining = snapshots[target_phase_id]
        else:
            target_remaining = target_phase_definition.get("duration_seconds")
            _save_phase_timer_snapshot(previous, target_phase_id, target_remaining)
        now = _utcnow_naive()
        previous["phaseStartedAt"] = now.isoformat() + "Z"
        attempt.remaining_seconds = target_remaining
    else:
        server_remaining = _refresh_server_clock(attempt, mock_definition)
        if "remainingSeconds" in payload:
            if payload["remainingSeconds"] is None:
                if mock_definition["phases"][target_phase].get("duration_seconds") is not None:
                    return jsonify({"error": "invalid_remaining_seconds"}), 400
                attempt.remaining_seconds = None
            else:
                try:
                    requested = int(payload["remainingSeconds"])
                except (TypeError, ValueError):
                    return jsonify({"error": "invalid_remaining_seconds"}), 400
                if server_remaining is not None and requested > server_remaining + 1:
                    return jsonify({"error": "remaining_time_increase"}), 409
                attempt.remaining_seconds = (
                    max(0, requested) if server_remaining is not None else None
                )
        _save_phase_timer_snapshot(
            previous,
            target_phase_definition["id"],
            attempt.remaining_seconds,
        )
    attempt.state_json = _json_text(previous)
    attempt.current_phase = target_phase_id
    db.session.commit()
    return jsonify({"attempt": _serialize_attempt(attempt)})


@toefl_mock_bp.post("/api/toefl/attempts/<attempt_id>/complete")
def complete_attempt(attempt_id: str):
    attempt = _owned_attempt(attempt_id)
    if not attempt:
        return jsonify({"error": "attempt_not_found"}), 404
    if attempt.status == "in_progress":
        mock_definition = _attempt_definition(attempt)
        current_phase, current_group = _phase_indices(attempt)
        if current_phase != len(mock_definition["phases"]) - 1:
            return jsonify({"error": "attempt_incomplete"}), 409
        if current_group != len(mock_definition["phases"][current_phase].get("group_ids", [])) - 1:
            return jsonify({"error": "attempt_incomplete"}), 409
    if attempt.status != "completed":
        attempt.status = "completed"
        attempt.completed_at = _utcnow_naive()
        attempt.remaining_seconds = 0
        review_workflow.ensure_review_state(attempt)
        db.session.commit()
    return jsonify({"attempt": _serialize_attempt(attempt)})


@toefl_mock_bp.get("/api/toefl/attempts/<attempt_id>/report")
def attempt_report(attempt_id: str):
    attempt = _owned_attempt(attempt_id)
    if not attempt:
        return jsonify({"error": "attempt_not_found"}), 404
    if attempt.status != "completed":
        return jsonify({"error": "attempt_incomplete"}), 409
    mock_definition = definition(
        attempt.exam_id,
        _load_json_text(attempt.sections_json, []),
    )
    if review_workflow.ensure_review_state(attempt):
        db.session.commit()
    review = review_workflow.build_review(attempt, student_view=True)
    objective = review["summary"]["objective"]
    practice_breakdown = review["summary"]["practice_breakdown"]
    return jsonify(
        {
            "attemptId": attempt.id,
            "status": attempt.status,
            "preview": attempt.is_preview,
            "objective": {
                "correct": objective["correct"],
                "auto_total": objective["eligible_total"],
                "answered": objective["answered"],
                "accuracy": objective["accuracy"],
            },
            "manual": {
                "total": review["summary"]["manual_total"],
                "submitted": review["summary"]["manual_submitted"],
                "status": (
                    attempt.review_status
                    if review["summary"]["manual_total"]
                    else review_workflow.REVIEW_NOT_REQUIRED
                ),
            },
            "practice_breakdown": practice_breakdown,
            "blocked": {
                "total": sum(
                    item.get("grading_status") == "blocked"
                    for item in mock_definition["questions"]
                ),
                "excluded_from_objective_denominator": True,
            },
            "routes": _load_json_text(attempt.routes_json, {}),
            "release": mock_definition["release"],
        }
    )


def _private_json(payload: dict[str, Any], status: int = 200):
    response = no_store(jsonify(payload))
    response.headers["Cache-Control"] = (
        "private, no-store, no-cache, must-revalidate, max-age=0"
    )
    return response, status


def _review_recording_url(row: ToeflMockResponse) -> str:
    return f"/api/toefl/attempts/{row.attempt_id}/responses/{row.id}/recording"


def _review_attempt(attempt_id: str) -> ToeflMockAttempt | None:
    return db.session.get(ToeflMockAttempt, attempt_id)


def _review_json(attempt: ToeflMockAttempt, *, student_view: bool):
    changed = review_workflow.ensure_review_state(attempt)
    if changed:
        db.session.commit()
    return review_workflow.build_review(
        attempt,
        student_view=student_view,
        recording_url_factory=_review_recording_url,
    )


@toefl_mock_bp.get("/api/toefl/attempts/<attempt_id>/review")
def student_attempt_review(attempt_id: str):
    attempt = _owned_attempt(attempt_id)
    if not attempt:
        return _private_json({"error": "attempt_not_found"}, 404)
    if attempt.status != "completed":
        return _private_json({"error": "attempt_incomplete"}, 409)
    if _is_staff():
        return _private_json({"error": "student_endpoint_required"}, 403)
    return _private_json(_review_json(attempt, student_view=True))


@toefl_mock_bp.get("/api/toefl/attempts/history")
def student_attempt_history():
    profile = _current_student()
    if not profile:
        return _private_json({"error": "student_login_required"}, 401)
    attempts = (
        ToeflMockAttempt.query.filter_by(
            student_id=profile.id,
            status="completed",
        )
        .order_by(ToeflMockAttempt.completed_at.desc())
        .all()
    )
    return _private_json(
        {
            "attempts": [review_workflow.attempt_summary(item) for item in attempts]
        }
    )


def _teacher_attempt_query():
    query = ToeflMockAttempt.query
    status = str(request.args.get("status") or "completed").strip()
    if status and status != "all":
        query = query.filter(ToeflMockAttempt.status == status)
    review_status = str(request.args.get("reviewStatus") or "").strip()
    if review_status:
        query = query.filter(ToeflMockAttempt.review_status == review_status)
    exam_id = str(request.args.get("examId") or "").strip()
    if exam_id:
        query = query.filter(ToeflMockAttempt.exam_id == exam_id)
    student = str(request.args.get("student") or "").strip()
    if student:
        ids = [
            item.id
            for item in StudentProfile.query.filter(
                StudentProfile.full_name.ilike(f"%{student}%"),
                StudentProfile.is_deleted.is_(False),
            ).all()
        ]
        query = query.filter(ToeflMockAttempt.student_id.in_(ids or [-1]))
    return query.order_by(ToeflMockAttempt.completed_at.desc())


@toefl_mock_bp.get("/api/toefl/teacher/attempts")
def teacher_attempt_list_api():
    if not _is_staff():
        return _private_json({"error": "staff_required"}, 403)
    attempts = _teacher_attempt_query().all()
    return _private_json(
        {"attempts": [review_workflow.attempt_summary(item) for item in attempts]}
    )


@toefl_mock_bp.get("/api/toefl/teacher/attempts/<attempt_id>")
def teacher_attempt_detail_api(attempt_id: str):
    if not _is_staff():
        return _private_json({"error": "staff_required"}, 403)
    attempt = _review_attempt(attempt_id)
    if not attempt:
        return _private_json({"error": "attempt_not_found"}, 404)
    if attempt.status != "completed":
        return _private_json({"error": "attempt_incomplete"}, 409)
    payload = _review_json(attempt, student_view=False)
    payload["student"] = {
        "id": attempt.student_id,
        "name": getattr(attempt.student, "full_name", None) or "未绑定学生",
    }
    return _private_json(payload)


def _teacher_review_attempt(attempt_id: str):
    if not _is_staff():
        return None, _private_json({"error": "staff_required"}, 403)
    attempt = _review_attempt(attempt_id)
    if not attempt:
        return None, _private_json({"error": "attempt_not_found"}, 404)
    if attempt.status != "completed":
        return None, _private_json({"error": "attempt_incomplete"}, 409)
    return attempt, None


@toefl_mock_bp.patch("/api/toefl/teacher/attempts/<attempt_id>/review")
def save_teacher_review(attempt_id: str):
    attempt, error = _teacher_review_attempt(attempt_id)
    if error:
        return error
    if not request.is_json:
        return _private_json({"error": "json_required"}, 415)
    ok, reason = review_workflow.save_reviews(
        attempt,
        request.get_json(silent=True) or {},
        int(current_user.id),
    )
    if not ok:
        status = 409 if reason == "review_version_conflict" else 400
        return _private_json({"error": reason}, status)
    db.session.commit()
    return _private_json(_review_json(attempt, student_view=False))


@toefl_mock_bp.post("/api/toefl/teacher/attempts/<attempt_id>/review/publish")
def publish_teacher_review(attempt_id: str):
    attempt, error = _teacher_review_attempt(attempt_id)
    if error:
        return error
    if not request.is_json:
        return _private_json({"error": "json_required"}, 415)
    ok, reason = review_workflow.publish_reviews(
        attempt,
        request.get_json(silent=True) or {},
        int(current_user.id),
    )
    if not ok:
        status = 409 if reason in {
            "review_version_conflict",
            "manual_submission_incomplete",
            "manual_review_incomplete",
        } else 400
        return _private_json({"error": reason}, status)
    db.session.commit()
    return _private_json(_review_json(attempt, student_view=False))


@toefl_mock_bp.post("/api/toefl/teacher/attempts/<attempt_id>/review/reopen")
def reopen_teacher_review(attempt_id: str):
    attempt, error = _teacher_review_attempt(attempt_id)
    if error:
        return error
    if not request.is_json:
        return _private_json({"error": "json_required"}, 415)
    payload = request.get_json(silent=True) or {}
    ok, reason = review_workflow.reopen_review(
        attempt,
        int(current_user.id),
        payload.get("version"),
    )
    if not ok:
        status = 409 if reason in {
            "review_not_published",
            "review_version_conflict",
        } else 400
        return _private_json({"error": reason}, status)
    db.session.commit()
    return _private_json(_review_json(attempt, student_view=False))


def _recording_path(attempt: ToeflMockAttempt, row: ToeflMockResponse) -> Path | None:
    token = str(row.recording_token or "")
    relative = Path(token)
    parts = relative.parts
    if (
        relative.is_absolute()
        or len(parts) != 2
        or parts[0] != attempt.id
        or any(part in {"", ".", ".."} for part in parts)
        or Path(parts[1]).suffix.lower() not in RECORDING_SUFFIXES
    ):
        return None
    root = _recording_root()
    expected_dir = (root / attempt.id).resolve()
    target = (root / relative).resolve()
    try:
        target.relative_to(expected_dir)
    except ValueError:
        return None
    try:
        if not target.is_file() or target.stat().st_size > MAX_RECORDING_BYTES:
            return None
    except OSError:
        return None
    return target


@toefl_mock_bp.get("/api/toefl/attempts/<attempt_id>/responses/<int:response_id>/recording")
def stream_attempt_recording(attempt_id: str, response_id: int):
    attempt = _owned_attempt(attempt_id)
    if not attempt:
        return _private_json({"error": "attempt_not_found"}, 404)
    if attempt.status != "completed":
        return _private_json({"error": "attempt_incomplete"}, 409)
    if not _is_staff() and attempt.review_status != review_workflow.REVIEW_PUBLISHED:
        return _private_json({"error": "review_not_published"}, 403)
    row = db.session.get(ToeflMockResponse, response_id)
    if not row or row.attempt_id != attempt.id or not row.recording_token:
        return _private_json({"error": "recording_not_found"}, 404)
    target = _recording_path(attempt, row)
    if not target:
        return _private_json({"error": "recording_not_found"}, 404)
    response = send_file(
        target,
        mimetype=RECORDING_SUFFIXES[target.suffix.lower()],
        conditional=True,
        max_age=0,
        etag=False,
    )
    response = no_store(response)
    response.headers["Cache-Control"] = (
        "private, no-store, no-cache, must-revalidate, max-age=0"
    )
    response.headers["Accept-Ranges"] = "bytes"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@toefl_mock_bp.get("/toefl/mock/history")
def student_attempt_history_page():
    profile = _current_student()
    if not profile:
        return "student login required", 401
    attempts = (
        ToeflMockAttempt.query.filter_by(student_id=profile.id, status="completed")
        .order_by(ToeflMockAttempt.completed_at.desc())
        .all()
    )
    response = render_template(
        "toefl/attempt_history.html",
        attempts=[review_workflow.attempt_summary(item) for item in attempts],
    )
    return no_store(response)


@toefl_mock_bp.get("/toefl/mock/attempts/<attempt_id>/review")
def student_attempt_review_page(attempt_id: str):
    attempt = _owned_attempt(attempt_id)
    if not attempt:
        return "attempt not found", 404
    if attempt.status != "completed":
        return "attempt incomplete", 409
    if _is_staff():
        return "student endpoint required", 403
    response = render_template(
        "toefl/review_detail.html",
        review=_review_json(attempt, student_view=True),
        student_view=True,
    )
    return no_store(response)


@toefl_mock_bp.get("/toefl/mock/teacher/attempts")
def teacher_attempt_list_page():
    if not _is_staff():
        return "staff login required", 403
    attempts = _teacher_attempt_query().all()
    response = render_template(
        "toefl/teacher_attempts.html",
        attempts=[review_workflow.attempt_summary(item) for item in attempts],
    )
    return no_store(response)


@toefl_mock_bp.get("/toefl/mock/teacher/attempts/<attempt_id>")
def teacher_attempt_detail_page(attempt_id: str):
    attempt, error = _teacher_review_attempt(attempt_id)
    if error:
        return error
    response = render_template(
        "toefl/review_detail.html",
        review=_review_json(attempt, student_view=False),
        student_view=False,
        student={
            "id": attempt.student_id,
            "name": getattr(attempt.student, "full_name", None) or "未绑定学生",
        },
    )
    return no_store(response)
