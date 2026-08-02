"""Workflow helpers for teacher writing review and student mock-exam history.

The existing :mod:`services.mock_exam_review` module owns the pure objective
question rendering and band helpers.  This module owns the stateful parts of
the first review loop: draft creation, score persistence, signed capabilities,
short-lived editor scopes, and student visibility rules.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timedelta
from urllib.parse import urlsplit, urlunsplit

from flask import current_app, request, url_for
from flask import session as browser_session
from flask_login import current_user
from itsdangerous import BadSignature, URLSafeSerializer

from models import (
    MockExamReview,
    MockExamReviewEditSession,
    MockExamSession,
    StudentProfile,
    User,
    db,
)
from services import mock_exam_review as logic

TEXT_LIMITS = {
    "listening_feedback": 12000,
    "reading_feedback": 12000,
    "overall_feedback": 12000,
    "next_stage_advice": 12000,
    "task1_teacher_draft": 30000,
    "task2_teacher_draft": 30000,
    "reviewer_name": 64,
    "override_reason": 2000,
    "task1_feedback": 6000,
    "task2_feedback": 6000,
}
SCORE_MAP = {
    "task1_ta": "task1_ta",
    "task1_cc": "task1_cc",
    "task1_lr": "task1_lr",
    "task1_gra": "task1_gra",
    "task2_tr": "task2_tr",
    "task2_cc": "task2_cc",
    "task2_lr": "task2_lr",
    "task2_gra": "task2_gra",
}
EDITOR_SESSION_KEY = "mock_exam_review_edit_sessions"
EXAM_SESSION_KEY = "mock_exam_session_id"
EXAM_SESSION_AUTH_AT_KEY = "mock_exam_session_auth_at"
EXAM_SESSION_PROOF_KEY = "mock_exam_session_access_proof"
DEFAULT_LINK_DAYS = 14
DEFAULT_EDITOR_HOURS = 2
DEFAULT_STUDENT_BROWSER_DAYS = 14


def utcnow() -> datetime:
    return datetime.utcnow()


def _safe_json_object(blob, default=None):
    try:
        value = json.loads(blob or "")
    except (TypeError, ValueError):
        return {} if default is None else default
    return value if isinstance(value, dict) else ({} if default is None else default)


def _clip_text(value, field: str) -> str:
    limit = TEXT_LIMITS.get(field, 12000)
    return str(value or "").strip()[:limit]


def ensure_review_draft(mock_session: MockExamSession) -> MockExamReview | None:
    """Create the one-to-one draft exactly once after the full exam is submitted."""
    if not mock_session or mock_session.status != MockExamSession.STATUS_SUBMITTED:
        return None
    review = MockExamReview.query.filter_by(session_id=mock_session.id).first()
    if review:
        return review
    review = MockExamReview(
        session_id=mock_session.id,
        status=MockExamReview.STATUS_DRAFT,
        task1_teacher_draft=mock_session.writing_essay_task1 or "",
        task2_teacher_draft=mock_session.writing_essay_task2 or "",
        question_feedback_json=json.dumps({"task1": "", "task2": ""}, ensure_ascii=False),
        annotations_json=json.dumps({}, ensure_ascii=False),
    )
    db.session.add(review)
    db.session.flush()
    return review


def score_options() -> list[str]:
    return [logic.NOT_SCORABLE] + [f"{step / 2:.1f}" for step in range(19)]


def _review_score_input(review: MockExamReview, payload: dict) -> dict:
    values = {}
    for field in logic.ALL_SCORE_FIELDS + (
        "task1_band_override",
        "task2_band_override",
        "writing_band_override",
        "override_reason",
    ):
        if field in payload:
            values[field] = payload.get(field)
        elif field in SCORE_MAP:
            values[field] = getattr(review, field)
        else:
            values[field] = getattr(review, field)
    return values


def _score_payload(review: MockExamReview) -> dict:
    task1 = {field: getattr(review, f"task1_{field}") for field in logic.TASK1_SCORE_FIELDS}
    task2 = {field: getattr(review, f"task2_{field}") for field in logic.TASK2_SCORE_FIELDS}
    calculated = logic.calculate_writing_scores(
        task1,
        task2,
        task1_override=review.task1_band_override,
        task2_override=review.task2_band_override,
        writing_override=review.writing_band_override,
    )
    return {
        "task1": {
            **task1,
            "raw_average": calculated.get("task1", {}).get("raw_average"),
            "band": review.task1_band,
            "state": review.task1_band_state,
            "override": review.task1_band_override,
        },
        "task2": {
            **task2,
            "raw_average": calculated.get("task2", {}).get("raw_average"),
            "band": review.task2_band,
            "state": review.task2_band_state,
            "override": review.task2_band_override,
        },
        "writing_raw": review.writing_raw,
        "writing_band": review.writing_band,
        "writing_state": review.writing_band_state,
        "writing_override": review.writing_band_override,
        "override_reason": review.override_reason or "",
    }


def _apply_calculated_scores(review: MockExamReview, normalized: dict) -> None:
    calculated = normalized["calculated"]
    for field in logic.ALL_SCORE_FIELDS:
        setattr(review, field, normalized.get(field))

    review.task1_band = calculated.get("task1", {}).get("band")
    review.task2_band = calculated.get("task2", {}).get("band")
    review.task1_band_state = calculated.get("task1", {}).get("state", "pending")
    review.task2_band_state = calculated.get("task2", {}).get("state", "pending")
    review.writing_raw = calculated.get("writing_raw")
    review.writing_band = calculated.get("writing_band")
    review.writing_band_state = calculated.get("writing_state", "pending")
    for field in ("task1", "task2", "writing"):
        raw = normalized.get(f"{field}_band_override")
        setattr(review, f"{field}_band_override", float(raw) if raw else None)
    review.override_reason = normalized.get("override_reason") or None


def apply_review_fields(
    review: MockExamReview,
    payload: dict,
    *,
    has_writing: bool,
    require_complete: bool = False,
    saved_by: int | None = None,
) -> dict:
    """Validate and apply a draft/publish payload without committing it."""
    payload = payload if isinstance(payload, dict) else {}
    score_input = _review_score_input(review, payload)
    normalized, errors = logic.validate_score_payload(
        score_input,
        require_complete=bool(require_complete and has_writing),
    )
    if errors:
        return {"ok": False, "errors": errors}

    for field in (
        "listening_feedback",
        "reading_feedback",
        "overall_feedback",
        "next_stage_advice",
        "task1_teacher_draft",
        "task2_teacher_draft",
    ):
        if field in payload:
            setattr(review, field, _clip_text(payload.get(field), field))

    if "reviewer_name" in payload:
        review.reviewer_name = _clip_text(payload.get("reviewer_name"), "reviewer_name") or None
    if "task1_feedback" in payload or "task2_feedback" in payload:
        feedback = _safe_json_object(review.question_feedback_json)
        for key in ("task1", "task2"):
            input_key = f"{key}_feedback"
            if input_key in payload:
                feedback[key] = _clip_text(payload.get(input_key), input_key)
        review.question_feedback_json = json.dumps(feedback, ensure_ascii=False)
    if "question_feedback" in payload and isinstance(payload.get("question_feedback"), dict):
        feedback = _safe_json_object(review.question_feedback_json)
        for key in ("task1", "task2"):
            if key in payload["question_feedback"]:
                feedback[key] = _clip_text(payload["question_feedback"].get(key), f"{key}_feedback")
        review.question_feedback_json = json.dumps(feedback, ensure_ascii=False)
    if isinstance(payload.get("annotations"), dict):
        review.annotations_json = json.dumps(payload["annotations"], ensure_ascii=False)

    if has_writing:
        _apply_calculated_scores(review, normalized)
    review.auto_saved_at = utcnow()
    review.last_saved_by = saved_by
    return {"ok": True, "errors": {}}


def question_feedback(review: MockExamReview) -> dict:
    feedback = _safe_json_object(review.question_feedback_json)
    return {
        "task1": str(feedback.get("task1") or ""),
        "task2": str(feedback.get("task2") or ""),
    }


def review_payload(review: MockExamReview, *, writing_tasks: list | None = None) -> dict:
    mock_session = review.session
    writing_tasks = writing_tasks or []
    prompts = []
    for task in writing_tasks[:2]:
        task = task if isinstance(task, dict) else {}
        prompts.append(str(task.get("prompt") or ""))
    while len(prompts) < 2:
        prompts.append("")
    return {
        "id": review.id,
        "session_id": review.session_id,
        "version": review.version,
        "status": review.status,
        "read_only": review.status == MockExamReview.STATUS_PUBLISHED,
        "reviewer_name": review.reviewer_name or "",
        "listening_feedback": review.listening_feedback or "",
        "reading_feedback": review.reading_feedback or "",
        "overall_feedback": review.overall_feedback or "",
        "next_stage_advice": review.next_stage_advice or "",
        "task1_teacher_draft": review.task1_teacher_draft or "",
        "task2_teacher_draft": review.task2_teacher_draft or "",
        "question_feedback": question_feedback(review),
        "scores": _score_payload(review),
        "original": {
            "student_name": mock_session.student_name,
            "task1": mock_session.writing_essay_task1 or "",
            "task2": mock_session.writing_essay_task2 or "",
            "task1_words": mock_session.writing_task1_words or 0,
            "task2_words": mock_session.writing_task2_words or 0,
            "task1_prompt": prompts[0],
            "task2_prompt": prompts[1],
        },
        "auto_saved_at": (
            review.auto_saved_at.isoformat() if review.auto_saved_at else None
        ),
        "published_at": review.published_at.isoformat() if review.published_at else None,
    }


def publish_review(
    review: MockExamReview,
    payload: dict,
    *,
    has_writing: bool,
    saved_by: int | None = None,
) -> dict:
    reviewer_name = _clip_text(payload.get("reviewer_name"), "reviewer_name")
    if not reviewer_name:
        return {"ok": False, "errors": {"reviewer_name": "reviewer_name_required"}}
    result = apply_review_fields(
        review,
        payload,
        has_writing=has_writing,
        require_complete=True,
        saved_by=saved_by,
    )
    if not result["ok"]:
        return result
    review.reviewer_name = reviewer_name
    review.status = MockExamReview.STATUS_PUBLISHED
    review.published_at = utcnow()
    review.auto_saved_at = review.published_at
    return {"ok": True, "errors": {}}


def _capability_serializer() -> URLSafeSerializer:
    return URLSafeSerializer(
        current_app.config["SECRET_KEY"],
        salt="studytracker-mock-exam-review-capability-v1",
    )


def _capability_token(review: MockExamReview) -> str:
    return _capability_serializer().dumps(
        {
            "review_id": review.id,
            "link_version": int(review.link_version or 0),
            "expires_at": int(review.link_expires_at.timestamp()),
        }
    )


def issue_capability(review: MockExamReview) -> tuple[str, datetime]:
    now = utcnow()
    days = int(current_app.config.get("MOCK_REVIEW_LINK_DAYS", DEFAULT_LINK_DAYS))
    expires_at = now + timedelta(days=max(1, min(days, 90)))
    review.link_version = int(review.link_version or 0) + 1
    review.link_expires_at = expires_at
    review.link_revoked_at = None
    return _capability_token(review), expires_at


def active_capability(review: MockExamReview) -> tuple[str, datetime] | None:
    """Return the current capability without rotating its generation."""
    now = utcnow()
    if (
        not review
        or not review.link_version
        or review.link_revoked_at
        or not review.link_expires_at
        or review.link_expires_at <= now
    ):
        return None
    return _capability_token(review), review.link_expires_at


def capability_url(token: str) -> str:
    """Build a capability URL with the externally visible request scheme.

    The app is behind a TLS-terminating proxy in production and does not use
    ``ProxyFix`` globally.  Prefer an explicitly configured public scheme;
    otherwise accept only the first trusted-looking ``X-Forwarded-Proto``
    value when it is exactly ``http`` or ``https``.  Any other value falls
    back to Flask's request scheme, so it cannot inject a URL scheme.
    """
    path = url_for("mock_exam_review.access_link", token=token)
    configured = str(current_app.config.get("MOCK_REVIEW_PUBLIC_SCHEME") or "").strip().lower()
    forwarded = (request.headers.get("X-Forwarded-Proto") or "").split(",", 1)[0].strip().lower()
    scheme = configured if configured in {"http", "https"} else forwarded
    if scheme not in {"http", "https"}:
        scheme = request.scheme if request.scheme in {"http", "https"} else "https"
    parts = urlsplit(request.host_url)
    return urlunsplit((scheme, parts.netloc, path, "", ""))


def revoke_capability(review: MockExamReview) -> None:
    review.link_version = int(review.link_version or 0) + 1
    review.link_revoked_at = utcnow()
    MockExamReviewEditSession.query.filter_by(review_id=review.id, revoked_at=None).update(
        {"revoked_at": utcnow()}, synchronize_session=False
    )


def decode_capability(token: str) -> tuple[MockExamReview | None, str | None]:
    try:
        payload = _capability_serializer().loads(token)
    except (BadSignature, TypeError, ValueError):
        return None, "invalid"
    try:
        review_id = int(payload.get("review_id"))
        link_version = int(payload.get("link_version"))
        token_expiry = int(payload.get("expires_at"))
    except (AttributeError, TypeError, ValueError):
        return None, "invalid"
    review = db.session.get(MockExamReview, review_id)
    now = utcnow()
    if (
        not review
        or link_version != review.link_version
        or review.link_revoked_at
        or not review.link_expires_at
        or review.link_expires_at <= now
        or token_expiry <= int(now.timestamp())
    ):
        return None, "invalid"
    return review, None


def create_editor_scope(review: MockExamReview) -> tuple[MockExamReviewEditSession, str]:
    hours = int(current_app.config.get("MOCK_REVIEW_EDITOR_HOURS", DEFAULT_EDITOR_HOURS))
    raw_token = secrets.token_urlsafe(32)
    row = MockExamReviewEditSession(
        review_id=review.id,
        token_hash=hashlib.sha256(raw_token.encode("utf-8")).hexdigest(),
        link_version=review.link_version,
        expires_at=utcnow() + timedelta(hours=max(1, min(hours, 24))),
    )
    db.session.add(row)
    db.session.flush()
    scopes = dict(browser_session.get(EDITOR_SESSION_KEY) or {})
    scopes[str(review.id)] = {"id": row.id, "token": raw_token}
    browser_session[EDITOR_SESSION_KEY] = scopes
    browser_session.modified = True
    return row, raw_token


def current_editor_scope(review_id: int) -> MockExamReviewEditSession | None:
    scopes = browser_session.get(EDITOR_SESSION_KEY) or {}
    raw_scope = scopes.get(str(review_id))
    if not isinstance(raw_scope, dict):
        return None
    row = db.session.get(MockExamReviewEditSession, raw_scope.get("id"))
    raw_token = str(raw_scope.get("token") or "")
    if not row or not raw_token:
        return None
    review = row.review
    now = utcnow()
    if (
        row.review_id != review_id
        or not secrets.compare_digest(
            row.token_hash,
            hashlib.sha256(raw_token.encode("utf-8")).hexdigest(),
        )
        or row.revoked_at
        or row.expires_at <= now
        or row.link_version != review.link_version
        or review.link_revoked_at
        or not review.link_expires_at
        or review.link_expires_at <= now
    ):
        return None
    row.last_seen_at = now
    return row


def remember_browser_exam_session(session_id: int) -> None:
    """Authorize only the just-started mock session for light practice mode."""
    mock_session = db.session.get(MockExamSession, int(session_id))
    if not mock_session or not mock_session.access_token:
        browser_session.pop(EXAM_SESSION_KEY, None)
        browser_session.pop(EXAM_SESSION_AUTH_AT_KEY, None)
        browser_session.pop(EXAM_SESSION_PROOF_KEY, None)
        browser_session.modified = True
        return
    browser_session[EXAM_SESSION_KEY] = mock_session.id
    browser_session[EXAM_SESSION_PROOF_KEY] = hashlib.sha256(
        mock_session.access_token.encode("utf-8")
    ).hexdigest()
    browser_session[EXAM_SESSION_AUTH_AT_KEY] = int(utcnow().timestamp())
    browser_session.modified = True


def light_browser_exam_session_id() -> int | None:
    try:
        session_id = int(browser_session.get(EXAM_SESSION_KEY))
        authorized_at = int(browser_session.get(EXAM_SESSION_AUTH_AT_KEY))
        saved_proof = str(browser_session.get(EXAM_SESSION_PROOF_KEY) or "")
    except (TypeError, ValueError):
        return None
    if not saved_proof:
        return None
    max_age = int(
        current_app.config.get("MOCK_REVIEW_BROWSER_SESSION_DAYS", DEFAULT_STUDENT_BROWSER_DAYS)
    ) * 86400
    if utcnow().timestamp() - authorized_at > max(1, max_age):
        browser_session.pop(EXAM_SESSION_KEY, None)
        browser_session.pop(EXAM_SESSION_AUTH_AT_KEY, None)
        browser_session.pop(EXAM_SESSION_PROOF_KEY, None)
        return None
    mock_session = db.session.get(MockExamSession, session_id)
    if not mock_session or not mock_session.access_token:
        return None
    expected_proof = hashlib.sha256(mock_session.access_token.encode("utf-8")).hexdigest()
    if not secrets.compare_digest(saved_proof, expected_proof):
        return None
    return session_id


def current_student_profile() -> StudentProfile | None:
    if current_user.is_authenticated and current_user.role == User.ROLE_STUDENT:
        return StudentProfile.query.filter_by(
            user_id=current_user.id,
            is_deleted=False,
        ).first()
    if current_user.is_authenticated:
        return None
    session_id = light_browser_exam_session_id()
    if not session_id:
        return None
    mock_session = db.session.get(MockExamSession, session_id)
    if not mock_session or not mock_session.student_profile_id:
        return None
    return StudentProfile.query.filter_by(
        id=mock_session.student_profile_id,
        is_deleted=False,
    ).first()


def can_student_view_session(mock_session: MockExamSession, profile: StudentProfile) -> bool:
    if not mock_session or not profile:
        return False
    if current_user.is_authenticated and current_user.role == User.ROLE_STUDENT:
        return mock_session.student_profile_id == profile.id
    return (
        light_browser_exam_session_id() == mock_session.id
        and mock_session.student_profile_id == profile.id
    )


def student_session_summary(mock_session: MockExamSession, review: MockExamReview | None) -> dict:
    submitted = mock_session.status == MockExamSession.STATUS_SUBMITTED
    review_status = review.status if review else None
    objective_band = logic.overall_band(
        mock_session.listening_ielts_score,
        mock_session.reading_ielts_score,
    ) if submitted else None
    return {
        "id": mock_session.id,
        "exam_id": mock_session.exam_id,
        "exam_name": mock_session.exam.name if mock_session.exam else "",
        "student_name": mock_session.student_name,
        "status": mock_session.status,
        "status_label": "已交卷" if submitted else "进行中",
        "review_status": review_status,
        "review_status_label": (
            "老师已发布" if review_status == MockExamReview.STATUS_PUBLISHED else "等待老师发布"
        ) if submitted else "",
        "objective_band": objective_band,
        "listening_band": mock_session.listening_ielts_score if submitted else None,
        "reading_band": mock_session.reading_ielts_score if submitted else None,
        "writing_band": (
            review.writing_band
            if review and review.status == MockExamReview.STATUS_PUBLISHED
            else None
        ),
        "started_at": mock_session.started_at.isoformat() if mock_session.started_at else None,
        "finished_at": mock_session.finished_at.isoformat() if mock_session.finished_at else None,
    }
