"""Bridge the opt-in error policy to the existing frozen review protocol.

The original question builders, answer grading, correction and settlement
records remain authoritative. This module selects bounded policy allocations
and supplies policy counts without scanning the optional maintenance backlog.
"""

from __future__ import annotations

import json
import secrets
from contextlib import closing

from flask import current_app
from sqlalchemy.exc import IntegrityError, OperationalError

from models import (
    StudentVocabularyMastery,
    VocabularyErrorQueue,
    VocabularyLearningFlow,
    VocabularyPolicyAllocation,
    VocabularyReviewItem,
    VocabularyReviewSession,
    db,
)
from services.dictation_review import local_date
from services.task_date_gate import TaskDateGateError, assert_task_write_allowed
from services.vocabulary_mastery import _dimension_due, _dimension_stage, utc_naive


def _legacy():
    from services import vocabulary_autonomous_review

    return vocabulary_autonomous_review


def _policy():
    from services import vocabulary_error_queue

    return vocabulary_error_queue


def enabled(user, now=None):
    """Global OFF short-circuits before any new policy table is queried."""
    return _policy().enabled_for(user, now=now) is not None


def prepare_answer_write(error_class):
    """Keep first-answer SAVEPOINTs atomic with the later policy transition.

    Check the global flag, not an earlier enrollment snapshot: enrollment can
    change while an answer waits for its first write. OFF remains untouched.
    """
    if not current_app.config.get(_policy().FEATURE_FLAG, False):
        return
    try:
        _legacy()._begin_claim_outer_transaction()
    except (IntegrityError, OperationalError) as error:
        raise error_class("state_conflict", 409, retryable=True) from error


def _conflict(error):
    return _legacy().VocabularyAutonomousReviewError("review_policy_changed", 409, retryable=True)


def session_mode(user, session, now=None):
    if not enabled(user, now):
        return None
    allocation = (
        VocabularyPolicyAllocation.query.filter_by(student_id=user.id, session_id=session.id)
        .order_by(VocabularyPolicyAllocation.id.asc())
        .first()
    )
    return allocation.mode if allocation else None


def _public_summary(summary):
    remaining = max(0, int(summary.get("mandatory_remaining", 0)))
    maintenance_remaining = max(0, int(summary.get("maintenance_remaining", 0)))
    return {
        "policy_enabled": True,
        "policy_version": "error_queue_v1",
        "mandatory_remaining": remaining,
        "mandatory_answered": int(summary.get("mandatory_answered", 0)),
        "mandatory_limit": int(summary.get("mandatory_limit", 20)),
        "checkpoint_limit": int(summary.get("sample_reserved_limit", 4)),
        "maintenance_remaining": maintenance_remaining,
        "maintenance_limit": int(summary.get("maintenance_limit", 10)),
        # This is remaining optional capacity, not an exact old-pool count.
        "optional_available": maintenance_remaining > 0,
        "overloaded": bool(summary.get("overloaded", False)),
        "deferred_count": int(summary.get("overdue_transferred_count", 0)),
        "paused_count": int(summary.get("paused_count", 0)),
    }


def _active(user, now):
    return _legacy()._active_session_for_date(user.id, local_date(now))


def _pending_items(session):
    legacy = _legacy()
    return sum(
        item.first_attempt_id is None or legacy._correction_required(item) for item in session.items
    )


def review_summary(user, *, now=None):
    now = utc_naive(now)
    fields = _public_summary(_policy().summary(user, now=now))
    active = _active(user, now)
    mode = session_mode(user, active, now) if active else None
    mandatory_active = active if mode == "mandatory" else None
    optional_active = active if mode == "maintenance" else None
    if optional_active:
        # Reserved/answered slots already consumed the daily budget, but the
        # frozen batch still needs an entrance for correction and settlement.
        fields["optional_available"] = True
    due = fields["mandatory_remaining"]
    visible_due = max(1, _pending_items(mandatory_active), due) if mandatory_active else due
    return {
        "ok": True,
        **fields,
        "due_count": due,
        "review_due_count": visible_due,
        "batch_limit": fields["mandatory_limit"],
        "active_session_id": mandatory_active.id if mandatory_active else None,
        "active_session_token": mandatory_active.session_token if mandatory_active else None,
        "has_active_session": bool(mandatory_active),
        "optional_active_session_id": optional_active.id if optional_active else None,
        "optional_active_session_token": optional_active.session_token if optional_active else None,
    }


def review_preflight(user, task_id, *, now=None, gate_only=False):
    now = utc_naive(now)
    legacy = _legacy()
    task = legacy._validate_origin_task(user, task_id)
    started = (
        VocabularyLearningFlow.query.filter_by(student_id=user.id, task_id=task.id).first()
        is not None
    )
    # Preserve the old entry-only gate: a new error never interrupts a task.
    if gate_only and started:
        settings = _policy().policy_settings()
        return {
            "ok": True,
            "task_id": task.id,
            "required": False,
            "review_required": False,
            "task_flow_started": True,
            "due_count": None,
            "remaining_due_count": None,
            "batch_limit": settings["daily_limit"],
            "mandatory_limit": settings["daily_limit"],
            "checkpoint_limit": settings["sample_limit"],
            "maintenance_limit": settings["maintenance_limit"],
            "policy_enabled": True,
            "policy_version": "error_queue_v1",
            "origin_task_id": task.id,
            "active_session_id": None,
            "active_session_token": None,
            "clearance_session_id": None,
            "clearance_review_date": None,
        }
    summary = review_summary(user, now=now)
    required = bool(
        not started and (summary["mandatory_remaining"] or summary["has_active_session"])
    )
    return {
        **summary,
        "task_id": task.id,
        "required": required,
        "review_required": required,
        "task_flow_started": started,
        "remaining_due_count": summary["due_count"],
        "origin_task_id": task.id,
        "clearance_session_id": None,
        "clearance_review_date": local_date(now).isoformat() if not required else None,
    }


def session_due_counts(user, session, now):
    mode = session_mode(user, session, now)
    if not mode:
        return None
    summary = _policy().summary(user, now=now)
    unanswered = _pending_items(session)
    if mode == "maintenance":
        return unanswered, 0
    total = max(unanswered, int(summary.get("mandatory_remaining", 0)))
    return total, max(0, total - unanswered)


def decorate_session(user, session, payload, now):
    mode = session_mode(user, session, now)
    if mode:
        payload.update(_public_summary(_policy().summary(user, now=now)))
        payload["session_mode"] = mode
        if mode == "maintenance" and session.status == VocabularyReviewSession.STATUS_ACTIVE:
            payload["optional_available"] = True
    return payload


def _materialize_entries(user, entries, now, *, optional=False):
    legacy = _legacy()
    sense_ids = {entry["sense_id"] for entry in entries}
    masteries = (
        StudentVocabularyMastery.query.filter(
            StudentVocabularyMastery.student_id == user.id,
            StudentVocabularyMastery.sense_id.in_(sense_ids or {-1}),
        )
        .populate_existing()
        .all()
    )
    by_sense = {row.sense_id: row for row in masteries}
    words = legacy._bulk_representative_words(masteries)
    candidates, unusable = [], []
    catalog, availability = {}, {}
    for entry in entries:
        mastery = by_sense.get(entry["sense_id"])
        word = words.get(mastery.id) if mastery else None
        dimension = entry["dimension"]
        if (
            not mastery
            or not word
            or not legacy._candidate_is_eligible(word, mastery, dimension, catalog, availability)
        ):
            unusable.append(entry)
            continue
        due = _dimension_due(mastery, dimension)
        if optional and (due is None or due > now):
            continue
        candidates.append(
            {
                "word": word,
                "mastery": mastery,
                "dimension": dimension,
                "due_at": due or now,
                "stage": _dimension_stage(mastery, dimension),
                "remediation_kind": None,
                "policy_entry": entry,
            }
        )
    materialized = legacy._materialize_due_candidates(candidates, len(candidates))
    materialized_ids = {id(item["policy_entry"]) for item in materialized}
    unusable.extend(
        item["policy_entry"]
        for item in candidates
        if id(item["policy_entry"]) not in materialized_ids
    )
    return materialized, unusable


def _optional_candidates(user, now, plan):
    policy, legacy = _policy(), _legacy()
    capacity = max(0, int(plan.get("maintenance_remaining", 0)))
    candidates, unusable = _materialize_entries(user, plan.get("entries", []), now, optional=True)
    seen = {(item["mastery"].sense_id, item["dimension"]) for item in candidates}
    if len(candidates) < capacity:
        # One scalar snapshot for all candidate exclusions. The legacy iterator
        # can visit a large pool; per-candidate policy SQL would reintroduce an
        # N+1 path. reserve_items rechecks the final finite batch under its lock.
        enrollment = policy.enabled_for(user, now=now)
        if enrollment is None:
            raise _conflict(None)
        blocked = set(
            db.session.query(VocabularyErrorQueue.sense_id, VocabularyErrorQueue.dimension)
            .filter(
                VocabularyErrorQueue.student_id == user.id,
                VocabularyErrorQueue.cohort_key == policy._cohort(enrollment),
                VocabularyErrorQueue.status.in_(("active", "paused")),
            )
            .all()
        )
        blocked.update(
            db.session.query(
                VocabularyPolicyAllocation.sense_id, VocabularyPolicyAllocation.dimension
            )
            .filter_by(student_id=user.id, local_date=local_date(now))
            .all()
        )
        with closing(legacy._iter_due_candidates(user, now)) as old_candidates:
            for candidate in old_candidates:
                key = (candidate["mastery"].sense_id, candidate["dimension"])
                if key in seen or key in blocked:
                    continue
                candidate = {
                    name: candidate[name]
                    for name in ("word", "mastery", "dimension", "due_at", "stage")
                }
                candidate["remediation_kind"] = None
                candidate["policy_entry"] = {
                    "queue_id": None,
                    "checkpoint_id": None,
                    "sense_id": key[0],
                    "dimension": key[1],
                    "word_id": candidate["word"].id,
                    "kind": "maintenance",
                    "version": None,
                }
                materialized = legacy._materialize_due_candidates([candidate], 1)
                if materialized:
                    candidates.extend(materialized)
                    seen.add(key)
                if len(candidates) >= capacity:
                    break
    return candidates[:capacity], unusable


def _empty_payload(user, now, origin_task, optional):
    summary = _public_summary(_policy().summary(user, now=now))
    remaining = 0 if optional else summary["mandatory_remaining"]
    return {
        "ok": True,
        "supports_forgot_response": True,
        "empty": True,
        "status": "empty",
        "session_id": None,
        "origin_task_id": origin_task.id if origin_task else None,
        "total_count": 0,
        "due_count": remaining,
        "remaining_due_count": remaining,
        "continue_available": bool(remaining),
        "batch_limit": summary["maintenance_limit" if optional else "mandatory_limit"],
        "items": [],
        "words": [],
        **summary,
        "session_mode": "maintenance" if optional else "mandatory",
    }


def claim_today_review(user, *, origin_task_id=None, now=None, optional=False):
    legacy, policy = _legacy(), _policy()
    now = utc_naive(now)
    origin_task = legacy._validate_origin_task(user, origin_task_id)
    if origin_task:
        try:
            assert_task_write_allowed(origin_task, now)
        except TaskDateGateError as error:
            raise legacy.VocabularyAutonomousReviewError(
                error.error, error.status_code, message=error.message, **error.details
            ) from error
    active = _active(user, now)
    if active:
        mode = session_mode(user, active, now)
        if mode is None:
            raise legacy.VocabularyAutonomousReviewError("review_policy_transition_pending", 409)
        if mode != ("maintenance" if optional else "mandatory"):
            raise legacy.VocabularyAutonomousReviewError(
                "review_other_mode_active",
                409,
                session_mode=mode,
                active_session_id=active.id,
                active_session_token=active.session_token,
            )
        return legacy._session_payload(user, active, now)
    plan = policy.plan_today(user, now=now, optional=optional)
    if optional:
        candidates, unusable = _optional_candidates(user, now, plan)
    else:
        candidates, unusable = _materialize_entries(user, plan.get("entries", []), now)
    prepared = legacy._claim_candidate_signature(candidates)
    legacy._expire_stale_active_sessions(user.id, now)
    if unusable:
        try:
            policy.defer_unusable_entries(user, unusable, now=now)
        except (policy.PolicyConflict, IntegrityError, OperationalError) as error:
            raise _conflict(error) from error
    if not candidates:
        try:
            policy.refresh_day(user, now=now)
        except (policy.PolicyConflict, IntegrityError, OperationalError) as error:
            raise _conflict(error) from error
        return _empty_payload(user, now, origin_task, optional)
    session = VocabularyReviewSession(
        student_id=user.id,
        origin_task_id=origin_task.id if origin_task else None,
        review_date=local_date(now),
        status=VocabularyReviewSession.STATUS_ACTIVE,
        claim_key=f"vocabulary-review:{user.id}:{local_date(now).isoformat()}",
        session_token=secrets.token_urlsafe(32)[: legacy.SESSION_TOKEN_MAX_LENGTH],
        queue_token=secrets.token_urlsafe(32)[: legacy.SESSION_TOKEN_MAX_LENGTH],
        batch_limit=int(plan["maintenance_limit" if optional else "mandatory_limit"]),
        started_at=now,
    )
    try:
        legacy._begin_claim_outer_transaction()
        with db.session.begin_nested():
            db.session.add(session)
            db.session.flush()
        # The session insertion owns the SQLite writer lock. Rebuild at most
        # this finite batch and verify fresh question/owner state before reserving.
        refreshed, invalid = _materialize_entries(
            user, [item["policy_entry"] for item in candidates], now, optional=optional
        )
        if invalid or legacy._claim_candidate_signature(refreshed) != prepared:
            raise legacy.VocabularyAutonomousReviewError("review_claim_changed", 409)
        reservations = []
        for index, candidate in enumerate(refreshed):
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
            reservations.append({"item_id": item.id, "entry": candidate["policy_entry"]})
        policy.reserve_items(user, session.id, reservations, now=now, optional=optional)
    except policy.PolicyConflict as error:
        raise _conflict(error) from error
    except OperationalError as error:
        raise legacy.VocabularyAutonomousReviewError("review_claim_in_progress", 409) from error
    except IntegrityError as error:
        raise legacy.VocabularyAutonomousReviewError("review_claim_conflict", 409) from error
    return legacy._session_payload(user, session, now)


def record_review_answer(user, item, correct, now):
    if not enabled(user, now):
        return
    policy = _policy()
    try:
        policy.apply_review_answer(
            user,
            item_id=item.id,
            correct=bool(correct),
            source_key=f"review:{item.id}:{item.first_attempt_id}",
            now=now,
            response_kind=item.first_response_kind,
        )
    except (policy.PolicyConflict, IntegrityError, OperationalError) as error:
        raise _conflict(error) from error


def record_learning_answer(
    user, item, correct, source_key, now, error_class, *, response_kind="answer"
):
    if not enabled(user, now):
        return
    policy = _policy()
    try:
        policy.record_learning_answer(
            user,
            sense_id=item.sense_id,
            dimension=item.dimension,
            word_id=item.word_id,
            correct=bool(correct),
            source_key=source_key,
            now=now,
            response_kind=response_kind,
        )
    except (policy.PolicyConflict, IntegrityError, OperationalError) as error:
        raise error_class("state_conflict", 409, retryable=True) from error


def mark_skipped(user, item_ids, now):
    policy = _policy()
    try:
        policy.mark_skipped(user, item_ids=item_ids, now=now)
    except (policy.PolicyConflict, IntegrityError, OperationalError) as error:
        raise _conflict(error) from error


def settlement_counts(user, session, now):
    mode = session_mode(user, session, now)
    if mode is None:
        return None
    summary = _public_summary(_policy().summary(user, now=now))
    remaining = (
        summary["mandatory_remaining"] if mode == "mandatory" else summary["maintenance_remaining"]
    )
    return {
        **summary,
        "session_mode": mode,
        "remaining_due_count": remaining,
        "continue_available": remaining > 0,
    }
