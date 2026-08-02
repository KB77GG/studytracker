"""学生模考逐题复盘。

学生模考使用随机 ``access_token`` 作为会话凭证；本蓝图只接受该 token，且仅在整场交卷后
展示答案与原文。教师端仍使用独立的登录鉴权后台路由。
"""

from __future__ import annotations

from flask import Blueprint, redirect, render_template, url_for

from models import MockExam, MockExamSession, db
from services import mock_exam_review as review

mock_exam_student_bp = Blueprint("mock_exam_student", __name__)


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


@mock_exam_student_bp.get("/exam/<int:exam_id>/session/<token>/review")
def session_review(exam_id: int, token: str):
    """用当前模考会话 token 查看本人复盘；考试中不下发答案。"""
    exam = MockExam.query.get_or_404(exam_id)
    session = MockExamSession.query.filter_by(
        exam_id=exam.id,
        access_token=token,
    ).first_or_404()
    if session.status != MockExamSession.STATUS_SUBMITTED:
        return redirect(url_for("mock_exam_process", exam_id=exam.id, token=token))

    listening_payload = _load_payload("listening", exam.listening_test_id)
    reading_payload = _load_payload("reading", exam.reading_test_id)
    writing_payload = _load_payload("writing", exam.writing_test_id)
    if review.repair_legacy_not_given_grade(session, reading_payload):
        db.session.commit()

    listening_index = review.build_question_index(listening_payload, "listening")
    reading_index = review.build_question_index(reading_payload, "reading")
    return render_template(
        "exam/review.html",
        exam=exam,
        session=session,
        summary=review.summarize_session(session),
        listening_units=review.build_review_units(
            review.parse_json_list(session.listening_results_json), listening_index
        ),
        reading_units=review.build_review_units(
            review.parse_json_list(session.reading_results_json), reading_index
        ),
        writing_tasks=review.build_writing_review_tasks(writing_payload),
        has_writing=bool(exam.writing_test_id),
    )
