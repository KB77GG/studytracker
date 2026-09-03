"""Server-owned group learning chain for opt-in vocabulary v2 tasks.

The chain is intentionally separate from the legacy dictation queue and from
autonomous review. A task snapshot contains fixed word groups and frozen
questions; the server, rather than the mini program, owns the current group,
phase, question position, first answers, retry pass, and final score.
"""

from __future__ import annotations

import hashlib
import heapq
import json
from datetime import datetime

from sqlalchemy import update
from sqlalchemy.exc import IntegrityError, OperationalError

from dictation_answers import (
    canonical_vocabulary_word,
    is_chinese_answer_correct,
    is_english_answer_correct,
)
from models import (
    DictationRecord,
    DictationWord,
    Task,
    User,
    VocabularyLearningFlow,
    VocabularyLearningQuestion,
    VocabularyTaskSettlement,
    db,
)
from services.dictation_input_policy import resolve_submission_input
from services.vocabulary_autonomous_review import (
    VocabularyAutonomousReviewError,
    review_preflight,
)
from services.vocabulary_context import build_context_question, grade_context_answer
from services.vocabulary_mastery import (
    MAX_ENGLISH_ANSWER_LENGTH,
    SAFE_ENGLISH_SEPARATORS,
    _apply_dimension_answer,
    _assigned_words,
    _bootstrap_unstarted_dimensions,
    _dimension_stage,
    _mastery_for,
    _question_for,
    dimensions_for_goal,
    ensure_mastery,
    ensure_word_sense,
    is_vocabulary_v2_task,
    normalize_goal,
    utc_naive,
)
from services.vocabulary_remediation import (
    MAX_CORRECTION_ATTEMPTS,
    MAX_FORMAL_QUESTIONS_PER_WORD,
    MAX_REMEDIATION_PER_WORD,
    MIN_OTHER_FORMAL_QUESTIONS,
    RELATED_DIMENSION_BY_ERROR,
    correction_state,
)
from services.task_date_gate import (
    TaskDateGateError,
    assert_task_write_allowed,
    task_date_access,
)

GROUP_SIZES = {
    "reading": 10,
    "listening": 8,
    "writing": 8,
    "comprehensive": 6,
}

# Comprehensive first learning deliberately owns only the two capabilities
# that are useful immediately. The other dimensions remain in the independent
# spaced-review queue instead of becoming short-term repeats.
COMPREHENSIVE_BASE_DIMENSIONS = ("form_recall", "context_use")
# Kept as a compatibility alias for callers/tests that imported the old
# name; the shared policy is the only source of the actual limit.
MAX_CORRECTIONS_PER_QUESTION = MAX_CORRECTION_ATTEMPTS
COMPREHENSIVE_REVIEW_DIMENSIONS = ("meaning_recall", "audio_form_recall")

PHASE_FAMILIARITY = "familiarity"
PHASE_RECALL = "active_recall"
PHASE_DISCRIMINATION = "context_discrimination"
PHASE_PRODUCTION = "context_production"
PHASE_RETRY = "retry"
PHASE_COMPLETE = "complete"
PHASE_ORDER = (PHASE_RECALL, PHASE_DISCRIMINATION, PHASE_PRODUCTION)
PHASE_LABELS = {
    PHASE_FAMILIARITY: "熟悉材料",
    PHASE_RECALL: "主动提取",
    PHASE_DISCRIMINATION: "语境辨析",
    PHASE_PRODUCTION: "语境产出",
    PHASE_RETRY: "错题再测",
    PHASE_COMPLETE: "本组完成",
}


class VocabularyGroupLearningError(Exception):
    """Safe, user-facing group-flow error."""

    def __init__(self, error: str, status_code: int = 400, **details):
        super().__init__(error)
        self.error = error
        self.status_code = status_code
        self.details = details


class _FlowRace(Exception):
    """Internal savepoint abort when another request won the current step."""


def group_size_for_goal(goal: str) -> int:
    normalized = normalize_goal(goal)
    if not normalized:
        raise VocabularyGroupLearningError("invalid_vocabulary_goal", 400)
    return GROUP_SIZES[normalized]


def build_fixed_groups(words: list[DictationWord], group_size: int) -> list[list[DictationWord]]:
    """Split the server-selected word order without a client-configurable size."""

    if group_size <= 0:
        raise ValueError("group_size must be positive")
    return [words[start : start + group_size] for start in range(0, len(words), group_size)]


def _schedule_comprehensive_review_dimensions(mastery, now):
    """Bootstrap unused dimensions with the normal first Day-1 interval."""

    # Do not make an unused dimension immediately due after Day 0. This helper
    # is the same bootstrap used by mastery answers and therefore preserves
    # REVIEW_INTERVALS_DAYS and any future interval policy change.
    _bootstrap_unstarted_dimensions(mastery, COMPREHENSIVE_REVIEW_DIMENSIONS, now)


def stable_question_order(specs: list[dict], seed: str, previous_sense_id=None) -> list[dict]:
    """Stable shuffle with a no-adjacent-sense preference.

    The greedy pass only relaxes the preference when all remaining questions
    use the same sense. Callers pass the last sense from the previous phase so
    a phase boundary is handled by the same deterministic rule.
    """

    # A plain hash sort can strand an avoidable pair at the end (A3/B1/C1
    # may become B/C/A/A/A). Keep one deterministic bucket per sense and use
    # the remaining count as the primary priority. The heap is the standard
    # rearrangement strategy: never pick the previous sense while another
    # bucket exists, and relax only when no legal bucket remains.
    buckets = {}
    for spec in specs or []:
        key = str(spec.get("sense_id"))
        buckets.setdefault(key, []).append(spec)
    for _key, bucket in buckets.items():
        bucket.sort(
            key=lambda spec: hashlib.sha256(
                f"{seed}|question|{spec.get('question_id')}|{spec.get('word_id')}|{spec.get('dimension')}".encode()
            ).hexdigest(),
            reverse=True,
        )

    def tie_key(sense_key):
        return hashlib.sha256(f"{seed}|sense|{sense_key}".encode()).hexdigest()

    heap = [(-len(bucket), tie_key(key), key) for key, bucket in buckets.items()]
    heapq.heapify(heap)
    ordered = []
    previous = str(previous_sense_id) if previous_sense_id is not None else None
    while heap:
        blocked = []
        while heap and heap[0][2] == previous:
            blocked.append(heapq.heappop(heap))
        if heap:
            count, tie, selected_key = heapq.heappop(heap)
            heap.extend(blocked)
            heapq.heapify(heap)
        else:
            # No legal alternative exists; this is the explicit deterministic
            # relaxation for a mathematically impossible arrangement.
            count, tie, selected_key = blocked.pop()
            heap.extend(blocked)
            heapq.heapify(heap)
        selected = buckets[selected_key].pop()
        ordered.append(selected)
        previous = selected_key
        if buckets[selected_key]:
            heapq.heappush(heap, (count + 1, tie, selected_key))
    return ordered


def _json_list(value) -> list:
    try:
        parsed = json.loads(value or "[]") if isinstance(value, str) else value
    except (TypeError, ValueError):
        parsed = []
    return parsed if isinstance(parsed, list) else []


def _json_dict(value) -> dict:
    try:
        parsed = json.loads(value or "{}") if isinstance(value, str) else value
    except (TypeError, ValueError):
        parsed = {}
    return parsed if isinstance(parsed, dict) else {}


def _task_owner(task: Task, user: User) -> bool:
    profile = getattr(user, "student_profile", None)
    return bool(profile and task.student_name == profile.full_name)


def _familiarity_snapshot(word: DictationWord) -> dict:
    """Return approved/material fields only; familiarity is not a mastery event."""

    return {
        "word_id": word.id,
        "word": canonical_vocabulary_word(word.word, word.accepted_answers) or word.word,
        "phonetic": word.phonetic,
        "meaning": word.core_meaning_zh or word.translation,
        "usage_pattern": word.usage_pattern,
        "example_en": word.example_en,
        "example_zh": word.example_zh,
        "usage_note": word.usage_note,
        "audio_tts_url": f"/dictation/words/{word.id}/tts",
    }


def _context_question(word, candidates, *, seed: str, allowed_kinds: set[str], rotation: int):
    result = build_context_question(
        word,
        candidates,
        seed=seed,
        rotation=rotation,
        allowed_kinds=allowed_kinds,
    )
    if not result:
        return None
    public, answer = result
    public = dict(public)
    public["dimension"] = "context_use"
    return public, answer


def _question_spec(
    word,
    sense,
    public,
    answer,
    *,
    group_index: int,
    phase: str,
    context_role: str | None = None,
    score_eligible: bool = True,
) -> dict:
    return {
        "word": word,
        "sense": sense,
        "word_id": word.id,
        "sense_id": sense.id,
        "phase": phase,
        "dimension": public.get("dimension") or "context_use",
        "context_role": context_role,
        "score_eligible": bool(score_eligible),
        "question_id": public["question_id"],
        "public": public,
        "answer": answer,
        "group_index": group_index,
    }


def _build_group_specs(
    user,
    group_words,
    group_index,
    goal,
    candidates,
    used_score_keys,
    diagnostics,
):
    if goal == "comprehensive":
        return _build_comprehensive_group_specs(
            user,
            group_words,
            group_index,
            candidates,
            used_score_keys,
            diagnostics,
        )
    by_phase = {phase: [] for phase in PHASE_ORDER}
    has_context_dimension = "context_use" in dimensions_for_goal(goal)
    for word in group_words:
        sense = ensure_word_sense(word)
        mastery = ensure_mastery(user, word, sense)
        for dimension in dimensions_for_goal(goal):
            if dimension == "context_use":
                continue
            question = _question_for(
                word,
                dimension,
                goal,
                _dimension_stage(mastery, dimension),
                candidates,
            )
            if not question:
                diagnostics.append(
                    {
                        "group_index": group_index,
                        "word_id": word.id,
                        "sense_id": sense.id,
                        "phase": PHASE_RECALL,
                        "reason": "missing_required_recall_material",
                        "dimension": dimension,
                    }
                )
                continue
            public, answer = question
            score_key = (sense.id, dimension)
            by_phase[PHASE_RECALL].append(
                _question_spec(
                    word,
                    sense,
                    public,
                    answer,
                    group_index=group_index,
                    phase=PHASE_RECALL,
                    score_eligible=score_key not in used_score_keys,
                )
            )
            used_score_keys.add(score_key)

        if not has_context_dimension:
            continue
        choice = _context_question(
            word,
            candidates,
            seed=f"g2:{group_index}:{word.id}:context-choice",
            allowed_kinds={"meaning_choice", "collocation_choice"},
            rotation=0,
        )
        fill = _context_question(
            word,
            candidates,
            seed=f"g2:{group_index}:{word.id}:context-production",
            allowed_kinds={"example_fill", "collocation_fill"},
            rotation=1,
        )
        if choice:
            public, answer = choice
            by_phase[PHASE_DISCRIMINATION].append(
                _question_spec(
                    word,
                    sense,
                    public,
                    answer,
                    group_index=group_index,
                    phase=PHASE_DISCRIMINATION,
                    context_role="guide" if fill else "degraded",
                    # A production question, when available, is the sole
                    # score/mastery-bearing context encounter.
                    score_eligible=not bool(fill) and (sense.id, "context_use") not in used_score_keys,
                )
            )
            if not fill:
                used_score_keys.add((sense.id, "context_use"))
        else:
            diagnostics.append(
                {
                    "group_index": group_index,
                    "word_id": word.id,
                    "sense_id": sense.id,
                    "phase": PHASE_DISCRIMINATION,
                    "reason": "missing_safe_context_choice",
                }
            )
        if fill:
            public, answer = fill
            eligible = (sense.id, "context_use") not in used_score_keys
            by_phase[PHASE_PRODUCTION].append(
                _question_spec(
                    word,
                    sense,
                    public,
                    answer,
                    group_index=group_index,
                    phase=PHASE_PRODUCTION,
                    context_role="production",
                    score_eligible=eligible,
                )
            )
            if eligible:
                used_score_keys.add((sense.id, "context_use"))
        else:
            diagnostics.append(
                {
                    "group_index": group_index,
                    "word_id": word.id,
                    "sense_id": sense.id,
                    "phase": PHASE_PRODUCTION,
                    "reason": "missing_safe_context_production",
                }
            )
        if choice and not fill:
            diagnostics.append(
                {
                    "group_index": group_index,
                    "word_id": word.id,
                    "sense_id": sense.id,
                    "phase": PHASE_PRODUCTION,
                    "reason": "degraded_to_context_discrimination",
                }
            )
        if not choice and not fill:
            diagnostics.append(
                {
                    "group_index": group_index,
                    "word_id": word.id,
                    "sense_id": sense.id,
                    "phase": "context_use",
                    "reason": "context_skipped_no_safe_question",
                }
            )
    return by_phase


def _build_comprehensive_group_specs(
    user,
    group_words,
    group_index,
    candidates,
    used_score_keys,
    diagnostics,
):
    """Build one active-recall and one context task per comprehensive word.

    The two phases deliberately use the same server-owned word order. With a
    six-word group this gives each word five other formal questions between its
    two base tasks; larger groups naturally land in the preferred 8–12 range.
    """

    active_specs = []
    context_by_word = {}
    for word in group_words:
        sense = ensure_word_sense(word)
        mastery = ensure_mastery(user, word, sense)
        recall = _question_for(
            word,
            "form_recall",
            "comprehensive",
            _dimension_stage(mastery, "form_recall"),
            candidates,
        )
        if recall:
            public, answer = recall
            active_specs.append(
                _question_spec(
                    word,
                    sense,
                    public,
                    answer,
                    group_index=group_index,
                    phase=PHASE_RECALL,
                    context_role="base_recall",
                    score_eligible=(sense.id, "form_recall") not in used_score_keys,
                )
            )
            used_score_keys.add((sense.id, "form_recall"))
        else:
            diagnostics.append(
                {
                    "group_index": group_index,
                    "word_id": word.id,
                    "sense_id": sense.id,
                    "phase": PHASE_RECALL,
                    "reason": "missing_required_recall_material",
                    "dimension": "form_recall",
                }
            )

        # Choice is the default context task. Fill is only the safe fallback
        # when no approved choice can be built for this word.
        context = _context_question(
            word,
            candidates,
            seed=f"g2:{group_index}:{word.id}:context-choice",
            allowed_kinds={"meaning_choice", "collocation_choice"},
            rotation=0,
        )
        if not context:
            context = _context_question(
                word,
                candidates,
                seed=f"g2:{group_index}:{word.id}:context-production",
                allowed_kinds={"example_fill", "collocation_fill"},
                rotation=1,
            )
        if context:
            public, answer = context
            context_by_word[word.id] = _question_spec(
                word,
                sense,
                public,
                answer,
                group_index=group_index,
                phase=PHASE_DISCRIMINATION,
                context_role="base_context",
                score_eligible=(sense.id, "context_use") not in used_score_keys,
            )
            used_score_keys.add((sense.id, "context_use"))
        else:
            diagnostics.append(
                {
                    "group_index": group_index,
                    "word_id": word.id,
                    "sense_id": sense.id,
                    "phase": PHASE_DISCRIMINATION,
                    "reason": "context_skipped_no_safe_question",
                }
            )

    active_ordered = stable_question_order(
        active_specs,
        f"vocabulary-group:{group_index}:active_recall:comprehensive",
        ensure_word_sense(group_words[-1]).id if group_words else None,
    )
    context_ordered = [
        context_by_word[spec["word_id"]]
        for spec in active_ordered
        if spec["word_id"] in context_by_word
    ]
    return {
        PHASE_RECALL: active_ordered,
        PHASE_DISCRIMINATION: context_ordered,
        PHASE_PRODUCTION: [],
    }


def _public_question(
    question: VocabularyLearningQuestion,
    *,
    retry=False,
    correction=False,
) -> dict:
    snapshot = _json_dict(question.question_snapshot_json)
    payload = {
        "learning_question_id": question.id,
        "queue_item_id": question.id,
        "question_id": question.question_id,
        "word_id": question.word_id,
        "sense_id": question.sense_id,
        "dimension": question.dimension,
        "phase": question.phase,
        "context_role": question.context_role,
        "score_eligible": bool(question.score_eligible),
        "retry": bool(retry),
        "correction": bool(correction),
        "remediation_kind": question.remediation_kind,
        "question": snapshot,
        "mode": snapshot.get("mode"),
        "dictation_mode": snapshot.get("mode"),
        "answer_length": MAX_ENGLISH_ANSWER_LENGTH
        if snapshot.get("mode") in {"audio_to_en", "zh_to_en", "context_fill"}
        else 0,
        "answer_separators": SAFE_ENGLISH_SEPARATORS
        if snapshot.get("mode") in {"audio_to_en", "zh_to_en", "context_fill"}
        else [],
    }
    if retry or correction or question.first_attempt_id:
        payload["first_is_correct"] = bool(question.first_is_correct)
        payload["first_attempt_id"] = question.first_attempt_id
        payload["first_answer"] = question.first_answer
        payload["revealed_answer"] = _revealed_answer(question)
    if correction:
        payload["correction_required"] = True
        payload["correction_count"] = int(question.correction_count or 0)
        payload["correction_max_attempts"] = MAX_CORRECTION_ATTEMPTS
        payload["correction_retry_allowed"] = int(question.correction_count or 0) < MAX_CORRECTION_ATTEMPTS
        payload["correction_is_correct"] = question.correction_is_correct
        payload["correction_exhausted"] = bool(question.deferred_to_review)
    return payload


def _queue_token(flow, questions) -> str:
    raw = {
        "task_id": flow.task_id,
        "goal": flow.vocabulary_goal,
        "groups": _json_list(flow.groups_json),
        "questions": [
            [q.id, q.question_id, q.group_index, q.phase, q.word_id, q.sense_id, q.dimension]
            for q in questions
        ],
    }
    return hashlib.sha256(json.dumps(raw, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def _flow_or_error(user, task_id, *, lock=False):
    task = Task.query.filter_by(id=task_id).first()
    if not task:
        raise VocabularyGroupLearningError("task_not_found", 404)
    if not _task_owner(task, user):
        raise VocabularyGroupLearningError("forbidden", 403)
    if not is_vocabulary_v2_task(task):
        raise VocabularyGroupLearningError("task_not_vocabulary_v2", 409)
    query = VocabularyLearningFlow.query.filter_by(student_id=user.id, task_id=task.id)
    try:
        flow = query.with_for_update().first() if lock else query.first()
    except OperationalError as error:
        raise VocabularyGroupLearningError(
            "state_conflict",
            409,
            retryable=True,
        ) from error
    return task, flow


def _initialize_flow(user, task, now):
    existing = VocabularyLearningFlow.query.filter_by(student_id=user.id, task_id=task.id).first()
    if existing:
        return existing
    goal = normalize_goal(task.vocabulary_goal)
    assigned = _assigned_words(task)
    if not assigned:
        raise VocabularyGroupLearningError("empty_vocabulary_task", 409)
    group_size = group_size_for_goal(goal)
    book_id = task.dictation_book_id
    candidates = DictationWord.query.filter_by(book_id=book_id).order_by(DictationWord.id.asc()).all()
    for candidate in candidates:
        ensure_word_sense(candidate)
    db.session.flush()
    groups = build_fixed_groups(assigned, group_size)
    group_payload = []
    diagnostics = []
    all_specs = []
    used_score_keys = set()
    for group_index, group_words in enumerate(groups):
        for word in group_words:
            mastery = ensure_mastery(user, word, ensure_word_sense(word))
            if goal == "comprehensive":
                _schedule_comprehensive_review_dimensions(mastery, now)
        phase_specs = _build_group_specs(
            user,
            group_words,
            group_index,
            goal,
            candidates,
            used_score_keys,
            diagnostics,
        )
        # A is a server-ordered familiarity pass. Seed B with the last card's
        # sense so the first active-recall prompt cannot immediately reuse the
        # answer just shown (a one-sense group is the explicit relaxation).
        previous_sense = (
            ensure_word_sense(group_words[-1]).id if group_words else None
        )
        for phase in PHASE_ORDER:
            if goal == "comprehensive" and phase in {PHASE_RECALL, PHASE_DISCRIMINATION}:
                # The comprehensive builder has already paired each context
                # task with the active-recall order. Re-shuffling either phase
                # would collapse the required same-word cooldown.
                ordered = list(phase_specs[phase])
            else:
                ordered = stable_question_order(
                    phase_specs[phase],
                    f"vocabulary-group:{task.id}:{group_index}:{phase}",
                    previous_sense,
                )
            for phase_index, spec in enumerate(ordered):
                spec["phase_index"] = phase_index
                all_specs.append(spec)
            if ordered:
                previous_sense = ordered[-1]["sense_id"]
        group_payload.append(
            {
                "group_index": group_index,
                "word_ids": [word.id for word in group_words],
                "size": len(group_words),
                "familiarity": [_familiarity_snapshot(word) for word in group_words],
            }
        )

    flow = VocabularyLearningFlow(
        student_id=user.id,
        task_id=task.id,
        book_id=book_id,
        vocabulary_goal=goal,
        group_size=group_size,
        total_word_count=len(assigned),
        total_group_count=len(groups),
        groups_json=json.dumps(group_payload, ensure_ascii=False, sort_keys=True),
        diagnostics_json=json.dumps(diagnostics, ensure_ascii=False, sort_keys=True),
        group_results_json="[]",
        context_applied_json="{}",
        retry_question_ids_json="[]",
        related_source_question_ids_json="[]",
        weak_word_ids_json="[]",
        current_group_index=0,
        phase=PHASE_FAMILIARITY,
        phase_index=0,
        remediation_wave=1,
        pending_correction_question_id=None,
        viewed_word_ids_json="[]",
        queue_token="pending",
        status=VocabularyLearningFlow.STATUS_ACTIVE,
        state_version=0,
        started_at=now,
    )
    db.session.add(flow)
    db.session.flush()
    for question_order, spec in enumerate(all_specs):
        question = VocabularyLearningQuestion(
            flow_id=flow.id,
            student_id=user.id,
            task_id=task.id,
            book_id=book_id,
            group_index=spec["group_index"],
            phase=spec["phase"],
            phase_index=spec["phase_index"],
            question_order=question_order,
            word_id=spec["word_id"],
            sense_id=spec["sense_id"],
            dimension=spec["dimension"],
            context_role=spec["context_role"],
            score_eligible=spec["score_eligible"],
            mastery_applied=False,
            question_id=spec["question_id"],
            question_snapshot_json=json.dumps(spec["public"], ensure_ascii=False, sort_keys=True),
            answer_payload_json=json.dumps(spec["answer"], ensure_ascii=False, sort_keys=True),
            formal_ordinal=(question_order + 1),
        )
        db.session.add(question)
    db.session.flush()
    flow.queue_token = _queue_token(flow, flow.questions)
    return flow


def _ensure_flow(user, task, now):
    try:
        flow = VocabularyLearningFlow.query.filter_by(student_id=user.id, task_id=task.id).first()
    except OperationalError as error:
        raise VocabularyGroupLearningError("state_conflict", 409, retryable=True) from error
    if flow:
        return flow
    try:
        with db.session.begin_nested():
            flow = _initialize_flow(user, task, now)
            db.session.flush()
        return flow
    except OperationalError as error:
        raise VocabularyGroupLearningError("state_conflict", 409, retryable=True) from error
    except IntegrityError:
        flow = VocabularyLearningFlow.query.filter_by(student_id=user.id, task_id=task.id).first()
        if not flow:
            raise
        return flow


def _group_payload(flow):
    groups = _json_list(flow.groups_json)
    return groups[flow.current_group_index] if 0 <= flow.current_group_index < len(groups) else None


def _group_questions(flow, phase=None):
    query = VocabularyLearningQuestion.query.filter_by(
        flow_id=flow.id,
        group_index=flow.current_group_index,
    )
    if phase:
        query = query.filter_by(phase=phase)
    return query.order_by(
        VocabularyLearningQuestion.phase_index.asc(),
        VocabularyLearningQuestion.question_order.asc(),
    ).all()


def _retry_questions(flow):
    ids = [int(item) for item in _json_list(flow.retry_question_ids_json) if str(item).isdigit()]
    if not ids:
        return []
    # Related remediation rows are appended after the flow relationship may
    # already have been loaded. Query by the persisted ids so a same-request
    # refresh cannot mistake a newly-created wave for an empty retry queue.
    by_id = {
        question.id: question
        for question in VocabularyLearningQuestion.query.filter(
            VocabularyLearningQuestion.flow_id == flow.id,
            VocabularyLearningQuestion.id.in_(ids),
        ).all()
    }
    return [by_id[item_id] for item_id in ids if item_id in by_id]


def _base_formal_questions(flow):
    return [
        question
        for question in _group_questions(flow)
        if question.remediation_kind is None and question.phase in PHASE_ORDER
    ]


def _uses_comprehensive_scheduler(flow):
    """Gate the new contract so an older in-progress flow remains resumable."""

    if flow.vocabulary_goal != "comprehensive":
        return False
    base_questions = _base_formal_questions(flow)
    return bool(base_questions) and all(
        question.formal_ordinal is not None for question in base_questions
    )


def _formal_questions(flow):
    return [
        question
        for question in _group_questions(flow)
        if question.phase in PHASE_ORDER or question.remediation_kind
    ]


def _word_remediation_count(flow, word_id):
    base_retries = sum(
        1
        for question in _base_formal_questions(flow)
        if question.word_id == word_id and question.retry_attempt_id
    )
    related = sum(
        1
        for question in _group_questions(flow)
        if question.word_id == word_id and question.remediation_kind
    )
    return base_retries + related


def _mark_weak_word(flow, word_id):
    weak = set(_json_list(flow.weak_word_ids_json))
    weak.add(int(word_id))
    flow.weak_word_ids_json = json.dumps(sorted(weak), ensure_ascii=False)


def _set_retry_questions(flow):
    questions = [
        question
        for question in _base_formal_questions(flow)
        if question.first_attempt_id and question.first_is_correct is False and not question.retry_attempt_id
    ]
    if not _uses_comprehensive_scheduler(flow):
        ordered = stable_question_order(
            [
                {
                    "question_id": question.question_id,
                    "word_id": question.word_id,
                    "sense_id": question.sense_id,
                    "dimension": question.dimension,
                    "question": question,
                }
                for question in questions
            ],
            f"vocabulary-group-retry:{flow.id}:{flow.current_group_index}",
            previous_sense_id=next(
                (
                    question.sense_id
                    for phase in reversed(PHASE_ORDER)
                    for question in reversed(_group_questions(flow, phase))
                    if question.first_attempt_id
                ),
                None,
            ),
        )
        flow.retry_question_ids_json = json.dumps(
            [item["question"].id for item in ordered],
            ensure_ascii=False,
        )
        flow.related_source_question_ids_json = "[]"
        flow.remediation_wave = 1
        flow.phase = PHASE_RETRY
        flow.phase_index = 0
        return
    # Sort by the last formal occurrence, not by a fresh random shuffle. A
    # later retry can then be placed after earlier retries and still maintain
    # the same-word cooldown.
    questions.sort(key=lambda question: (question.formal_ordinal or question.question_order, question.id))
    base_count = len(_base_formal_questions(flow))
    retry_ids = []
    for offset, question in enumerate(questions):
        retry_position = base_count + offset + 1
        last_position = question.formal_ordinal or question.question_order + 1
        if retry_position - last_position < MIN_OTHER_FORMAL_QUESTIONS + 1:
            question.deferred_to_review = True
            _mark_weak_word(flow, question.word_id)
            continue
        retry_ids.append(question.id)
    flow.retry_question_ids_json = json.dumps(retry_ids, ensure_ascii=False)
    flow.related_source_question_ids_json = "[]"
    flow.remediation_wave = 1
    # Even an all-correct group enters the explicit retry boundary. The state
    # machine then calls _finish_group, so the next group/finalize transition
    # cannot be skipped by an ambiguous ``complete`` phase.
    flow.phase = PHASE_RETRY
    flow.phase_index = 0


def _require_daily_clearance(user, task_id, now):
    task = Task.query.filter_by(id=task_id).first()
    if not task:
        raise VocabularyGroupLearningError("task_not_found", 404)
    try:
        assert_task_write_allowed(task, now)
    except TaskDateGateError as error:
        raise VocabularyGroupLearningError(
            error.error,
            error.status_code,
            message=error.message,
            **error.details,
        ) from error
    try:
        gate = review_preflight(user, task_id, now=now)
    except OperationalError as error:
        raise VocabularyGroupLearningError("state_conflict", 409, retryable=True) from error
    except VocabularyAutonomousReviewError as error:
        # Keep all v2 mutations on one stable error contract. Invalid or
        # foreign tasks must not leak an autonomous-review exception to the
        # route and turn into a 500 response.
        raise VocabularyGroupLearningError(
            error.error,
            error.status_code,
            **error.details,
        ) from error
    if gate.get("required"):
        raise VocabularyGroupLearningError(
            "vocabulary_review_required",
            409,
            due_count=gate.get("due_count", 0),
            batch_limit=gate.get("batch_limit"),
            active_session_id=gate.get("active_session_id"),
        )
    return gate


def _apply_context_once(flow, user, now):
    applied = _json_dict(flow.context_applied_json)
    group_key = str(flow.current_group_index)
    if group_key in applied:
        return applied[group_key]
    questions = _group_questions(flow)
    production = [
        question
        for question in questions
        if question.dimension == "context_use"
        and question.context_role in {"production", "base_context"}
    ]
    degraded = [
        question
        for question in questions
        if question.dimension == "context_use" and question.context_role == "degraded"
    ]
    # Prefer production per sense. A group can contain many independent
    # word/sense encounters; applying only candidates[0] would silently drop
    # every other context mastery update.
    selected_by_sense = {}
    for question in production:
        if question.score_eligible:
            selected_by_sense.setdefault(question.sense_id, question)
    for question in degraded:
        if question.score_eligible:
            selected_by_sense.setdefault(question.sense_id, question)
    sense_results = {}
    for sense_id, selected in selected_by_sense.items():
        sense_key = str(sense_id)
        already_applied = any(
            question.mastery_applied
            for question in flow.questions
            if question.sense_id == sense_id and question.dimension == "context_use"
        )
        if already_applied:
            sense_results[sense_key] = {
                "applied": False,
                "source": "already_applied",
                "question_id": selected.question_id,
            }
            continue
        mastery = _mastery_for(user.id, sense_id) or ensure_mastery(
            user, selected.word, selected.sense
        )
        _apply_dimension_answer(
            mastery,
            "context_use",
            bool(selected.first_is_correct),
            now,
            bootstrap_dimensions=dimensions_for_goal(flow.vocabulary_goal),
        )
        selected.mastery_applied = True
        record = DictationRecord.query.filter_by(
            student_id=user.id,
            task_id=flow.task_id,
            attempt_id=selected.first_attempt_id,
        ).first()
        if record:
            record.vocabulary_mastery_applied = True
        sense_results[sense_key] = {
            "applied": True,
            "source": "production" if selected in production else "degraded",
            "question_id": selected.question_id,
        }
    result = {
        "senses": sense_results,
        "applied_count": sum(1 for item in sense_results.values() if item["applied"]),
        "skipped_count": max(0, len({question.sense_id for question in questions if question.dimension == "context_use"}) - len(sense_results)),
    }
    applied[group_key] = result
    flow.context_applied_json = json.dumps(applied, ensure_ascii=False, sort_keys=True)
    return result


def _prepare_related_remediations(flow, user, now):
    """Create at most one related-dimension wave after same-dimension retries."""

    if not _uses_comprehensive_scheduler(flow) or flow.remediation_wave != 1:
        return False
    source_ids = [int(item) for item in _json_list(flow.related_source_question_ids_json) if str(item).isdigit()]
    primary_ids = [int(item) for item in _json_list(flow.retry_question_ids_json) if str(item).isdigit()]
    flow.remediation_wave = 2
    if not source_ids:
        return False

    base_questions = _base_formal_questions(flow)
    base_count = len(base_questions)
    candidate_cache = {}
    related_ids = []
    max_question_order = max(
        (question.question_order for question in flow.questions),
        default=-1,
    )
    max_formal_ordinal = max(
        (question.formal_ordinal or question.question_order + 1 for question in flow.questions),
        default=0,
    )
    primary_positions = {question_id: index for index, question_id in enumerate(primary_ids)}
    related_offset = 0
    for source_id in sorted(source_ids, key=lambda item: primary_positions.get(item, 10**9)):
        source = db.session.get(VocabularyLearningQuestion, source_id)
        if not source or source.retry_is_correct is not False:
            continue
        failed_dimensions = {
            question.dimension
            for question in base_questions
            if question.word_id == source.word_id and question.first_is_correct is False
        }
        if len(failed_dimensions) >= 2 or _word_remediation_count(flow, source.word_id) >= MAX_REMEDIATION_PER_WORD:
            _mark_weak_word(flow, source.word_id)
            continue
        related_dimension = RELATED_DIMENSION_BY_ERROR.get(source.dimension)
        if not related_dimension:
            _mark_weak_word(flow, source.word_id)
            continue
        word = source.word
        if not word:
            _mark_weak_word(flow, source.word_id)
            continue
        if word.book_id not in candidate_cache:
            candidate_cache[word.book_id] = (
                DictationWord.query.filter_by(book_id=word.book_id)
                .order_by(DictationWord.id.asc())
                .all()
            )
        candidates = candidate_cache[word.book_id]
        question_data = None
        if related_dimension == "context_use":
            question_data = _context_question(
                word,
                candidates,
                seed=f"remediation:{flow.id}:{source.id}:context-choice",
                allowed_kinds={"meaning_choice", "collocation_choice"},
                rotation=1,
            )
            if not question_data:
                question_data = _context_question(
                    word,
                    candidates,
                    seed=f"remediation:{flow.id}:{source.id}:context-production",
                    allowed_kinds={"example_fill", "collocation_fill"},
                    rotation=2,
                )
        else:
            mastery = _mastery_for(user.id, source.sense_id) or ensure_mastery(
                user, word, source.sense
            )
            question_data = _question_for(
                word,
                related_dimension,
                flow.vocabulary_goal,
                _dimension_stage(mastery, related_dimension),
                candidates,
            )
        if not question_data:
            _mark_weak_word(flow, source.word_id)
            continue
        public, answer = question_data
        source_position = base_count + primary_positions.get(source.id, len(primary_ids)) + 1
        related_position = base_count + len(primary_ids) + related_offset + 1
        if related_position - source_position < MIN_OTHER_FORMAL_QUESTIONS + 1:
            source.deferred_to_review = True
            _mark_weak_word(flow, source.word_id)
            continue
        max_question_order += 1
        max_formal_ordinal = max(max_formal_ordinal, related_position)
        related = VocabularyLearningQuestion(
            flow_id=flow.id,
            student_id=user.id,
            task_id=flow.task_id,
            book_id=flow.book_id,
            group_index=flow.current_group_index,
            phase=PHASE_RETRY,
            phase_index=related_offset,
            question_order=max_question_order,
            word_id=source.word_id,
            sense_id=source.sense_id,
            dimension=related_dimension,
            context_role="remediation",
            score_eligible=False,
            mastery_applied=False,
            question_id=public["question_id"],
            question_snapshot_json=json.dumps(public, ensure_ascii=False, sort_keys=True),
            answer_payload_json=json.dumps(answer, ensure_ascii=False, sort_keys=True),
            remediation_kind="related_dimension",
            source_question_id=source.id,
            formal_ordinal=max_formal_ordinal,
        )
        db.session.add(related)
        db.session.flush()
        related_ids.append(related.id)
        related_offset += 1
    flow.related_source_question_ids_json = "[]"
    if not related_ids:
        return False
    flow.retry_question_ids_json = json.dumps(related_ids, ensure_ascii=False)
    flow.phase_index = 0
    flow.queue_token = _queue_token(
        flow,
        VocabularyLearningQuestion.query.filter_by(flow_id=flow.id).all(),
    )
    return True


def _finish_group(flow, now):
    results = _json_list(flow.group_results_json)
    group_questions = _group_questions(flow)
    scored = [
        question
        for question in group_questions
        if question.score_eligible and question.first_attempt_id
    ]
    results.append(
        {
            "group_index": flow.current_group_index,
            "scorable_count": len(scored),
            "correct_count": sum(bool(question.first_is_correct) for question in scored),
            "retry_count": sum(
                bool(question.retry_attempt_id)
                or bool(question.remediation_kind and question.first_attempt_id)
                for question in group_questions
            ),
            "weak_word_ids": sorted(int(item) for item in _json_list(flow.weak_word_ids_json)),
        }
    )
    flow.group_results_json = json.dumps(results, ensure_ascii=False, sort_keys=True)
    if flow.current_group_index + 1 < flow.total_group_count:
        flow.current_group_index += 1
        flow.phase = PHASE_FAMILIARITY
        flow.phase_index = 0
        flow.viewed_word_ids_json = "[]"
        flow.retry_question_ids_json = "[]"
        flow.related_source_question_ids_json = "[]"
        flow.weak_word_ids_json = "[]"
        flow.remediation_wave = 1
        flow.pending_correction_question_id = None
    else:
        flow.phase = PHASE_COMPLETE
        flow.phase_index = 0
        flow.status = VocabularyLearningFlow.STATUS_COMPLETED
        flow.completed_at = now


def _advance_after_answer(flow, user, now):
    """Advance only from a server-validated current position."""

    while flow.status == VocabularyLearningFlow.STATUS_ACTIVE:
        # A wrong answer is followed by a persisted correction action before
        # any next formal task may be exposed. This also makes refreshes safe.
        if flow.pending_correction_question_id:
            return
        if flow.phase == PHASE_FAMILIARITY:
            group = _group_payload(flow) or {}
            viewed = set(_json_list(flow.viewed_word_ids_json))
            if not set(group.get("word_ids") or []).issubset(viewed):
                return
            flow.phase = PHASE_RECALL
            flow.phase_index = 0
        if flow.phase in PHASE_ORDER:
            questions = _group_questions(flow, flow.phase)
            if flow.phase_index < len(questions):
                return
            if flow.phase == PHASE_RECALL:
                flow.phase = PHASE_DISCRIMINATION
                flow.phase_index = 0
                continue
            if flow.phase == PHASE_DISCRIMINATION:
                production = _group_questions(flow, PHASE_PRODUCTION)
                if production:
                    flow.phase = PHASE_PRODUCTION
                    flow.phase_index = 0
                else:
                    _apply_context_once(flow, user, now)
                    _set_retry_questions(flow)
                continue
            if flow.phase == PHASE_PRODUCTION:
                _apply_context_once(flow, user, now)
                _set_retry_questions(flow)
                continue
        if flow.phase == PHASE_RETRY:
            retry_questions = _retry_questions(flow)
            if flow.phase_index < len(retry_questions):
                return
            if _prepare_related_remediations(flow, user, now):
                continue
            _finish_group(flow, now)
            continue
        if flow.phase == PHASE_COMPLETE:
            return


def _release_legacy_pending_correction(flow) -> None:
    """Unblock clients published before the correction UI existed."""

    if not flow.pending_correction_question_id:
        return
    question = db.session.get(
        VocabularyLearningQuestion,
        flow.pending_correction_question_id,
    )
    if question:
        _mark_weak_word(flow, question.word_id)
    flow.pending_correction_question_id = None


def _public_flow(flow):
    group = _group_payload(flow) or {"word_ids": [], "familiarity": [], "size": 0}
    viewed = set(_json_list(flow.viewed_word_ids_json))
    familiarity = [dict(item, viewed=item.get("word_id") in viewed) for item in group.get("familiarity", [])]
    current_question = None
    retry = False
    correction_question = None
    if flow.pending_correction_question_id:
        correction_question = db.session.get(
            VocabularyLearningQuestion,
            flow.pending_correction_question_id,
        )
    correction_required = correction_question is not None
    if correction_required:
        current_question = _public_question(correction_question, correction=True)
    elif flow.phase in PHASE_ORDER:
        questions = _group_questions(flow, flow.phase)
        if flow.phase_index < len(questions):
            current_question = _public_question(questions[flow.phase_index])
    elif flow.phase == PHASE_RETRY:
        questions = _retry_questions(flow)
        if flow.phase_index < len(questions):
            current_question = _public_question(questions[flow.phase_index], retry=True)
            retry = True
    diagnostics = [
        item
        for item in _json_list(flow.diagnostics_json)
        if item.get("group_index") == flow.current_group_index
    ]
    base_questions = _base_formal_questions(flow)
    base_completed = sum(bool(question.first_attempt_id) for question in base_questions)
    remediation_questions = [
        question
        for question in _group_questions(flow)
        if question.remediation_kind
        or question.retry_attempt_id
        or (question.first_attempt_id is not None and question.first_is_correct is not True)
    ]
    remediation_completed = sum(
        bool(question.retry_attempt_id)
        if question.remediation_kind is None
        else bool(question.first_attempt_id)
        for question in remediation_questions
    )
    remediation_budget = max(0, len(group.get("word_ids") or []) * MAX_REMEDIATION_PER_WORD)
    remediation_allocated = len(remediation_questions)
    pending_remediation = max(0, len(_retry_questions(flow)) - flow.phase_index) if flow.phase == PHASE_RETRY else 0
    return {
        "ok": True,
        "task_id": flow.task_id,
        "task_mode": "vocabulary_group_v2",
        "mode": "vocabulary_group_v2",
        "vocabulary_goal": flow.vocabulary_goal,
        "learning_goal": flow.vocabulary_goal,
        "dimensions": list(dimensions_for_goal(flow.vocabulary_goal)),
        "group_index": flow.current_group_index,
        "group_number": flow.current_group_index + 1,
        "group_count": flow.total_group_count,
        "group_size": group.get("size", 0),
        "total_word_count": flow.total_word_count,
        "phase": flow.phase,
        "phase_label": PHASE_LABELS.get(flow.phase, flow.phase),
        "phase_index": flow.phase_index,
        "viewed_word_ids": sorted(viewed),
        "familiarity": familiarity,
        "current_question": current_question,
        "retry": retry,
        "correction_required": correction_required,
        "correction_question_id": correction_question.id if correction_question else None,
        "base_progress_completed": min(base_completed, len(base_questions)),
        "base_progress_total": len(base_questions),
        "remediation_progress_completed": min(remediation_completed, remediation_allocated),
        # ``progress_total`` is the work actually allocated by observed
        # errors. The budget is a ceiling, not twelve promised questions.
        "remediation_progress_total": remediation_allocated,
        "remediation_allocated_total": remediation_allocated,
        "remediation_budget_total": remediation_budget,
        "remediation_pending_count": pending_remediation,
        "deferred_review_count": sum(
            bool(question.deferred_to_review)
            for question in _group_questions(flow)
        ),
        "weak_word_ids": sorted(int(item) for item in _json_list(flow.weak_word_ids_json)),
        "diagnostics": diagnostics,
        "queue_token": flow.queue_token,
        "completed": flow.status == VocabularyLearningFlow.STATUS_COMPLETED,
        "status": flow.status,
    }


def get_vocabulary_group_queue(
    user: User,
    task_id: int,
    *,
    now: datetime | None = None,
    supports_correction: bool = True,
) -> dict:
    now = utc_naive(now)
    task, existing_flow = _flow_or_error(user, task_id, lock=False)
    access = task_date_access(task, now)
    if access.read_only:
        if not existing_flow:
            return {
                "ok": True,
                "task_id": task.id,
                "task_mode": "vocabulary_group_v2",
                "mode": "vocabulary_group_v2",
                **access.as_dict(),
                "completed": access.completed,
                "status": task.status,
                "current_question": None,
                "familiarity": [],
            }
        result = _public_flow(existing_flow)
        result.update(access.as_dict())
        return result
    _require_daily_clearance(user, task_id, now)
    task, flow = _flow_or_error(user, task_id, lock=True)
    flow = flow or _ensure_flow(user, task, now)
    if not supports_correction:
        _release_legacy_pending_correction(flow)
    _advance_after_answer(flow, user, now)
    result = _public_flow(flow)
    result.update(access.as_dict())
    return result


def mark_familiarity_viewed(user: User, task_id: int, payload: dict, *, now=None) -> dict:
    now = utc_naive(now)
    _require_daily_clearance(user, task_id, now)
    task, flow = _flow_or_error(user, task_id, lock=True)
    flow = flow or _ensure_flow(user, task, now)
    supplied_token = str(payload.get("queue_token") or "").strip()
    if supplied_token != flow.queue_token:
        raise VocabularyGroupLearningError("queue_changed", 409, state=_public_flow(flow))
    if flow.status != VocabularyLearningFlow.STATUS_ACTIVE:
        return _public_flow(flow)
    if flow.phase != PHASE_FAMILIARITY:
        raise VocabularyGroupLearningError("familiarity_phase_complete", 409, state=_public_flow(flow))
    try:
        word_id = int(payload.get("word_id"))
    except (TypeError, ValueError) as error:
        raise VocabularyGroupLearningError("invalid_word_id", 400) from error
    group = _group_payload(flow) or {}
    word_ids = list(group.get("word_ids") or [])
    viewed = _json_list(flow.viewed_word_ids_json)
    expected = next((item for item in word_ids if item not in viewed), None)
    if word_id in viewed:
        return _public_flow(flow)
    if expected != word_id:
        raise VocabularyGroupLearningError(
            "familiarity_order_violation",
            409,
            expected_word_id=expected,
            state=_public_flow(flow),
        )
    viewed.append(word_id)
    expected_version = int(flow.state_version or 0)
    try:
        updated = db.session.execute(
            update(VocabularyLearningFlow)
            .where(
                VocabularyLearningFlow.id == flow.id,
                VocabularyLearningFlow.state_version == expected_version,
                VocabularyLearningFlow.current_group_index == flow.current_group_index,
                VocabularyLearningFlow.phase == PHASE_FAMILIARITY,
            )
            .values(
                viewed_word_ids_json=json.dumps(viewed),
                state_version=expected_version + 1,
            )
        )
    except OperationalError as error:
        raise VocabularyGroupLearningError("state_conflict", 409, retryable=True) from error
    if updated.rowcount != 1:
        raise VocabularyGroupLearningError("state_conflict", 409)
    flow.viewed_word_ids_json = json.dumps(viewed)
    flow.state_version = expected_version + 1
    _advance_after_answer(flow, user, now)
    return _public_flow(flow)


def _current_question(flow):
    if flow.phase in PHASE_ORDER:
        questions = _group_questions(flow, flow.phase)
        return questions[flow.phase_index] if flow.phase_index < len(questions) else None
    if flow.phase == PHASE_RETRY:
        questions = _retry_questions(flow)
        return questions[flow.phase_index] if flow.phase_index < len(questions) else None
    return None


def _grade_question(question, answer: str) -> bool:
    snapshot = _json_dict(question.question_snapshot_json)
    expected = _json_dict(question.answer_payload_json)
    if question.dimension == "context_use":
        return grade_context_answer(snapshot, expected, answer)
    if expected.get("answer_type") == "chinese":
        return is_chinese_answer_correct(answer, expected.get("answer") or "")
    return is_english_answer_correct(
        answer,
        expected.get("answer") or "",
        accepted_answers=expected.get("accepted_answers") or [],
    )


def _revealed_answer(question):
    snapshot = _json_dict(question.question_snapshot_json)
    expected = _json_dict(question.answer_payload_json)
    if expected.get("answer_type") != "option_id":
        return expected.get("answer")
    option_id = expected.get("answer_option_id")
    option = next(
        (item for item in snapshot.get("options") or [] if str(item.get("id")) == str(option_id)),
        None,
    )
    return option.get("label") if option else None


def _serialize_answer(question, record, *, idempotent=False):
    flow = question.flow
    correction_required = bool(
        flow
        and flow.pending_correction_question_id == question.id
        and question.first_is_correct is False
    )
    return {
        "ok": True,
        "is_correct": bool(record.is_correct),
        "first_attempt": bool(record.is_first_attempt),
        "idempotent": bool(idempotent),
        "attempt_id": record.attempt_id,
        "student_answer": record.student_answer,
        "first_attempt_id": question.first_attempt_id,
        "first_attempt_is_correct": question.first_is_correct,
        "first_attempt_answer": question.first_answer,
        "learning_question_id": question.id,
        "queue_item_id": question.id,
        "question_id": question.question_id,
        "word_id": question.word_id,
        "sense_id": question.sense_id,
        "dimension": question.dimension,
        "phase": question.phase,
        "revealed_answer": _revealed_answer(question),
        "retry_required": bool(question.first_is_correct is False and not question.retry_attempt_id),
        "correction_required": correction_required,
        "correction_count": int(question.correction_count or 0),
        "remediation_kind": question.remediation_kind,
        "queue_token": flow.queue_token if flow else None,
    }


def submit_vocabulary_group_answer(user: User, payload: dict, *, now=None) -> dict:
    now = utc_naive(now)
    try:
        task_id = int(payload.get("task_id"))
    except (TypeError, ValueError) as error:
        raise VocabularyGroupLearningError("invalid_task_id", 400) from error
    _require_daily_clearance(user, task_id, now)
    task, flow = _flow_or_error(user, task_id, lock=True)
    flow = flow or _ensure_flow(user, task, now)
    supplied_token = str(payload.get("queue_token") or "").strip()
    if supplied_token != flow.queue_token:
        raise VocabularyGroupLearningError("queue_changed", 409, state=_public_flow(flow))
    raw_attempt_id = str(payload.get("attempt_id") or "").strip()
    if not raw_attempt_id:
        raise VocabularyGroupLearningError("attempt_id_required", 400)
    if len(raw_attempt_id) > 96:
        raise VocabularyGroupLearningError("attempt_id_too_long", 400, max_length=96)
    if not isinstance(payload.get("retry"), bool):
        raise VocabularyGroupLearningError("attempt_phase_required", 400)
    supplied_retry = payload["retry"]
    existing_record = DictationRecord.query.filter_by(
        student_id=user.id,
        attempt_id=raw_attempt_id,
    ).first()
    if existing_record:
        question = VocabularyLearningQuestion.query.filter_by(
            flow_id=flow.id,
            question_id=existing_record.vocabulary_question_id,
        ).first()
        if question and existing_record.task_id == task_id:
            expected_retry = bool(question.remediation_kind) or not existing_record.is_first_attempt
            if supplied_retry != expected_retry:
                raise VocabularyGroupLearningError("attempt_phase_required", 400)
            return _serialize_answer(question, existing_record, idempotent=True)
        raise VocabularyGroupLearningError("attempt_id_conflict", 409)
    if supplied_retry != (flow.phase == PHASE_RETRY):
        raise VocabularyGroupLearningError(
            "question_not_current",
            409,
            state=_public_flow(flow),
        )
    if flow.status != VocabularyLearningFlow.STATUS_ACTIVE:
        raise VocabularyGroupLearningError("task_already_completed", 409, state=_public_flow(flow))
    question = _current_question(flow)
    if not question:
        raise VocabularyGroupLearningError("question_not_current", 409, state=_public_flow(flow))
    for field, expected in (
        ("learning_question_id", question.id),
        ("queue_item_id", question.id),
        ("question_id", question.question_id),
        ("word_id", question.word_id),
        ("sense_id", question.sense_id),
        ("dimension", question.dimension),
    ):
        if payload.get(field) in (None, "") or str(payload.get(field)) != str(expected):
            raise VocabularyGroupLearningError("question_not_current", 409, state=_public_flow(flow))
    answer = str(payload.get("answer") or "").strip()
    if not answer or len(answer) > 200:
        raise VocabularyGroupLearningError("missing_answer", 400)
    snapshot = _json_dict(question.question_snapshot_json)
    try:
        input_mode, input_grant_id = resolve_submission_input(
            user,
            snapshot.get("mode") or "en_to_zh",
            payload.get("input_mode"),
            task_id=task_id,
            now=now,
        )
    except ValueError as error:
        raise VocabularyGroupLearningError("invalid_input_mode", 400) from error
    is_correct = _grade_question(question, answer)
    is_first = question.first_attempt_id is None
    is_remediation = bool(question.remediation_kind)
    if is_remediation:
        if not supplied_retry:
            raise VocabularyGroupLearningError(
                "question_not_current",
                409,
                state=_public_flow(flow),
            )
    elif supplied_retry != (not is_first):
        raise VocabularyGroupLearningError(
            "question_not_current",
            409,
            state=_public_flow(flow),
        )
    attempt_id = raw_attempt_id
    if is_first and not is_remediation:
        attempt_id = attempt_id or f"vocabulary-group:{flow.id}:question:{question.id}"
    elif not is_first:
        if flow.phase != PHASE_RETRY or question.first_is_correct is not False:
            raise VocabularyGroupLearningError("question_not_current", 409, state=_public_flow(flow))
        attempt_id = attempt_id or f"vocabulary-group-retry:{flow.id}:question:{question.id}"
    else:
        attempt_id = attempt_id or f"vocabulary-group-remediation:{flow.id}:question:{question.id}"
    record = DictationRecord(
        student_id=user.id,
        task_id=task_id,
        book_id=question.book_id,
        word_id=question.word_id,
        student_answer=answer[:100],
        is_correct=is_correct,
        input_mode=input_mode,
        input_grant_id=input_grant_id,
        attempt_id=attempt_id,
        is_first_attempt=is_first,
        vocabulary_dimension=question.dimension,
        vocabulary_question_id=question.question_id,
        vocabulary_phase=question.phase,
        vocabulary_score_eligible=bool(question.score_eligible) if is_first else False,
        vocabulary_mastery_applied=False,
    )
    expected_version = int(flow.state_version or 0)
    next_phase_index = flow.phase_index + 1
    try:
        with db.session.begin_nested():
            if is_first:
                reserved = db.session.execute(
                    update(VocabularyLearningQuestion)
                    .where(
                        VocabularyLearningQuestion.id == question.id,
                        VocabularyLearningQuestion.first_attempt_id.is_(None),
                    )
                    .values(
                        first_attempt_id=attempt_id,
                        first_is_correct=is_correct,
                        first_answer=answer[:100],
                    )
                )
            else:
                reserved = db.session.execute(
                    update(VocabularyLearningQuestion)
                    .where(
                        VocabularyLearningQuestion.id == question.id,
                        VocabularyLearningQuestion.first_is_correct.is_(False),
                        VocabularyLearningQuestion.retry_attempt_id.is_(None),
                    )
                    .values(
                        retry_attempt_id=attempt_id,
                        retry_is_correct=is_correct,
                        retry_answer=answer[:100],
                    )
                )
            if reserved.rowcount != 1:
                raise _FlowRace()
            moved = db.session.execute(
                update(VocabularyLearningFlow)
                .where(
                    VocabularyLearningFlow.id == flow.id,
                    VocabularyLearningFlow.state_version == expected_version,
                    VocabularyLearningFlow.status == VocabularyLearningFlow.STATUS_ACTIVE,
                    VocabularyLearningFlow.current_group_index == flow.current_group_index,
                    VocabularyLearningFlow.phase == flow.phase,
                    VocabularyLearningFlow.phase_index == flow.phase_index,
                )
                .values(
                    phase_index=next_phase_index,
                    state_version=expected_version + 1,
                )
            )
            if moved.rowcount != 1:
                raise _FlowRace()
            db.session.add(record)
            db.session.flush()
    except _FlowRace as error:
        raise VocabularyGroupLearningError("state_conflict", 409) from error
    except OperationalError as error:
        raise VocabularyGroupLearningError("state_conflict", 409, retryable=True) from error
    except IntegrityError as error:
        duplicate = DictationRecord.query.filter_by(student_id=user.id, attempt_id=attempt_id).first()
        if duplicate and duplicate.vocabulary_question_id == question.question_id:
            return _serialize_answer(question, duplicate, idempotent=True)
        raise VocabularyGroupLearningError("attempt_id_conflict", 409) from error
    if is_first:
        question.first_attempt_id = attempt_id
        question.first_is_correct = is_correct
        question.first_answer = answer[:100]
        if question.phase == PHASE_RECALL and question.score_eligible and not question.mastery_applied:
            already_applied = any(
                item.mastery_applied
                for item in flow.questions
                if item.sense_id == question.sense_id
                and item.dimension == question.dimension
            )
            if not already_applied:
                mastery = _mastery_for(user.id, question.sense_id) or ensure_mastery(
                    user, question.word, question.sense
                )
                _apply_dimension_answer(
                    mastery,
                    question.dimension,
                    is_correct,
                    now,
                    bootstrap_dimensions=dimensions_for_goal(flow.vocabulary_goal),
                )
                question.mastery_applied = True
                record.vocabulary_mastery_applied = True
        elif question.phase == PHASE_DISCRIMINATION and question.context_role == "degraded":
            # The aggregate context result is applied at the phase boundary,
            # after we know there is no safe production question.
            pass
        elif is_remediation and not is_correct and not question.mastery_applied:
            mastery = _mastery_for(user.id, question.sense_id) or ensure_mastery(
                user, question.word, question.sense
            )
            _apply_dimension_answer(mastery, question.dimension, False, now)
            question.mastery_applied = True
            record.vocabulary_mastery_applied = True
            _mark_weak_word(flow, question.word_id)
    else:
        question.retry_attempt_id = attempt_id
        question.retry_is_correct = is_correct
        question.retry_answer = answer[:100]
    if (
        not is_correct
        and _uses_comprehensive_scheduler(flow)
        and payload.get("supports_correction", True) is not False
    ):
        # A correction is a one-shot action for the current formal attempt.
        # The same question may later be shown as a delayed retry, so its
        # idempotency slot must be reopened for that new attempt.
        question.correction_attempt_id = None
        question.correction_is_correct = None
        question.correction_answer = None
        question.correction_count = 0
        flow.pending_correction_question_id = question.id
    if is_first:
        question.first_attempt_id = attempt_id
        question.first_is_correct = is_correct
        question.first_answer = answer[:100]
    else:
        question.retry_attempt_id = attempt_id
        question.retry_is_correct = is_correct
        question.retry_answer = answer[:100]
    flow.phase_index = next_phase_index
    flow.state_version = expected_version + 1
    _advance_after_answer(flow, user, now)
    return _serialize_answer(question, record)


def submit_vocabulary_group_correction(user: User, payload: dict, *, now=None) -> dict:
    """Persist one immediate correction without creating a formal attempt."""

    now = utc_naive(now)
    try:
        task_id = int(payload.get("task_id"))
    except (TypeError, ValueError) as error:
        raise VocabularyGroupLearningError("invalid_task_id", 400) from error
    _require_daily_clearance(user, task_id, now)
    task, flow = _flow_or_error(user, task_id, lock=True)
    flow = flow or _ensure_flow(user, task, now)
    raw_attempt_id = str(payload.get("attempt_id") or "").strip()
    if not raw_attempt_id:
        raise VocabularyGroupLearningError("attempt_id_required", 400)
    if len(raw_attempt_id) > 96:
        raise VocabularyGroupLearningError("attempt_id_too_long", 400, max_length=96)
    try:
        question_id = int(payload.get("learning_question_id") or payload.get("queue_item_id"))
    except (TypeError, ValueError) as error:
        raise VocabularyGroupLearningError("invalid_learning_question_id", 400) from error
    question = db.session.get(VocabularyLearningQuestion, question_id)
    all_flow_questions = VocabularyLearningQuestion.query.filter_by(flow_id=flow.id).all()
    for candidate in all_flow_questions:
        if candidate.correction_attempt_id == raw_attempt_id:
            if candidate.id != question_id:
                raise VocabularyGroupLearningError("attempt_id_conflict", 409)
            exhausted = bool(
                candidate.correction_is_correct is False
                and int(candidate.correction_count or 0) >= MAX_CORRECTION_ATTEMPTS
            )
            result = _public_flow(flow)
            result.update(
                {
                    "correction_completed": bool(candidate.correction_is_correct) or exhausted,
                    "correction_required": not bool(candidate.correction_is_correct) and not exhausted,
                    "correction_idempotent": True,
                    "correction_is_correct": candidate.correction_is_correct,
                    "correction_attempt_id": candidate.correction_attempt_id,
                    "correction_count": candidate.correction_count,
                    "correction_limit": MAX_CORRECTION_ATTEMPTS,
                    "correction_retry_allowed": not bool(candidate.correction_is_correct) and not exhausted,
                    "correction_exhausted": exhausted,
                }
            )
            return result
    supplied_token = str(payload.get("queue_token") or "").strip()
    if supplied_token != flow.queue_token:
        raise VocabularyGroupLearningError("queue_changed", 409, state=_public_flow(flow))
    if not question or flow.pending_correction_question_id != question.id:
        raise VocabularyGroupLearningError("correction_not_current", 409, state=_public_flow(flow))
    if question.first_is_correct is not False:
        raise VocabularyGroupLearningError("correction_not_required", 409, state=_public_flow(flow))
    if int(question.correction_count or 0) >= MAX_CORRECTION_ATTEMPTS:
        raise VocabularyGroupLearningError("correction_limit_reached", 409, state=_public_flow(flow))
    answer = str(payload.get("answer") or "").strip()
    if not answer or len(answer) > 200:
        raise VocabularyGroupLearningError("missing_answer", 400)
    is_correct = _grade_question(question, answer)
    previous_count = int(question.correction_count or 0)
    state = correction_state(previous_count, is_correct)
    question.correction_attempt_id = raw_attempt_id
    question.correction_count = state["count"]
    question.correction_answer = answer[:100]
    question.correction_is_correct = is_correct

    # A failed same-dimension retry may earn one related-dimension diagnostic;
    # it is created only after this correction and after the retry wave ends.
    if (
        _uses_comprehensive_scheduler(flow)
        and question.remediation_kind is None
        and question.retry_is_correct is False
    ):
        related_sources = [
            int(item)
            for item in _json_list(flow.related_source_question_ids_json)
            if str(item).isdigit()
        ]
        if question.id not in related_sources:
            related_sources.append(question.id)
        flow.related_source_question_ids_json = json.dumps(
            related_sources,
            ensure_ascii=False,
        )
    # A wrong correction is feedback, not completion. Keep the same persisted
    # question current for one bounded retry. At the cap, mark it weak/deferred
    # and release the queue so a student can never be trapped by a bad input.
    if state["required"]:
        flow.state_version = int(flow.state_version or 0) + 1
    else:
        if state["exhausted"]:
            question.deferred_to_review = True
            _mark_weak_word(flow, question.word_id)
        flow.pending_correction_question_id = None
        flow.state_version = int(flow.state_version or 0) + 1
        _advance_after_answer(flow, user, now)
    result = _public_flow(flow)
    result.update(
        {
            "correction_completed": state["completed"],
            "correction_required": state["required"],
            "correction_is_correct": is_correct,
            "correction_attempt_id": raw_attempt_id,
            "correction_count": state["count"],
            "correction_limit": MAX_CORRECTION_ATTEMPTS,
            "correction_retry_allowed": state["retry_allowed"],
            "correction_exhausted": state["exhausted"],
        }
    )
    return result


def finalize_vocabulary_group_task(user: User, task_id: int, payload: dict, *, now=None) -> dict:
    now = utc_naive(now)
    _require_daily_clearance(user, task_id, now)
    task, flow = _flow_or_error(user, task_id, lock=True)
    flow = flow or _ensure_flow(user, task, now)
    supplied_token = str(payload.get("queue_token") or "").strip()
    if not supplied_token:
        raise VocabularyGroupLearningError("queue_token_required", 400)
    if supplied_token != flow.queue_token:
        raise VocabularyGroupLearningError("queue_changed", 409)
    if flow.status != VocabularyLearningFlow.STATUS_COMPLETED:
        raise VocabularyGroupLearningError("group_flow_incomplete", 409, state=_public_flow(flow))
    if flow.pending_correction_question_id:
        raise VocabularyGroupLearningError(
            "correction_incomplete",
            409,
            correction_question_id=flow.pending_correction_question_id,
        )
    settlement = VocabularyTaskSettlement.query.filter_by(
        student_id=user.id,
        task_id=task.id,
    ).first()
    if settlement:
        return _json_dict(settlement.result_json)
    questions = VocabularyLearningQuestion.query.filter_by(flow_id=flow.id).all()
    missing_retry = [
        question.id
        for question in questions
        if (
            question.remediation_kind is None
            and question.first_is_correct is False
            and not question.retry_attempt_id
            and not question.deferred_to_review
        )
        or (question.remediation_kind and not question.first_attempt_id)
    ]
    if missing_retry:
        raise VocabularyGroupLearningError(
            "retry_incomplete",
            409,
            missing_learning_question_ids=missing_retry,
        )
    scored = [
        question
        for question in questions
        if question.score_eligible and question.first_attempt_id
    ]
    correct_count = sum(bool(question.first_is_correct) for question in scored)
    total_count = len(scored)
    diagnostics = _json_list(flow.diagnostics_json)
    skipped_count = sum(
        1
        for item in diagnostics
        if item.get("reason") in {
            "missing_required_recall_material",
            "context_skipped_no_safe_question",
        }
    )
    accuracy = round(correct_count / total_count * 100, 1) if total_count else 0.0
    by_dimension = {}
    for question in scored:
        bucket = by_dimension.setdefault(question.dimension, {"correct": 0, "total": 0})
        bucket["total"] += 1
        bucket["correct"] += int(bool(question.first_is_correct))
    result = {
        "ok": True,
        "server_scored": True,
        "task_mode": "vocabulary_group_v2",
        "vocabulary_goal": flow.vocabulary_goal,
        "correct_count": correct_count,
        "total_count": total_count,
        "accuracy": accuracy,
        "completion_rate": 100.0,
        "dimensions": by_dimension,
        "group_count": flow.total_group_count,
        "total_word_count": flow.total_word_count,
        "scorable_count": total_count,
        "skipped_count": skipped_count,
        "guidance_count": sum(
            1 for question in questions if question.context_role == "guide" and question.first_attempt_id
        ),
        "retry_count": sum(
            bool(question.retry_attempt_id)
            or bool(question.remediation_kind and question.first_attempt_id)
            for question in questions
        ),
        "needs_review_count": sum(
            bool(
                (question.retry_attempt_id and question.retry_is_correct is False)
                or (
                    question.remediation_kind
                    and question.first_attempt_id
                    and question.first_is_correct is False
                )
            )
            for question in questions
        ),
        "remediation_budget_per_word": MAX_REMEDIATION_PER_WORD,
        "max_formal_questions_per_word": MAX_FORMAL_QUESTIONS_PER_WORD,
        "deferred_review_count": sum(bool(question.deferred_to_review) for question in questions),
        "weak_word_ids": sorted(int(item) for item in _json_list(flow.weak_word_ids_json)),
        "diagnostics": diagnostics,
        "queue_token": flow.queue_token,
    }
    duration = payload.get("duration_seconds")
    if duration is not None:
        try:
            task.actual_seconds = max(0, int(duration))
        except (TypeError, ValueError) as error:
            raise VocabularyGroupLearningError("invalid_duration", 400) from error
    task.student_submitted = True
    task.submitted_at = now
    task.accuracy = accuracy
    task.completion_rate = 100.0
    task.status = "done"
    settlement = VocabularyTaskSettlement(
        student_id=user.id,
        task_id=task.id,
        queue_token=flow.queue_token,
        result_json=json.dumps(result, ensure_ascii=False, sort_keys=True),
        settled_at=now,
    )
    db.session.add(settlement)
    try:
        db.session.flush()
    except OperationalError as error:
        raise VocabularyGroupLearningError("state_conflict", 409, retryable=True) from error
    except IntegrityError as error:
        db.session.rollback()
        existing = VocabularyTaskSettlement.query.filter_by(
            student_id=user.id,
            task_id=task.id,
        ).first()
        if existing:
            return _json_dict(existing.result_json)
        raise VocabularyGroupLearningError("settlement_conflict", 409) from error
    return result


def group_flow_diagnostics(user: User, task_id: int) -> dict:
    task, flow = _flow_or_error(user, task_id)
    if not flow:
        return {"ok": True, "task_id": task.id, "diagnostics": []}
    return {
        "ok": True,
        "task_id": task.id,
        "diagnostics": _json_list(flow.diagnostics_json),
        "group_results": _json_list(flow.group_results_json),
    }
