"""模考成绩 / 逐题复盘（教师后台）。

配卷和学生答题流程在 app.py 的模考路由里；这里只加教师侧的"看谁考了、逐题看错在哪"，
判分结果通常直接读交卷时写入的 ``*_results_json``；仅对可明确识别的旧版
``NOT``/``NOT GIVEN`` 误判按已保存答案幂等重算一次。
"""

from __future__ import annotations

import json

from flask import Blueprint, flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from models import MockExam, MockExamSession, User, db
from services import mock_exam_review as review
from services.ielts_practice_scoring import grade_reading_test_answers

mock_exam_admin_bp = Blueprint("mock_exam_admin", __name__, url_prefix="/admin/mock-exams")


def _can_manage(user) -> bool:
    return bool(
        user.is_authenticated
        and user.role in (User.ROLE_ADMIN, User.ROLE_TEACHER, User.ROLE_ASSISTANT)
    )


def _load_payload(kind: str, test_id: str | None):
    """复用 app.py 的题库加载器（延迟 import：app 在启动时才注册本蓝图）。"""
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


def _repair_legacy_not_given_grade(sess, reading_payload: dict | None) -> bool:
    """幂等修复历史 ``NOT`` 被当成错误的模考阅读成绩。"""
    saved_results = review.parse_json_list(sess.reading_results_json)
    if not reading_payload or not review.has_legacy_not_given_misgrade(saved_results):
        return False
    answers = review.parse_json_dict(sess.reading_answers_json)
    if not answers:
        return False
    grade = grade_reading_test_answers(reading_payload, answers)
    sess.reading_correct = grade["correct"]
    sess.reading_total = grade["total"]
    sess.reading_accuracy = grade["accuracy"]
    sess.reading_ielts_score = grade["ielts_score"]
    sess.reading_results_json = json.dumps(grade["results"], ensure_ascii=False)
    sess.reading_wrong_numbers_json = json.dumps(grade["wrong_numbers"], ensure_ascii=False)
    return True


@mock_exam_admin_bp.route("/<int:exam_id>/sessions")
@login_required
def exam_sessions(exam_id):
    if not _can_manage(current_user):
        flash("无权限查看模考成绩。")
        return redirect(url_for("index"))
    exam = MockExam.query.get_or_404(exam_id)
    sessions = (
        MockExamSession.query.filter_by(exam_id=exam.id)
        .order_by(MockExamSession.started_at.desc())
        .all()
    )
    reading_payload = _load_payload("reading", exam.reading_test_id)
    repaired = [sess for sess in sessions if _repair_legacy_not_given_grade(sess, reading_payload)]
    if repaired:
        db.session.commit()
    return render_template(
        "admin/mock_exam_sessions.html",
        exam=exam,
        rows=[review.summarize_session(sess) for sess in sessions],
    )


@mock_exam_admin_bp.route("/<int:exam_id>/sessions/<int:session_id>")
@login_required
def exam_session_detail(exam_id, session_id):
    if not _can_manage(current_user):
        flash("无权限查看模考成绩。")
        return redirect(url_for("index"))
    exam = MockExam.query.get_or_404(exam_id)
    sess = MockExamSession.query.filter_by(id=session_id, exam_id=exam.id).first_or_404()

    listening_payload = _load_payload("listening", exam.listening_test_id)
    reading_payload = _load_payload("reading", exam.reading_test_id)
    if _repair_legacy_not_given_grade(sess, reading_payload):
        db.session.commit()

    listening_index = review.build_question_index(listening_payload, "listening")
    reading_index = review.build_question_index(reading_payload, "reading")
    writing_payload = _load_payload("writing", exam.writing_test_id)

    return render_template(
        "admin/mock_exam_session_detail.html",
        exam=exam,
        session=sess,
        summary=review.summarize_session(sess),
        listening_units=review.build_review_units(
            review.parse_json_list(sess.listening_results_json), listening_index
        ),
        reading_units=review.build_review_units(
            review.parse_json_list(sess.reading_results_json), reading_index
        ),
        writing_tasks=review.build_writing_review_tasks(writing_payload),
        has_writing=bool(exam.writing_test_id),
    )
