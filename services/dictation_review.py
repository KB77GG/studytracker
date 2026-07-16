"""Server-owned vocabulary review queue and first-answer state machine.

The legacy dictation endpoints remain available, but all new task clients use
this module for the durable queue snapshot, idempotent attempts, and automatic
wrong-word lifecycle.
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import Index, MetaData, Table, inspect, text
from sqlalchemy.exc import IntegrityError

from dictation_answers import (
    is_chinese_answer_correct,
    is_english_answer_correct,
    parse_answer_variants,
)
from models import (
    DictationBook,
    DictationRecord,
    DictationTaskReview,
    DictationWord,
    StudentWordMastery,
    Task,
    User,
    db,
)

UTC = timezone.utc  # noqa: UP017 - Python 3.10-compatible replacement.
SHANGHAI = ZoneInfo("Asia/Shanghai")
# These are product cutoffs, not deployment-time values.  Database datetimes
# remain naive UTC; the aware local values make the product boundary explicit.
AUTO_REVIEW_COLLECTION_START_LOCAL = datetime(2026, 7, 16, 0, 0, tzinfo=SHANGHAI)
AUTO_REVIEW_QUEUE_START_LOCAL = datetime(2026, 7, 17, 0, 0, tzinfo=SHANGHAI)
AUTO_REVIEW_COLLECTION_START_UTC = AUTO_REVIEW_COLLECTION_START_LOCAL.astimezone(UTC).replace(
    tzinfo=None
)
AUTO_REVIEW_QUEUE_START_UTC = AUTO_REVIEW_QUEUE_START_LOCAL.astimezone(UTC).replace(
    tzinfo=None
)
VALID_DICTATION_MODES = {
    "audio_to_en",
    "zh_to_en",
    "en_to_zh",
    "spelling_drill",
}
VALID_DICTATION_ORDERS = {"sequence", "random"}


class DictationReviewError(Exception):
    """A safe, user-facing validation error from the review service."""

    def __init__(self, error: str, status_code: int = 400, **details):
        super().__init__(error)
        self.error = error
        self.status_code = status_code
        self.details = details


def utc_naive(value: datetime | None = None) -> datetime:
    """Return a naive UTC datetime, matching the existing database convention."""

    value = value or datetime.utcnow()
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def local_date(value: datetime | None = None) -> date:
    current = utc_naive(value).replace(tzinfo=UTC)
    return current.astimezone(SHANGHAI).date()


def next_local_midnight(value: datetime | None = None) -> datetime:
    next_day = local_date(value) + timedelta(days=1)
    midnight = datetime.combine(next_day, time.min, tzinfo=SHANGHAI)
    return midnight.astimezone(UTC).replace(tzinfo=None)


def auto_review_collection_enabled(value: datetime | None = None) -> bool:
    """Whether a first-answer mistake may enter the new loop."""

    return utc_naive(value) >= AUTO_REVIEW_COLLECTION_START_UTC


def auto_review_queue_enabled(value: datetime | None = None) -> bool:
    """Whether automatic words may be claimed by a task queue."""

    return utc_naive(value) >= AUTO_REVIEW_QUEUE_START_UTC


def _task_owner(task: Task, user: User) -> bool:
    profile = getattr(user, "student_profile", None)
    return bool(profile and task.student_name == profile.full_name)


def _resolve_mode(task: Task, book: DictationBook) -> str:
    raw = str(getattr(task, "dictation_mode", "") or "").strip().lower()
    if raw in VALID_DICTATION_MODES:
        return raw
    if (book.book_type or "").strip().lower() == "translation":
        return "zh_to_en"
    return "audio_to_en"


def _resolve_order(task: Task) -> str:
    raw = str(getattr(task, "dictation_order", "") or "").strip().lower()
    return raw if raw in VALID_DICTATION_ORDERS else "sequence"


def _assigned_words(task: Task) -> list[DictationWord]:
    if not task.dictation_book_id:
        raise DictationReviewError("task_not_dictation", 409)
    start = max(1, int(task.dictation_word_start or 1))
    query = DictationWord.query.filter(
        DictationWord.book_id == task.dictation_book_id,
        DictationWord.sequence >= start,
    )
    if task.dictation_word_end:
        query = query.filter(DictationWord.sequence <= int(task.dictation_word_end))
    words = query.order_by(DictationWord.sequence.asc()).all()
    if _resolve_order(task) == "random":
        words.sort(
            key=lambda word: hashlib.sha256(
                f"{task.id}:{task.dictation_book_id}:{word.id}".encode()
            ).hexdigest()
        )
    return words


def _mastery(student_id: int, word_id: int) -> StudentWordMastery | None:
    return StudentWordMastery.query.filter_by(
        student_id=student_id,
        word_id=word_id,
    ).first()


def _same_day_claimed_word_ids(
    student_id: int,
    book_id: int,
    review_day: date,
    *,
    lock: bool = False,
) -> set[int]:
    query = DictationTaskReview.query.filter_by(
        student_id=student_id,
        book_id=book_id,
        review_date=review_day,
    )
    # A locking read is required here because MySQL's default REPEATABLE READ
    # can otherwise keep an old snapshot after another task has claimed the
    # due words.  SQLite simply ignores FOR UPDATE, which is fine for its
    # single-writer test/development behavior.
    if lock:
        query = query.with_for_update()
    rows = query.all()
    return {row.word_id for row in rows}


def _queue_token(items: list[DictationTaskReview]) -> str:
    raw = "|".join(
        f"{item.id}:{item.word_id}:{item.source}:{int(bool(item.is_auto_review))}"
        for item in items
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _word_payload(word: DictationWord, item: DictationTaskReview, mode: str) -> dict:
    mastery = _mastery(item.student_id, word.id)
    return {
        "id": word.id,
        "word_id": word.id,
        "queue_item_id": item.id,
        "task_id": item.task_id,
        "book_id": word.book_id,
        "sequence": word.sequence,
        "word": word.word,
        "accepted_answers": parse_answer_variants(word.accepted_answers),
        "translation": word.translation,
        "phonetic": word.phonetic,
        "audio_us": word.audio_us,
        "audio_uk": word.audio_uk,
        "core_meaning_zh": word.core_meaning_zh,
        "usage_pattern": word.usage_pattern,
        "example_en": word.example_en,
        "example_zh": word.example_zh,
        "usage_note": word.usage_note,
        "mode": mode,
        "dictation_mode": mode,
        "source": item.source,
        "is_auto_review": bool(item.is_auto_review),
        "review_level": mastery.review_level if mastery else 0,
        "auto_review_active": bool(mastery and mastery.auto_review_active),
        "auto_review_correct_streak": mastery.auto_review_correct_streak if mastery else 0,
    }


def get_task_queue(user: User, task_id: int, now: datetime | None = None) -> dict:
    """Create or restore one durable merged queue for a dictation task."""

    now = utc_naive(now)
    # Serialize queue creation for repeated opens of the same task.  The
    # mastery-row lock below serializes competing same-book tasks.
    task = Task.query.filter_by(id=task_id).with_for_update().first()
    if not task:
        raise DictationReviewError("task_not_found", 404)
    if not _task_owner(task, user):
        raise DictationReviewError("forbidden", 403)
    book = db.session.get(DictationBook, task.dictation_book_id)
    if not book:
        raise DictationReviewError("dictation_book_not_found", 404)

    existing = (
        DictationTaskReview.query.filter_by(
            student_id=user.id,
            task_id=task.id,
        )
        .order_by(DictationTaskReview.queue_index.asc(), DictationTaskReview.id.asc())
        .all()
    )
    if not existing:
        assigned = _assigned_words(task)
        assigned_ids = {word.id for word in assigned}
        review_day = local_date(now)
        due_rows = []
        if auto_review_queue_enabled(now):
            due_rows = (
                StudentWordMastery.query.filter(
                    StudentWordMastery.student_id == user.id,
                    StudentWordMastery.book_id == book.id,
                    StudentWordMastery.auto_review_active.is_(True),
                    StudentWordMastery.auto_review_activated_at.isnot(None),
                    StudentWordMastery.auto_review_due_at.isnot(None),
                    StudentWordMastery.auto_review_due_at <= now,
                )
                .order_by(
                    StudentWordMastery.auto_review_due_at.asc(),
                    StudentWordMastery.word_id.asc(),
                )
                .with_for_update()
                .all()
            )
        # Do this after the due-row lock.  The first transaction commits its
        # snapshots before the second transaction reaches this current read,
        # so only the first same-book task receives each due review word.
        claimed_ids = _same_day_claimed_word_ids(
            user.id,
            book.id,
            review_day,
            lock=True,
        )
        review_words = []
        for row in due_rows:
            if row.word_id in assigned_ids or row.word_id in claimed_ids:
                continue
            word = db.session.get(DictationWord, row.word_id)
            if word and word.book_id == book.id:
                review_words.append(word)

        snapshots = []
        queue_index = 0
        for word in assigned:
            mastery = _mastery(user.id, word.id)
            is_due_review = bool(
                auto_review_queue_enabled(now)
                and mastery
                and mastery.auto_review_active
                and mastery.auto_review_activated_at
                and mastery.auto_review_due_at
                and mastery.auto_review_due_at <= now
            )
            snapshots.append(
                DictationTaskReview(
                    student_id=user.id,
                    task_id=task.id,
                    book_id=book.id,
                    word_id=word.id,
                    review_date=review_day,
                    source=DictationTaskReview.SOURCE_ASSIGNED,
                    is_auto_review=is_due_review,
                    queue_index=queue_index,
                )
            )
            queue_index += 1

        # Evenly distribute due review words into the gaps around the day's
        # assignment while preserving the assignment's stable order.
        if review_words:
            merged = []
            assigned_index = 0
            review_count = len(review_words)
            assigned_count = len(snapshots)
            for review_index, word in enumerate(review_words):
                target = ((review_index + 1) * (assigned_count + 1)) // (review_count + 1)
                while assigned_index < min(target, assigned_count):
                    merged.append(snapshots[assigned_index])
                    assigned_index += 1
                merged.append(
                    DictationTaskReview(
                        student_id=user.id,
                        task_id=task.id,
                        book_id=book.id,
                        word_id=word.id,
                        review_date=review_day,
                        source=DictationTaskReview.SOURCE_AUTO_REVIEW,
                        is_auto_review=True,
                        queue_index=0,
                    )
                )
            merged.extend(snapshots[assigned_index:])
            snapshots = merged

        for index, snapshot in enumerate(snapshots):
            snapshot.queue_index = index
            db.session.add(snapshot)
        db.session.flush()
        existing = snapshots

    mode = _resolve_mode(task, book)
    items = [
        _word_payload(snapshot.word, snapshot, mode)
        for snapshot in existing
        if snapshot.word is not None
    ]
    return {
        "ok": True,
        "task_id": task.id,
        "book_id": book.id,
        "task_mode": mode,
        "mode": mode,
        "dictation_order": _resolve_order(task),
        "queue_date": existing[0].review_date.isoformat() if existing else local_date(now).isoformat(),
        "assigned_count": sum(1 for item in existing if item.source == DictationTaskReview.SOURCE_ASSIGNED),
        "auto_review_count": sum(1 for item in existing if item.source == DictationTaskReview.SOURCE_AUTO_REVIEW),
        "auto_review_overlap_count": sum(
            1 for item in existing if item.is_auto_review and item.source == DictationTaskReview.SOURCE_ASSIGNED
        ),
        "total_count": len(items),
        "strict_submission": True,
        "queue_token": _queue_token(existing),
        "words": items,
    }


def _answer_is_correct(word: DictationWord, answer: str, mode: str) -> bool:
    if mode == "en_to_zh":
        return is_chinese_answer_correct(answer, word.translation)
    return is_english_answer_correct(
        answer,
        word.word,
        accepted_answers=word.accepted_answers,
    )


def _apply_auto_state(
    *,
    student_id: int,
    word: DictationWord,
    is_correct: bool,
    mode: str,
    is_auto_review: bool,
    now: datetime,
) -> StudentWordMastery | None:
    mastery = _mastery(student_id, word.id)
    if mastery is None and is_correct:
        # A correct first answer for a new assigned word never enters the loop.
        return None
    if mastery is None:
        mastery = StudentWordMastery(
            student_id=student_id,
            word_id=word.id,
            book_id=word.book_id,
            mistake_count=0,
            correct_streak=0,
            review_level=0,
        )
        db.session.add(mastery)

    mastery.last_seen_at = now
    mastery.last_mode = mode
    if not is_correct:
        mastery.mistake_count = int(mastery.mistake_count or 0) + 1
        mastery.review_level = 1
        mastery.correct_streak = 0
        mastery.auto_review_correct_streak = 0
        mastery.auto_review_due_at = next_local_midnight(now)
        mastery.auto_review_last_date = local_date(now)
        mastery.next_review_at = mastery.auto_review_due_at
        if auto_review_collection_enabled(now):
            # A mistake captured after the explicit collection cutoff starts a
            # new automatic cycle, including for a historical mastery row.
            mastery.auto_review_active = True
            mastery.auto_review_activated_at = now
        elif mastery.auto_review_activated_at is None:
            # Before collection starts, retain only legacy mastery data.  Do
            # not create an automatic-review eligibility marker.
            mastery.auto_review_active = False
            mastery.auto_review_due_at = None
        return mastery

    if is_auto_review and mastery.auto_review_active and mastery.auto_review_activated_at:
        mastery.auto_review_correct_streak = int(mastery.auto_review_correct_streak or 0) + 1
        mastery.correct_streak = mastery.auto_review_correct_streak
        mastery.auto_review_last_date = local_date(now)
        if mastery.auto_review_correct_streak >= 2:
            mastery.auto_review_active = False
            mastery.auto_review_due_at = None
            mastery.auto_review_activated_at = None
            mastery.auto_review_correct_streak = 0
            mastery.correct_streak = 0
            mastery.review_level = StudentWordMastery.LEVEL_GRADUATED
            mastery.next_review_at = None
        else:
            mastery.review_level = max(1, int(mastery.review_level or 1))
            mastery.auto_review_due_at = next_local_midnight(now)
            mastery.next_review_at = mastery.auto_review_due_at
        return mastery

    # Preserve the old review-page progression when a legacy client submits a
    # due word without a task snapshot.
    return StudentWordMastery.apply_answer(
        student_id=student_id,
        word_id=word.id,
        book_id=word.book_id,
        is_correct=True,
        mode=mode,
        now=now,
        create_if_missing=False,
    )


def _serialize_answer_result(
    *,
    word: DictationWord,
    record: DictationRecord,
    mastery: StudentWordMastery | None,
    idempotent: bool = False,
) -> dict:
    return {
        "ok": True,
        "is_correct": bool(record.is_correct),
        "first_attempt": bool(record.is_first_attempt),
        "idempotent": idempotent,
        "attempt_id": record.attempt_id,
        "correct_answer": word.word,
        "translation": word.translation,
        "phonetic": word.phonetic,
        "auto_review_active": bool(mastery and mastery.auto_review_active),
        "auto_review_correct_streak": mastery.auto_review_correct_streak if mastery else 0,
        "auto_review_exited": bool(
            mastery
            and not mastery.auto_review_active
            and mastery.review_level >= StudentWordMastery.LEVEL_GRADUATED
        ),
        "next_review_at": mastery.next_review_at.isoformat() if mastery and mastery.next_review_at else None,
        "next_review_date": (
            local_date(mastery.next_review_at).isoformat()
            if mastery and mastery.next_review_at
            else None
        ),
        "review_level": mastery.review_level if mastery else None,
    }


def submit_dictation_answer(
    user: User,
    payload: dict,
    *,
    now: datetime | None = None,
) -> dict:
    """Grade one answer and mutate mastery only once for its first attempt."""

    now = utc_naive(now)
    word_id = payload.get("word_id")
    answer = str(payload.get("answer") or "").strip()
    if not word_id or not answer:
        raise DictationReviewError("missing_params", 400)
    try:
        word_id = int(word_id)
    except (TypeError, ValueError) as error:
        raise DictationReviewError("invalid_word_id", 400) from error
    word = db.session.get(DictationWord, word_id)
    if not word:
        raise DictationReviewError("word_not_found", 404)

    mode = str(payload.get("mode") or "audio_to_en").strip().lower()
    if mode not in VALID_DICTATION_MODES:
        mode = "audio_to_en"
    task_id = payload.get("task_id")
    try:
        task_id = int(task_id) if task_id else None
    except (TypeError, ValueError) as error:
        raise DictationReviewError("invalid_task_id", 400) from error
    submitted_book_id = payload.get("book_id")
    if submitted_book_id not in (None, ""):
        try:
            submitted_book_id = int(submitted_book_id)
        except (TypeError, ValueError) as error:
            raise DictationReviewError("invalid_book_id", 400) from error
        if submitted_book_id != word.book_id:
            raise DictationReviewError("book_mismatch", 409)
    expected_book_id = word.book_id
    raw_attempt_id = str(payload.get("attempt_id") or "").strip()
    if len(raw_attempt_id) > 96:
        raise DictationReviewError("attempt_id_too_long", 400, max_length=96)
    attempt_id = raw_attempt_id or None
    if attempt_id:
        duplicate = DictationRecord.query.filter_by(
            student_id=user.id,
            attempt_id=attempt_id,
        ).first()
        if duplicate:
            if (
                duplicate.word_id != word.id
                or duplicate.task_id != task_id
                or duplicate.book_id != expected_book_id
            ):
                raise DictationReviewError("attempt_id_conflict", 409)
            mastery = _mastery(user.id, word.id)
            result = _serialize_answer_result(
                word=word,
                record=duplicate,
                mastery=mastery,
                idempotent=True,
            )
            return result

    snapshot = None
    if task_id:
        task = db.session.get(Task, task_id)
        if not task:
            raise DictationReviewError("task_not_found", 404)
        if not _task_owner(task, user):
            raise DictationReviewError("forbidden", 403)
        snapshot = DictationTaskReview.query.filter_by(
            student_id=user.id,
            task_id=task_id,
            word_id=word.id,
        ).with_for_update().first()
        if payload.get("strict_queue") and snapshot is None:
            raise DictationReviewError("word_not_in_queue", 409, word_id=word.id)
        if payload.get("strict_queue"):
            if task.dictation_book_id != word.book_id or (snapshot and snapshot.book_id != word.book_id):
                raise DictationReviewError("queue_changed", 409, word_id=word.id)
            task_book = db.session.get(DictationBook, task.dictation_book_id)
            if not task_book:
                raise DictationReviewError("dictation_book_not_found", 404)
            # New clients cannot switch the grading mode by changing the
            # request payload; the server-owned task mode is authoritative.
            mode = _resolve_mode(task, task_book)

    is_correct = _answer_is_correct(word, answer, mode)
    is_first = True
    if snapshot is not None:
        is_first = snapshot.first_attempt_id is None
        if not is_first and attempt_id and attempt_id == snapshot.first_attempt_id:
            existing = DictationRecord.query.filter_by(
                student_id=user.id,
                attempt_id=attempt_id,
            ).first()
            if existing:
                return _serialize_answer_result(
                    word=word,
                    record=existing,
                    mastery=_mastery(user.id, word.id),
                    idempotent=True,
                )
        if is_first:
            attempt_id = attempt_id or f"legacy:{user.id}:{task_id}:{word.id}"
        elif not attempt_id:
            attempt_id = f"retry:{user.id}:{task_id}:{word.id}:{now.timestamp()}"

    # Automatic-review correctness is intentionally applied at strict task
    # finalization, not at answer time.  A first wrong answer still mutates the
    # loop immediately, but a first correct answer must not advance a streak
    # when the student abandons the task.
    defer_auto_correct = bool(snapshot and snapshot.is_auto_review and is_first and is_correct)
    record = DictationRecord(
        student_id=user.id,
        task_id=task_id,
        book_id=word.book_id,
        word_id=word.id,
        student_answer=answer[:100],
        is_correct=is_correct,
        attempt_id=attempt_id,
        is_first_attempt=is_first,
        task_review_id=snapshot.id if snapshot else None,
    )
    try:
        # The savepoint makes a concurrent duplicate attempt_id recoverable:
        # the unique index raises here, without poisoning the outer request
        # transaction.  Snapshot fields are assigned only after this flush so
        # they are not dirty before the savepoint starts.
        with db.session.begin_nested():
            db.session.add(record)
            db.session.flush()
    except IntegrityError as error:
        if attempt_id:
            duplicate = DictationRecord.query.filter_by(
                student_id=user.id,
                attempt_id=attempt_id,
            ).with_for_update().first()
            if (
                duplicate
                and duplicate.word_id == word.id
                and duplicate.task_id == task_id
                and duplicate.book_id == expected_book_id
            ):
                return _serialize_answer_result(
                    word=word,
                    record=duplicate,
                    mastery=_mastery(user.id, word.id),
                    idempotent=True,
                )
            if duplicate:
                raise DictationReviewError("attempt_id_conflict", 409) from error
        raise

    if snapshot is not None and is_first:
        snapshot.first_attempt_id = attempt_id
        snapshot.first_is_correct = is_correct
        snapshot.first_answer = answer[:200]

    mastery = _mastery(user.id, word.id)
    if is_first:
        if snapshot is not None:
            if not defer_auto_correct:
                mastery = _apply_auto_state(
                    student_id=user.id,
                    word=word,
                    is_correct=is_correct,
                    mode=mode,
                    is_auto_review=bool(snapshot.is_auto_review),
                    now=now,
                )
                snapshot.state_applied = True
        else:
            # Legacy clients did not identify a first answer.  Keep their old
            # level progression while making an error enter the new loop.
            mastery = _apply_auto_state(
                student_id=user.id,
                word=word,
                is_correct=is_correct,
                mode=mode,
                # A non-task/legacy review answer must never advance or exit
                # the new automatic loop.  Its old progression remains
                # available through _apply_auto_state's legacy branch.
                is_auto_review=False,
                now=now,
            )

    return _serialize_answer_result(
        word=word,
        record=record,
        mastery=mastery,
    )


def finalize_strict_task(
    user: User,
    task_id: int,
    payload: dict,
    *,
    now: datetime | None = None,
) -> dict:
    """Finalize a task, rolling back both validation and mutation failures."""

    try:
        return _finalize_strict_task(user, task_id, payload, now=now)
    except Exception:
        db.session.rollback()
        raise


def _finalize_strict_task(
    user: User,
    task_id: int,
    payload: dict,
    *,
    now: datetime | None = None,
) -> dict:
    """Compute the merged task score from server-side first answers only."""

    now = utc_naive(now)
    task = Task.query.filter_by(id=task_id).with_for_update().first()
    if not task:
        raise DictationReviewError("task_not_found", 404)
    if not _task_owner(task, user):
        raise DictationReviewError("forbidden", 403)
    items = (
        DictationTaskReview.query.filter_by(student_id=user.id, task_id=task.id)
        .order_by(DictationTaskReview.queue_index.asc())
        .with_for_update()
        .all()
    )
    if not items:
        raise DictationReviewError("queue_not_initialized", 409)
    supplied_token = str(payload.get("queue_token") or "").strip()
    expected_token = _queue_token(items)
    if supplied_token and supplied_token != expected_token:
        raise DictationReviewError("queue_changed", 409)

    task_book = db.session.get(DictationBook, task.dictation_book_id)
    if not task_book:
        raise DictationReviewError("dictation_book_not_found", 404)

    invalid_snapshots = [
        item.word_id
        for item in items
        if item.book_id != task.dictation_book_id
        or item.word is None
        or item.word.book_id != task.dictation_book_id
    ]
    if invalid_snapshots:
        raise DictationReviewError(
            "queue_changed",
            409,
            invalid_word_ids=invalid_snapshots,
        )

    missing = [item.word_id for item in items if item.first_attempt_id is None]
    if missing:
        raise DictationReviewError(
            "queue_incomplete",
            409,
            missing_word_ids=missing,
            total_count=len(items),
        )
    first_records = []
    invalid_records = []
    for item in items:
        record = DictationRecord.query.filter_by(
            student_id=user.id,
            task_review_id=item.id,
            is_first_attempt=True,
        ).first()
        if (
            record is None
            or record.task_id != task.id
            or record.book_id != item.book_id
            or record.word_id != item.word_id
            or record.attempt_id != item.first_attempt_id
        ):
            invalid_records.append(item.word_id)
        else:
            first_records.append(record)
    if invalid_records:
        raise DictationReviewError(
            "queue_incomplete",
            409,
            missing_word_ids=invalid_records,
            total_count=len(items),
        )

    duration_seconds = None
    if payload.get("duration_seconds") is not None:
        try:
            duration_seconds = max(0, int(payload.get("duration_seconds")))
        except (TypeError, ValueError) as error:
            raise DictationReviewError("invalid_duration", 400) from error

    # Apply deferred automatic-review correctness exactly once, in the same
    # transaction as task completion.  Repeated finalize calls see
    # state_applied=True and cannot add another streak.
    try:
        mode = _resolve_mode(task, task_book)
        for item in items:
            if item.state_applied or not item.is_auto_review or not item.first_is_correct:
                continue
            _apply_auto_state(
                student_id=user.id,
                word=item.word,
                is_correct=True,
                mode=mode,
                is_auto_review=True,
                now=now,
            )
            item.state_applied = True

        total = len(items)
        correct = sum(1 for record in first_records if record.is_correct)
        accuracy = round(correct / total * 100, 1) if total else 0.0
        task.student_submitted = True
        task.submitted_at = now
        task.accuracy = accuracy
        task.completion_rate = 100.0
        task.status = "done"
        if duration_seconds is not None:
            task.actual_seconds = duration_seconds
        db.session.flush()
    except Exception:
        db.session.rollback()
        raise
    return {
        "ok": True,
        "server_scored": True,
        "correct_count": correct,
        "total_count": total,
        "accuracy": accuracy,
        "queue_token": expected_token,
    }


def list_server_wrong_words(user: User, book_id: int | None = None) -> dict:
    query = StudentWordMastery.query.filter(
        StudentWordMastery.student_id == user.id,
        StudentWordMastery.auto_review_active.is_(True),
        StudentWordMastery.auto_review_activated_at.isnot(None),
        StudentWordMastery.mistake_count > 0,
        StudentWordMastery.review_level < StudentWordMastery.LEVEL_GRADUATED,
    )
    if book_id:
        query = query.filter(StudentWordMastery.book_id == book_id)
    rows = query.order_by(StudentWordMastery.auto_review_due_at.asc(), StudentWordMastery.word_id.asc()).all()
    items = []
    for row in rows:
        word = row.word
        if not word:
            continue
        items.append(
            {
                "id": word.id,
                "word_id": word.id,
                "book_id": word.book_id,
                "word": word.word,
                "translation": word.translation,
                "phonetic": word.phonetic,
                "due_at": row.auto_review_due_at.isoformat() if row.auto_review_due_at else None,
                "due_date": local_date(row.auto_review_due_at).isoformat() if row.auto_review_due_at else None,
                "correct_streak": row.auto_review_correct_streak,
                "mistake_count": row.mistake_count,
            }
        )
    return {
        "ok": True,
        "student": {
            "id": user.id,
            "username": user.username,
            "name": getattr(getattr(user, "student_profile", None), "full_name", None),
        },
        "count": len(items),
        "items": items,
    }


def import_legacy_wrong_words(
    user: User,
    payload: dict,
    *,
    now: datetime | None = None,
) -> dict:
    if payload.get("confirmed") is not True:
        raise DictationReviewError("student_confirmation_required", 400)
    confirmed_id = payload.get("confirmed_student_id", payload.get("student_id"))
    try:
        confirmed_id = int(confirmed_id)
    except (TypeError, ValueError) as error:
        raise DictationReviewError("student_confirmation_required", 400) from error
    if confirmed_id != user.id:
        raise DictationReviewError("student_confirmation_mismatch", 403)
    book_id = payload.get("book_id")
    try:
        book_id = int(book_id)
    except (TypeError, ValueError) as error:
        raise DictationReviewError("book_required", 400) from error
    words = payload.get("words", payload.get("wrong_words", []))
    if not isinstance(words, list):
        raise DictationReviewError("invalid_words", 400)
    now = utc_naive(now)
    imported = []
    already_active = []
    skipped_graduated = []
    skipped_inactive = []
    unresolved = []
    book_words = DictationWord.query.filter_by(book_id=book_id).all()
    words_by_name = {
        (word.word or "").strip().lower(): word
        for word in book_words
        if word.word
    }
    words_by_id = {word.id: word for word in book_words}
    for raw in words:
        raw_word_id = raw.get("word_id", raw.get("id")) if isinstance(raw, dict) else None
        try:
            raw_word_id = int(raw_word_id) if raw_word_id else None
        except (TypeError, ValueError):
            raw_word_id = None
        label = raw.get("word", raw.get("name")) if isinstance(raw, dict) else raw
        normalized = str(label or "").strip().lower()
        if not normalized and not raw_word_id:
            continue
        match = words_by_id.get(raw_word_id) if raw_word_id else words_by_name.get(normalized)
        if not match:
            unresolved.append(str(label or raw_word_id))
            continue
        mastery = _mastery(user.id, match.id)
        if mastery is None:
            mastery = StudentWordMastery(
                student_id=user.id,
                word_id=match.id,
                book_id=book_id,
                mistake_count=0,
                correct_streak=0,
                review_level=1,
            )
            db.session.add(mastery)
            mastery.mistake_count = 1
            mastery.review_level = 1
            mastery.auto_review_active = True
            mastery.auto_review_correct_streak = 0
            mastery.auto_review_due_at = next_local_midnight(now)
            mastery.auto_review_activated_at = now
            mastery.next_review_at = mastery.auto_review_due_at
            imported.append(match.id)
            continue

        # A stale local notebook entry must never rewind an active streak or
        # resurrect a word that has already graduated from the server loop.
        if mastery.review_level >= StudentWordMastery.LEVEL_GRADUATED:
            skipped_graduated.append(match.id)
        elif mastery.auto_review_active:
            already_active.append(match.id)
        else:
            skipped_inactive.append(match.id)
    db.session.flush()
    return {
        "ok": True,
        "student": {
            "id": user.id,
            "username": user.username,
            "name": getattr(getattr(user, "student_profile", None), "full_name", None),
        },
        "imported_count": len(imported),
        "imported_word_ids": imported,
        "already_active_count": len(already_active),
        "already_active_word_ids": already_active,
        "skipped_graduated_count": len(skipped_graduated),
        "skipped_graduated_word_ids": skipped_graduated,
        "skipped_inactive_count": len(skipped_inactive),
        "skipped_inactive_word_ids": skipped_inactive,
        "unresolved": unresolved,
    }


def ensure_incremental_schema(engine, logger=None, now: datetime | None = None) -> None:
    """Add schema objects only; never infer eligibility from legacy rows.

    ``now`` remains accepted for startup-call compatibility, but is
    intentionally unused because migration must not backfill historical
    automatic-review state.
    """

    inspector = inspect(engine)

    def add_columns(table_name: str, columns: dict[str, str]) -> None:
        if table_name not in inspector.get_table_names():
            return
        existing = {column["name"] for column in inspector.get_columns(table_name)}
        for name, column_type in columns.items():
            if name in existing:
                continue
            try:
                with engine.begin() as connection:
                    connection.execute(
                        text(f"ALTER TABLE {table_name} ADD COLUMN {name} {column_type}")
                    )
                existing.add(name)
            except Exception as exc:  # pragma: no cover - production safeguard
                if logger:
                    logger.warning("Failed to add %s.%s: %s", table_name, name, exc)

    add_columns(
        "student_word_mastery",
        {
            "auto_review_active": "BOOLEAN NOT NULL DEFAULT 0",
            "auto_review_due_at": "DATETIME",
            "auto_review_correct_streak": "INTEGER NOT NULL DEFAULT 0",
            "auto_review_last_date": "DATE",
            "auto_review_activated_at": "DATETIME",
        },
    )
    add_columns(
        "dictation_record",
        {
            "attempt_id": "VARCHAR(96)",
            "is_first_attempt": "BOOLEAN NOT NULL DEFAULT 1",
            "task_review_id": "INTEGER",
        },
    )

    try:
        from models import DictationTaskReview

        DictationTaskReview.__table__.create(bind=engine, checkfirst=True)
    except Exception as exc:  # pragma: no cover - production safeguard
        if logger:
            logger.warning("Failed to ensure dictation_task_review table: %s", exc)

    add_columns(
        "dictation_task_review",
        {"state_applied": "BOOLEAN NOT NULL DEFAULT 0"},
    )

    index_specs = (
        (
            "dictation_record",
            "uq_dictation_record_student_attempt",
            ("student_id", "attempt_id"),
            True,
        ),
        (
            "student_word_mastery",
            "ix_mastery_auto_review_due",
            ("student_id", "book_id", "auto_review_active", "auto_review_due_at"),
            False,
        ),
        (
            "student_word_mastery",
            "ix_mastery_auto_review_activated",
            (
                "student_id",
                "book_id",
                "auto_review_active",
                "auto_review_activated_at",
                "auto_review_due_at",
            ),
            False,
        ),
    )
    for table_name, index_name, column_names, unique in index_specs:
        try:
            if table_name not in inspect(engine).get_table_names():
                continue
            # Reflect into throwaway metadata so a startup migration does not
            # mutate the global ORM table and make a later db.create_all()
            # attempt to create the same index a second time.
            reflected = Table(table_name, MetaData(), autoload_with=engine)
            index = Index(
                index_name,
                *(reflected.c[column] for column in column_names),
                unique=unique,
            )
            index.create(bind=engine, checkfirst=True)
        except Exception as exc:  # pragma: no cover - production safeguard
            if logger:
                logger.warning("Failed to ensure vocabulary review index %s: %s", index_name, exc)

    # Intentionally no backfill: rows created before the explicit collection
    # cutoff have a NULL activation marker and can never be auto-claimed.
