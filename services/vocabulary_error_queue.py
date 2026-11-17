"""Opt-in error review policy, isolated from the legacy mastery scheduler.

All mutators participate in the caller's transaction and never commit. Read
planning does not mutate dates or import legacy mastery. The global OFF path
returns before querying any new table, including on an unmigrated database.
"""

from datetime import datetime, timedelta, timezone

from flask import current_app, has_app_context
from sqlalchemy import update

from models import (
    DictationWord,
    User,
    VocabularyErrorQueue,
    VocabularyPolicyAllocation,
    VocabularyPolicyCheckpoint,
    VocabularyPolicyEvent,
    VocabularyReviewItem,
    VocabularyReviewPolicyEnrollment,
    VocabularyReviewSession,
    db,
)
from services.vocabulary_checkpoint_identity import checkpoint_selection_key

DIMENSIONS = frozenset(("meaning_recall", "form_recall", "audio_form_recall", "context_use"))
FEATURE_FLAG = "VOCABULARY_ERROR_REVIEW_ENABLED"
DAILY_LIMIT = 20
SAMPLE_LIMIT = 4
MAINTENANCE_LIMIT = 10
SUCCESS_INTERVAL_DAYS = 2
FAILURE_LIMIT = 3
PAUSE_DAYS = 7
OVERDUE_DAYS = 7


def policy_settings():
    """Validated knobs, evaluated only on opt-in paths (OFF does no policy work)."""
    defaults = {
        "DAILY_LIMIT": DAILY_LIMIT,
        "SAMPLE_LIMIT": SAMPLE_LIMIT,
        "MAINTENANCE_LIMIT": MAINTENANCE_LIMIT,
        "SUCCESS_INTERVAL_DAYS": SUCCESS_INTERVAL_DAYS,
        "FAILURE_LIMIT": FAILURE_LIMIT,
        "PAUSE_DAYS": PAUSE_DAYS,
        "OVERDUE_DAYS": OVERDUE_DAYS,
    }
    values = {}
    for name, default in defaults.items():
        key = f"VOCABULARY_ERROR_REVIEW_{name}"
        value = current_app.config.get(key, default)
        # Do not truncate floats or interpret booleans as integer capacities.
        if isinstance(value, bool) or not isinstance(value, (int, str)):
            raise ValueError(f"invalid_policy_config:{key}")
        try:
            parsed = int(value)
        except (ValueError, TypeError) as error:
            raise ValueError(f"invalid_policy_config:{key}") from error
        minimum = 0 if name == "SAMPLE_LIMIT" else 1
        if parsed < minimum:
            raise ValueError(f"invalid_policy_config:{key}")
        values[name.lower()] = parsed
    if values["sample_limit"] > values["daily_limit"]:
        raise ValueError("policy_sample_limit_exceeds_daily_limit")
    return values


class PolicyConflict(ValueError):
    status_code = 409
    error = "review_policy_changed"


def utc_naive(now=None):
    now = now or datetime.now(timezone.utc)  # noqa: UP017 - production Python 3.10
    return now.astimezone(timezone.utc).replace(tzinfo=None) if now.tzinfo else now  # noqa: UP017


def local_date(now=None):
    return (utc_naive(now) + timedelta(hours=8)).date()


def _cohort(enrollment):
    return utc_naive(enrollment.starts_at).strftime("%Y%m%dT%H%M%S.%f")


def enabled_for(user, now=None):
    if not has_app_context() or not current_app.config.get(FEATURE_FLAG, False):
        return None
    now = utc_naive(now)
    return (
        VocabularyReviewPolicyEnrollment.query.populate_existing()
        .filter_by(student_id=int(user.id), enabled=True)
        .filter(VocabularyReviewPolicyEnrollment.starts_at <= now)
        .first()
    )


def enroll_student(user, *, starts_at=None, now=None):
    """Management helper only: caller authorizes/apply/commits explicit enrollment."""
    now = utc_naive(now)
    starts_at = utc_naive(starts_at or now)
    if user.role != User.ROLE_STUDENT or not user.is_active:
        raise ValueError("student_not_active")
    existing = db.session.get(VocabularyReviewPolicyEnrollment, int(user.id))
    if existing:
        if utc_naive(existing.starts_at) != starts_at:
            raise PolicyConflict("enrollment_cohort_cannot_be_replaced")
        db.session.execute(
            update(VocabularyReviewPolicyEnrollment)
            .where(VocabularyReviewPolicyEnrollment.student_id == user.id)
            .values(state_version=VocabularyReviewPolicyEnrollment.state_version + 1)
            .execution_options(synchronize_session=False)
        )
        if VocabularyReviewSession.query.filter_by(student_id=user.id, status="active").first():
            raise PolicyConflict("active_review_must_finish_before_enrollment")
        existing.enabled = True
        return existing
    enrollment = VocabularyReviewPolicyEnrollment(
        student_id=user.id, enabled=False, starts_at=starts_at, state_version=0
    )
    db.session.add(enrollment)
    # Obtain a DB writer before checking legacy sessions. Otherwise a claim
    # could commit after the precheck and leave an active legacy batch at opt-in.
    db.session.flush()
    if VocabularyReviewSession.query.filter_by(student_id=user.id, status="active").first():
        raise PolicyConflict("active_review_must_finish_before_enrollment")
    enrollment.enabled = True
    db.session.flush()
    return enrollment


def _lock_enrollment(user, now):
    # SQLite serializes writes here; subsequent fresh reads cannot race another
    # policy writer. PostgreSQL also locks this one enrollment row.
    changed = db.session.execute(
        update(VocabularyReviewPolicyEnrollment)
        .where(
            VocabularyReviewPolicyEnrollment.student_id == user.id,
            VocabularyReviewPolicyEnrollment.enabled.is_(True),
            VocabularyReviewPolicyEnrollment.starts_at <= now,
        )
        .values(state_version=VocabularyReviewPolicyEnrollment.state_version + 1)
        .execution_options(synchronize_session=False)
    )
    if changed.rowcount != 1:
        raise PolicyConflict("enrollment_changed")
    return (
        VocabularyReviewPolicyEnrollment.query.populate_existing()
        .filter_by(student_id=user.id, enabled=True)
        .one()
    )


def _key(sense_id, dimension):
    if dimension not in DIMENSIONS or int(sense_id) <= 0:
        raise ValueError("invalid_policy_ability")
    return int(sense_id), dimension


def _source_key(value):
    if not isinstance(value, str) or not value.strip() or len(value) > 192:
        raise ValueError("invalid_policy_source_key")
    return value


def _event(
    user_id,
    source_key,
    *,
    now,
    kind,
    source,
    queue=None,
    checkpoint=None,
    correct=None,
    detail=None,
    allocation=None,
    sense_id=None,
    dimension=None,
):
    ability = queue or checkpoint or allocation
    event = VocabularyPolicyEvent(
        student_id=user_id,
        source_key=_source_key(source_key),
        queue_id=queue.id if queue else None,
        checkpoint_id=checkpoint.id if checkpoint else None,
        allocation_id=allocation.id if allocation else None,
        sense_id=ability.sense_id if ability else sense_id,
        dimension=ability.dimension if ability else dimension,
        kind=kind,
        source=source,
        occurred_at=now,
        local_date=local_date(now),
        is_correct=correct,
        detail_code=detail,
    )
    db.session.add(event)
    return event


def _transition(queue, kind, now, detail=None):
    queue.version += 1
    return _event(
        queue.student_id,
        f"transition:{queue.id}:{queue.version}:{kind}",
        now=now,
        kind=kind,
        source="system",
        queue=queue,
        detail=detail,
    )


def _queue(user_id, sense_id, dimension):
    return (
        VocabularyErrorQueue.query.populate_existing()
        .filter_by(student_id=user_id, sense_id=sense_id, dimension=dimension)
        .first()
    )


def _word_id(word_id, sense_id):
    if word_id is None:
        return None
    word = db.session.get(DictationWord, int(word_id))
    if word is None or word.sense_id != sense_id:
        raise ValueError("policy_word_sense_mismatch")
    return word.id


def _open_error(
    user, enrollment, sense_id, dimension, word_id, now, *, reset_source="learning_error"
):
    day = local_date(now)
    queue = _queue(user.id, sense_id, dimension)
    new_cycle = (
        queue is None
        or queue.cohort_key != _cohort(enrollment)
        or queue.status in {"closed", "maintenance"}
    )
    resets_progress = (
        queue is not None and not new_cycle and queue.status == "active" and queue.success_count > 0
    )
    if queue is None:
        queue = VocabularyErrorQueue(
            student_id=user.id,
            sense_id=sense_id,
            dimension=dimension,
            cohort_key=_cohort(enrollment),
            status="active",
            due_local_date=day + timedelta(days=1),
            success_count=0,
            failure_streak=0,
            version=0,
            opened_at=now,
        )
        db.session.add(queue)
        db.session.flush()
    if new_cycle:
        queue.cohort_key = _cohort(enrollment)
        queue.opened_at = now
        queue.failure_streak = 0
        queue.last_attempt_local_date = None
        queue.status = "active"
        queue.pause_until_local_date = None
        queue.closed_at = None
        queue.closed_reason = None
        _transition(queue, "reopened", now, "new_error")
    if word_id is not None:
        queue.representative_word_id = _word_id(word_id, sense_id)
    if resets_progress:
        _transition(queue, "success_reset", now, reset_source)
    queue.success_count = 0
    queue.last_success_local_date = None
    # A new learning error does not bypass the seven-day teaching pause.
    if queue.status != "paused":
        queue.due_local_date = day + timedelta(days=1)
    queue.version += 1
    return queue


def _schedule_checkpoints(user, enrollment, sense_id, dimension, word_id, now):
    if VocabularyPolicyCheckpoint.query.filter_by(
        student_id=user.id,
        sense_id=sense_id,
        dimension=dimension,
        cohort_key=_cohort(enrollment),
        source_kind="first_correct",
        source_key="initial",
    ).first():
        return
    representative_word_id = _word_id(word_id, sense_id)
    for interval in (7, 30):
        db.session.add(
            VocabularyPolicyCheckpoint(
                student_id=user.id,
                sense_id=sense_id,
                dimension=dimension,
                cohort_key=_cohort(enrollment),
                representative_word_id=representative_word_id,
                source_kind="first_correct",
                source_key="initial",
                anchor_at=now,
                interval_days=interval,
                due_local_date=local_date(now) + timedelta(days=interval),
                status="pending",
            )
        )


def _schedule_graduation_checkpoint(user, enrollment, queue, closed_event, now):
    """One D7 opportunity per real graduation; no historical reconstruction."""
    db.session.flush()  # The closed event is the stable per-cycle provenance.
    source_key = f"graduation:{closed_event.id}"
    existing = VocabularyPolicyCheckpoint.query.filter_by(
        student_id=user.id,
        sense_id=queue.sense_id,
        dimension=queue.dimension,
        cohort_key=_cohort(enrollment),
        source_kind="graduation",
        source_key=source_key,
        interval_days=7,
    ).first()
    if existing:
        return existing
    checkpoint = VocabularyPolicyCheckpoint(
        student_id=user.id,
        sense_id=queue.sense_id,
        dimension=queue.dimension,
        cohort_key=_cohort(enrollment),
        representative_word_id=queue.representative_word_id,
        source_kind="graduation",
        source_key=source_key,
        origin_event_id=closed_event.id,
        anchor_at=now,
        interval_days=7,
        due_local_date=local_date(now) + timedelta(days=7),
        status="pending",
    )
    db.session.add(checkpoint)
    return checkpoint


def record_learning_answer(
    user,
    *,
    sense_id,
    dimension,
    correct,
    source_key,
    now=None,
    word_id=None,
    first_attempt=True,
    response_kind="answer",
):
    enrollment = enabled_for(user, now)
    if enrollment is None or not first_attempt:
        return None
    now = utc_naive(now)
    sense_id, dimension = _key(sense_id, dimension)
    source_key = _source_key(source_key)
    if response_kind not in {"answer", "forgot"}:
        raise ValueError("invalid_policy_response")
    enrollment = _lock_enrollment(user, now)
    prior = VocabularyPolicyEvent.query.filter_by(student_id=user.id, source_key=source_key).first()
    if prior:
        if prior.source != "learning" or (prior.sense_id, prior.dimension) != (sense_id, dimension):
            raise PolicyConflict("policy_source_key_reused")
        return {"idempotent": True, "event_id": prior.id}
    correct = bool(correct) and response_kind != "forgot"
    queue = _queue(user.id, sense_id, dimension)
    if not correct:
        queue = _open_error(user, enrollment, sense_id, dimension, word_id, now)
    elif queue is None or queue.cohort_key != _cohort(enrollment):
        _schedule_checkpoints(user, enrollment, sense_id, dimension, word_id, now)
    event = _event(
        user.id,
        source_key,
        now=now,
        kind="answer",
        source="learning",
        queue=queue,
        correct=correct,
        detail="forgot" if response_kind == "forgot" else "formal_first",
        sense_id=sense_id,
        dimension=dimension,
    )
    db.session.flush()
    return {"idempotent": False, "event_id": event.id}


def _entry(queue=None, checkpoint=None):
    row = queue or checkpoint
    return {
        "queue_id": queue.id if queue else None,
        "checkpoint_id": checkpoint.id if checkpoint else None,
        "sense_id": row.sense_id,
        "dimension": row.dimension,
        "word_id": row.representative_word_id,
        "kind": (
            ("maintenance" if queue.status == "maintenance" else "error") if queue else "sample"
        ),
        "version": queue.version if queue else None,
        "due_local_date": row.due_local_date,
    }


def _stable_sample(row):
    return row.selection_key or checkpoint_selection_key(
        row.student_id,
        row.cohort_key,
        row.sense_id,
        row.dimension,
        row.interval_days,
        row.source_kind,
        row.source_key,
    )


def _slots(user_id, day):
    return (
        VocabularyPolicyAllocation.query.populate_existing()
        .filter_by(student_id=user_id, local_date=day)
        .order_by(VocabularyPolicyAllocation.id)
        .all()
    )


def _planning(user, enrollment, now, *, cleanup=False):
    from services.vocabulary_policy_planning import planning

    return planning(user, enrollment, now, cleanup=cleanup)


def summary(user, now=None):
    enrollment = enabled_for(user, now)
    if enrollment is None:
        return {"enabled": False}
    return _planning(user, enrollment, utc_naive(now))["summary"]


def plan_today(user, *, now=None, optional=False, prepare=False):
    enrollment = enabled_for(user, now)
    if enrollment is None:
        return {"enabled": False, "entries": []}
    now = utc_naive(now)
    planned = _planning(user, enrollment, now, cleanup=prepare)
    entries = planned["entries"]
    if optional:
        used = {(row.sense_id, row.dimension) for row in planned["slots"]}
        rows = (
            VocabularyErrorQueue.query.populate_existing()
            .filter_by(student_id=user.id, cohort_key=_cohort(enrollment), status="maintenance")
            .filter(VocabularyErrorQueue.due_local_date <= local_date(now))
            .order_by(VocabularyErrorQueue.due_local_date, VocabularyErrorQueue.id)
            .limit(min(20, planned["summary"]["maintenance_limit"]) + len(used))
            .all()
        )
        entries = [_entry(queue=row) for row in rows if (row.sense_id, row.dimension) not in used][
            : min(20, planned["summary"]["maintenance_remaining"])
        ]
    result = {**planned["summary"], "entries": entries, "optional": bool(optional)}
    if prepare:
        result["_reservation_plan"] = planned
    return result


def _housekeeping(user, enrollment, now, planned):
    from services.vocabulary_policy_planning import housekeeping

    housekeeping(user, enrollment, now, planned)


def refresh_day(user, *, now=None, prepared_plan=None, unusable_entries=()):
    """Persist one bounded pre-read cleanup batch; never scan under the writer."""
    enrollment = enabled_for(user, now)
    if enrollment is None:
        return {"enabled": False}
    now = utc_naive(now)
    planned = prepared_plan or _planning(user, enrollment, now, cleanup=True)
    enrollment = _lock_enrollment(user, now)
    if enrollment.state_version != planned["enrollment_version"] + 1:
        raise PolicyConflict("policy_plan_changed")
    if unusable_entries:
        defer_unusable_entries(user, unusable_entries, now=now)
        invalid_ids = {entry.get("queue_id") for entry in unusable_entries}
        planned = dict(
            planned,
            paused_ids=[value for value in planned["paused_ids"] if value not in invalid_ids],
            transfer_ids=[value for value in planned["transfer_ids"] if value not in invalid_ids],
        )
    _housekeeping(user, enrollment, now, planned)
    from services.vocabulary_policy_planning import after_claim_summary

    return after_claim_summary(planned, [], False, unusable_entries)


def optional_candidate_allowed(user, sense_id, dimension, *, now=None):
    enrollment = enabled_for(user, now)
    if enrollment is None:
        return False
    sense_id, dimension = _key(sense_id, dimension)
    queue = _queue(user.id, sense_id, dimension)
    if queue and queue.cohort_key == _cohort(enrollment) and queue.status in {"active", "paused"}:
        return False
    return not VocabularyPolicyAllocation.query.filter_by(
        student_id=user.id, local_date=local_date(now), sense_id=sense_id, dimension=dimension
    ).first()


def _identity(entry):
    return (
        entry.get("queue_id"),
        entry.get("checkpoint_id"),
        int(entry["sense_id"]),
        entry["dimension"],
        entry["kind"],
    )


def reserve_items(
    user, session_id, items, *, now=None, optional=False, prepared_plan=None, unusable_entries=()
):
    enrollment = enabled_for(user, now)
    if enrollment is None:
        raise PolicyConflict("policy_not_enabled")
    now = utc_naive(now)
    planned = prepared_plan or _planning(user, enrollment, now, cleanup=True)
    enrollment = _lock_enrollment(user, now)
    session = db.session.get(VocabularyReviewSession, int(session_id))
    if session is None or session.student_id != user.id or session.status != "active":
        raise PolicyConflict("review_session_changed")
    mode = "maintenance" if optional else "mandatory"
    existing = VocabularyPolicyAllocation.query.filter_by(
        student_id=user.id, session_id=session.id
    ).all()
    if existing:
        if {row.item_id for row in existing} == {int(item["item_id"]) for item in items} and all(
            row.mode == mode for row in existing
        ):
            return existing
        raise PolicyConflict("session_already_bound")
    if enrollment.state_version != planned["enrollment_version"] + 1:
        raise PolicyConflict("policy_plan_changed")
    candidates = {_identity(entry): entry for entry in planned["entries"]}
    limit = planned["summary"]["maintenance_limit" if optional else "mandatory_limit"]
    used = [row for row in planned["slots"] if row.mode == mode]
    if len(items) > 20 or len(items) + len(used) > limit:
        raise PolicyConflict("daily_policy_capacity_changed")
    supplied = set()
    for item in items:
        entry = item["entry"]
        identity = _identity(entry)
        if identity in supplied:
            raise PolicyConflict("duplicate_policy_ability")
        supplied.add(identity)
        stored = db.session.get(VocabularyReviewItem, int(item["item_id"]))
        if (
            stored is None
            or stored.student_id != user.id
            or stored.session_id != session.id
            or stored.sense_id != int(entry["sense_id"])
            or stored.dimension != entry["dimension"]
        ):
            raise PolicyConflict("review_item_changed")
        if optional:
            if entry["kind"] != "maintenance" or not optional_candidate_allowed(
                user, entry["sense_id"], entry["dimension"], now=now
            ):
                raise PolicyConflict("maintenance_candidate_changed")
            if entry.get("checkpoint_id") is not None:
                raise PolicyConflict("maintenance_checkpoint_not_allowed")
            if entry.get("queue_id") is not None:
                queue = _queue(user.id, int(entry["sense_id"]), entry["dimension"])
                if (
                    queue is None
                    or queue.id != entry["queue_id"]
                    or queue.cohort_key != _cohort(enrollment)
                    or queue.status != "maintenance"
                    or queue.version != entry.get("version")
                ):
                    raise PolicyConflict("maintenance_queue_changed")
        elif identity not in candidates or candidates[identity]["version"] != entry.get("version"):
            raise PolicyConflict("policy_candidate_changed")
    # Validate against pre-housekeeping versions, then persist transitions in
    # this same outer transaction. Slot references survive paused resumption.
    if unusable_entries:
        defer_unusable_entries(user, unusable_entries, now=now)
        invalid_ids = {entry.get("queue_id") for entry in unusable_entries}
        planned = dict(
            planned,
            paused_ids=[value for value in planned["paused_ids"] if value not in invalid_ids],
            transfer_ids=[value for value in planned["transfer_ids"] if value not in invalid_ids],
        )
    _housekeeping(user, enrollment, now, planned)
    ordinal = max((row.ordinal for row in used), default=0)
    allocations = []
    for supplied_item in items:
        ordinal += 1
        entry = supplied_item["entry"]
        allocation = VocabularyPolicyAllocation(
            student_id=user.id,
            local_date=local_date(now),
            mode=mode,
            ordinal=ordinal,
            kind=entry["kind"],
            queue_id=entry.get("queue_id"),
            checkpoint_id=entry.get("checkpoint_id"),
            session_id=session.id,
            item_id=int(supplied_item["item_id"]),
            sense_id=int(entry["sense_id"]),
            dimension=entry["dimension"],
            status="reserved",
        )
        db.session.add(allocation)
        allocations.append(allocation)
    db.session.flush()
    return allocations


def _apply_error_review(queue, correct, now):
    day = local_date(now)
    settings = policy_settings()
    # Another ongoing task can record a fresh error after this slot was issued.
    # Keep the real answer/slot completion, but never treat same-day practice
    # after that error as the scheduled independent next-day assessment.
    if queue.last_attempt_local_date == day or queue.due_local_date > day:
        return
    queue.last_attempt_local_date = day
    closed_event = None
    if correct:
        queue.failure_streak = 0
        if queue.last_success_local_date is None:
            queue.success_count = 1
            queue.last_success_local_date = day
            queue.due_local_date = day + timedelta(days=settings["success_interval_days"])
        elif (day - queue.last_success_local_date).days >= settings["success_interval_days"]:
            queue.success_count += 1
            queue.last_success_local_date = day
            if queue.success_count >= 2:
                queue.status = "closed"
                queue.closed_at = now
                queue.closed_reason = "two_delayed_successes"
                closed_event = _transition(queue, "closed", now, "two_delayed_successes")
            else:
                queue.due_local_date = day + timedelta(days=settings["success_interval_days"])
        # Early formal successes are retained as answer events but do not
        # advance the two-day criterion or postpone the original due date.
    else:
        if queue.success_count > 0:
            _transition(queue, "success_reset", now, "review_error")
        queue.success_count = 0
        queue.last_success_local_date = None
        queue.failure_streak += 1
        queue.due_local_date = day + timedelta(days=1)
        if queue.failure_streak >= settings["failure_limit"]:
            queue.status = "paused"
            queue.pause_until_local_date = day + timedelta(days=settings["pause_days"])
            queue.due_local_date = queue.pause_until_local_date
            _transition(queue, "paused", now, "consecutive_review_failures")
    queue.version += 1
    return closed_event


def apply_review_answer(user, *, item_id, correct, source_key, now=None, response_kind="answer"):
    enrollment = enabled_for(user, now)
    if enrollment is None:
        return None
    now = utc_naive(now)
    _lock_enrollment(user, now)
    source_key = _source_key(source_key)
    allocation = (
        VocabularyPolicyAllocation.query.populate_existing()
        .filter_by(student_id=user.id, item_id=int(item_id))
        .first()
    )
    if allocation is None:
        return None  # Old, already-issued session; activation normally refuses these.
    prior = VocabularyPolicyEvent.query.filter_by(student_id=user.id, source_key=source_key).first()
    if prior:
        if prior.source != "review" or prior.allocation_id != allocation.id:
            raise PolicyConflict("policy_source_key_reused")
        return {"idempotent": True, "event_id": prior.id}
    if allocation.local_date != local_date(now):
        raise PolicyConflict("policy_review_day_expired")
    if allocation.status != "reserved":
        return {"idempotent": True, "allocation_id": allocation.id}
    if response_kind not in {"answer", "forgot"}:
        raise ValueError("invalid_policy_response")
    correct = bool(correct) and response_kind != "forgot"
    queue = (
        db.session.get(VocabularyErrorQueue, allocation.queue_id, populate_existing=True)
        if allocation.queue_id
        else None
    )
    checkpoint = (
        db.session.get(VocabularyPolicyCheckpoint, allocation.checkpoint_id, populate_existing=True)
        if allocation.checkpoint_id
        else None
    )
    if queue is not None and (
        queue.student_id != user.id
        or (queue.sense_id, queue.dimension) != (allocation.sense_id, allocation.dimension)
    ):
        raise PolicyConflict("policy_queue_owner_changed")
    if checkpoint is not None and (
        checkpoint.student_id != user.id
        or (checkpoint.sense_id, checkpoint.dimension)
        != (allocation.sense_id, allocation.dimension)
    ):
        raise PolicyConflict("policy_checkpoint_owner_changed")
    if allocation.kind == "error":
        if queue is None or queue.cohort_key != _cohort(enrollment) or queue.status != "active":
            raise PolicyConflict("error_queue_changed")
        closed_event = _apply_error_review(queue, correct, now)
        if closed_event is not None:
            _schedule_graduation_checkpoint(user, enrollment, queue, closed_event, now)
    elif allocation.kind == "sample":
        if (
            checkpoint is None
            or checkpoint.status != "pending"
            or checkpoint.due_local_date != local_date(now)
        ):
            raise PolicyConflict("checkpoint_changed")
        checkpoint.status = "answered"
        if not correct:
            queue = _open_error(
                user,
                enrollment,
                allocation.sense_id,
                allocation.dimension,
                checkpoint.representative_word_id,
                now,
                reset_source="sample_error",
            )
    elif allocation.kind == "maintenance":
        if not correct:
            item = db.session.get(VocabularyReviewItem, allocation.item_id)
            queue = _open_error(
                user,
                enrollment,
                allocation.sense_id,
                allocation.dimension,
                item.word_id if item else None,
                now,
                reset_source="maintenance_error",
            )
        elif queue is not None and queue.status == "maintenance":
            queue.status = "closed"
            queue.closed_at = now
            queue.closed_reason = "maintenance_answered"
            _transition(queue, "closed", now, "maintenance_answered")
    else:
        raise PolicyConflict("unknown_policy_allocation")
    allocation.status = "answered"
    allocation.answered_at = now
    event = _event(
        user.id,
        source_key,
        now=now,
        kind="answer",
        source="review",
        queue=queue,
        checkpoint=checkpoint,
        correct=correct,
        allocation=allocation,
        detail="forgot" if response_kind == "forgot" else allocation.kind,
    )
    db.session.flush()
    return {"idempotent": False, "event_id": event.id, "allocation_id": allocation.id}


def defer_unusable_entries(user, entries, *, now=None, reason="unanswerable"):
    enrollment = enabled_for(user, now)
    if enrollment is None:
        return 0
    settings = policy_settings()
    if reason != "unanswerable" or len(entries) > max(
        settings["daily_limit"], settings["maintenance_limit"]
    ):
        raise ValueError("invalid_policy_deferral")
    now = utc_naive(now)
    _lock_enrollment(user, now)
    changed = 0
    for entry in entries:
        if entry.get("queue_id"):
            queue = _queue(user.id, int(entry["sense_id"]), entry["dimension"])
            if (
                queue
                and queue.id == entry["queue_id"]
                and queue.cohort_key == _cohort(enrollment)
                and queue.status in {"active", "paused"}
            ):
                if entry.get("version") != queue.version:
                    raise PolicyConflict("policy_candidate_changed")
                queue.status = "maintenance"
                queue.closed_at = now
                queue.closed_reason = reason
                _transition(queue, "unanswerable", now, reason)
                changed += 1
        elif entry.get("checkpoint_id"):
            checkpoint = db.session.get(VocabularyPolicyCheckpoint, int(entry["checkpoint_id"]))
            if (
                checkpoint
                and checkpoint.student_id == user.id
                and checkpoint.cohort_key == _cohort(enrollment)
                and (checkpoint.sense_id, checkpoint.dimension)
                == (int(entry["sense_id"]), entry["dimension"])
                and checkpoint.status == "pending"
            ):
                checkpoint.status = "missed"
                _event(
                    user.id,
                    f"unanswerable:checkpoint:{checkpoint.id}",
                    now=now,
                    kind="unanswerable",
                    source="system",
                    checkpoint=checkpoint,
                    detail=reason,
                )
                changed += 1
    db.session.flush()
    return changed


def mark_skipped(user, *, item_ids, now=None):
    if enabled_for(user, now) is None:
        return 0
    now = utc_naive(now)
    _lock_enrollment(user, now)
    rows = VocabularyPolicyAllocation.query.filter(
        VocabularyPolicyAllocation.student_id == user.id,
        VocabularyPolicyAllocation.item_id.in_([int(value) for value in item_ids]),
    ).all()
    changed = 0
    for row in rows:
        if row.status != "reserved":
            continue
        if row.local_date != local_date(now):
            raise PolicyConflict("policy_review_day_expired")
        entry = {
            "queue_id": None,
            "checkpoint_id": row.checkpoint_id,
            "sense_id": row.sense_id,
            "dimension": row.dimension,
        }
        if row.queue_id:
            queue = _queue(user.id, row.sense_id, row.dimension)
            # A newer task error may have rescheduled this ability after the
            # frozen slot was issued. Skipping that old bad question must not
            # downgrade the newer future-due error cycle.
            if queue and queue.id == row.queue_id and queue.due_local_date <= local_date(now):
                entry["queue_id"] = queue.id
                entry["version"] = queue.version
        defer_unusable_entries(user, [entry], now=now)
        row.status = "skipped"
        row.answered_at = now
        changed += 1
    db.session.flush()
    return changed
