"""Web teacher writing review and student mock-exam review routes."""

from __future__ import annotations

from flask import Blueprint, jsonify, make_response, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from sqlalchemy.orm.exc import StaleDataError
from werkzeug.exceptions import NotFound

from models import MockExamReview, MockExamSession, User, db
from services import mock_exam_review as objective_review
from services import mock_exam_review_workflow as workflow

mock_exam_review_bp = Blueprint("mock_exam_review", __name__)


def _can_manage(user) -> bool:
    return bool(
        user.is_authenticated
        and user.role in (User.ROLE_ADMIN, User.ROLE_TEACHER, User.ROLE_ASSISTANT)
    )


def _no_store(response):
    if not hasattr(response, "headers"):
        response = make_response(response)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive"
    return response


def _json(payload, status=200):
    return _no_store(jsonify(payload)), status


def _load_payload(kind: str, test_id: str | None):
    if not test_id:
        return None
    try:
        from app import (
            _load_listening_test_payload,
            _load_reading_test_payload,
            _load_writing_test_payload,
        )

        loader = {
            "listening": _load_listening_test_payload,
            "reading": _load_reading_test_payload,
            "writing": _load_writing_test_payload,
        }[kind]
        payload, _path, _safe = loader(test_id)
        return payload
    except (ImportError, KeyError, RuntimeError, TypeError):
        return None


def _writing_tasks(mock_session: MockExamSession) -> list:
    payload = _load_payload("writing", mock_session.exam.writing_test_id)
    return (payload or {}).get("tasks") or []


def _objective_units(mock_session: MockExamSession) -> tuple[list, list]:
    exam = mock_session.exam
    listening_payload = _load_payload("listening", exam.listening_test_id)
    reading_payload = _load_payload("reading", exam.reading_test_id)
    listening_index = objective_review.build_question_index(listening_payload, "listening")
    reading_index = objective_review.build_question_index(reading_payload, "reading")
    return (
        objective_review.build_review_units(
            objective_review.parse_json_list(mock_session.listening_results_json),
            listening_index,
        ),
        objective_review.build_review_units(
            objective_review.parse_json_list(mock_session.reading_results_json),
            reading_index,
        ),
    )


def _get_submitted_review(exam_id: int, session_id: int):
    mock_session = MockExamSession.query.filter_by(id=session_id, exam_id=exam_id).first()
    if not mock_session:
        raise NotFound()
    if mock_session.status != MockExamSession.STATUS_SUBMITTED:
        return mock_session, None
    review = workflow.ensure_review_draft(mock_session)
    return mock_session, review


def _editor_context(review: MockExamReview) -> dict:
    mock_session = review.session
    listening_units, reading_units = _objective_units(mock_session)
    return {
        "review": review,
        "mock_session": mock_session,
        "exam": mock_session.exam,
        "review_payload": workflow.review_payload(
            review,
            writing_tasks=_writing_tasks(mock_session),
        ),
        "listening_units": listening_units,
        "reading_units": reading_units,
        "score_options": workflow.score_options(),
    }


def _scope_or_forbidden(review_id: int):
    review = db.session.get(MockExamReview, review_id)
    if not review:
        return None, _no_store(jsonify({"ok": False, "error": "not_found"})), 404
    scope = workflow.current_editor_scope(review_id)
    if not scope:
        # Do not let clean review IDs become an existence oracle.
        return review, _no_store(jsonify({"ok": False, "error": "not_found"})), 404
    return review, None, None


def _expected_version(data: dict):
    try:
        return int(data.get("version"))
    except (TypeError, ValueError):
        return None


def _review_update_payload(review: MockExamReview, data: dict, *, publish: bool = False):
    if review.status == MockExamReview.STATUS_PUBLISHED and not publish:
        return {"ok": False, "status": 409, "payload": {"ok": False, "error": "read_only"}}
    expected = _expected_version(data)
    if expected is None:
        return {"ok": False, "status": 400, "payload": {"ok": False, "error": "version_required"}}
    if expected != review.version:
        return {
            "ok": False,
            "status": 409,
            "payload": {
                "ok": False,
                "error": "version_conflict",
                "current": workflow.review_payload(review, writing_tasks=_writing_tasks(review.session)),
            },
        }
    fields = data.get("fields") if isinstance(data.get("fields"), dict) else data
    has_writing = bool(review.session.exam.writing_test_id)
    if publish:
        result = workflow.publish_review(
            review,
            fields,
            has_writing=has_writing,
            saved_by=current_user.id if current_user.is_authenticated else None,
        )
    else:
        result = workflow.apply_review_fields(
            review,
            fields,
            has_writing=has_writing,
            saved_by=current_user.id if current_user.is_authenticated else None,
        )
    if not result["ok"]:
        return {"ok": False, "status": 422, "payload": {"ok": False, "errors": result["errors"]}}
    review.version += 1
    try:
        db.session.commit()
    except StaleDataError:
        db.session.rollback()
        current = db.session.get(MockExamReview, review.id)
        return {
            "ok": False,
            "status": 409,
            "payload": {
                "ok": False,
                "error": "version_conflict",
                "current": workflow.review_payload(
                    current or review,
                    writing_tasks=_writing_tasks((current or review).session),
                ),
            },
        }
    return {
        "ok": True,
        "status": 200,
        "payload": {
            "ok": True,
            "review": workflow.review_payload(review, writing_tasks=_writing_tasks(review.session)),
        },
    }


@mock_exam_review_bp.post("/admin/mock-exams/<int:exam_id>/sessions/<int:session_id>/review-link")
@login_required
def issue_review_link(exam_id: int, session_id: int):
    if not _can_manage(current_user):
        return _json({"ok": False, "error": "forbidden"}, 403)
    mock_session, review = _get_submitted_review(exam_id, session_id)
    if review is None:
        return _json({"ok": False, "error": "exam_not_submitted"}, 409)
    token, expires_at = workflow.issue_capability(review)
    db.session.commit()
    return _json(
        {
            "ok": True,
            "review_id": review.id,
            "status": review.status,
            "url": url_for("mock_exam_review.access_link", token=token, _external=True),
            "expires_at": expires_at.isoformat(),
        }
    )


@mock_exam_review_bp.post("/admin/mock-exams/<int:exam_id>/sessions/<int:session_id>/review-link/revoke")
@login_required
def revoke_review_link(exam_id: int, session_id: int):
    if not _can_manage(current_user):
        return _json({"ok": False, "error": "forbidden"}, 403)
    _mock_session, review = _get_submitted_review(exam_id, session_id)
    if review is None:
        return _json({"ok": False, "error": "exam_not_submitted"}, 409)
    workflow.revoke_capability(review)
    db.session.commit()
    return _json({"ok": True, "revoked": True, "link_version": review.link_version})


@mock_exam_review_bp.post("/admin/mock-exams/<int:exam_id>/sessions/<int:session_id>/review-link/reopen")
@login_required
def reopen_review(exam_id: int, session_id: int):
    if not _can_manage(current_user):
        return _json({"ok": False, "error": "forbidden"}, 403)
    _mock_session, review = _get_submitted_review(exam_id, session_id)
    if review is None:
        return _json({"ok": False, "error": "exam_not_submitted"}, 409)
    review.status = MockExamReview.STATUS_DRAFT
    review.published_at = None
    review.version += 1
    token, expires_at = workflow.issue_capability(review)
    db.session.commit()
    return _json(
        {
            "ok": True,
            "status": review.status,
            "url": url_for("mock_exam_review.access_link", token=token, _external=True),
            "expires_at": expires_at.isoformat(),
        }
    )


@mock_exam_review_bp.get("/admin/mock-exams/<int:exam_id>/sessions/<int:session_id>/review/open")
@login_required
def open_admin_review(exam_id: int, session_id: int):
    if not _can_manage(current_user):
        return redirect(url_for("index"))
    _mock_session, review = _get_submitted_review(exam_id, session_id)
    if review is None:
        return _no_store(jsonify({"ok": False, "error": "exam_not_submitted"})), 409
    token, _expires_at = workflow.issue_capability(review)
    db.session.commit()
    return _no_store(redirect(url_for("mock_exam_review.access_link", token=token)))


@mock_exam_review_bp.get("/mock-review/access/<token>")
def access_link(token: str):
    review, error = workflow.decode_capability(token)
    if error or not review:
        return _no_store(jsonify({"ok": False, "error": "link_invalid_or_expired"})), 404
    workflow.create_editor_scope(review)
    db.session.commit()
    response = redirect(url_for("mock_exam_review.editor", review_id=review.id), code=303)
    return _no_store(response)


@mock_exam_review_bp.get("/mock-review/<int:review_id>")
def editor(review_id: int):
    review, error_response, error_status = _scope_or_forbidden(review_id)
    if error_response is not None:
        return error_response, error_status
    db.session.commit()
    context = _editor_context(review)
    return _no_store(render_template("admin/mock_exam_review_editor.html", **context))


@mock_exam_review_bp.post("/mock-review/<int:review_id>/save")
def save_review(review_id: int):
    review, error_response, error_status = _scope_or_forbidden(review_id)
    if error_response is not None:
        return error_response, error_status
    data = request.get_json(silent=True) or {}
    result = _review_update_payload(review, data)
    if not result["ok"]:
        db.session.rollback()
        return _json(result["payload"], result["status"])
    return _json(result["payload"])


@mock_exam_review_bp.post("/mock-review/<int:review_id>/publish")
def publish_review(review_id: int):
    review, error_response, error_status = _scope_or_forbidden(review_id)
    if error_response is not None:
        return error_response, error_status
    if review.status == MockExamReview.STATUS_PUBLISHED:
        return _json({"ok": False, "error": "already_published"}, 409)
    data = request.get_json(silent=True) or {}
    result = _review_update_payload(review, data, publish=True)
    if not result["ok"]:
        db.session.rollback()
        return _json(result["payload"], result["status"])
    return _json(result["payload"])


@mock_exam_review_bp.get("/api/practice/mock-exams")
def student_mock_exams():
    profile = workflow.current_student_profile()
    if not profile:
        return _json({"ok": False, "error": "not_verified"}, 401)
    if current_user.is_authenticated and current_user.role == User.ROLE_STUDENT:
        sessions = (
            MockExamSession.query.filter_by(student_profile_id=profile.id)
            .order_by(MockExamSession.started_at.desc())
            .all()
        )
    else:
        current_id = workflow.light_browser_exam_session_id()
        sessions = (
            [
                db.session.get(MockExamSession, current_id)
            ]
            if current_id
            else []
        )
        sessions = [
            mock_session
            for mock_session in sessions
            if mock_session and workflow.can_student_view_session(mock_session, profile)
        ]
    rows = []
    created_draft = False
    for mock_session in sessions:
        review = mock_session.review
        if mock_session.status == MockExamSession.STATUS_SUBMITTED and review is None:
            review = workflow.ensure_review_draft(mock_session)
            created_draft = created_draft or review is not None
        row = workflow.student_session_summary(mock_session, review)
        if mock_session.status != MockExamSession.STATUS_SUBMITTED:
            try:
                row["continue_url"] = url_for(
                    "mock_exam_process",
                    exam_id=mock_session.exam_id,
                    token=mock_session.access_token,
                )
            except RuntimeError:
                row["continue_url"] = None
        else:
            row["detail_url"] = url_for(
                "mock_exam_review.student_review",
                session_id=mock_session.id,
            )
        rows.append(row)
    if created_draft:
        db.session.commit()
    return _json({"ok": True, "verified": True, "name": profile.full_name, "sessions": rows})


@mock_exam_review_bp.get("/practice/mock-exams/<int:session_id>/review")
def student_review(session_id: int):
    profile = workflow.current_student_profile()
    mock_session = db.session.get(MockExamSession, session_id)
    if not profile or not mock_session or not workflow.can_student_view_session(mock_session, profile):
        return _no_store(jsonify({"ok": False, "error": "not_found"})), 404
    if mock_session.status != MockExamSession.STATUS_SUBMITTED:
        return _no_store(jsonify({"ok": False, "error": "exam_not_submitted"})), 409
    review = workflow.ensure_review_draft(mock_session)
    db.session.commit()
    listening_units, reading_units = _objective_units(mock_session)
    published = review.status == MockExamReview.STATUS_PUBLISHED
    return _no_store(
        render_template(
            "practice/mock_exam_review.html",
            exam=mock_session.exam,
            session=mock_session,
            summary=objective_review.summarize_session(mock_session),
            listening_units=listening_units,
            reading_units=reading_units,
            writing_tasks=_writing_tasks(mock_session),
            review=workflow.review_payload(
                review,
                writing_tasks=_writing_tasks(mock_session),
            ) if published else None,
            published=published,
        )
    )
