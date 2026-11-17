"""Bounded policy candidates and cleanup prepared before acquiring a writer.

Counts use indexed SQL aggregates (not a claim of constant database CPU). Only
the next question batch and a fixed cleanup budget cross the ORM boundary.
"""

from datetime import timedelta

from sqlalchemy import String, and_, case, cast, exists, func, insert, literal, or_, select, update

from models import StudentVocabularyMastery, db
from models import VocabularyErrorQueue as Queue
from models import VocabularyPolicyAllocation as Allocation
from models import VocabularyPolicyCheckpoint as Checkpoint
from models import VocabularyPolicyEvent as Event

BATCH_LIMIT = 20
CLEANUP_LIMIT = 100


def optional_mastery_condition(user_id, cohort, now):
    """Drop only senses for which every due ability is policy-blocked.

    A partially blocked sense must retain the legacy first-eligible-ability
    selection: pushing an individual ability filter into that query would
    silently pick a different dimension. This whole-sense predicate cannot
    remove a result the existing iterator/caller could have accepted.
    """
    core = _core()
    mastery = StudentVocabularyMastery
    day = core.local_date(now)
    clauses = []
    for dimension in sorted(core.DIMENSIONS):
        blocked_queue = exists().where(
            Queue.student_id == user_id,
            Queue.cohort_key == cohort,
            Queue.sense_id == mastery.sense_id,
            Queue.dimension == dimension,
            Queue.status.in_(("active", "paused")),
        )
        allocated = exists().where(
            Allocation.student_id == user_id,
            Allocation.local_date == day,
            Allocation.sense_id == mastery.sense_id,
            Allocation.dimension == dimension,
        )
        clauses.append(
            and_(getattr(mastery, f"{dimension}_next_due_at") <= now, ~blocked_queue, ~allocated)
        )
    return or_(*clauses)


def _core():
    from services import vocabulary_error_queue

    return vocabulary_error_queue


def _unallocated(user_id, day, model):
    return ~exists().where(
        Allocation.student_id == user_id,
        Allocation.local_date == day,
        Allocation.sense_id == model.sense_id,
        Allocation.dimension == model.dimension,
    )


def planning(user, enrollment, now, *, cleanup=False):
    core = _core()
    day, cohort, settings = core.local_date(now), core._cohort(enrollment), core.policy_settings()
    slots = core._slots(user.id, day)
    mandatory = [row for row in slots if row.mode == "mandatory"]
    optional = [row for row in slots if row.mode == "maintenance"]
    remaining = max(0, settings["daily_limit"] - len(mandatory))
    sample_left = max(0, settings["sample_limit"] - sum(row.kind == "sample" for row in mandatory))
    base = Queue.query.filter_by(student_id=user.id, cohort_key=cohort)
    paused_due = and_(Queue.status == "paused", Queue.pause_until_local_date <= day)
    due = base.filter(
        _unallocated(user.id, day, Queue),
        or_(and_(Queue.status == "active", Queue.due_local_date <= day), paused_due),
    )
    blocked_sample = exists().where(
        Queue.student_id == user.id,
        Queue.cohort_key == cohort,
        Queue.sense_id == Checkpoint.sense_id,
        Queue.dimension == Checkpoint.dimension,
        Queue.status.in_(("active", "paused")),
    )
    # Distinct source opportunities may land on one ability/date. Allocate one
    # stable opportunity; an answer must never count for two origins.
    ranked = (
        db.session.query(
            Checkpoint.id.label("id"),
            func.row_number()
            .over(
                partition_by=(Checkpoint.sense_id, Checkpoint.dimension),
                order_by=(Checkpoint.selection_key, Checkpoint.id),
            )
            .label("ability_rank"),
        )
        .filter(
            Checkpoint.student_id == user.id,
            Checkpoint.cohort_key == cohort,
            Checkpoint.status == "pending",
            Checkpoint.due_local_date == day,
            _unallocated(user.id, day, Checkpoint),
            ~blocked_sample,
        )
        .subquery()
    )
    checkpoints = Checkpoint.query.join(ranked, ranked.c.id == Checkpoint.id).filter(
        ranked.c.ability_rank == 1
    )
    sample_count = checkpoints.count()
    chosen_samples = (
        checkpoints.order_by(Checkpoint.selection_key, Checkpoint.id)
        .limit(min(sample_left, remaining, BATCH_LIMIT))
        .all()
    )
    error_capacity = max(0, remaining - len(chosen_samples))
    due_count = due.count()
    overloaded = due_count > error_capacity
    overdue = and_(
        Queue.status == "active",
        Queue.due_local_date < day - timedelta(days=settings["overdue_days"]),
    )
    transfer_query = due.filter(overdue)
    transfer_count = transfer_query.count() if overloaded else 0
    eligible_due = due.filter(~overdue) if overloaded else due
    selected_errors = (
        eligible_due.order_by(
            case((or_(paused_due, Queue.due_local_date == day), 0), else_=1),
            case((paused_due, day), else_=Queue.due_local_date),
            Queue.opened_at,
            Queue.id,
        )
        .limit(min(error_capacity, BATCH_LIMIT - len(chosen_samples)))
        .all()
    )
    entries = [core._entry(checkpoint=row) for row in chosen_samples] + [
        core._entry(queue=row) for row in selected_errors
    ]
    for entry in entries:
        if entry["due_local_date"] > day:
            entry["due_local_date"] = day
    pending = sum(row.status == "reserved" for row in mandatory)
    completed = sum(row.status in {"answered", "skipped"} for row in mandatory)
    actionable = len(chosen_samples) + min(error_capacity, due_count - transfer_count)
    transferred_today = Event.query.filter_by(
        student_id=user.id, local_date=day, kind="overdue_overload"
    ).count()
    counts = {
        "enabled": True,
        "mandatory_remaining": pending + actionable,
        "mandatory_answered": completed,
        "mandatory_limit": settings["daily_limit"],
        "sample_reserved_limit": settings["sample_limit"],
        "maintenance_remaining": max(0, settings["maintenance_limit"] - len(optional)),
        "maintenance_limit": settings["maintenance_limit"],
        "batch_limit": BATCH_LIMIT,
        "error_due_count": due_count,
        "sample_due_count": sample_count,
        "overloaded": overloaded,
        "overload_count": max(0, due_count - error_capacity),
        "overdue_transferred_count": transferred_today + transfer_count,
        "overdue_transferred_today": transferred_today,
        "overdue_transfer_pending_count": transfer_count,
        "paused_count": base.filter(
            Queue.status == "paused", Queue.pause_until_local_date > day
        ).count(),
        "maintenance_count": base.filter(Queue.status == "maintenance").count(),
        "due_count": pending + actionable,
        "required_count": pending + actionable,
        "completed_count": completed,
        "daily_limit": settings["daily_limit"],
        "reviewed_today": completed,
        "checkup_due_count": sample_count,
    }
    transfer_ids = (
        [
            row[0]
            for row in transfer_query.with_entities(Queue.id)
            .order_by(Queue.id)
            .limit(CLEANUP_LIMIT)
        ]
        if cleanup and overloaded
        else []
    )
    missed_ids = (
        [
            row[0]
            for row in db.session.query(Checkpoint.id)
            .filter(
                Checkpoint.student_id == user.id,
                Checkpoint.cohort_key == cohort,
                Checkpoint.status == "pending",
                Checkpoint.due_local_date < day,
            )
            .order_by(Checkpoint.due_local_date, Checkpoint.id)
            .limit(CLEANUP_LIMIT - len(transfer_ids))
        ]
        if cleanup
        else []
    )
    return {
        "summary": counts,
        "entries": entries,
        "slots": slots,
        "enrollment_version": int(enrollment.state_version),
        "cohort": cohort,
        "day": day,
        "transfer_ids": transfer_ids,
        "missed_checkpoint_ids": missed_ids,
        "paused_ids": [row.id for row in selected_errors if row.status == "paused"],
    }


def after_claim_summary(planned, entries, optional, unusable=()):
    """Project only this transaction's finite changes without another scan."""
    result = dict(planned["summary"])
    slots = planned["slots"]
    mandatory = [row for row in slots if row.mode == "mandatory"]
    selected = [] if optional else entries
    used = len(mandatory) + len(selected)
    remaining = max(0, result["mandatory_limit"] - used)
    sample_left = max(
        0,
        result["sample_reserved_limit"]
        - sum(row.kind == "sample" for row in mandatory)
        - sum(entry["kind"] == "sample" for entry in selected),
    )
    bad_errors = sum(entry["kind"] == "error" for entry in unusable)
    bad_samples = sum(entry["kind"] == "sample" for entry in unusable)
    sample_due = max(
        0,
        result["sample_due_count"]
        - bad_samples
        - sum(entry["kind"] == "sample" for entry in selected),
    )
    error_due = max(
        0,
        result["error_due_count"]
        - result["overdue_transfer_pending_count"]
        - bad_errors
        - sum(entry["kind"] == "error" for entry in selected),
    )
    samples = min(sample_left, sample_due, remaining)
    pending = sum(row.status == "reserved" for row in mandatory) + len(selected)
    result["mandatory_remaining"] = pending + samples + min(error_due, remaining - samples)
    result["maintenance_remaining"] = max(
        0, result["maintenance_remaining"] - (len(entries) if optional else 0)
    )
    transferred = len(planned["transfer_ids"])
    result["overdue_transferred_today"] += transferred
    result["overdue_transfer_pending_count"] -= transferred
    result["maintenance_count"] += transferred + bad_errors
    return result


def housekeeping(user, enrollment, now, planned):
    """Apply at most 100 preselected cleanup rows and this batch's pause resumes."""
    core = _core()
    day = core.local_date(now)
    for ids, kind, detail, values in (
        (
            planned["paused_ids"],
            "reopened",
            "pause_elapsed",
            {
                "status": "active",
                "due_local_date": day,
                "pause_until_local_date": None,
                "failure_streak": 0,
                "success_count": 0,
                "last_success_local_date": None,
            },
        ),
        (
            planned["transfer_ids"],
            "overdue_overload",
            "overdue_overload",
            {
                "status": "maintenance",
                "closed_at": now,
                "closed_reason": "overdue_overload",
            },
        ),
    ):
        if not ids:
            continue
        condition = and_(
            Queue.student_id == user.id,
            Queue.cohort_key == core._cohort(enrollment),
            Queue.id.in_(ids),
        )
        source_key = (
            literal("transition:")
            + cast(Queue.id, String)
            + literal(":")
            + cast(Queue.version + 1, String)
            + literal(":" + kind)
        )
        db.session.execute(
            insert(Event).from_select(
                [
                    "student_id",
                    "source_key",
                    "queue_id",
                    "sense_id",
                    "dimension",
                    "kind",
                    "source",
                    "occurred_at",
                    "local_date",
                    "detail_code",
                    "created_at",
                    "updated_at",
                ],
                select(
                    Queue.student_id,
                    source_key,
                    Queue.id,
                    Queue.sense_id,
                    Queue.dimension,
                    literal(kind),
                    literal("system"),
                    literal(now),
                    literal(day),
                    literal(detail),
                    literal(now),
                    literal(now),
                ).where(condition),
            )
        )
        db.session.execute(
            update(Queue)
            .where(condition)
            .values(**values, version=Queue.version + 1)
            .execution_options(synchronize_session="fetch")
        )
    if planned["missed_checkpoint_ids"]:
        db.session.execute(
            update(Checkpoint)
            .where(
                Checkpoint.student_id == user.id,
                Checkpoint.id.in_(planned["missed_checkpoint_ids"]),
                Checkpoint.status == "pending",
                Checkpoint.due_local_date < day,
            )
            .values(status="missed")
            .execution_options(synchronize_session="fetch")
        )
    db.session.flush()
