"""Student-facing automatic vocabulary review APIs."""

from flask import Blueprint, jsonify, request

from models import Task, User, db
from services.dictation_review import (
    DictationReviewError,
    get_task_queue,
    import_legacy_wrong_words,
    list_server_wrong_words,
)
from services.vocabulary_autonomous_review import (
    VocabularyAutonomousReviewError,
    claim_today_review,
    continue_review,
    get_review_session,
    review_preflight,
    review_summary,
    settle_review_session,
    submit_review_answer,
    submit_review_correction,
)
from services.vocabulary_group_learning import (
    VocabularyGroupLearningError,
    get_vocabulary_group_queue,
    group_flow_diagnostics,
    mark_familiarity_viewed,
    submit_vocabulary_group_correction,
)
from services.task_date_gate import task_date_access
from services.vocabulary_mastery import (
    VocabularyMasteryError,
    is_vocabulary_v2_task,
    list_vocabulary_due,
)

from .auth_utils import require_api_user

vocab_review_bp = Blueprint("vocab_review", __name__, url_prefix="/api")


def _error_response(error: DictationReviewError):
    payload = {"ok": False, "error": error.error}
    payload.update(error.details)
    return jsonify(payload), error.status_code


def _vocabulary_error_response(error: VocabularyMasteryError):
    payload = {"ok": False, "error": error.error}
    payload.update(error.details)
    return jsonify(payload), error.status_code


def _autonomous_error_response(error: VocabularyAutonomousReviewError):
    payload = {"ok": False, "error": error.error}
    payload.update(error.details)
    return jsonify(payload), error.status_code


def _group_error_response(error: VocabularyGroupLearningError):
    payload = {"ok": False, "error": error.error}
    payload.update(error.details)
    return jsonify(payload), error.status_code


@vocab_review_bp.route(
    "/miniprogram/student/tasks/<int:task_id>/dictation-queue",
    methods=["GET"],
)
@require_api_user(User.ROLE_STUDENT)
def get_dictation_queue(task_id):
    try:
        task = Task.query.get(task_id)
        if is_vocabulary_v2_task(task):
            if not task_date_access(task).read_only:
                gate = review_preflight(request.current_api_user, task_id)
                if gate["required"]:
                    raise VocabularyMasteryError(
                        "vocabulary_review_required",
                        409,
                        due_count=gate["due_count"],
                        batch_limit=gate["batch_limit"],
                        active_session_id=gate["active_session_id"],
                    )
            result = get_vocabulary_group_queue(
                request.current_api_user,
                task_id,
                supports_correction=request.args.get("supports_correction") == "1",
            )
        else:
            result = get_task_queue(request.current_api_user, task_id)
        # Queue creation is the claim operation.  Persist it before returning
        # so another device/task on the same day sees the same snapshot.
        db.session.commit()
        return jsonify(result)
    except DictationReviewError as error:
        db.session.rollback()
        return _error_response(error)
    except VocabularyMasteryError as error:
        db.session.rollback()
        return _vocabulary_error_response(error)
    except VocabularyAutonomousReviewError as error:
        db.session.rollback()
        return _autonomous_error_response(error)
    except VocabularyGroupLearningError as error:
        db.session.rollback()
        return _group_error_response(error)


@vocab_review_bp.route(
    "/miniprogram/student/tasks/<int:task_id>/vocabulary-queue",
    methods=["GET"],
)
@require_api_user(User.ROLE_STUDENT)
def get_vocabulary_queue(task_id):
    try:
        task = Task.query.get(task_id)
        if not is_vocabulary_v2_task(task):
            raise VocabularyMasteryError("task_not_vocabulary_v2", 409)
        if not task_date_access(task).read_only:
            gate = review_preflight(request.current_api_user, task_id)
            if gate["required"]:
                raise VocabularyMasteryError(
                    "vocabulary_review_required",
                    409,
                    due_count=gate["due_count"],
                    batch_limit=gate["batch_limit"],
                    active_session_id=gate["active_session_id"],
                )
        result = get_vocabulary_group_queue(
            request.current_api_user,
            task_id,
            supports_correction=request.args.get("supports_correction") == "1",
        )
        db.session.commit()
        return jsonify(result)
    except VocabularyMasteryError as error:
        db.session.rollback()
        return _vocabulary_error_response(error)
    except VocabularyAutonomousReviewError as error:
        db.session.rollback()
        return _autonomous_error_response(error)
    except VocabularyGroupLearningError as error:
        db.session.rollback()
        return _group_error_response(error)


@vocab_review_bp.route(
    "/miniprogram/student/tasks/<int:task_id>/vocabulary-learning/familiarity",
    methods=["POST"],
)
@require_api_user(User.ROLE_STUDENT)
def mark_vocabulary_learning_familiarity(task_id):
    """Advance the server-owned familiarity cursor by one group word."""

    try:
        result = mark_familiarity_viewed(
            request.current_api_user,
            task_id,
            request.get_json(silent=True) or {},
        )
        db.session.commit()
        return jsonify(result)
    except VocabularyGroupLearningError as error:
        db.session.rollback()
        return _group_error_response(error)


@vocab_review_bp.route(
    "/miniprogram/student/tasks/<int:task_id>/vocabulary-learning/correction",
    methods=["POST"],
)
@require_api_user(User.ROLE_STUDENT)
def submit_vocabulary_learning_correction(task_id):
    try:
        payload = request.get_json(silent=True) or {}
        payload["task_id"] = task_id
        result = submit_vocabulary_group_correction(
            request.current_api_user,
            payload,
        )
        db.session.commit()
        return jsonify(result)
    except VocabularyGroupLearningError as error:
        db.session.rollback()
        return _group_error_response(error)


@vocab_review_bp.route(
    "/miniprogram/student/tasks/<int:task_id>/vocabulary-learning/diagnostics",
    methods=["GET"],
)
@require_api_user(User.ROLE_STUDENT)
def get_vocabulary_learning_diagnostics(task_id):
    try:
        return jsonify(group_flow_diagnostics(request.current_api_user, task_id))
    except VocabularyGroupLearningError as error:
        return _group_error_response(error)


@vocab_review_bp.route("/miniprogram/student/vocabulary-review/today", methods=["GET"])
@require_api_user(User.ROLE_STUDENT)
def get_vocabulary_review_today():
    try:
        result = claim_today_review(
            request.current_api_user,
            origin_task_id=request.args.get("origin_task_id", type=int),
        )
        db.session.commit()
        return jsonify(result)
    except VocabularyAutonomousReviewError as error:
        db.session.rollback()
        return _autonomous_error_response(error)


@vocab_review_bp.route("/miniprogram/student/vocabulary-review/summary", methods=["GET"])
@require_api_user(User.ROLE_STUDENT)
def get_vocabulary_review_summary():
    try:
        return jsonify(review_summary(request.current_api_user))
    except VocabularyAutonomousReviewError as error:
        return _autonomous_error_response(error)


@vocab_review_bp.route("/miniprogram/student/tasks/<int:task_id>/vocabulary-review/preflight", methods=["GET"])
@require_api_user(User.ROLE_STUDENT)
def get_vocabulary_review_preflight(task_id):
    try:
        return jsonify(review_preflight(request.current_api_user, task_id))
    except VocabularyAutonomousReviewError as error:
        return _autonomous_error_response(error)


@vocab_review_bp.route("/miniprogram/student/vocabulary-review/sessions/<int:session_id>", methods=["GET"])
@require_api_user(User.ROLE_STUDENT)
def get_vocabulary_review_session(session_id):
    try:
        session_token = (request.args.get("session_token") or "").strip() or None
        return jsonify(get_review_session(request.current_api_user, session_id, session_token))
    except VocabularyAutonomousReviewError as error:
        return _autonomous_error_response(error)


@vocab_review_bp.route(
    "/miniprogram/student/vocabulary-review/sessions/<int:session_id>/answers",
    methods=["POST"],
)
@require_api_user(User.ROLE_STUDENT)
def submit_vocabulary_review_answer(session_id):
    try:
        payload = request.get_json(silent=True) or {}
        payload["supports_correction"] = payload.get("supports_correction") is True
        session_token = str(payload.get("session_token") or "").strip() or None
        result = submit_review_answer(
            request.current_api_user,
            session_id,
            payload,
            session_token=session_token,
        )
        db.session.commit()
        return jsonify(result)
    except VocabularyAutonomousReviewError as error:
        db.session.rollback()
        return _autonomous_error_response(error)


@vocab_review_bp.route(
    "/miniprogram/student/vocabulary-review/sessions/<int:session_id>/corrections",
    methods=["POST"],
)
@require_api_user(User.ROLE_STUDENT)
def submit_vocabulary_review_correction(session_id):
    try:
        payload = request.get_json(silent=True) or {}
        session_token = str(payload.get("session_token") or "").strip() or None
        result = submit_review_correction(
            request.current_api_user,
            session_id,
            payload,
            session_token=session_token,
        )
        db.session.commit()
        return jsonify(result)
    except VocabularyAutonomousReviewError as error:
        db.session.rollback()
        return _autonomous_error_response(error)


@vocab_review_bp.route(
    "/miniprogram/student/vocabulary-review/sessions/<int:session_id>/settle",
    methods=["POST"],
)
@require_api_user(User.ROLE_STUDENT)
def settle_vocabulary_review_session(session_id):
    try:
        payload = request.get_json(silent=True) or {}
        payload["supports_correction"] = payload.get("supports_correction") is True
        session_token = str(payload.get("session_token") or "").strip() or None
        result = settle_review_session(
            request.current_api_user,
            session_id,
            payload,
            session_token=session_token,
        )
        db.session.commit()
        return jsonify(result)
    except VocabularyAutonomousReviewError as error:
        db.session.rollback()
        return _autonomous_error_response(error)


@vocab_review_bp.route(
    "/miniprogram/student/vocabulary-review/sessions/<int:session_id>/continue",
    methods=["POST"],
)
@require_api_user(User.ROLE_STUDENT)
def continue_vocabulary_review(session_id):
    try:
        payload = request.get_json(silent=True) or {}
        session_token = str(payload.get("session_token") or "").strip() or None
        result = continue_review(
            request.current_api_user,
            session_id,
            session_token=session_token,
        )
        db.session.commit()
        return jsonify(result)
    except VocabularyAutonomousReviewError as error:
        db.session.rollback()
        return _autonomous_error_response(error)


@vocab_review_bp.route("/miniprogram/student/vocabulary-review/due", methods=["GET"])
@require_api_user(User.ROLE_STUDENT)
def get_vocabulary_review_due_compat():
    """Compatibility alias returning the real claimable review snapshot."""
    try:
        result = claim_today_review(request.current_api_user)
        db.session.commit()
        return jsonify(result)
    except VocabularyAutonomousReviewError as error:
        db.session.rollback()
        return _autonomous_error_response(error)


@vocab_review_bp.route("/miniprogram/student/vocabulary-review/legacy-due", methods=["GET"])
@require_api_user(User.ROLE_STUDENT)
def get_vocabulary_review_legacy_due():
    """Keep the pre-v2 ID-only diagnostic endpoint available to old tools."""
    try:
        result = list_vocabulary_due(
            request.current_api_user,
            request.args.get("limit", type=int) or 100,
        )
        return jsonify(result)
    except VocabularyMasteryError as error:
        return _vocabulary_error_response(error)


@vocab_review_bp.route("/miniprogram/student/dictation-wrongs", methods=["GET"])
@require_api_user(User.ROLE_STUDENT)
def get_server_wrong_words():
    try:
        book_id = request.args.get("book_id", type=int)
        result = list_server_wrong_words(request.current_api_user, book_id)
        db.session.commit()
        return jsonify(result)
    except DictationReviewError as error:
        db.session.rollback()
        return _error_response(error)


@vocab_review_bp.route(
    "/miniprogram/student/dictation-wrongs/import",
    methods=["POST"],
)
@require_api_user(User.ROLE_STUDENT)
def import_server_wrong_words():
    try:
        payload = request.get_json(silent=True) or {}
        result = import_legacy_wrong_words(request.current_api_user, payload)
        db.session.commit()
        return jsonify(result), 201
    except DictationReviewError as error:
        db.session.rollback()
        return _error_response(error)
