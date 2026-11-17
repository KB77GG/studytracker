"""Ordered, lightweight review metadata for fresh gates and finite batches.

The database may still scan/sort due metadata. Only a page of ORM words and
masteries is hydrated at a time, and callers can stop eligibility work early.
Question eligibility and materialization remain in the review service.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone

from sqlalchemy import and_, case, func, literal, or_, select, union_all
from sqlalchemy.orm import aliased

from models import (
    DictationWord,
    StudentVocabularyMastery,
    VocabularyReviewAttempt,
    VocabularyReviewItem,
    db,
)
from services.dictation_review import SHANGHAI, local_date
from services.vocabulary_mastery import DIMENSIONS
from services.vocabulary_remediation import MAX_REMEDIATION_PER_WORD, dimension_priority

SELECTION_PAGE_SIZE = 128


def _due_metadata_query(user_id, now, only_sense_ids=None, exclude_sense_ids=None):
    mastery = StudentVocabularyMastery
    item = VocabularyReviewItem
    attempt = VocabularyReviewAttempt
    review_day = local_date(now)
    start = datetime.combine(review_day, time.min, tzinfo=SHANGHAI)
    end = datetime.combine(review_day + timedelta(days=1), time.min, tzinfo=SHANGHAI)
    start = start.astimezone(timezone.utc).replace(tzinfo=None)  # noqa: UP017
    end = end.astimezone(timezone.utc).replace(tzinfo=None)  # noqa: UP017
    sense_filter = [item.sense_id.in_(only_sense_ids)] if only_sense_ids is not None else []
    if exclude_sense_ids:
        sense_filter.append(~item.sense_id.in_(exclude_sense_ids))
    cooled = (
        select(item.sense_id)
        .join(attempt, attempt.item_id == item.id)
        .where(
            item.student_id == user_id,
            attempt.student_id == user_id,
            attempt.is_first_attempt.is_(True),
            attempt.submitted_at >= start,
            attempt.submitted_at < end,
            *sense_filter,
        )
        .distinct()
        .cte("review_cooled_senses")
    )
    latest_ids = (
        select(func.max(item.id).label("item_id"), item.sense_id, item.dimension)
        .where(item.student_id == user_id, *sense_filter)
        .group_by(item.sense_id, item.dimension)
        .cte("review_latest_ids")
    )
    representative = aliased(DictationWord)
    fallback = aliased(DictationWord)
    representative_id = (
        select(representative.id)
        .where(representative.id == mastery.representative_word_id)
        .correlate(mastery)
        .scalar_subquery()
    )
    fallback_id = (
        select(fallback.id)
        .where(fallback.sense_id == mastery.sense_id)
        .order_by(fallback.book_id, fallback.sequence, fallback.id)
        .limit(1)
        .correlate(mastery)
        .scalar_subquery()
    )
    chosen_word = func.coalesce(representative_id, fallback_id)
    latest = aliased(VocabularyReviewItem)
    word = aliased(DictationWord)
    branches = []
    for dimension in DIMENSIONS:
        due_at = getattr(mastery, f"{dimension}_next_due_at")
        stage = func.coalesce(getattr(mastery, f"{dimension}_stage"), 0)
        last_answer = getattr(mastery, f"{dimension}_last_answered_at")
        correction_required = and_(
            func.coalesce(latest.first_attempt_id, "") != "",
            latest.first_is_correct.is_(False),
            or_(latest.first_response_kind.is_(None), latest.first_response_kind != "forgot"),
            latest.correction_is_correct.is_not(True),
            func.coalesce(latest.correction_exhausted, False).is_(False),
        )
        priority = case(
            (
                and_(
                    mastery.review_related_dimension == dimension,
                    mastery.review_related_due_at.is_not(None),
                    mastery.review_related_due_at <= now,
                ),
                3,
            ),
            (and_(latest.first_is_correct.is_(False), ~correction_required), 2),
            else_=0,
        )
        filters = [
            mastery.student_id == user_id,
            due_at <= now,
            word.sense_id.is_not(None),
            ~mastery.sense_id.in_(select(cooled.c.sense_id)),
            ~and_(
                priority > 0,
                func.coalesce(mastery.review_remediation_date == review_day, False),
                func.coalesce(mastery.review_remediation_count, 0) >= MAX_REMEDIATION_PER_WORD,
            ),
        ]
        if only_sense_ids is not None:
            filters.append(mastery.sense_id.in_(only_sense_ids))
        if exclude_sense_ids:
            filters.append(~mastery.sense_id.in_(exclude_sense_ids))
        branches.append(
            select(
                mastery.id.label("mastery_id"),
                mastery.sense_id.label("sense_id"),
                word.id.label("word_id"),
                word.book_id.label("book_id"),
                word.sequence.label("word_sequence"),
                literal(dimension).label("dimension"),
                due_at.label("due_at"),
                stage.label("stage"),
                last_answer.label("last_answered_at"),
                priority.label("remediation_priority"),
                case((and_(stage == 0, last_answer.is_not(None)), 1), else_=0).label(
                    "error_priority"
                ),
                case((and_(stage == 0, last_answer.is_(None)), 1), else_=0).label(
                    "untested_priority"
                ),
                literal(dimension_priority(dimension)).label("dimension_priority"),
            )
            .select_from(mastery)
            .join(word, word.id == chosen_word)
            .outerjoin(
                latest_ids,
                and_(
                    latest_ids.c.sense_id == mastery.sense_id, latest_ids.c.dimension == dimension
                ),
            )
            .outerjoin(latest, latest.id == latest_ids.c.item_id)
            .where(*filters)
        )
    candidates = union_all(*branches).subquery("review_due_metadata")
    return select(candidates).order_by(
        candidates.c.remediation_priority.desc(),
        candidates.c.error_priority.desc(),
        candidates.c.untested_priority.desc(),
        candidates.c.due_at,
        func.coalesce(candidates.c.last_answered_at, datetime.min),
        candidates.c.book_id,
        candidates.c.word_sequence,
        candidates.c.word_id,
        candidates.c.dimension_priority,
        # The old Python stable sort starts from mastery sense order.
        candidates.c.sense_id,
    )


def due_metadata_pages(
    user_id, now, *, only_sense_ids=None, exclude_sense_ids=None, page_size=SELECTION_PAGE_SIZE
):
    """Yield ordered scalar pages; close the cursor when callers stop early."""

    if only_sense_ids is not None:
        only_sense_ids = frozenset(only_sense_ids)
        if not only_sense_ids:
            return
    result = db.session.execute(
        _due_metadata_query(user_id, now, only_sense_ids, exclude_sense_ids)
    )
    try:
        while True:
            rows = result.fetchmany(page_size)
            if not rows:
                break
            yield rows
    finally:
        result.close()
