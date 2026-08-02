"""学生模考逐题复盘。

学生模考使用随机 ``access_token`` 作为会话凭证；本蓝图只接受该 token，且仅在整场交卷后
展示答案与原文。教师端仍使用独立的登录鉴权后台路由。
"""

from __future__ import annotations

from flask import Blueprint, redirect, render_template, url_for

from models import MockExam, MockExamReview, MockExamSession, db
from services import mock_exam_review as review
from services import mock_exam_review_workflow as review_workflow
from services.web_privacy import no_store

mock_exam_student_bp = Blueprint("mock_exam_student", __name__)


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
