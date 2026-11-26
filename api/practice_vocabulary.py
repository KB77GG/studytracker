"""Cookie-authenticated vocabulary task pages; domain rules remain shared."""

from __future__ import annotations

import secrets
from urllib.parse import urlsplit

from flask import Blueprint, current_app, g, jsonify, render_template, request, session
from sqlalchemy.exc import OperationalError, SQLAlchemyError

from models import VocabularyLearningQuestion, db
from services import vocabulary_autonomous_review as review
from services import vocabulary_group_learning as learning
from services.practice_student_identity import PracticeIdentityError, resolve_practice_student
from services.practice_vocabulary_web import (
    PracticeVocabularyError,
    answer_feedback,
    envelope,
    flow_envelope,
    owned_task,
    read_state,
    sanitize_review,
    sanitized_error_details,
    sync_state,
    task_metadata,
)
from services.task_date_gate import TaskDateGateError, assert_task_write_allowed, task_date_access
from services.vocabulary_mastery import VocabularyMasteryError
from services.vocabulary_task_submission import settle_vocabulary_group_submission

practice_vocabulary_bp = Blueprint("practice_vocabulary", __name__)
API = "/api/practice/vocabulary/tasks/<int:task_id>"


def _enabled():
    if not current_app.config.get("PRACTICE_VOCABULARY_WEB_ENABLED", False):
        raise PracticeVocabularyError("feature_disabled", 403)


def _context(task_id):
    student = resolve_practice_student()
    return student, owned_task(student, task_id)


@practice_vocabulary_bp.before_request
def validate_request():
    if not request.path.startswith("/api/practice/vocabulary/"):
        return
    _enabled()
    g.practice_student = resolve_practice_student()
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        g.practice_task = owned_task(g.practice_student, request.view_args["task_id"])
        return
    if (request.content_length or 0) > 16384 or len(request.get_data()) > 16384:
        raise PracticeVocabularyError("request_too_large", 413)
    if not request.is_json:
        raise PracticeVocabularyError("json_required", 415)
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise PracticeVocabularyError("invalid_json", 400)
    expected = str(session.get("practice_vocabulary_csrf") or "")
    actual = request.headers.get("X-CSRF-Token", "")
    if not expected or not secrets.compare_digest(expected.encode(), actual.encode()):
        raise PracticeVocabularyError("csrf", 403)
    origin = request.headers.get("Origin")
    if origin:
        try:
            parsed = urlsplit(origin)
            valid_origin = parsed.scheme == request.scheme and parsed.netloc == request.host
        except ValueError:
            valid_origin = False
        if not valid_origin:
            raise PracticeVocabularyError("csrf", 403)
    identity = request.headers.get("X-Practice-Identity", "")
    if not secrets.compare_digest(g.practice_student.identity_key.encode(), identity.encode()):
        raise PracticeVocabularyError("identity_changed", 409)
    g.practice_task = owned_task(g.practice_student, request.view_args["task_id"])
    g.practice_payload = payload


@practice_vocabulary_bp.get("/practice/vocabulary/tasks/<int:task_id>")
def task_page(task_id):
    boot = {
        "task_id": task_id,
        "stage": "booting",
        "api_base": f"/api/practice/vocabulary/tasks/{task_id}",
    }
    status = 200
    try:
        _enabled()
        student, task = _context(task_id)
        boot.update(
            task=task_metadata(task),
            access={**task_date_access(task).as_dict(), "label": task_date_access(task).label},
            identity_key=student.identity_key,
        )
        boot["csrf_token"] = session.setdefault(
            "practice_vocabulary_csrf", secrets.token_urlsafe(32)
        )
    except (PracticeIdentityError, PracticeVocabularyError) as error:
        status = getattr(error, "status", getattr(error, "status_code", 400))
        boot.update(
            stage="blocked",
            error=getattr(error, "code", getattr(error, "error", "identity_missing")),
        )
    return render_template("practice/vocabulary_task.html", boot_data=boot), status


@practice_vocabulary_bp.get(API + "/state")
def task_state(task_id):
    return jsonify(read_state(g.practice_student, g.practice_task))


def _reply(payload):
    db.session.commit()
    return jsonify(payload)


def _payload(*fields):
    result = {key: g.practice_payload[key] for key in fields if key in g.practice_payload}
    for key in ("attempt_id", "queue_token", "session_token"):
        if key in result and not isinstance(result[key], str):
            raise PracticeVocabularyError("invalid_" + key, 400)
    if len(result.get("attempt_id", "")) > 96:
        raise PracticeVocabularyError("attempt_id_too_long", 400, max_length=96)
    result.update(task_id=g.practice_task.id, input_mode="native", supports_correction=True)
    return result


@practice_vocabulary_bp.after_request
def private_response(response):
    response.headers["Cache-Control"] = "no-store, private"
    return response


@practice_vocabulary_bp.post(API + "/sync")
def sync(task_id):
    return _reply(sync_state(g.practice_student, g.practice_task, _payload("attempt_id")))


@practice_vocabulary_bp.post(API + "/familiarity")
def familiarity(task_id):
    result = learning.mark_familiarity_viewed(
        g.practice_student.user, task_id, _payload("queue_token", "word_id")
    )
    return _reply(flow_envelope(g.practice_student, g.practice_task, result))


ANSWER_FIELDS = (
    "queue_token",
    "learning_question_id",
    "queue_item_id",
    "question_id",
    "word_id",
    "sense_id",
    "dimension",
    "answer",
    "attempt_id",
    "retry",
    "response_kind",
)


@practice_vocabulary_bp.post(API + "/answers")
def answers(task_id):
    result = learning.submit_vocabulary_group_answer(
        g.practice_student.user, _payload(*ANSWER_FIELDS)
    )
    question = db.session.get(VocabularyLearningQuestion, result["learning_question_id"])
    result["answer_feedback"] = answer_feedback(question.word, question)
    return _reply(envelope(g.practice_student, g.practice_task, "feedback", feedback=result))


@practice_vocabulary_bp.post(API + "/corrections")
def corrections(task_id):
    payload = _payload(
        "queue_token", "learning_question_id", "queue_item_id", "answer", "attempt_id"
    )
    result = learning.submit_vocabulary_group_correction(g.practice_student.user, payload)
    question = db.session.get(
        VocabularyLearningQuestion,
        int(payload.get("learning_question_id") or payload.get("queue_item_id")),
    )
    feedback = {key: value for key, value in result.items() if key.startswith("correction_")}
    feedback.update(
        is_correct=bool(result.get("correction_is_correct")),
        student_answer=question.correction_answer,
        idempotent=bool(result.get("correction_idempotent")),
        answer_feedback=answer_feedback(question.word, question),
    )
    response = flow_envelope(g.practice_student, g.practice_task, result)
    response.update(stage="feedback", feedback=feedback)
    return _reply(response)


@practice_vocabulary_bp.post(API + "/settle")
def settle(task_id):
    result = settle_vocabulary_group_submission(
        g.practice_student.user,
        task_id,
        _payload("queue_token", "duration_seconds"),
        uploader_id=g.practice_student.user.id,
    )
    response = read_state(g.practice_student, g.practice_task)
    response.update(
        stage="result", settlement=result, already_settled=bool(result.get("already_settled"))
    )
    return _reply(response)


@practice_vocabulary_bp.post(API + "/review/claim")
def review_claim(task_id):
    assert_task_write_allowed(g.practice_task)
    gate = review.review_preflight(g.practice_student.user, task_id, gate_only=True)
    if not gate["required"]:
        return _reply(sync_state(g.practice_student, g.practice_task, {}))
    result = review.claim_today_review(g.practice_student.user, origin_task_id=task_id)
    return _reply(
        envelope(g.practice_student, g.practice_task, "review", review=sanitize_review(result))
    )


def _review_context():
    assert_task_write_allowed(g.practice_task)
    payload = _payload(
        *ANSWER_FIELDS, "session_id", "session_token", "review_item_id", "duration_seconds"
    )
    try:
        session_id = int(payload.get("session_id"))
    except (TypeError, ValueError):
        raise PracticeVocabularyError("invalid_session_id", 400) from None
    token = str(payload.get("session_token") or "")
    return session_id, token, payload


def _review_answer(fn):
    session_id, token, payload = _review_context()
    feedback = fn(g.practice_student.user, session_id, payload, session_token=token)
    current = review.get_review_session(g.practice_student.user, session_id, token)
    return _reply(
        envelope(
            g.practice_student,
            g.practice_task,
            "review_feedback",
            feedback=feedback,
            review=sanitize_review(current),
        )
    )


@practice_vocabulary_bp.post(API + "/review/answers")
def review_answers(task_id):
    return _review_answer(review.submit_review_answer)


@practice_vocabulary_bp.post(API + "/review/corrections")
def review_corrections(task_id):
    return _review_answer(review.submit_review_correction)


@practice_vocabulary_bp.post(API + "/review/settle")
def review_settle(task_id):
    session_id, token, payload = _review_context()
    result = review.settle_review_session(
        g.practice_student.user, session_id, payload, session_token=token
    )
    return _reply(envelope(g.practice_student, g.practice_task, "review_result", settlement=result))


def domain_error(error):
    db.session.rollback()
    code = getattr(error, "error", getattr(error, "code", "request_failed"))
    details = sanitized_error_details(getattr(error, "details", {}))
    return jsonify(ok=False, error=code, **details), getattr(
        error, "status_code", getattr(error, "status", 400)
    )


for _error in (
    PracticeIdentityError,
    PracticeVocabularyError,
    learning.VocabularyGroupLearningError,
    review.VocabularyAutonomousReviewError,
    VocabularyMasteryError,
    TaskDateGateError,
):
    practice_vocabulary_bp.register_error_handler(_error, domain_error)


@practice_vocabulary_bp.errorhandler(SQLAlchemyError)
def database_error(error):
    db.session.rollback()
    current_app.logger.exception("Vocabulary web database operation failed")
    if isinstance(error, OperationalError):
        return jsonify(ok=False, error="state_conflict", retryable=True), 409
    return jsonify(ok=False, error="save_failed"), 500
