"""Review workflow and safe read-only serialization for TOEFL v2 attempts."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import update
from sqlalchemy.orm.attributes import set_committed_value

from models import ToeflMockAttempt, ToeflMockResponse, db
from services.toefl_mock_v2 import (
    definition,
    load_private_answer_key,
    resolve_package,
    score_responses,
)

REVIEW_PENDING = "pending"
REVIEW_DRAFT = "draft"
REVIEW_PUBLISHED = "published"
REVIEW_NOT_REQUIRED = "not_required"
REVIEW_NOT_STARTED = "not_started"
REVIEWED = "reviewed"
MAX_FEEDBACK_LENGTH = 8000
MAX_SCORE = 100.0


def _json(value: str | None, fallback: Any = None) -> Any:
    try:
        return json.loads(value or "")
    except (TypeError, ValueError):
        return fallback


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)  # noqa: UP017


def _claim_review_version(
    attempt: ToeflMockAttempt,
    expected_version: int,
) -> bool:
    """Atomically claim the next review version before persisting edits."""
    with db.session.no_autoflush:
        result = db.session.execute(
            update(ToeflMockAttempt)
            .where(
                ToeflMockAttempt.id == attempt.id,
                ToeflMockAttempt.review_version == expected_version,
            )
            .values(review_version=expected_version + 1),
            execution_options={"synchronize_session": False},
        )
    if result.rowcount != 1:
        db.session.rollback()
        return False
    set_committed_value(attempt, "review_version", expected_version + 1)
    return True


def _definition(attempt: ToeflMockAttempt) -> dict[str, Any]:
    return definition(attempt.exam_id, _json(attempt.sections_json, []))


def _answer_index(test_id: str) -> dict[str, dict[str, Any]]:
    return {
        item["question_id"]: item
        for item in load_private_answer_key(test_id).get("answers", [])
        if item.get("question_id")
    }


def _review_context_index(test_id: str) -> dict[str, str]:
    """Load only post-submit prompt context stripped from the exam API."""
    try:
        content = json.loads(
            (resolve_package(test_id) / "content.json").read_text(encoding="utf-8")
        )
    except (OSError, TypeError, ValueError):
        return {}
    return {
        str(item["id"]): str(item["context_sentence"])
        for item in content.get("questions", [])
        if item.get("id") and item.get("context_sentence")
    }


def _response_index(attempt: ToeflMockAttempt) -> dict[str, ToeflMockResponse]:
    return {row.question_id: row for row in attempt.responses}


def _raw_response(row: ToeflMockResponse | None) -> Any:
    return _json(row.response_json, None) if row else None


def _has_student_response(question: dict[str, Any], row: ToeflMockResponse | None) -> bool:
    if not row:
        return False
    if question.get("response_type") == "recording":
        return bool(row.recording_token)
    value = _raw_response(row)
    if isinstance(value, str):
        return bool(value.strip())
    return value not in (None, "", [], {})


def _option_pairs(question: dict[str, Any]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for index, option in enumerate(question.get("options") or []):
        if isinstance(option, dict):
            key = str(option.get("key") or option.get("id") or chr(65 + index))
            label = str(option.get("text") or option.get("label") or option)
        else:
            key = chr(65 + index)
            label = str(option)
        pairs.append((key, label))
    return pairs


def _display_answer(question: dict[str, Any], answer: dict[str, Any] | None) -> Any:
    if not answer:
        return None
    if answer.get("correct_option_keys"):
        labels = dict(_option_pairs(question))
        return [
            {
                "key": key,
                "text": labels.get(key, key),
            }
            for key in answer["correct_option_keys"]
        ]
    if answer.get("ordered_tokens"):
        return " ".join(str(token) for token in answer["ordered_tokens"])
    if answer.get("canonical_text") is not None:
        return answer.get("canonical_text")
    accepted = answer.get("accepted_text")
    if isinstance(accepted, list):
        return accepted[0] if accepted else None
    return accepted


def _display_student_answer(question: dict[str, Any], value: Any) -> Any:
    if question.get("response_type") == "mc" and value is not None:
        labels = dict(_option_pairs(question))
        keys = value if isinstance(value, list) else [value]
        return [
            {"key": str(key), "text": labels.get(str(key), str(key))}
            for key in keys
        ]
    if question.get("response_type") == "order" and isinstance(value, list):
        return " ".join(str(item) for item in value)
    return value


def _safe_evidence(answer: dict[str, Any] | None) -> list[dict[str, Any]]:
    result = []
    for item in (answer or {}).get("evidence") or []:
        if not isinstance(item, dict):
            continue
        source = item.get("path")
        result.append(
            {
                "source": Path(str(source)).name if source else None,
                "confidence": item.get("confidence"),
                "module": item.get("module"),
                "question_number": item.get("question_number"),
            }
        )
    return result


def _stimulus(group: dict[str, Any] | None) -> dict[str, Any] | None:
    if not group:
        return None
    stimulus = group.get("stimulus")
    if not isinstance(stimulus, dict):
        return None
    result = {"format": stimulus.get("format")}
    for key in ("title", "text", "display_text", "transcript"):
        if stimulus.get(key) is not None:
            result[key] = stimulus[key]
    return result


def _audio_urls(mock_definition: dict[str, Any]) -> dict[str, str]:
    """Return only already-public, published TOEFL media URLs."""
    result: dict[str, str] = {}
    for asset in mock_definition.get("assets", []):
        if asset.get("kind") != "audio":
            continue
        delivery = asset.get("delivery") or {}
        url = str(delivery.get("url") or "")
        if (
            delivery.get("status") == "published"
            and url.startswith("/static/toefl/v2/")
        ):
            result[str(asset.get("id") or "")] = url
    return result


def _review_stimulus(
    group: dict[str, Any] | None,
    audio_urls: dict[str, str],
) -> dict[str, Any] | None:
    result = _stimulus(group)
    if not result or not group:
        return result
    asset_id = str((group.get("stimulus") or {}).get("asset_id") or "")
    if asset_id in audio_urls:
        result["audio_url"] = audio_urls[asset_id]
    return result


def _manual_status(row: ToeflMockResponse | None) -> str:
    return str(getattr(row, "review_status", None) or REVIEW_PENDING)


def ensure_review_state(attempt: ToeflMockAttempt) -> bool:
    """Initialize legacy/new rows without changing an already-published review."""
    mock_definition = _definition(attempt)
    manual_ids = {
        item["id"]
        for item in mock_definition.get("questions", [])
        if item.get("grading_status") == "manual"
    }
    changed = False
    if getattr(attempt, "review_version", None) is None:
        attempt.review_version = 1
        changed = True
    if attempt.status == "completed" and attempt.review_status in {
        None,
        REVIEW_NOT_STARTED,
    }:
        attempt.review_status = REVIEW_PENDING if manual_ids else REVIEW_NOT_REQUIRED
        attempt.review_updated_at = _now()
        changed = True
    for row in attempt.responses:
        expected = REVIEW_PENDING if row.question_id in manual_ids else REVIEW_NOT_REQUIRED
        if not getattr(row, "review_status", None) or (
            expected == REVIEW_NOT_REQUIRED
            and row.review_status == REVIEW_PENDING
        ):
            row.review_status = expected
            changed = True
    return changed


def _objective_units(
    attempt: ToeflMockAttempt,
    mock_definition: dict[str, Any],
    responses: dict[str, ToeflMockResponse],
) -> list[dict[str, Any]]:
    groups = {item["id"]: item for item in mock_definition.get("groups", [])}
    modules = {item["id"]: item for item in mock_definition.get("modules", [])}
    audio_urls = _audio_urls(mock_definition)
    answers = _answer_index(attempt.exam_id)
    response_values = {
        key: _raw_response(row) for key, row in responses.items()
    }
    score = score_responses(
        attempt.exam_id,
        response_values,
        question_ids={
            item["id"]
            for item in mock_definition.get("questions", [])
            if item.get("grading_status") == "auto"
        },
    )
    score_by_id = {item["question_id"]: item for item in score.get("results", [])}
    units = []
    for question in mock_definition.get("questions", []):
        if question.get("grading_status") != "auto":
            continue
        question_id = question["id"]
        row = responses.get(question_id)
        answer = answers.get(question_id)
        result = score_by_id.get(question_id, {})
        group = groups.get(question.get("group_id"))
        module = modules.get(question.get("module_id"))
        student_value = _raw_response(row)
        is_answered = bool(result.get("answered"))
        units.append(
            {
                "id": question_id,
                "number": question.get("number"),
                "section": question.get("subject"),
                "module": module.get("module") if module else None,
                "group_title": group.get("title") if group else None,
                "task_type": group.get("task_type") if group else None,
                "prompt": question.get("prompt"),
                "context": question.get("context_sentence"),
                "stimulus": _review_stimulus(group, audio_urls),
                "options": [
                    {"key": key, "text": text}
                    for key, text in _option_pairs(question)
                ],
                "student_answer": _display_student_answer(question, student_value),
                "correct_answer": _display_answer(question, answer),
                "is_answered": is_answered,
                "is_correct": bool(result.get("correct")) if is_answered else False,
                "is_wrong": not bool(result.get("correct")) or not is_answered,
                "explanation": question.get("explanation")
                or (answer or {}).get("explanation")
                or (answer or {}).get("rationale"),
                "evidence": _safe_evidence(answer),
            }
        )
    units.sort(key=lambda item: (not item["is_wrong"], item.get("section") or "", item.get("number") or 0))
    return units


def _manual_units(
    attempt: ToeflMockAttempt,
    mock_definition: dict[str, Any],
    responses: dict[str, ToeflMockResponse],
    student_view: bool,
    recording_url_factory: Callable[[ToeflMockResponse], str] | None,
) -> list[dict[str, Any]]:
    groups = {item["id"]: item for item in mock_definition.get("groups", [])}
    modules = {item["id"]: item for item in mock_definition.get("modules", [])}
    audio_urls = _audio_urls(mock_definition)
    review_contexts = _review_context_index(attempt.exam_id)
    published = attempt.review_status == REVIEW_PUBLISHED
    units = []
    for question in mock_definition.get("questions", []):
        if question.get("grading_status") != "manual":
            continue
        row = responses.get(question["id"])
        group = groups.get(question.get("group_id"))
        module = modules.get(question.get("module_id"))
        raw = _raw_response(row)
        submitted = _has_student_response(question, row)
        unit = {
            "id": question["id"],
            "number": question.get("number"),
            "section": question.get("subject"),
            "module": module.get("module") if module else None,
            "group_title": group.get("title") if group else None,
            "task_type": group.get("task_type") if group else None,
            "prompt": question.get("prompt"),
            "context": question.get("context_sentence")
            or review_contexts.get(question["id"]),
            "stimulus": _review_stimulus(group, audio_urls),
            "student_answer": None if question.get("response_type") == "recording" else raw,
            "submitted": submitted,
            "recording_available": bool(row and row.recording_token),
            "recording_url": (
                recording_url_factory(row)
                if row and row.recording_token and (not student_view or published)
                and recording_url_factory
                else None
            ),
            "review_status": (
                REVIEW_PENDING
                if student_view and not published
                else _manual_status(row)
            ),
            "score": None if student_view and not published else getattr(row, "teacher_score", None),
            "score_max": None if student_view and not published else getattr(row, "score_max", None),
            "feedback": None
            if student_view and not published
            else getattr(row, "teacher_feedback", None),
        }
        units.append(unit)
    return units


def build_review(
    attempt: ToeflMockAttempt,
    *,
    student_view: bool = False,
    recording_url_factory: Callable[[ToeflMockResponse], str] | None = None,
) -> dict[str, Any]:
    """Return one shared, JSON-safe review view model.

    This function is only called after the HTTP layer has checked ownership and
    completion.  It never includes recording tokens, storage paths, or private
    answer-key evidence paths.
    """
    mock_definition = _definition(attempt)
    responses = _response_index(attempt)
    objective = _objective_units(attempt, mock_definition, responses)
    manual = _manual_units(
        attempt,
        mock_definition,
        responses,
        student_view,
        recording_url_factory,
    )
    manual_total = len(manual)
    submitted = sum(item["submitted"] for item in manual)
    reviewed = sum(item["score"] is not None for item in manual)
    return {
        "attempt": {
            "id": attempt.id,
            "exam_id": attempt.exam_id,
            "exam_title": mock_definition.get("test", {}).get("title") or attempt.exam_id,
            "sections": _json(attempt.sections_json, []),
            "status": attempt.status,
            "preview": bool(attempt.is_preview),
            "started_at": attempt.started_at.isoformat() if attempt.started_at else None,
            "completed_at": attempt.completed_at.isoformat() if attempt.completed_at else None,
            "review_status": attempt.review_status,
            "review_version": attempt.review_version,
            "published_at": attempt.review_published_at.isoformat()
            if attempt.review_published_at
            else None,
        },
        "objective": objective,
        "manual": manual,
        "summary": {
            "objective_total": len(objective),
            "objective_correct": sum(item["is_correct"] for item in objective),
            "objective_wrong": sum(item["is_wrong"] for item in objective),
            "manual_total": manual_total,
            "manual_submitted": submitted,
            "manual_reviewed": reviewed,
            "manual_complete": manual_total == submitted == reviewed,
        },
    }


def attempt_summary(attempt: ToeflMockAttempt) -> dict[str, Any]:
    mock_definition = _definition(attempt)
    review = build_review(attempt)
    student = getattr(attempt, "student", None)
    return {
        "id": attempt.id,
        "exam_id": attempt.exam_id,
        "exam_title": mock_definition.get("test", {}).get("title") or attempt.exam_id,
        "student_id": attempt.student_id,
        "student_name": getattr(student, "full_name", None) or "未绑定学生",
        "status": attempt.status,
        "preview": bool(attempt.is_preview),
        "sections": _json(attempt.sections_json, []),
        "started_at": attempt.started_at.isoformat() if attempt.started_at else None,
        "completed_at": attempt.completed_at.isoformat() if attempt.completed_at else None,
        "review_status": attempt.review_status,
        "review_version": attempt.review_version,
        "summary": review["summary"],
    }


def save_reviews(
    attempt: ToeflMockAttempt,
    payload: dict[str, Any],
    reviewer_id: int,
) -> tuple[bool, str | None]:
    if attempt.review_status == REVIEW_PUBLISHED:
        return False, "review_published"
    version = payload.get("version")
    try:
        version = int(version)
    except (TypeError, ValueError):
        return False, "review_version_required"
    if version != (attempt.review_version or 1):
        return False, "review_version_conflict"
    mock_definition = _definition(attempt)
    manual_questions = {
        item["id"]: item
        for item in mock_definition.get("questions", [])
        if item.get("grading_status") == "manual"
    }
    responses = _response_index(attempt)
    incoming = payload.get("reviews") or []
    if isinstance(incoming, dict):
        incoming = [dict(value, question_id=key) for key, value in incoming.items()]
    if not isinstance(incoming, list):
        return False, "reviews_invalid"
    validated = []
    for item in incoming:
        if not isinstance(item, dict):
            return False, "reviews_invalid"
        question_id = str(item.get("question_id") or item.get("questionId") or "").strip()
        if question_id not in manual_questions:
            return False, "question_not_manual"
        row = responses.get(question_id)
        raw_score = item.get("score", item.get("teacher_score"))
        if raw_score in (None, ""):
            score = None
        else:
            try:
                score = float(raw_score)
            except (TypeError, ValueError):
                return False, "score_invalid"
            if not 0 <= score <= MAX_SCORE:
                return False, "score_invalid"
        raw_max = item.get(
            "score_max",
            item.get("scoreMax", (row.score_max if row else None) or 5),
        )
        try:
            score_max = float(raw_max)
        except (TypeError, ValueError):
            return False, "score_max_invalid"
        if not 0 < score_max <= MAX_SCORE:
            return False, "score_max_invalid"
        if score is not None and score > score_max:
            return False, "score_invalid"
        feedback = str(item.get("feedback", item.get("teacher_feedback", "")) or "").strip()
        if len(feedback) > MAX_FEEDBACK_LENGTH:
            return False, "feedback_too_long"
        validated.append((question_id, score, score_max, feedback))
    if not _claim_review_version(attempt, version):
        return False, "review_version_conflict"
    reviewed_at = _now()
    for question_id, score, score_max, feedback in validated:
        row = responses.get(question_id)
        if not row:
            row = ToeflMockResponse(
                attempt_id=attempt.id,
                question_id=question_id,
                response_json="null",
            )
            db.session.add(row)
            responses[question_id] = row
        row.teacher_score = score
        row.score_max = score_max
        row.teacher_feedback = feedback
        row.review_status = REVIEWED if score is not None else REVIEW_DRAFT
        row.reviewed_by = reviewer_id
        row.reviewed_at = reviewed_at
    attempt.review_status = REVIEW_DRAFT if manual_questions else REVIEW_NOT_REQUIRED
    attempt.review_reviewer_id = reviewer_id
    attempt.review_updated_at = _now()
    return True, None


def publish_reviews(
    attempt: ToeflMockAttempt,
    payload: dict[str, Any],
    reviewer_id: int,
) -> tuple[bool, str | None]:
    if attempt.review_status == REVIEW_PUBLISHED:
        return False, "review_published"
    version_claimed = False
    if payload.get("reviews"):
        ok, error = save_reviews(attempt, payload, reviewer_id)
        if not ok:
            return False, error
        version_claimed = True
    else:
        try:
            version = int(payload.get("version"))
        except (TypeError, ValueError):
            return False, "review_version_required"
        if version != (attempt.review_version or 1):
            return False, "review_version_conflict"
        if not _claim_review_version(attempt, version):
            return False, "review_version_conflict"
        version_claimed = True
    mock_definition = _definition(attempt)
    manual = [
        item for item in mock_definition.get("questions", [])
        if item.get("grading_status") == "manual"
    ]
    responses = _response_index(attempt)
    for question in manual:
        row = responses.get(question["id"])
        if not _has_student_response(question, row):
            if version_claimed:
                db.session.rollback()
            return False, "manual_submission_incomplete"
        if not row or row.teacher_score is None:
            if version_claimed:
                db.session.rollback()
            return False, "manual_review_incomplete"
    attempt.review_status = REVIEW_PUBLISHED if manual else REVIEW_NOT_REQUIRED
    attempt.review_reviewer_id = reviewer_id
    attempt.review_published_at = _now()
    attempt.review_updated_at = attempt.review_published_at
    return True, None


def reopen_review(
    attempt: ToeflMockAttempt,
    reviewer_id: int,
    expected_version: Any,
) -> tuple[bool, str | None]:
    if attempt.review_status != REVIEW_PUBLISHED:
        return False, "review_not_published"
    try:
        version = int(expected_version)
    except (TypeError, ValueError):
        return False, "review_version_required"
    if version != (attempt.review_version or 1):
        return False, "review_version_conflict"
    if not _claim_review_version(attempt, version):
        return False, "review_version_conflict"
    attempt.review_status = REVIEW_DRAFT
    attempt.review_reviewer_id = reviewer_id
    attempt.review_reopened_at = _now()
    attempt.review_published_at = None
    attempt.review_updated_at = attempt.review_reopened_at
    return True, None
