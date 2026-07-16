"""Student-facing automatic vocabulary review APIs."""

from flask import Blueprint, jsonify, request

from models import User, db
from services.dictation_review import (
    DictationReviewError,
    get_task_queue,
    import_legacy_wrong_words,
    list_server_wrong_words,
)

from .auth_utils import require_api_user

vocab_review_bp = Blueprint("vocab_review", __name__, url_prefix="/api")


def _error_response(error: DictationReviewError):
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
        result = get_task_queue(request.current_api_user, task_id)
        # Queue creation is the claim operation.  Persist it before returning
        # so another device/task on the same day sees the same snapshot.
        db.session.commit()
        return jsonify(result)
    except DictationReviewError as error:
        db.session.rollback()
        return _error_response(error)


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
