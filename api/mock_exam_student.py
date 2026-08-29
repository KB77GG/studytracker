"""学生模考逐题复盘。

学生模考使用随机 ``access_token`` 作为会话凭证；本蓝图只接受该 token，且仅在整场交卷后
展示答案与原文。教师端仍使用独立的登录鉴权后台路由。
"""

from __future__ import annotations

from datetime import datetime

from flask import Blueprint, jsonify, redirect, render_template, request, url_for

from models import MockExam, MockExamReview, MockExamSession, db
from services import mock_exam_review as review
from services import mock_exam_review_workflow as review_workflow
from services import mock_exam_runtime as runtime
from services.practice_navigation import safe_local_target
from services.web_privacy import no_store

mock_exam_student_bp = Blueprint("mock_exam_student", __name__)


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


def _runtime_session(exam_id: int, token: str):
    exam = MockExam.query.get(exam_id)
    if not exam:
        return None, None, ("exam_not_found", 404)
    mock_session = MockExamSession.query.filter_by(
        exam_id=exam.id,
        access_token=token,
    ).first()
    if not mock_session:
        return exam, None, ("session_not_found", 404)
    return exam, mock_session, None


@mock_exam_student_bp.post(
    "/api/exam/<int:exam_id>/session/<token>/start-listening"
)
def start_listening_runtime(exam_id: int, token: str):
    """Start the server clock only after the client has passed media preflight."""
    exam, mock_session, error = _runtime_session(exam_id, token)
    if error:
        return jsonify({"ok": False, "error": error[0]}), error[1]
    if mock_session.listening_submitted_at:
        return jsonify({"ok": False, "error": "section_already_submitted"}), 409
    if mock_session.current_section not in {
        MockExamSession.SECTION_INTRO,
        MockExamSession.SECTION_LISTENING,
    }:
        return jsonify({"ok": False, "error": "section_not_available"}), 409
    data = request.get_json(silent=True) or {}
    runtime_seconds = runtime.listening_runtime_seconds(
        exam.listening_minutes,
        data.get("audio_duration_seconds"),
    )
    started_at, deadline_at = runtime.start_section_seconds(
        mock_session,
        MockExamSession.SECTION_LISTENING,
        runtime_seconds,
    )
    db.session.commit()
    return jsonify(
        {
            "ok": True,
            "started_at": started_at.isoformat() + "Z",
            "deadline_at": deadline_at.isoformat() + "Z",
        }
    )


@mock_exam_student_bp.post(
    "/api/exam/<int:exam_id>/session/<token>/complete-listening-audio"
)
def complete_listening_audio(exam_id: int, token: str):
    """Close the server-owned Listening deadline to the official review window."""
    _exam, mock_session, error = _runtime_session(exam_id, token)
    if error:
        return jsonify({"ok": False, "error": error[0]}), error[1]
    if mock_session.listening_submitted_at:
        return jsonify({"ok": False, "error": "section_already_submitted"}), 409
    if mock_session.current_section != MockExamSession.SECTION_LISTENING:
        return jsonify({"ok": False, "error": "section_not_active"}), 409
    try:
        deadline_at = runtime.close_listening_to_review_window(mock_session)
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 409
    db.session.commit()
    return jsonify({"ok": True, "deadline_at": deadline_at.isoformat() + "Z"})


@mock_exam_student_bp.put(
    "/api/exam/<int:exam_id>/session/<token>/draft/<section>"
)
def save_objective_draft(exam_id: int, token: str, section: str):
    """Persist the last pre-deadline objective answers used for recovery."""
    exam, mock_session, error = _runtime_session(exam_id, token)
    if error:
        return jsonify({"ok": False, "error": error[0]}), error[1]
    if section not in runtime.OBJECTIVE_SECTIONS:
        return jsonify({"ok": False, "error": "unsupported_section"}), 404
    if getattr(mock_session, f"{section}_submitted_at", None):
        return jsonify({"ok": False, "error": "section_already_submitted"}), 409
    if not getattr(mock_session, f"{section}_started_at", None):
        return jsonify({"ok": False, "error": "section_not_started"}), 409
    if mock_session.current_section != section:
        return jsonify({"ok": False, "error": "section_not_active"}), 409

    data = request.get_json(silent=True) or {}
    answers = data.get("answers")
    try:
        saved = runtime.save_draft(
            mock_session,
            section,
            answers,
            datetime.utcnow(),
        )
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400

    if not saved:
        payload = _load_payload(section, getattr(exam, f"{section}_test_id"))
        if payload:
            runtime.finalize_expired_section(
                mock_session,
                exam,
                section,
                payload,
            )
            if mock_session.status == MockExamSession.STATUS_SUBMITTED:
                review_workflow.ensure_review_draft(mock_session)
            db.session.commit()
        return (
            jsonify(
                {
                    "ok": False,
                    "error": "time_expired",
                    "submitted": bool(getattr(mock_session, f"{section}_submitted_at", None)),
                    "next_url": url_for(
                        "mock_exam_process",
                        exam_id=exam.id,
                        token=mock_session.access_token,
                        **_navigation_args(),
                    ),
                }
            ),
            409,
        )

    db.session.commit()
    return jsonify(
        {
            "ok": True,
            "saved_at": datetime.utcnow().isoformat() + "Z",
            "deadline_at": getattr(mock_session, f"{section}_deadline_at").isoformat()
            + "Z",
        }
    )


@mock_exam_student_bp.get(
    "/api/exam/<int:exam_id>/session/<token>/draft/<section>"
)
def load_objective_draft(exam_id: int, token: str, section: str):
    """Return only the student's saved answers; never return grading data."""
    _exam, mock_session, error = _runtime_session(exam_id, token)
    if error:
        return jsonify({"ok": False, "error": error[0]}), error[1]
    if section not in runtime.OBJECTIVE_SECTIONS:
        return jsonify({"ok": False, "error": "unsupported_section"}), 404
    if getattr(mock_session, f"{section}_submitted_at", None):
        return jsonify({"ok": False, "error": "section_already_submitted"}), 409
    return jsonify(
        {
            "ok": True,
            "answers": runtime.parse_draft(mock_session, section),
            "started_at": (
                getattr(mock_session, f"{section}_started_at").isoformat() + "Z"
                if getattr(mock_session, f"{section}_started_at", None)
                else None
            ),
            "deadline_at": (
                getattr(mock_session, f"{section}_deadline_at").isoformat() + "Z"
                if getattr(mock_session, f"{section}_deadline_at", None)
                else None
            ),
        }
    )


@mock_exam_student_bp.after_request
def _private_review_headers(response):
    return no_store(response)


def _load_payload(kind: str, test_id: str | None):
    """延迟复用现有题库加载器，避免 app 初始化阶段循环导入。"""
    if not test_id:
        return None
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


def student_review_context(exam: MockExam, mock_session: MockExamSession) -> dict:
    """Build the single context shared by token and profile-authorized pages."""
    listening_payload = _load_payload("listening", exam.listening_test_id)
    reading_payload = _load_payload("reading", exam.reading_test_id)
    writing_payload = _load_payload("writing", exam.writing_test_id)
    review_row = None
    if mock_session.status == MockExamSession.STATUS_SUBMITTED:
        review_row = mock_session.review
        review_created = False
        if review_row is None:
            review_row = review_workflow.ensure_review_draft(mock_session)
            review_created = review_row is not None
        review_workflow_changed = review.repair_legacy_not_given_grade(
            mock_session, reading_payload
        )
        if review_created or review_workflow_changed:
            db.session.commit()

    listening_index = review.build_question_index(listening_payload, "listening")
    reading_index = review.build_question_index(reading_payload, "reading")
    writing_tasks = review.build_writing_review_tasks(writing_payload)
    teacher_review = (
        review_workflow.review_payload(review_row, writing_tasks=writing_tasks)
        if review_row and review_row.status == MockExamReview.STATUS_PUBLISHED
        else None
    )
    return {
        "exam": exam,
        "session": mock_session,
        "summary": review.summarize_session(mock_session),
        "listening_units": review.build_review_units(
            review.parse_json_list(mock_session.listening_results_json), listening_index
        ),
        "reading_units": review.build_review_units(
            review.parse_json_list(mock_session.reading_results_json), reading_index
        ),
        "writing_tasks": writing_tasks,
        "has_writing": bool(exam.writing_test_id),
        "teacher_review": teacher_review,
    }


def render_student_review_page(
    exam: MockExam,
    mock_session: MockExamSession,
    *,
    template_name: str = "exam/review.html",
):
    return no_store(render_template(template_name, **student_review_context(exam, mock_session)))


@mock_exam_student_bp.get("/exam/<int:exam_id>/session/<token>/review")
def session_review(exam_id: int, token: str):
    """用当前模考会话 token 查看本人复盘；考试中不下发答案。"""
    exam = MockExam.query.get_or_404(exam_id)
    session = MockExamSession.query.filter_by(
        exam_id=exam.id,
        access_token=token,
    ).first_or_404()
    if session.status != MockExamSession.STATUS_SUBMITTED:
        return no_store(redirect(url_for("mock_exam_process", exam_id=exam.id, token=token)))

    return render_student_review_page(exam, session)
