"""Independent four-dimension vocabulary review sessions.

Teacher vocabulary tasks and autonomous review deliberately use different
tables and settlement code.  A review session can therefore be claimed from
the home page, resumed on another device, or used as a task preflight without
changing the teacher task's score, denominator, or completion state.
"""

from __future__ import annotations

import json
import re
import secrets
from datetime import datetime, time, timedelta, timezone
from functools import lru_cache

from sqlalchemy.exc import IntegrityError, OperationalError

from dictation_answers import (
    canonical_vocabulary_word,
    is_chinese_answer_correct,
    is_english_answer_correct,
)
from models import (
    DictationWord,
    StudentVocabularyMastery,
    Task,
    User,
    VocabularyLearningFlow,
    VocabularyReviewAttempt,
    VocabularyReviewItem,
    VocabularyReviewSession,
    VocabularyReviewSettlement,
    db,
)
from services.dictation_input_policy import resolve_submission_input
from services.dictation_review import SHANGHAI, local_date
from services.vocabulary_context import grade_context_answer
from services.vocabulary_mastery import (
    DIMENSIONS,
    MAX_ENGLISH_ANSWER_LENGTH,
    REVIEW_INTERVALS_DAYS,
    _apply_dimension_answer,
    _dimension_due,
    _dimension_stage,
    _mastery_for,
    _question_for,
    _safe_json,
    build_meaning_recall_options,
    ensure_mastery,
    is_vocabulary_v2_task,
    utc_naive,
)
from services.vocabulary_remediation import (
    MAX_CORRECTION_ATTEMPTS,
    MAX_REMEDIATION_PER_WORD,
    correction_state,
    dimension_priority,
    related_dimension_for,
    remediation_kind_for_dimension,
    remediation_priority,
)

MAX_REVIEW_BATCH = 20
SESSION_TOKEN_MAX_LENGTH = 96
SAFE_ENGLISH_SEPARATORS = [" ", "-", "'"]
_FEEDBACK_HYPHENATOR = None


def _correction_required(item: VocabularyReviewItem) -> bool:
    """A wrong formal answer must be corrected before the session can settle."""

    return bool(
        item.first_attempt_id
        and item.first_is_correct is False
        and item.correction_is_correct is not True
        and not item.correction_exhausted
    )


def _candidate_remediation_kind(
    user: User,
    mastery: StudentVocabularyMastery,
    dimension: str,
    now: datetime,
) -> str | None:
    """Classify a due item without creating a second queue.

    A wrong item is re-exposed in the next due cycle as a same-dimension
    remediation. A marker on mastery identifies the single related dimension
    released after that delayed retry; the marker is cleared once answered.
    """

    related_due = getattr(mastery, "review_related_due_at", None)
    if (
        getattr(mastery, "review_related_dimension", None) == dimension
        and related_due is not None
        and related_due <= now
    ):
        return remediation_kind_for_dimension(is_retry=False, is_related=True)
    latest = (
        VocabularyReviewItem.query.filter_by(
            student_id=user.id,
            sense_id=mastery.sense_id,
            dimension=dimension,
        )
        .order_by(VocabularyReviewItem.id.desc())
        .first()
    )
    if latest and latest.first_is_correct is False and not _correction_required(latest):
        return remediation_kind_for_dimension(is_retry=True)
    return None


class VocabularyAutonomousReviewError(Exception):
    """Safe API error for the independent review flow."""

    def __init__(self, error: str, status_code: int = 400, **details):
        super().__init__(error)
        self.error = error
        self.status_code = status_code
        self.details = details


def _goal_for_dimension(
    dimension: str,
    mastery: StudentVocabularyMastery | None = None,
    word: DictationWord | None = None,
) -> str:
    if dimension == "audio_form_recall":
        return "listening"
    if dimension == "form_recall":
        return "writing"
    if dimension == "context_use":
        return "comprehensive"
    # ``meaning_recall`` uses sound as its cue for listening books and the
    # written form elsewhere. The dimension alone cannot express that cue, so
    # retain the curriculum goal from the mastery row's representative book.
    book = mastery.representative_book if mastery else None
    if book is None and word is not None:
        book = word.book
    if str(getattr(book, "default_vocabulary_goal", "") or "").strip().lower() == "listening":
        return "listening"
    return "reading"


def _word_for_mastery(mastery: StudentVocabularyMastery) -> DictationWord | None:
    if mastery.representative_word:
        return mastery.representative_word
    sense = mastery.sense
    if not sense:
        return None
    return sense.words.order_by(DictationWord.book_id.asc(), DictationWord.sequence.asc()).first()


def _candidate_words(word: DictationWord, cache: dict[int, list[DictationWord]]):
    if word.book_id not in cache:
        cache[word.book_id] = (
            DictationWord.query.filter_by(book_id=word.book_id)
            .order_by(DictationWord.id.asc())
            .all()
        )
        # A migrated word can have no sense link yet.  Question generation is
        # still allowed to use the catalog, but never invents a distractor.
        for candidate in cache[word.book_id]:
            if candidate.sense_id is None:
                continue
    return cache[word.book_id]


def _answered_senses_on_local_date(user: User, now: datetime) -> set[int]:
    """Return senses with a formal autonomous answer on the local day.

    The answer-attempt table is the durable source for this cooldown, so it
    also works for old sessions and for a request that resumes after a crash.
    Corrections are deliberately excluded: they are not formal questions, but
    the first formal attempt still cools the whole sense for the day.
    """

    review_date = local_date(now)
    day_start = datetime.combine(review_date, time.min, tzinfo=SHANGHAI)
    day_end = datetime.combine(review_date + timedelta(days=1), time.min, tzinfo=SHANGHAI)
    start_utc = day_start.astimezone(timezone.utc).replace(tzinfo=None)  # noqa: UP017
    end_utc = day_end.astimezone(timezone.utc).replace(tzinfo=None)  # noqa: UP017
    rows = (
        db.session.query(
            VocabularyReviewItem.sense_id,
        )
        .join(
            VocabularyReviewAttempt,
            VocabularyReviewAttempt.item_id == VocabularyReviewItem.id,
        )
        .filter(
            VocabularyReviewItem.student_id == user.id,
            VocabularyReviewAttempt.student_id == user.id,
            VocabularyReviewAttempt.is_first_attempt.is_(True),
            VocabularyReviewAttempt.submitted_at >= start_utc,
            VocabularyReviewAttempt.submitted_at < end_utc,
        )
        .all()
    )
    return {int(sense_id) for (sense_id,) in rows if sense_id is not None}


def _due_candidates(user: User, now: datetime | None = None) -> list[dict]:
    """Return at most one qualified due dimension per sense.

    Several dimension timestamps can legitimately be due together after a
    comprehensive first exposure. They are a backlog, not four questions to
    freeze into one batch. Select one dimension per sense using the shared
    remediation priority, then untested-stage priority, due time, last-answer
    age, and the stable dimension order. A formal answer cools the whole sense
    until the next local date, so ``continue`` cannot immediately reopen the
    other dimensions of the same word.
    """

    now = utc_naive(now)
    rows = (
        StudentVocabularyMastery.query.filter_by(student_id=user.id)
        .order_by(StudentVocabularyMastery.sense_id.asc())
        .all()
    )
    candidate_cache: dict[int, list[DictationWord]] = {}
    candidates_by_sense: dict[int, list[dict]] = {}
    cooled_senses = _answered_senses_on_local_date(user, now)
    planned_remediation_counts: dict[int, int] = {}
    for mastery in rows:
        word = _word_for_mastery(mastery)
        if not word:
            continue
        if word.sense_id is None:
            # Existing mastery rows should point to a sense.  Avoid writing or
            # guessing during a read-only count if a hand-created row does not.
            continue
        if mastery.sense_id in cooled_senses:
            continue
        for dimension in DIMENSIONS:
            due_at = _dimension_due(mastery, dimension)
            if not due_at or due_at > now:
                continue
            question = _question_for(
                word,
                dimension,
                _goal_for_dimension(dimension, mastery, word),
                _dimension_stage(mastery, dimension),
                _candidate_words(word, candidate_cache),
            )
            if not question:
                continue
            public, answer = question
            remediation_kind = _candidate_remediation_kind(
                user,
                mastery,
                dimension,
                now,
            )
            existing_remediation_count = (
                int(getattr(mastery, "review_remediation_count", 0) or 0)
                if getattr(mastery, "review_remediation_date", None) == local_date(now)
                else 0
            )
            if (
                remediation_kind
                and existing_remediation_count >= MAX_REMEDIATION_PER_WORD
            ):
                # Keep the bounded budget explicit. The existing due timestamp
                # remains intact; the next claim after the date boundary can
                # pick it up instead of spinning on the same word today.
                continue
            overdue_seconds = max(0, int((now - due_at).total_seconds()))
            stage = _dimension_stage(mastery, dimension)
            last_answered_at = getattr(
                mastery,
                f"{dimension}_last_answered_at",
                None,
            )
            candidates_by_sense.setdefault(mastery.sense_id, []).append(
                {
                    "word": word,
                    "mastery": mastery,
                    "dimension": dimension,
                    "due_at": due_at,
                    "stage": stage,
                    "public": public,
                    "answer": answer,
                    "remediation_kind": remediation_kind,
                    "overdue_seconds": overdue_seconds,
                    "last_answered_at": last_answered_at,
                    # Stage 0 also represents a newly unlocked dimension. A
                    # real wrong answer is distinguishable because it records
                    # ``last_answered_at`` before resetting the stage.
                    "error_priority": 1 if stage == 0 and last_answered_at else 0,
                    "untested_priority": int(stage == 0 and not last_answered_at),
                    "remediation_priority": remediation_priority(remediation_kind),
                    "dimension_priority": dimension_priority(dimension),
                }
            )

    result = []
    for sense_id, options in candidates_by_sense.items():
        options.sort(
            key=lambda item: (
                -item["remediation_priority"],
                -item["error_priority"],
                -item["untested_priority"],
                item["due_at"],
                item["last_answered_at"] or datetime.min,
                item["dimension_priority"],
            )
        )
        selected = None
        for candidate in options:
            if candidate["remediation_kind"]:
                if (
                    planned_remediation_counts.get(sense_id, 0)
                    >= MAX_REMEDIATION_PER_WORD
                ):
                    continue
                planned_remediation_counts[sense_id] = (
                    planned_remediation_counts.get(sense_id, 0) + 1
                )
            selected = candidate
            break
        if selected is not None:
            result.append(selected)
    result.sort(
        key=lambda item: (
            -item["remediation_priority"],
            -item["error_priority"],
            -item["untested_priority"],
            item["due_at"],
            item["last_answered_at"] or datetime.min,
            item["word"].book_id,
            item["word"].sequence,
            item["word"].id,
            item["dimension_priority"],
        )
    )
    return result


def _due_count(user: User, now: datetime | None = None) -> int:
    return len(_due_candidates(user, now))


def _session_due_counts(
    user: User,
    session: VocabularyReviewSession,
    now: datetime,
) -> tuple[int, int]:
    """Return actionable count and due debt outside the frozen session."""

    candidates = _due_candidates(user, now)
    session_senses = {item.sense_id for item in session.items}
    outside_due = sum(
        candidate["mastery"].sense_id not in session_senses
        for candidate in candidates
    )
    unanswered = sum(
        item.first_attempt_id is None or _correction_required(item)
        for item in session.items
    )
    return unanswered + outside_due, outside_due


def _session_for_user(
    user: User,
    session_id: int,
    session_token: str | None = None,
    *,
    lock: bool = False,
    require_token: bool = False,
) -> VocabularyReviewSession:
    if require_token and not session_token:
        raise VocabularyAutonomousReviewError("review_session_token_required", 400)
    query = VocabularyReviewSession.query.filter_by(id=session_id, student_id=user.id)
    if lock:
        query = query.with_for_update()
    session = query.first()
    if not session:
        raise VocabularyAutonomousReviewError("review_session_not_found", 404)
    if session_token and session.session_token != session_token:
        raise VocabularyAutonomousReviewError("review_session_token_invalid", 404)
    return session


def _validate_origin_task(user: User, task_id) -> Task | None:
    if task_id in (None, ""):
        return None
    try:
        task = Task.query.filter_by(id=int(task_id)).first()
    except (TypeError, ValueError) as error:
        raise VocabularyAutonomousReviewError("invalid_origin_task", 400) from error
    if not task:
        raise VocabularyAutonomousReviewError("task_not_found", 404)
    profile = getattr(user, "student_profile", None)
    if not profile or task.student_name != profile.full_name:
        raise VocabularyAutonomousReviewError("forbidden", 403)
    if not is_vocabulary_v2_task(task):
        raise VocabularyAutonomousReviewError("task_not_vocabulary_v2", 409)
    return task


@lru_cache(maxsize=8192)
def _feedback_syllables(value: str) -> str:
    """Return a display-only syllable hint without importing an API module."""

    text = str(value or "").strip()
    if not text:
        return ""

    global _FEEDBACK_HYPHENATOR
    if _FEEDBACK_HYPHENATOR is None:
        try:
            import pyphen

            _FEEDBACK_HYPHENATOR = pyphen.Pyphen(lang="en_US")
        except Exception:
            _FEEDBACK_HYPHENATOR = False
    if not _FEEDBACK_HYPHENATOR:
        return text

    def replace(match):
        token = match.group(0)
        parts = [part for part in _FEEDBACK_HYPHENATOR.inserted(token).split("-") if part]
        return "·".join(parts) if len(parts) > 1 else token

    return re.sub(r"[A-Za-z]+", replace, text)


def _answer_feedback(item: VocabularyReviewItem) -> dict:
    """Build the approved memory aid that is safe only after first answer."""

    word = item.word or db.session.get(DictationWord, item.word_id)
    if word is None:
        return {
            "word": "",
            "syllables": "",
            "phonetic": None,
            "core_meaning_zh": None,
            "usage_pattern": None,
            "example_en": None,
            "example_zh": None,
            "usage_note": None,
            "audio_tts_url": None,
        }
    canonical = canonical_vocabulary_word(word.word, word.accepted_answers)
    return {
        "word": canonical,
        "syllables": _feedback_syllables(canonical),
        "phonetic": word.phonetic,
        "core_meaning_zh": word.core_meaning_zh or word.translation,
        "usage_pattern": word.usage_pattern,
        "example_en": word.example_en,
        "example_zh": word.example_zh,
        "usage_note": word.usage_note,
        "audio_tts_url": f"/dictation/words/{word.id}/tts",
    }


def _public_item(item: VocabularyReviewItem, candidate_cache=None) -> dict:
    snapshot = _safe_json(item.question_snapshot_json)
    answer_payload = _safe_json(item.answer_payload_json)
    if snapshot.get("mode") == "audio_to_zh" and not snapshot.get("options"):
        word = db.session.get(DictationWord, item.word_id)
        if word:
            candidates = _candidate_words(word, candidate_cache if candidate_cache is not None else {})
            snapshot = dict(snapshot)
            snapshot["options"] = build_meaning_recall_options(
                word,
                candidates,
                f"review-item:{item.id}:{item.question_id}",
            )
    english_mode = snapshot.get("mode") in {"audio_to_en", "zh_to_en", "context_fill"}
    payload = {
        "review_item_id": item.id,
        "queue_item_id": item.id,
        "word_id": item.word_id,
        "book_id": item.book_id,
        "sense_id": item.sense_id,
        "dimension": item.dimension,
        "question_id": item.question_id,
        "question": snapshot,
        "mode": snapshot.get("mode"),
        "due_at": item.due_at.isoformat() if item.due_at else None,
        "stage": item.stage_at_claim,
        "answered": item.first_attempt_id is not None,
        "first_attempt_id": item.first_attempt_id,
        "first_is_correct": item.first_is_correct,
        "first_answer": item.first_answer,
        "correction_required": _correction_required(item),
        "correction_attempt_id": item.correction_attempt_id,
        "correction_is_correct": item.correction_is_correct,
        "correction_answer": item.correction_answer,
        "correction_count": int(item.correction_count or 0),
        "correction_max_attempts": MAX_CORRECTION_ATTEMPTS,
        "correction_retry_allowed": _correction_required(item)
        and int(item.correction_count or 0) < MAX_CORRECTION_ATTEMPTS,
        "correction_exhausted": bool(item.correction_exhausted),
        "remediation_kind": item.remediation_kind,
        "deferred_to_review": bool(item.deferred_to_review),
        # These are only input capabilities.  The answer and its shape remain
        # server-side until this item has been answered.
        "answer_length": MAX_ENGLISH_ANSWER_LENGTH if english_mode else 0,
        "answer_separators": SAFE_ENGLISH_SEPARATORS if english_mode else [],
    }
    if item.first_attempt_id:
        revealed_answer = answer_payload.get("answer")
        revealed_option_id = None
        if answer_payload.get("answer_type") == "option_id":
            revealed_option_id = answer_payload.get("answer_option_id")
            option = next(
                (
                    candidate
                    for candidate in snapshot.get("options") or []
                    if str(candidate.get("id")) == str(revealed_option_id)
                ),
                None,
            )
            revealed_answer = option.get("label") if option else None
        payload["revealed_answer"] = revealed_answer
        payload["revealed_answer_option_id"] = revealed_option_id
        payload["answer_feedback"] = _answer_feedback(item)
    return payload


def _session_payload(user: User, session: VocabularyReviewSession, now=None) -> dict:
    now = utc_naive(now)
    candidate_cache = {}
    items = [_public_item(item, candidate_cache) for item in session.items]
    due_count, remaining_due_count = _session_due_counts(user, session, now)
    answered_count = sum(
        item["answered"] and not item["correction_required"] for item in items
    )
    return {
        "ok": True,
        "session_id": session.id,
        "session_token": session.session_token,
        "status": session.status,
        "review_date": session.review_date.isoformat(),
        "origin_task_id": session.origin_task_id,
        "batch_limit": session.batch_limit,
        "total_count": len(items),
        "answered_count": answered_count,
        "remaining_count": max(0, len(items) - answered_count),
        "due_count": due_count,
        "remaining_due_count": remaining_due_count,
        # ``words`` keeps the response compatible with the existing miniprogram
        # queue renderer while the session fields make its ownership explicit.
        "items": items,
        "words": items,
        "queue_token": session.queue_token,
    }


def claim_today_review(
    user: User,
    *,
    origin_task_id=None,
    now: datetime | None = None,
) -> dict:
    """Restore one active session or claim the next finite due batch."""

    now = utc_naive(now)
    origin_task = _validate_origin_task(user, origin_task_id)
    active = (
        VocabularyReviewSession.query.filter_by(
            student_id=user.id,
            status=VocabularyReviewSession.STATUS_ACTIVE,
        )
        .order_by(VocabularyReviewSession.started_at.desc(), VocabularyReviewSession.id.desc())
        .first()
    )
    if active:
        if origin_task and active.origin_task_id is None:
            active.origin_task_id = origin_task.id
        return _session_payload(user, active, now)

    candidates = _due_candidates(user, now)
    if not candidates:
        return {
            "ok": True,
            "empty": True,
            "status": "empty",
            "session_id": None,
            "origin_task_id": origin_task.id if origin_task else None,
            "total_count": 0,
            "due_count": 0,
            "remaining_due_count": 0,
            "items": [],
            "words": [],
        }

    # The mandatory batch size is a server policy. Accepting a client-provided
    # lower limit would let a modified client answer one item and obtain the
    # whole day's task clearance.
    batch_limit = MAX_REVIEW_BATCH
    review_date = local_date(now)
    claim_key = f"vocabulary-review:{user.id}:{review_date.isoformat()}"
    session = VocabularyReviewSession(
        student_id=user.id,
        origin_task_id=origin_task.id if origin_task else None,
        review_date=review_date,
        status=VocabularyReviewSession.STATUS_ACTIVE,
        claim_key=claim_key,
        session_token=secrets.token_urlsafe(32)[:SESSION_TOKEN_MAX_LENGTH],
        queue_token=secrets.token_urlsafe(32)[:SESSION_TOKEN_MAX_LENGTH],
        batch_limit=batch_limit,
        started_at=now,
    )
    try:
        # The unique active claim key is the database-level race guard.  A
        # nested transaction preserves an outer request transaction so the
        # winner's session can be returned after a concurrent loser retries.
        with db.session.begin_nested():
            db.session.add(session)
            db.session.flush()
    except OperationalError:
        raise VocabularyAutonomousReviewError("review_claim_in_progress", 409) from None
    except IntegrityError:
        active = (
            VocabularyReviewSession.query.filter_by(
                student_id=user.id,
                status=VocabularyReviewSession.STATUS_ACTIVE,
            )
            .order_by(VocabularyReviewSession.started_at.desc(), VocabularyReviewSession.id.desc())
            .first()
        )
        if active:
            return _session_payload(user, active, now)
        raise VocabularyAutonomousReviewError("review_claim_conflict", 409) from None

    for index, candidate in enumerate(candidates[:batch_limit]):
        word = candidate["word"]
        item = VocabularyReviewItem(
            session_id=session.id,
            student_id=user.id,
            book_id=word.book_id,
            word_id=word.id,
            sense_id=candidate["mastery"].sense_id,
            dimension=candidate["dimension"],
            due_at=candidate["due_at"],
            stage_at_claim=candidate["stage"],
            queue_index=index,
            remediation_kind=candidate.get("remediation_kind"),
            question_id=candidate["public"]["question_id"],
            question_snapshot_json=json.dumps(
                candidate["public"], ensure_ascii=False, sort_keys=True
            ),
            answer_payload_json=json.dumps(
                candidate["answer"], ensure_ascii=False, sort_keys=True
            ),
        )
        db.session.add(item)
    db.session.flush()
    return _session_payload(user, session, now)


def get_review_session(user: User, session_id: int, session_token: str | None = None) -> dict:
    session = _session_for_user(user, session_id, session_token, require_token=True)
    return _session_payload(user, session)


def _answer_result(item, attempt, *, idempotent=False, settled=False):
    snapshot = _safe_json(item.question_snapshot_json)
    answer_payload = _safe_json(item.answer_payload_json)
    revealed_answer = answer_payload.get("answer")
    revealed_option_id = None
    if answer_payload.get("answer_type") == "option_id":
        revealed_option_id = answer_payload.get("answer_option_id")
        option = next(
            (
                candidate
                for candidate in snapshot.get("options") or []
                if str(candidate.get("id")) == str(revealed_option_id)
            ),
            None,
        )
        revealed_answer = option.get("label") if option else None
    return {
        "ok": True,
        "independent_review": True,
        "is_correct": bool(attempt.is_correct),
        "first_attempt": bool(attempt.is_first_attempt),
        "idempotent": bool(idempotent),
        "settled": bool(settled),
        "attempt_id": attempt.attempt_id,
        "review_item_id": item.id,
        "queue_item_id": item.id,
        "word_id": item.word_id,
        "question_id": item.question_id,
        "dimension": item.dimension,
        "student_answer": attempt.student_answer,
        "attempt_kind": attempt.attempt_kind,
        "correction_required": _correction_required(item),
        "correction_count": int(item.correction_count or 0),
        "correction_max_attempts": MAX_CORRECTION_ATTEMPTS,
        "correction_retry_allowed": _correction_required(item)
        and int(item.correction_count or 0) < MAX_CORRECTION_ATTEMPTS,
        "correction_exhausted": bool(item.correction_exhausted),
        "revealed_answer": revealed_answer,
        "revealed_answer_option_id": revealed_option_id,
        "answer_feedback": _answer_feedback(item),
    }


def _apply_review_item_state(
    user: User,
    item: VocabularyReviewItem,
    is_correct: bool,
    answered_at: datetime,
) -> None:
    """Apply one durable first answer exactly once at answer time."""

    if item.state_applied:
        return
    mastery = _mastery_for(user.id, item.sense_id)
    if mastery is None:
        mastery = ensure_mastery(user, item.word, item.sense)
    if item.remediation_kind:
        answer_date = local_date(utc_naive(answered_at))
        if getattr(mastery, "review_remediation_date", None) != answer_date:
            mastery.review_remediation_date = answer_date
            mastery.review_remediation_count = 0
        mastery.review_remediation_count = min(
            MAX_REMEDIATION_PER_WORD,
            int(getattr(mastery, "review_remediation_count", 0) or 0) + 1,
        )
    if getattr(mastery, "review_related_dimension", None) == item.dimension:
        mastery.review_related_dimension = None
        mastery.review_related_due_at = None
    _apply_dimension_answer(
        mastery,
        item.dimension,
        bool(is_correct),
        utc_naive(answered_at),
        bootstrap_dimensions=(),
    )
    item.state_applied = True


def _schedule_related_dimension(
    mastery: StudentVocabularyMastery,
    dimension: str,
    now: datetime,
) -> str | None:
    """Release one related dimension at the normal first review interval."""

    related = related_dimension_for(dimension)
    if not related:
        return None
    due_attr = f"{related}_next_due_at"
    due = now + timedelta(days=REVIEW_INTERVALS_DAYS[0])
    current_due = getattr(mastery, due_attr, None)
    # Pulling an already-later due date forward is allowed for a diagnostic,
    # but the stage and every other dimension remain untouched. Never replace
    # an already-earlier due date.
    if current_due is None or current_due > due:
        setattr(mastery, due_attr, due)
    mastery.review_related_dimension = related
    mastery.review_related_due_at = getattr(mastery, due_attr, due)
    return related


def _restore_first_attempt_state(
    user: User,
    item: VocabularyReviewItem,
    attempt: VocabularyReviewAttempt,
) -> None:
    """Repair an interrupted/idempotent path without grading a second answer."""

    if not item.first_attempt_id:
        item.first_attempt_id = attempt.attempt_id
        item.first_is_correct = bool(attempt.is_correct)
        item.first_answer = attempt.student_answer[:100]
    _apply_review_item_state(
        user,
        item,
        bool(attempt.is_correct),
        attempt.submitted_at,
    )


def submit_review_answer(
    user: User,
    session_id: int,
    payload: dict,
    *,
    session_token: str | None = None,
    now: datetime | None = None,
) -> dict:
    now = utc_naive(now)
    session_token = session_token or str(payload.get("session_token") or "").strip() or None
    session = _session_for_user(
        user,
        session_id,
        session_token,
        lock=True,
        require_token=True,
    )
    try:
        item_id = int(payload.get("review_item_id") or payload.get("queue_item_id"))
    except (TypeError, ValueError) as error:
        raise VocabularyAutonomousReviewError("invalid_review_item_id", 400) from error
    item = (
        VocabularyReviewItem.query.filter_by(
            id=item_id,
            session_id=session.id,
            student_id=user.id,
        )
        .with_for_update()
        .first()
    )
    if not item:
        raise VocabularyAutonomousReviewError("review_item_not_in_session", 409)
    supplied_question_id = str(payload.get("question_id") or "").strip()
    supplied_word_id = payload.get("word_id")
    supplied_sense_id = payload.get("sense_id")
    supplied_dimension = str(payload.get("dimension") or "").strip().lower()
    if (
        supplied_question_id != item.question_id
        or str(supplied_word_id) != str(item.word_id)
        or str(supplied_sense_id) != str(item.sense_id)
        or supplied_dimension != item.dimension
    ):
        raise VocabularyAutonomousReviewError("review_question_changed", 409)
    raw_attempt_id = str(payload.get("attempt_id") or "").strip()
    if len(raw_attempt_id) > SESSION_TOKEN_MAX_LENGTH:
        raise VocabularyAutonomousReviewError(
            "attempt_id_too_long", 400, max_length=SESSION_TOKEN_MAX_LENGTH
        )
    attempt_id = raw_attempt_id or f"vocabulary-review:{session.id}:{item.id}"

    existing_attempt = VocabularyReviewAttempt.query.filter_by(
        student_id=user.id,
        attempt_id=attempt_id,
    ).first()
    if existing_attempt:
        if existing_attempt.item_id != item.id:
            raise VocabularyAutonomousReviewError("attempt_id_conflict", 409)
        _restore_first_attempt_state(user, item, existing_attempt)
        return _answer_result(item, existing_attempt, idempotent=True)
    if item.first_attempt_id:
        first_attempt = (
            VocabularyReviewAttempt.query.filter_by(
                item_id=item.id,
                is_first_attempt=True,
            )
            .order_by(VocabularyReviewAttempt.id.asc())
            .first()
        )
        if first_attempt:
            # A second tab may submit a stale local answer after the first tab
            # won.  Return the durable first result instead of grading twice.
            _restore_first_attempt_state(user, item, first_attempt)
            return _answer_result(item, first_attempt, idempotent=True)
        raise VocabularyAutonomousReviewError("review_item_already_answered", 409)
    answer = str(payload.get("answer") or "").strip()
    if not answer or len(answer) > 200:
        raise VocabularyAutonomousReviewError("missing_answer", 400)

    snapshot = _safe_json(item.question_snapshot_json)
    try:
        input_mode, input_grant_id = resolve_submission_input(
            user,
            snapshot.get("mode") or "en_to_zh",
            payload.get("input_mode"),
            task_id=session.origin_task_id,
            now=now,
        )
    except ValueError as error:
        raise VocabularyAutonomousReviewError("invalid_input_mode", 400) from error
    expected = _safe_json(item.answer_payload_json)
    if item.dimension == "context_use":
        is_correct = grade_context_answer(snapshot, expected, answer)
    elif expected.get("answer_type") == "chinese":
        is_correct = is_chinese_answer_correct(answer, expected.get("answer") or "")
    else:
        is_correct = is_english_answer_correct(
            answer,
            expected.get("answer") or "",
            accepted_answers=expected.get("accepted_answers") or [],
        )
    attempt = VocabularyReviewAttempt(
        session_id=session.id,
        item_id=item.id,
        student_id=user.id,
        attempt_id=attempt_id,
        question_id=item.question_id,
        student_answer=answer[:100],
        is_correct=is_correct,
        is_first_attempt=True,
        attempt_kind="first",
        input_mode=input_mode,
        input_grant_id=input_grant_id,
        submitted_at=now,
    )
    try:
        with db.session.begin_nested():
            db.session.add(attempt)
            db.session.flush()
    except OperationalError:
        raise VocabularyAutonomousReviewError("review_answer_in_progress", 409) from None
    except IntegrityError:
        duplicate = VocabularyReviewAttempt.query.filter_by(
            student_id=user.id,
            attempt_id=attempt_id,
        ).first()
        if duplicate and duplicate.item_id == item.id:
            _restore_first_attempt_state(user, item, duplicate)
            return _answer_result(item, duplicate, idempotent=True)
        first_attempt = (
            VocabularyReviewAttempt.query.filter_by(
                item_id=item.id,
                is_first_attempt=True,
            )
            .order_by(VocabularyReviewAttempt.id.asc())
            .first()
        )
        if first_attempt:
            _restore_first_attempt_state(user, item, first_attempt)
            return _answer_result(item, first_attempt, idempotent=True)
        raise VocabularyAutonomousReviewError("attempt_id_conflict", 409) from None

    item.first_attempt_id = attempt_id
    item.first_is_correct = is_correct
    item.first_answer = answer[:100]
    _apply_review_item_state(user, item, is_correct, now)
    return _answer_result(item, attempt)


def submit_review_correction(
    user: User,
    session_id: int,
    payload: dict,
    *,
    session_token: str | None = None,
    now: datetime | None = None,
) -> dict:
    """Record a bounded, non-formal correction for a wrong review answer."""

    now = utc_naive(now)
    session_token = session_token or str(payload.get("session_token") or "").strip() or None
    session = _session_for_user(
        user,
        session_id,
        session_token,
        lock=True,
        require_token=True,
    )
    try:
        item_id = int(payload.get("review_item_id") or payload.get("queue_item_id"))
    except (TypeError, ValueError) as error:
        raise VocabularyAutonomousReviewError("invalid_review_item_id", 400) from error
    item = (
        VocabularyReviewItem.query.filter_by(
            id=item_id,
            session_id=session.id,
            student_id=user.id,
        )
        .with_for_update()
        .first()
    )
    if not item:
        raise VocabularyAutonomousReviewError("review_item_not_in_session", 409)
    supplied_identity = (
        str(payload.get("question_id") or "").strip(),
        str(payload.get("word_id") or ""),
        str(payload.get("sense_id") or ""),
        str(payload.get("dimension") or "").strip().lower(),
    )
    expected_identity = (
        item.question_id,
        str(item.word_id),
        str(item.sense_id),
        item.dimension,
    )
    if supplied_identity != expected_identity:
        raise VocabularyAutonomousReviewError("review_question_changed", 409)
    attempt_id = str(payload.get("attempt_id") or "").strip()
    if not attempt_id:
        raise VocabularyAutonomousReviewError("attempt_id_required", 400)
    if len(attempt_id) > SESSION_TOKEN_MAX_LENGTH:
        raise VocabularyAutonomousReviewError(
            "attempt_id_too_long", 400, max_length=SESSION_TOKEN_MAX_LENGTH
        )
    existing = VocabularyReviewAttempt.query.filter_by(
        student_id=user.id,
        attempt_id=attempt_id,
    ).first()
    if existing:
        if existing.item_id != item.id or existing.attempt_kind != "correction":
            raise VocabularyAutonomousReviewError("attempt_id_conflict", 409)
        return _correction_result(item, existing, idempotent=True)
    if not _correction_required(item):
        raise VocabularyAutonomousReviewError("correction_not_required", 409)
    answer = str(payload.get("answer") or "").strip()
    if not answer or len(answer) > 200:
        raise VocabularyAutonomousReviewError("missing_answer", 400)

    snapshot = _safe_json(item.question_snapshot_json)
    try:
        input_mode, input_grant_id = resolve_submission_input(
            user,
            snapshot.get("mode") or "en_to_zh",
            payload.get("input_mode"),
            task_id=session.origin_task_id,
            now=now,
        )
    except ValueError as error:
        raise VocabularyAutonomousReviewError("invalid_input_mode", 400) from error
    expected = _safe_json(item.answer_payload_json)
    if item.dimension == "context_use":
        is_correct = grade_context_answer(snapshot, expected, answer)
    elif expected.get("answer_type") == "chinese":
        is_correct = is_chinese_answer_correct(answer, expected.get("answer") or "")
    else:
        is_correct = is_english_answer_correct(
            answer,
            expected.get("answer") or "",
            accepted_answers=expected.get("accepted_answers") or [],
        )
    attempt = VocabularyReviewAttempt(
        session_id=session.id,
        item_id=item.id,
        student_id=user.id,
        attempt_id=attempt_id,
        question_id=item.question_id,
        student_answer=answer[:100],
        is_correct=is_correct,
        is_first_attempt=False,
        attempt_kind="correction",
        input_mode=input_mode,
        input_grant_id=input_grant_id,
        submitted_at=now,
    )
    try:
        with db.session.begin_nested():
            db.session.add(attempt)
            db.session.flush()
    except OperationalError:
        raise VocabularyAutonomousReviewError("review_correction_in_progress", 409) from None
    except IntegrityError:
        duplicate = VocabularyReviewAttempt.query.filter_by(
            student_id=user.id,
            attempt_id=attempt_id,
        ).first()
        if duplicate and duplicate.item_id == item.id and duplicate.attempt_kind == "correction":
            return _correction_result(item, duplicate, idempotent=True)
        raise VocabularyAutonomousReviewError("attempt_id_conflict", 409) from None

    state = correction_state(item.correction_count, is_correct)
    item.correction_attempt_id = attempt_id
    item.correction_is_correct = is_correct
    item.correction_answer = answer[:100]
    item.correction_count = state["count"]
    item.correction_exhausted = state["exhausted"]
    if state["exhausted"]:
        item.deferred_to_review = True
    if state["completed"] and item.remediation_kind == "same_dimension":
        mastery = _mastery_for(user.id, item.sense_id)
        if mastery is None:
            mastery = ensure_mastery(user, item.word, item.sense)
        if item.first_is_correct is False:
            _schedule_related_dimension(mastery, item.dimension, now)
    return _correction_result(item, attempt)


def _correction_result(
    item: VocabularyReviewItem,
    attempt: VocabularyReviewAttempt,
    *,
    idempotent: bool = False,
) -> dict:
    result = _answer_result(item, attempt, idempotent=idempotent)
    result.update(
        {
            "correction_completed": bool(item.correction_is_correct) or bool(item.correction_exhausted),
            "correction_required": _correction_required(item),
            "correction_is_correct": item.correction_is_correct,
            "correction_answer": item.correction_answer,
            "correction_attempt_id": item.correction_attempt_id,
            "correction_count": int(item.correction_count or 0),
            "correction_max_attempts": MAX_CORRECTION_ATTEMPTS,
            "correction_retry_allowed": _correction_required(item)
            and int(item.correction_count or 0) < MAX_CORRECTION_ATTEMPTS,
            "correction_exhausted": bool(item.correction_exhausted),
            "deferred_to_review": bool(item.deferred_to_review),
        }
    )
    return result


def _settlement_result(session: VocabularyReviewSession) -> dict | None:
    if not session.result_json:
        return None
    return _safe_json(session.result_json)


def settle_review_session(
    user: User,
    session_id: int,
    payload: dict | None = None,
    *,
    session_token: str | None = None,
    now: datetime | None = None,
) -> dict:
    now = utc_naive(now)
    payload = payload or {}
    session_token = session_token or str(payload.get("session_token") or "").strip() or None
    session = _session_for_user(
        user,
        session_id,
        session_token,
        lock=True,
        require_token=True,
    )
    existing = _settlement_result(session)
    if existing:
        return existing
    if session.status != VocabularyReviewSession.STATUS_ACTIVE:
        raise VocabularyAutonomousReviewError("review_session_not_active", 409)
    items = (
        VocabularyReviewItem.query.filter_by(session_id=session.id, student_id=user.id)
        .order_by(VocabularyReviewItem.queue_index.asc())
        .with_for_update()
        .all()
    )
    missing = [
        item.id
        for item in items
        if not item.first_attempt_id or _correction_required(item)
    ]
    if missing:
        raise VocabularyAutonomousReviewError(
            "review_session_incomplete",
            409,
            missing_review_item_ids=missing,
            total_count=len(items),
        )
    supplied_queue_token = str(payload.get("queue_token") or "").strip()
    if not supplied_queue_token:
        raise VocabularyAutonomousReviewError("review_queue_token_required", 400)
    if supplied_queue_token != session.queue_token:
        raise VocabularyAutonomousReviewError("review_queue_changed", 409)
    duration = payload.get("duration_seconds")
    try:
        duration = max(0, int(duration)) if duration is not None else None
    except (TypeError, ValueError) as error:
        raise VocabularyAutonomousReviewError("invalid_duration", 400) from error

    # SQLite ignores SELECT ... FOR UPDATE. Claim the state transition with an
    # atomic compare-and-swap so two gthread requests cannot both advance the
    # same dimensions before the unique settlement row is written.
    try:
        claimed = VocabularyReviewSession.query.filter_by(
            id=session.id,
            student_id=user.id,
            status=VocabularyReviewSession.STATUS_ACTIVE,
        ).update(
            {VocabularyReviewSession.status: VocabularyReviewSession.STATUS_SETTLING},
            synchronize_session=False,
        )
    except OperationalError:
        raise VocabularyAutonomousReviewError(
            "review_settlement_in_progress",
            409,
        ) from None
    if claimed != 1:
        existing_settlement = VocabularyReviewSettlement.query.filter_by(
            session_id=session.id,
            student_id=user.id,
        ).first()
        if existing_settlement:
            return _safe_json(existing_settlement.result_json)
        raise VocabularyAutonomousReviewError("review_settlement_in_progress", 409)
    session.status = VocabularyReviewSession.STATUS_SETTLING

    for item in items:
        if item.state_applied:
            continue
        attempt = (
            VocabularyReviewAttempt.query.filter_by(
                item_id=item.id,
                is_first_attempt=True,
            )
            .order_by(VocabularyReviewAttempt.id.asc())
            .first()
        )
        if not attempt:
            raise VocabularyAutonomousReviewError(
                "review_session_incomplete",
                409,
                missing_review_item_ids=[item.id],
                total_count=len(items),
            )
        _restore_first_attempt_state(user, item, attempt)

    attempts = []
    for item in items:
        attempt = (
            VocabularyReviewAttempt.query.filter_by(
                item_id=item.id,
                is_first_attempt=True,
            )
            .order_by(VocabularyReviewAttempt.id.asc())
            .first()
        )
        if attempt:
            attempts.append((item, attempt))
    correct_count = sum(bool(attempt.is_correct) for _item, attempt in attempts)
    by_dimension = {}
    for item, attempt in attempts:
        bucket = by_dimension.setdefault(item.dimension, {"correct": 0, "total": 0})
        bucket["total"] += 1
        bucket["correct"] += int(bool(attempt.is_correct))
    total_count = len(attempts)
    accuracy = round(correct_count / total_count * 100, 1) if total_count else 0.0
    remaining_due_count = _due_count(user, now)
    result = {
        "ok": True,
        "independent_review": True,
        "session_id": session.id,
        "status": VocabularyReviewSession.STATUS_SETTLED,
        "correct_count": correct_count,
        "total_count": total_count,
        "accuracy": accuracy,
        "dimensions": by_dimension,
        "queue_token": session.queue_token,
        "origin_task_id": session.origin_task_id,
        "remaining_due_count": remaining_due_count,
        "continue_available": remaining_due_count > 0,
    }
    session.status = VocabularyReviewSession.STATUS_SETTLED
    # A session that crosses midnight grants clearance on the day it was
    # actually completed, not the day on which the frozen batch was opened.
    session.review_date = local_date(now)
    session.claim_key = None
    session.settled_at = now
    session.duration_seconds = duration
    session.result_json = json.dumps(result, ensure_ascii=False, sort_keys=True)
    settlement = VocabularyReviewSettlement(
        session_id=session.id,
        student_id=user.id,
        session_token=session.session_token,
        result_json=session.result_json,
        settled_at=now,
    )
    try:
        with db.session.begin_nested():
            db.session.add(settlement)
            db.session.flush()
    except OperationalError:
        raise VocabularyAutonomousReviewError("review_settlement_in_progress", 409) from None
    except IntegrityError:
        # The outer transaction still contains the mastery changes. Let the
        # route roll all of them back instead of returning an existing row and
        # accidentally committing a second state transition.
        raise VocabularyAutonomousReviewError("review_settlement_conflict", 409) from None
    return result


def continue_review(
    user: User,
    session_id: int,
    *,
    session_token: str | None = None,
    now: datetime | None = None,
) -> dict:
    session = _session_for_user(user, session_id, session_token, require_token=True)
    if session.status != VocabularyReviewSession.STATUS_SETTLED:
        raise VocabularyAutonomousReviewError("review_session_not_settled", 409)
    return claim_today_review(user, now=now, origin_task_id=session.origin_task_id)


def review_preflight(user: User, task_id: int, *, now: datetime | None = None) -> dict:
    """Tell a task launcher whether one finite autonomous batch is required."""

    now = utc_naive(now)
    task = _validate_origin_task(user, task_id)
    task_flow_started = (
        VocabularyLearningFlow.query.filter_by(
            student_id=user.id,
            task_id=task.id,
        ).first()
        is not None
    )
    active = (
        VocabularyReviewSession.query.filter_by(
            student_id=user.id,
            status=VocabularyReviewSession.STATUS_ACTIVE,
        )
        .order_by(VocabularyReviewSession.started_at.desc(), VocabularyReviewSession.id.desc())
        .first()
    )
    due_count = _due_count(user, now)
    latest_settled = (
        VocabularyReviewSession.query.filter_by(
            student_id=user.id,
            status=VocabularyReviewSession.STATUS_SETTLED,
            review_date=local_date(now),
        )
        .order_by(VocabularyReviewSession.settled_at.desc(), VocabularyReviewSession.id.desc())
        .first()
    )
    # A fully settled batch is a student/date-bound clearance, regardless of
    # whether it was entered from Home or from a particular task. This keeps
    # the finite-batch overload guard useful when a student has two tasks in a
    # day. The remaining due count is deliberately still returned so Home can
    # offer the next batch; it is not silently converted into task progress.
    # Review is an entry gate, not an interrupt. A group's queue is fetched
    # after every answer, so applying the due-time check to an existing flow
    # can redirect a student in the middle of a task when a dimension becomes
    # due by a few seconds. Keep Home's review debt/session intact, but let an
    # already-started teacher task resume until its own state machine settles.
    required = bool(
        not task_flow_started
        and (active or (due_count and latest_settled is None))
    )
    return {
        "ok": True,
        "task_id": task.id,
        "required": required,
        "review_required": required,
        "task_flow_started": task_flow_started,
        "due_count": due_count,
        "batch_limit": MAX_REVIEW_BATCH,
        "active_session_id": active.id if active else None,
        "active_session_token": active.session_token if active else None,
        "clearance_session_id": latest_settled.id if latest_settled else None,
        "clearance_review_date": (
            latest_settled.review_date.isoformat() if latest_settled else None
        ),
        "origin_task_id": task.id,
        "remaining_due_count": due_count,
    }


def review_summary(user: User, *, now: datetime | None = None) -> dict:
    now = utc_naive(now)
    active = (
        VocabularyReviewSession.query.filter_by(
            student_id=user.id,
            status=VocabularyReviewSession.STATUS_ACTIVE,
        )
        .order_by(VocabularyReviewSession.started_at.desc(), VocabularyReviewSession.id.desc())
        .first()
    )
    due_count = _due_count(user, now)
    active_remaining = 0
    if active:
        active_items = VocabularyReviewItem.query.filter_by(
            session_id=active.id,
            student_id=user.id,
        ).all()
        active_remaining = sum(
            item.first_attempt_id is None or _correction_required(item)
            for item in active_items
        )
    # Even an all-answered session still needs its once-only settlement. Keep
    # Home's entry visible so a crash between the final answer and settle does
    # not leave an invisible gate that blocks every teacher task.
    review_due_count = max(1, active_remaining) if active else due_count
    return {
        "ok": True,
        "due_count": due_count,
        "review_due_count": review_due_count,
        "batch_limit": MAX_REVIEW_BATCH,
        "active_session_id": active.id if active else None,
        "active_session_token": active.session_token if active else None,
        "has_active_session": bool(active),
    }
