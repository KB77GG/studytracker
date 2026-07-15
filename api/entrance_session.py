"""Server-side draft and interruption controls for entrance tests."""

from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timedelta

from models import EntranceTestDraft, db

RESUME_GRACE_SECONDS = 120
MAX_ANSWER_CHARS = 20000
MAX_ANSWERS = 300


class EntranceSessionError(Exception):
    def __init__(self, code: str, status_code: int = 400):
        super().__init__(code)
        self.code = code
        self.status_code = status_code


def utcnow() -> datetime:
    return datetime.utcnow()


def hash_device_id(device_id: str) -> str:
    value = str(device_id or "").strip()
    if len(value) < 8 or len(value) > 160:
        raise EntranceSessionError("invalid_device_id", 400)
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def paper_duration_minutes(paper) -> int:
    total = sum(max(0, int(section.duration_minutes or 0)) for section in paper.sections)
    return total or 30


def load_json_object(raw: str | None) -> dict:
    try:
        value = json.loads(raw or "{}")
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def dump_json_object(value: dict) -> str:
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"))


def normalize_answer_map(raw_answers, valid_question_ids: set[int]) -> dict[str, str]:
    if not isinstance(raw_answers, list) or len(raw_answers) > MAX_ANSWERS:
        raise EntranceSessionError("invalid_answers", 400)

    result: dict[str, str] = {}
    for item in raw_answers:
        if not isinstance(item, dict):
            continue
        try:
            question_id = int(item.get("question_id"))
        except (TypeError, ValueError):
            continue
        if question_id not in valid_question_ids:
            continue
        answer_text = str(item.get("answer_text") or "")
        if len(answer_text) > MAX_ANSWER_CHARS:
            raise EntranceSessionError("answer_too_long", 400)
        result[str(question_id)] = answer_text
    return result


def get_or_create_draft(invitation, now: datetime | None = None):
    now = now or utcnow()
    draft = invitation.draft
    created = False
    if draft is None:
        draft = EntranceTestDraft(
            invitation_id=invitation.id,
            answers_json="{}",
            audio_state_json="{}",
            last_seen_at=now,
        )
        db.session.add(draft)
        db.session.flush()
        created = True
    return draft, created


def _lock(draft: EntranceTestDraft, reason: str, now: datetime) -> None:
    draft.is_locked = True
    draft.locked_reason = reason
    draft.locked_at = now


def _claim_or_validate_device(
    draft: EntranceTestDraft,
    device_id: str,
    now: datetime,
) -> None:
    device_hash = hash_device_id(device_id)
    if not draft.device_hash:
        draft.device_hash = device_hash
        return
    if draft.device_hash != device_hash:
        if not draft.is_locked:
            draft.device_switch_count = (draft.device_switch_count or 0) + 1
            _lock(draft, "device_changed", now)
        raise EntranceSessionError("device_changed", 423)


def _close_hidden_period(draft: EntranceTestDraft, now: datetime) -> int:
    if not draft.hidden_at:
        return 0
    seconds = max(0, int((now - draft.hidden_at).total_seconds()))
    draft.total_hidden_seconds = (draft.total_hidden_seconds or 0) + seconds
    draft.hidden_at = None
    if seconds > RESUME_GRACE_SECONDS:
        _lock(draft, "left_too_long", now)
    return seconds


def _check_existing_gap(draft: EntranceTestDraft, now: datetime) -> None:
    if draft.hidden_at or not draft.last_seen_at:
        return
    seconds = max(0, int((now - draft.last_seen_at).total_seconds()))
    if seconds > RESUME_GRACE_SECONDS:
        draft.exit_count = (draft.exit_count or 0) + 1
        draft.last_exit_at = draft.last_seen_at
        draft.total_hidden_seconds = (draft.total_hidden_seconds or 0) + seconds
        _lock(draft, "session_interrupted", now)


def _raise_if_unavailable(draft: EntranceTestDraft, now: datetime) -> None:
    if draft.is_locked:
        raise EntranceSessionError(draft.locked_reason or "session_locked", 423)
    if draft.deadline_at and now >= draft.deadline_at:
        raise EntranceSessionError("time_expired", 409)


def start_or_resume(invitation, device_id: str, now: datetime | None = None):
    now = now or utcnow()
    draft, created = get_or_create_draft(invitation, now)
    _claim_or_validate_device(draft, device_id, now)

    if not created:
        had_hidden_period = bool(draft.hidden_at)
        _close_hidden_period(draft, now)
        if not had_hidden_period:
            _check_existing_gap(draft, now)

    if created or not draft.deadline_at:
        duration = paper_duration_minutes(invitation.paper)
        draft.deadline_at = now + timedelta(minutes=duration)
        invitation.started_at = now
        invitation.status = "in_progress"

    _raise_if_unavailable(draft, now)
    draft.last_seen_at = now
    return draft


def validate_active_session(
    invitation,
    device_id: str,
    now: datetime | None = None,
) -> EntranceTestDraft:
    now = now or utcnow()
    draft = invitation.draft
    if draft is None:
        raise EntranceSessionError("session_not_started", 409)
    _claim_or_validate_device(draft, device_id, now)
    _raise_if_unavailable(draft, now)
    draft.last_seen_at = now
    return draft


def save_answers(
    invitation,
    device_id: str,
    raw_answers,
    now: datetime | None = None,
) -> EntranceTestDraft:
    now = now or utcnow()
    draft = validate_active_session(invitation, device_id, now)
    valid_question_ids = {
        question.id
        for section in invitation.paper.sections
        for question in section.questions
    }
    draft.answers_json = dump_json_object(
        normalize_answer_map(raw_answers, valid_question_ids)
    )
    draft.last_saved_at = now
    return draft


def mark_hidden(
    invitation,
    device_id: str,
    now: datetime | None = None,
) -> EntranceTestDraft:
    now = now or utcnow()
    draft = validate_active_session(invitation, device_id, now)
    if not draft.hidden_at:
        draft.hidden_at = now
        draft.last_exit_at = now
        draft.exit_count = (draft.exit_count or 0) + 1
    return draft


def mark_visible(
    invitation,
    device_id: str,
    now: datetime | None = None,
) -> EntranceTestDraft:
    now = now or utcnow()
    draft = invitation.draft
    if draft is None:
        raise EntranceSessionError("session_not_started", 409)
    _claim_or_validate_device(draft, device_id, now)
    _close_hidden_period(draft, now)
    _raise_if_unavailable(draft, now)
    draft.last_seen_at = now
    return draft


def mark_heartbeat(
    invitation,
    device_id: str,
    now: datetime | None = None,
) -> EntranceTestDraft:
    return validate_active_session(invitation, device_id, now)


def mark_audio_started(
    invitation,
    device_id: str,
    section_id: int,
    now: datetime | None = None,
):
    now = now or utcnow()
    draft = validate_active_session(invitation, device_id, now)
    valid_section_ids = {
        section.id
        for section in invitation.paper.sections
        if section.section_type == "listening" and section.audio_url
    }
    if section_id not in valid_section_ids:
        raise EntranceSessionError("invalid_audio_section", 404)

    state = load_json_object(draft.audio_state_json)
    key = str(section_id)
    if key in state:
        return draft, False
    state[key] = now.isoformat()
    draft.audio_state_json = dump_json_object(state)
    return draft, True


def unlock_session(
    draft: EntranceTestDraft,
    reviewer_id: int,
    extra_minutes: int = 0,
    reset_device: bool = True,
    now: datetime | None = None,
) -> EntranceTestDraft:
    now = now or utcnow()
    extra_minutes = max(0, min(int(extra_minutes or 0), 120))
    draft.is_locked = False
    draft.locked_reason = None
    draft.locked_at = None
    draft.hidden_at = None
    draft.unlock_count = (draft.unlock_count or 0) + 1
    draft.unlocked_at = now
    draft.unlocked_by = reviewer_id
    draft.last_seen_at = now
    if reset_device:
        draft.device_hash = None
    if extra_minutes:
        base = max(draft.deadline_at or now, now)
        draft.deadline_at = base + timedelta(minutes=extra_minutes)
    return draft


def draft_answer_map(draft: EntranceTestDraft | None) -> dict[int, str]:
    raw = load_json_object(draft.answers_json if draft else None)
    result: dict[int, str] = {}
    for question_id, answer_text in raw.items():
        try:
            result[int(question_id)] = str(answer_text or "")
        except (TypeError, ValueError):
            continue
    return result


def serialize_draft(draft: EntranceTestDraft, now: datetime | None = None) -> dict:
    now = now or utcnow()
    remaining = None
    if draft.deadline_at:
        remaining = max(0, math.ceil((draft.deadline_at - now).total_seconds()))
    return {
        "answers": load_json_object(draft.answers_json),
        "audio_state": load_json_object(draft.audio_state_json),
        "deadline_at": draft.deadline_at.isoformat() if draft.deadline_at else None,
        "remaining_seconds": remaining,
        "last_saved_at": draft.last_saved_at.isoformat() if draft.last_saved_at else None,
        "last_seen_at": draft.last_seen_at.isoformat() if draft.last_seen_at else None,
        "exit_count": draft.exit_count or 0,
        "total_hidden_seconds": draft.total_hidden_seconds or 0,
        "device_switch_count": draft.device_switch_count or 0,
        "is_locked": bool(draft.is_locked),
        "locked_reason": draft.locked_reason,
        "unlock_count": draft.unlock_count or 0,
    }
