"""Optional IELTS integrity endpoints, isolated from exam saving and grading."""

from __future__ import annotations

import json
import math
from urllib.parse import urlsplit

from flask import Blueprint, abort, jsonify, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy import select

from api.mock_exam_admin import _can_manage
from models import MockExam, MockExamSession, db
from services import exam_integrity as integrity
from services.web_privacy import no_store

exam_integrity_bp = Blueprint("exam_integrity", __name__)
_BASE = "/admin/mock-exams/<int:exam_id>/integrity"
_STUDENT = "/api/exam/<int:exam_id>/session/<token>/integrity"
_SECTIONS = {"process", "listening", "reading", "writing"}
_EVENTS = {
    "hello",
    "ack",
    "hidden",
    "visible",
    "heartbeat",
    "blur",
    "viewport",
    "copy_blocked",
    "paste_blocked",
}


def _json(payload, status=200):
    return jsonify(payload), status


def _off():
    return {
        "ok": True,
        "mode": "off",
        "enabled": False,
        "is_locked": False,
        "device_conflict": False,
        "acked": True,
    }


def _session_row(exam_id, *, token=None, session_id=None):
    table = MockExamSession.__table__
    columns = (
        "id",
        "exam_id",
        "student_name",
        "status",
        "current_section",
        "started_at",
        "listening_submitted_at",
        "reading_submitted_at",
        "writing_submitted_at",
    )
    query = select(*(table.c[name] for name in columns)).where(table.c.exam_id == exam_id)
    query = (
        query.where(table.c.access_token == token)
        if token is not None
        else query.where(table.c.id == session_id)
    )
    with db.engine.connect() as connection:
        return connection.execute(query).mappings().first()


def _exam_row(exam_id):
    with db.engine.connect() as connection:
        return (
            connection.execute(select(MockExam.__table__).where(MockExam.id == exam_id))
            .mappings()
            .first()
        )


def _require_exam(exam_id):
    if not _can_manage(current_user):
        abort(403)
    exam = _exam_row(exam_id)
    if not exam:
        abort(404)
    return exam


def _small_json(*, beacon=False):
    if request.content_length is not None and request.content_length > 2048:
        abort(413)
    if not request.is_json and not (beacon and request.mimetype == "text/plain"):
        abort(415)
    raw = request.stream.read(2049)
    if len(raw) > 2048:
        abort(413)
    try:
        value = json.loads(raw)
    except (ValueError, UnicodeError, RecursionError):
        abort(400)
    if not isinstance(value, dict):
        abort(400)
    return value


def _admin_json():
    # JSON-only POST follows mock_exam_review's CSRF boundary; explicit foreign
    # Origin is also rejected. No CORS permission is granted by this blueprint.
    origin = request.headers.get("Origin")
    if origin:
        try:
            parsed = urlsplit(origin)
        except ValueError:
            abort(403)
        if parsed.scheme not in {"http", "https"} or parsed.netloc != request.host:
            abort(403)
    return _small_json()


def _bounded_number(value, lower, upper, *, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        abort(400)
    if not math.isfinite(value) or value < lower or value > upper:
        abort(400)
    if integer and int(value) != value:
        abort(400)
    return int(value) if integer else value


def _event_payload(data):
    if not isinstance(data.get("type"), str) or not isinstance(data.get("section"), str):
        abort(400)
    if data["type"] not in _EVENTS or data["section"] not in _SECTIONS:
        abort(400)
    result = {"type": data["type"], "section": data["section"]}
    for key, minimum, maximum in (("device_id", 8, 160), ("page_id", 1, 96)):
        value = data.get(key)
        if not isinstance(value, str) or not minimum <= len(value) <= maximum:
            abort(400)
        result[key] = value
    if "question" in data:
        if not isinstance(data["question"], (str, int)) or isinstance(data["question"], bool):
            abort(400)
        result["question"] = str(data["question"])[:80]
    for key, upper in (("client_hidden_ms", 86400000), ("length", 1000000), ("viewport_ratio", 10)):
        if key in data:
            result[key] = _bounded_number(data[key], 0, upper, integer=key == "length")
    if "detail" in data:
        detail = data["detail"]
        if not isinstance(detail, dict):
            abort(400)
        clean = {}
        for key, upper in (
            ("length", 1000000),
            ("ratio", 10),
            ("width", 100000),
            ("screen_width", 100000),
        ):
            if key in detail:
                clean[key] = _bounded_number(detail[key], 0, upper, integer=key == "length")
        if "blocked" in detail:
            if not isinstance(detail["blocked"], bool):
                abort(400)
            clean["blocked"] = detail["blocked"]
        if "signal" in detail:
            if detail["signal"] not in ("paste", "drop", "beforeinput", "copy", "cut"):
                abort(400)
            clean["signal"] = detail["signal"]
        result["detail"] = clean
    if "client_ts" in data:
        value = data["client_ts"]
        if isinstance(value, str) and len(value) <= 64:
            result["client_ts"] = value
        else:
            result["client_ts"] = _bounded_number(value, 0, 1e16)
    return result


def _student_response(exam_id, token, *, payload=None):
    try:
        row = _session_row(exam_id, token=token)
        if not row:
            return _json({"ok": False, "error": "session_not_found"}, 404)
        if row["status"] == MockExamSession.STATUS_SUBMITTED:
            return _json(_off())
        if payload is None:
            state = integrity.student_state(
                exam_id,
                row["id"],
                device_id=request.headers.get("X-Exam-Integrity-Device", "")[:160],
                section=request.args.get("section", "process"),
            )
        else:
            submitted = [
                section for section in _SECTIONS - {"process"} if row[f"{section}_submitted_at"]
            ]
            state = integrity.record_event(
                exam_id,
                row["id"],
                payload,
                current_section=row["current_section"],
                submitted_sections=submitted,
            )
        return _json({"ok": True, **state})
    except Exception:
        # Never roll back db.session: the optional feature owns no exam writes.
        return _json(_off())


@exam_integrity_bp.app_template_global()
def exam_integrity_config(exam_id, token, section):
    try:
        policy = integrity.read_policy(exam_id)
        if policy["mode"] == "off" or section not in _SECTIONS:
            return None
        row = _session_row(exam_id, token=token)
        if not row or row["status"] == MockExamSession.STATUS_SUBMITTED:
            return None
        return {
            **policy,
            "exam_id": exam_id,
            "token": token,
            "section": section,
            "student_name": row["student_name"],
            "started_at": row["started_at"].isoformat() + "Z" if row["started_at"] else "",
            "state_url": url_for("exam_integrity.student_state", exam_id=exam_id, token=token),
            "event_url": url_for("exam_integrity.student_event", exam_id=exam_id, token=token),
            "guide_url": url_for("exam_integrity.guide"),
        }
    except Exception:
        return None


@exam_integrity_bp.app_template_global()
def exam_integrity_summary(exam_id, session_id):
    try:
        if not _can_manage(current_user) or not _session_row(exam_id, session_id=session_id):
            return None
        return integrity.admin_states(exam_id, [session_id]).get(str(session_id))
    except Exception:
        return None


@exam_integrity_bp.after_request
def _private_headers(response):
    return no_store(response)


@exam_integrity_bp.get(_STUDENT + "/state")
def student_state(exam_id, token):
    return _student_response(exam_id, token)


@exam_integrity_bp.post(_STUDENT + "/event")
def student_event(exam_id, token):
    return _student_response(exam_id, token, payload=_event_payload(_small_json(beacon=True)))


@exam_integrity_bp.get("/exam/guide")
def guide():
    return render_template("exam/integrity_guide.html")


@exam_integrity_bp.get("/exam/integrity-help")
def help_page():
    return render_template("exam/integrity_help.html")


@exam_integrity_bp.get(_BASE + "/", strict_slashes=False)
@login_required
def dashboard(exam_id):
    exam = _require_exam(exam_id)
    available = integrity.ensure_schema()
    return render_template("admin/mock_exam_integrity.html", exam=exam, available=available)


def _dashboard_rows(exam_id):
    table = MockExamSession.__table__
    with db.engine.connect() as connection:
        sessions = (
            connection.execute(
                select(
                    table.c.id, table.c.student_name, table.c.current_section, table.c.status
                ).where(table.c.exam_id == exam_id)
            )
            .mappings()
            .all()
        )
    states = integrity.admin_states(exam_id, [row["id"] for row in sessions])
    rows = [{**states.get(str(row["id"]), {}), **dict(row)} for row in sessions]
    rows.sort(
        key=lambda row: (
            not (row.get("is_locked") or row.get("has_device_conflict", False)),
            row["id"],
        )
    )
    return rows


@exam_integrity_bp.get(_BASE + "/data")
@login_required
def dashboard_data(exam_id):
    _require_exam(exam_id)
    try:
        return _json(
            {"ok": True, "policy": integrity.read_policy(exam_id), "rows": _dashboard_rows(exam_id)}
        )
    except Exception:
        return _json({"ok": False, "error": "integrity_unavailable"}, 503)


@exam_integrity_bp.get(_BASE + "/sessions/<int:session_id>/events")
@login_required
def session_events(exam_id, session_id):
    _require_exam(exam_id)
    if not _session_row(exam_id, session_id=session_id):
        abort(404)
    try:
        return _json({"ok": True, "events": integrity.event_timeline(session_id)})
    except Exception:
        return _json({"ok": False, "error": "integrity_unavailable"}, 503)


def _set_policy(exam_id, data):
    mode = data.get("mode")
    if not isinstance(mode, str) or mode not in {"off", "monitor", "enforce"}:
        abort(400)
    leaves = _bounded_number(data.get("max_leaves", 3), 1, 100, integer=True)
    seconds = _bounded_number(data.get("max_hidden_seconds", 60), 2, 3600, integer=True)
    try:
        policy = integrity.set_policy(
            exam_id, mode, max_leaves=leaves, max_hidden_seconds=seconds, actor=current_user.id
        )
        return _json({"ok": True, "policy": policy})
    except Exception:
        return _json({"ok": False, "error": "integrity_unavailable"}, 503)


@exam_integrity_bp.post(_BASE + "/policy")
@login_required
def update_policy(exam_id):
    _require_exam(exam_id)
    return _set_policy(exam_id, _admin_json())


@exam_integrity_bp.post(_BASE + "/emergency-off")
@login_required
def emergency_off(exam_id):
    _require_exam(exam_id)
    _admin_json()
    return _set_policy(exam_id, {"mode": "off"})


@exam_integrity_bp.post(_BASE + "/sessions/<int:session_id>/<action>")
@login_required
def session_action(exam_id, session_id, action):
    _require_exam(exam_id)
    if action not in {"unlock", "reset-device", "exempt"}:
        abort(404)
    if not _session_row(exam_id, session_id=session_id):
        abort(404)
    data = _admin_json()
    exempt = data.get("exempt", True)
    if not isinstance(exempt, bool):
        abort(400)
    try:
        state = integrity.admin_action(
            exam_id, session_id, action, actor=current_user.id, exempt=exempt
        )
        return _json({"ok": True, **state})
    except Exception:
        return _json({"ok": False, "error": "integrity_unavailable"}, 503)
