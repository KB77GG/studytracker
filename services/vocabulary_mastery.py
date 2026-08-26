"""Four-dimension vocabulary mastery and task-owned review snapshots.

The legacy dictation service remains the compatibility path. This service is
entered only when a Task has both a dictation book and an explicit
``vocabulary_goal``. It owns sense resolution, independent dimension schedules,
answer idempotency, and strict once-only task settlement.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timedelta, timezone

from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from dictation_answers import (
    canonical_vocabulary_word,
    is_chinese_answer_correct,
    is_english_answer_correct,
    parse_answer_variants,
    parse_vocabulary_word_variants,
)
from models import (
    DictationBook,
    DictationRecord,
    DictationWord,
    StudentVocabularyMastery,
    Task,
    User,
    VocabularyLearningFlow,
    VocabularyLearningQuestion,
    VocabularyReviewAttempt,
    VocabularyReviewItem,
    VocabularyReviewSession,
    VocabularyReviewSettlement,
    VocabularySense,
    VocabularyTaskReview,
    VocabularyTaskSettlement,
    db,
)
from services.dictation_input_policy import resolve_submission_input
from services.dictation_review import local_date
from services.vocabulary_context import build_context_question, grade_context_answer

UTC = timezone.utc  # noqa: UP017 - production remains Python 3.10 compatible

DIMENSIONS = StudentVocabularyMastery.DIMENSIONS
GOAL_DIMENSIONS = {
    "reading": ("meaning_recall", "context_use"),
    "writing": ("form_recall", "context_use"),
    "listening": ("meaning_recall", "audio_form_recall"),
    "comprehensive": DIMENSIONS,
}
VALID_GOALS = frozenset(GOAL_DIMENSIONS)
REVIEW_INTERVALS_DAYS = (1, 3, 7, 14, 30, 60)
CONTEXT_FIRST_DELAY_DAYS = 7
# The live catalog already contains mapped books with 906 and 922 entries.
# Keep a hard safety ceiling, but never silently cut a normal full-book task.
MAX_QUEUE_ITEMS = 1200
SAFE_ENGLISH_SEPARATORS = [" ", "-", "'"]
MAX_ENGLISH_ANSWER_LENGTH = 100


class VocabularyMasteryError(Exception):
    """Safe, user-facing error raised by the v2 service."""

    def __init__(self, error: str, status_code: int = 400, **details):
        super().__init__(error)
        self.error = error
        self.status_code = status_code
        self.details = details


def utc_naive(value: datetime | None = None) -> datetime:
    value = value or datetime.utcnow()
    if value.tzinfo is None:
        return value
    return value.astimezone(UTC).replace(tzinfo=None)


def normalize_goal(value) -> str | None:
    value = str(value or "").strip().lower()
    return value if value in VALID_GOALS else None


def resolve_task_vocabulary_goal(
    material_id,
    requested_goal=None,
    default_goal=None,
) -> str | None:
    """Return a vocabulary goal only for an explicitly selected dictation book."""
    if not str(material_id or "").strip().startswith("dictation-"):
        return None
    return normalize_goal(requested_goal or default_goal)


def vocabulary_goal_for_task(task: Task | None) -> str | None:
    """Hide stray vocabulary metadata on tasks that are not dictation tasks."""
    if not task or not getattr(task, "dictation_book_id", None):
        return None
    return normalize_goal(getattr(task, "vocabulary_goal", None))


def is_vocabulary_v2_task(task: Task | None) -> bool:
    return bool(vocabulary_goal_for_task(task))


def dimensions_for_goal(goal: str) -> tuple[str, ...]:
    normalized = normalize_goal(goal)
    if not normalized:
        raise VocabularyMasteryError("invalid_vocabulary_goal", 400)
    return GOAL_DIMENSIONS[normalized]


def default_goal_for_book_id(book_id: int | None) -> str | None:
    try:
        book_id = int(book_id)
    except (TypeError, ValueError):
        return None
    if 2 <= book_id <= 39:
        return "listening"
    if 40 <= book_id <= 165:
        return "reading"
    if 166 <= book_id <= 173 or 175 <= book_id <= 187:
        return "comprehensive"
    if book_id == 188:
        return "writing"
    if book_id == 192:
        return "listening"
    if book_id == 194:
        return "reading"
    return None


def default_course_system_for_book_id(book_id: int | None) -> str | None:
    try:
        book_id = int(book_id)
    except (TypeError, ValueError):
        return None
    if 2 <= book_id <= 39:
        return "IELTS"
    if 40 <= book_id <= 165 or book_id in {188, 192, 194}:
        return "TOEFL"
    if 166 <= book_id <= 173 or 175 <= book_id <= 187:
        return "general"
    return None


def _task_owner(task: Task, user: User) -> bool:
    profile = getattr(user, "student_profile", None)
    return bool(profile and task.student_name == profile.full_name)


def _normalize_key(value) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip().lower())


def _sense_key(word: DictationWord) -> str:
    lemma = _normalize_key(canonical_vocabulary_word(word.word, word.accepted_answers))
    if not lemma:
        lemma = f"unresolved-word-id:{word.id}"
    core_meaning = _normalize_key(word.core_meaning_zh)
    full_translation = _normalize_key(word.translation)
    if not core_meaning and not full_translation:
        # With no meaning evidence, never infer that two catalog rows are the
        # same sense merely because their spelling matches.
        full_translation = f"unresolved-word-id:{word.id}"
    # Keep homographs conservative: a shared short core meaning is not enough
    # to merge rows whose full translation/part-of-speech cue differs.
    return hashlib.sha256(
        f"{lemma}\x1f{core_meaning}\x1f{full_translation}".encode()
    ).hexdigest()


def ensure_word_sense(word: DictationWord) -> VocabularySense:
    if word.sense_id:
        sense = db.session.get(VocabularySense, word.sense_id)
        if sense:
            return sense
    key = _sense_key(word)
    sense = VocabularySense.query.filter_by(canonical_key=key).first()
    if not sense:
        candidate = VocabularySense(
            canonical_key=key,
            lemma=canonical_vocabulary_word(word.word, word.accepted_answers) or word.word,
            meaning_zh=word.core_meaning_zh or word.translation,
        )
        try:
            # Concurrent task initialization can race on the same sense. The
            # nested transaction lets the unique constraint decide, then the
            # losing transaction reads the winner without discarding its
            # caller's outer queue transaction.
            with db.session.begin_nested():
                db.session.add(candidate)
                db.session.flush()
            sense = candidate
        except IntegrityError:
            sense = VocabularySense.query.filter_by(canonical_key=key).first()
            if not sense:
                raise
    word.sense_id = sense.id
    return sense


def _mastery_for(student_id: int, sense_id: int) -> StudentVocabularyMastery | None:
    return StudentVocabularyMastery.query.filter_by(
        student_id=student_id,
        sense_id=sense_id,
    ).first()


def ensure_mastery(user: User, word: DictationWord, sense: VocabularySense) -> StudentVocabularyMastery:
    mastery = _mastery_for(user.id, sense.id)
    if mastery:
        if not mastery.representative_word_id:
            mastery.representative_word_id = word.id
        if not mastery.representative_book_id:
            mastery.representative_book_id = word.book_id
        return mastery
    candidate = StudentVocabularyMastery(
        student_id=user.id,
        sense_id=sense.id,
        representative_word_id=word.id,
        representative_book_id=word.book_id,
    )
    try:
        with db.session.begin_nested():
            db.session.add(candidate)
            db.session.flush()
        mastery = candidate
    except IntegrityError:
        mastery = _mastery_for(user.id, sense.id)
        if mastery is None:
            raise
    return mastery


def _assigned_words(task: Task) -> list[DictationWord]:
    start = max(1, int(task.dictation_word_start or 1))
    query = DictationWord.query.filter(
        DictationWord.book_id == task.dictation_book_id,
        DictationWord.sequence >= start,
    )
    if task.dictation_word_end:
        query = query.filter(DictationWord.sequence <= int(task.dictation_word_end))
    words = query.order_by(DictationWord.sequence.asc(), DictationWord.id.asc()).all()
    if str(getattr(task, "dictation_order", "") or "").strip().lower() == "random":
        words.sort(
            key=lambda word: hashlib.sha256(
                f"vocabulary:{task.id}:{word.id}".encode()
            ).hexdigest()
        )
    return words


def _safe_json(value) -> dict:
    try:
        parsed = json.loads(value or "{}") if isinstance(value, str) else value
    except (TypeError, ValueError):
        parsed = {}
    return parsed if isinstance(parsed, dict) else {}


def _english_word_variants(word: DictationWord) -> list[str]:
    variants = parse_vocabulary_word_variants(word.word)
    seen = set(variants)
    for variant in parse_vocabulary_word_variants(
        word.accepted_answers,
        allow_approved_delimiters=True,
    ):
        if variant not in seen:
            variants.append(variant)
            seen.add(variant)
    return variants


def build_meaning_recall_options(word, candidates, seed: str, limit: int = 4) -> list[dict]:
    """Build stable Chinese choices while keeping free-text grading compatible."""

    correct = " ".join(
        str(getattr(word, "core_meaning_zh", None) or getattr(word, "translation", None) or "").split()
    ).strip()
    if not correct:
        return []
    distractors = []
    seen = {correct}
    ordered = sorted(
        list(candidates or []),
        key=lambda candidate: hashlib.sha256(
            f"{seed}|candidate|{getattr(candidate, 'id', '')}".encode()
        ).hexdigest(),
    )
    for candidate in ordered:
        label = " ".join(
            str(
                getattr(candidate, "core_meaning_zh", None)
                or getattr(candidate, "translation", None)
                or ""
            ).split()
        ).strip()
        if not label or label in seen:
            continue
        seen.add(label)
        distractors.append(label)
        if len(distractors) >= max(0, limit - 1):
            break
    labels = [correct, *distractors]
    labels.sort(key=lambda label: hashlib.sha256(f"{seed}|option|{label}".encode()).hexdigest())
    return [
        {
            "id": "meaning_"
            + hashlib.sha256(f"{seed}|{index}|{label}".encode()).hexdigest()[:16],
            "label": label,
        }
        for index, label in enumerate(labels)
    ]


def _question_for(word, dimension, goal, stage, candidates):
    seed = f"v2:{word.id}:{word.sense_id}:{dimension}:{goal}:{stage}"
    if dimension == "context_use":
        result = build_context_question(
            word,
            candidates,
            seed=seed,
            rotation=stage,
        )
        if not result:
            return None
        public, answer = result
        public = dict(public)
        public["dimension"] = dimension
        return public, answer

    if dimension == "meaning_recall":
        listening_mode = goal == "listening"
        mode = "audio_to_zh" if listening_mode else "en_to_zh"
        meaning = str(word.core_meaning_zh or word.translation or "").strip()
        if not meaning or (not listening_mode and not canonical_vocabulary_word(word.word, word.accepted_answers)):
            return None
        prompt = {
            "instruction": "听音选择/填写中文释义" if listening_mode else "看英文填写中文释义",
            "phonetic": word.phonetic if not listening_mode else None,
            # The word-id endpoint serves imported audio when available and
            # falls back to TTS without exposing answer text in the snapshot.
            "audio_tts_url": f"/dictation/words/{word.id}/tts",
        }
        if not listening_mode:
            prompt["word"] = canonical_vocabulary_word(word.word, word.accepted_answers)
        answer = meaning
        answer_type = "chinese"
        options = build_meaning_recall_options(word, candidates, seed) if listening_mode else []
    elif dimension == "form_recall":
        mode = "zh_to_en"
        meaning = str(word.core_meaning_zh or word.translation or "").strip()
        if not meaning:
            return None
        variants = _english_word_variants(word)
        if not variants:
            return None
        prompt = {
            "instruction": "根据中文释义填写英文单词",
            "meaning": meaning,
        }
        answer = variants[0]
        answer_type = "english"
        options = []
    else:
        mode = "audio_to_en"
        prompt = {
            "instruction": "听音填写英文单词",
            "phonetic": word.phonetic,
            "audio_tts_url": f"/dictation/words/{word.id}/tts",
        }
        variants = _english_word_variants(word)
        if not variants:
            return None
        answer = variants[0]
        answer_type = "english"
        options = []

    question_id = hashlib.sha256(
        json.dumps(
            {"seed": seed, "mode": mode, "prompt": prompt, "options": options},
            ensure_ascii=False,
            sort_keys=True,
        ).encode("utf-8")
    ).hexdigest()[:24]
    return (
        {
            "question_id": f"recall_{question_id}",
            "dimension": dimension,
            "kind": dimension,
            "mode": mode,
            "prompt": prompt,
            "options": options,
            "answer_type": answer_type,
        },
        {
            "answer": answer,
            "accepted_answers": [variant for variant in variants[1:]]
            if answer_type == "english"
            else parse_answer_variants(word.accepted_answers),
            "answer_type": answer_type,
        },
    )


def _dimension_stage(mastery, dimension) -> int:
    return int(getattr(mastery, f"{dimension}_stage") or 0)


def _dimension_due(mastery, dimension):
    return getattr(mastery, f"{dimension}_next_due_at")


def _is_due_for_new_task(mastery, dimension, now: datetime) -> bool:
    stage = _dimension_stage(mastery, dimension)
    due = _dimension_due(mastery, dimension)
    if stage == 0 and due is None:
        # Context starts after the first exposure; its row exists from day 0.
        return dimension != "context_use"
    return bool(due and due <= now)


def _candidate_dimensions(
    task,
    sense_id,
    mastery,
    dimensions,
    now,
    claimed,
    *,
    allow_early=False,
):
    """Return ordered candidates; the caller still creates only one item."""

    due = []
    new = []
    early = []
    for dimension in dimensions:
        dimension_due = _dimension_due(mastery, dimension)
        if dimension_due and dimension_due <= now:
            if (sense_id, dimension) not in claimed:
                due.append((dimension_due, dimension))
        elif (
            _dimension_stage(mastery, dimension) == 0
            and dimension_due is None
            and dimension != "context_use"
        ):
            new.append(dimension)
        elif (
            allow_early
            and _dimension_stage(mastery, dimension) > 0
            and dimension_due
            and dimension_due > now
            and (sense_id, dimension) not in claimed
        ):
            # A teacher may deliberately assign a word before its scheduled
            # review. It remains answerable, while _apply_dimension_answer
            # records a correct response without advancing the interval.
            early.append((dimension_due, dimension))
    due.sort(
        key=lambda pair: (
            pair[0],
            hashlib.sha256(f"{task.id}:{sense_id}:{pair[1]}".encode()).hexdigest(),
        )
    )
    new.sort(
        key=lambda dimension: hashlib.sha256(
            f"{task.id}:{sense_id}:{dimension}".encode()
        ).hexdigest()
    )
    early.sort(
        key=lambda pair: (
            pair[0],
            hashlib.sha256(f"{task.id}:{sense_id}:{pair[1]}".encode()).hexdigest(),
        )
    )
    return (
        [dimension for _due_at, dimension in due]
        + new
        + [dimension for _due_at, dimension in early]
    )


def _queue_token(items: list[VocabularyTaskReview]) -> str:
    raw = "|".join(
        f"{item.id}:{item.question_id}:{item.dimension}:{item.sense_id}"
        for item in items
    )
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _public_item(item: VocabularyTaskReview) -> dict:
    snapshot = _safe_json(item.question_snapshot_json)
    answer_payload = _safe_json(item.answer_payload_json)
    english_mode = snapshot.get("mode") in {"audio_to_en", "zh_to_en", "context_fill"}
    mastery = _mastery_for(item.student_id, item.sense_id)
    payload = {
        "id": item.word_id,
        "word_id": item.word_id,
        "queue_item_id": item.id,
        "task_id": item.task_id,
        "book_id": item.book_id,
        "sense_id": item.sense_id,
        "dimension": item.dimension,
        "source": item.source,
        "question_id": item.question_id,
        "question": snapshot,
        "mode": snapshot.get("mode"),
        "dictation_mode": snapshot.get("mode"),
        "first_attempt_id": item.first_attempt_id,
        "first_is_correct": item.first_is_correct,
        "first_answer": item.first_answer,
        "stage": _dimension_stage(mastery, item.dimension) if mastery else 0,
        # A fixed capability limit supports the shared keyboard without
        # leaking the exact answer length before the first submission.
        "answer_length": MAX_ENGLISH_ANSWER_LENGTH if english_mode else 0,
        # Structural keyboard capability only; the answer and accepted forms
        # remain server-side.  Supplying all safe separators avoids exposing
        # the answer shape while still supporting phrases/hyphen/apostrophe.
        "answer_separators": SAFE_ENGLISH_SEPARATORS if english_mode else [],
    }
    # A queue refresh may restore an already submitted first attempt.  The
    # correction is safe only after the server has recorded that attempt; an
    # untouched item must remain answer-blind.
    if item.first_attempt_id:
        revealed_answer = answer_payload.get("answer")
        revealed_answer_option_id = None
        if answer_payload.get("answer_type") == "option_id":
            revealed_answer_option_id = answer_payload.get("answer_option_id")
            correct_option = next(
                (
                    option
                    for option in snapshot.get("options") or []
                    if str(option.get("id")) == str(revealed_answer_option_id)
                ),
                None,
            )
            revealed_answer = correct_option.get("label") if correct_option else None
        payload["revealed_answer"] = revealed_answer
        payload["revealed_answer_option_id"] = revealed_answer_option_id
    # Convenience fields are prompt-only and never contain the answer for the
    # current question. They make the existing practice page able to render
    # audio/meaning prompts while it migrates to the nested question contract.
    prompt = snapshot.get("prompt") or {}
    payload.update(
        {
            "word": prompt.get("word"),
            "translation": prompt.get("meaning"),
            "phonetic": prompt.get("phonetic"),
            "audio_tts_url": prompt.get("audio_tts_url"),
            "core_meaning_zh": prompt.get("meaning"),
        }
    )
    return payload


def get_vocabulary_task_queue(user: User, task_id: int, now: datetime | None = None) -> dict:
    now = utc_naive(now)
    review_day = local_date(now)
    task = Task.query.filter_by(id=task_id).with_for_update().first()
    if not task:
        raise VocabularyMasteryError("task_not_found", 404)
    if not _task_owner(task, user):
        raise VocabularyMasteryError("forbidden", 403)
    goal = normalize_goal(getattr(task, "vocabulary_goal", None))
    if not goal or not task.dictation_book_id:
        raise VocabularyMasteryError("task_not_vocabulary_v2", 409)
    book = db.session.get(DictationBook, task.dictation_book_id)
    if not book:
        raise VocabularyMasteryError("dictation_book_not_found", 404)

    existing = (
        VocabularyTaskReview.query.filter_by(student_id=user.id, task_id=task.id)
        .order_by(VocabularyTaskReview.queue_index.asc(), VocabularyTaskReview.id.asc())
        .all()
    )
    if not existing:
        assigned = _assigned_words(task)
        if not assigned:
            raise VocabularyMasteryError("empty_vocabulary_task", 409)
        if len(assigned) > MAX_QUEUE_ITEMS:
            raise VocabularyMasteryError(
                "vocabulary_range_too_large",
                409,
                assigned_count=len(assigned),
                max_count=MAX_QUEUE_ITEMS,
            )
        candidates = (
            DictationWord.query.filter_by(book_id=book.id)
            .order_by(DictationWord.id.asc())
            .all()
        )
        dimensions = dimensions_for_goal(goal)
        # Resolve current-book sense links before creating the task snapshot.
        # This lets a sense learned from another book retain one mastery key.
        for candidate in candidates:
            ensure_word_sense(candidate)
        db.session.flush()
        targets = []
        for word in assigned:
            sense = ensure_word_sense(word)
            mastery = ensure_mastery(user, word, sense)
            targets.append((word, sense, mastery, VocabularyTaskReview.SOURCE_ASSIGNED))

        snapshots = []
        # Autonomous due states are claimed by VocabularyReviewSession.  A
        # teacher task never receives those rows, so its score and denominator
        # remain task-owned even when the due word comes from another book.
        claimed = set()
        seen_senses = set()
        for word, sense, mastery, target_source in targets:
            if sense.id in seen_senses:
                continue
            candidate_dimensions = _candidate_dimensions(
                task,
                sense.id,
                mastery,
                dimensions,
                now,
                claimed,
                allow_early=target_source == VocabularyTaskReview.SOURCE_ASSIGNED,
            )
            for dimension in candidate_dimensions:
                question = _question_for(
                    word,
                    dimension,
                    goal,
                    _dimension_stage(mastery, dimension),
                    candidates,
                )
                # Missing context/audio material safely falls through to the
                # next target dimension; it never fabricates a question.
                if not question:
                    continue
                public, answer = question
                dimension_due = _dimension_due(mastery, dimension)
                source = VocabularyTaskReview.SOURCE_ASSIGNED
                snapshot = VocabularyTaskReview(
                    student_id=user.id,
                    task_id=task.id,
                    book_id=book.id,
                    word_id=word.id,
                    sense_id=sense.id,
                    dimension=dimension,
                    source=source,
                    review_date=review_day,
                    mastery_due_at=dimension_due if dimension_due and dimension_due <= now else None,
                    queue_index=len(snapshots),
                    question_id=public["question_id"],
                    question_snapshot_json=json.dumps(public, ensure_ascii=False, sort_keys=True),
                    answer_payload_json=json.dumps(answer, ensure_ascii=False, sort_keys=True),
                )
                db.session.add(snapshot)
                snapshots.append(snapshot)
                claimed.add((sense.id, dimension))
                seen_senses.add(sense.id)
                break
            if len(snapshots) >= MAX_QUEUE_ITEMS:
                break
        if not snapshots:
            raise VocabularyMasteryError("no_qualified_vocabulary_questions", 409)
        db.session.flush()
        existing = snapshots

    items = [_public_item(item) for item in existing]
    return {
        "ok": True,
        "task_id": task.id,
        "book_id": book.id,
        "vocabulary_goal": goal,
        "learning_goal": goal,
        "dimensions": list(dimensions_for_goal(goal)),
        "task_mode": "vocabulary_v2",
        "mode": "vocabulary_v2",
        "total_count": len(items),
        "assigned_count": sum(
            item["source"] == VocabularyTaskReview.SOURCE_ASSIGNED for item in items
        ),
        # Kept for the old renderer's response contract.  This flow is now
        # always zero: due rows belong to the independent review session.
        "auto_review_count": 0,
        "strict_submission": True,
        "queue_token": _queue_token(existing),
        "words": items,
    }


def _find_item(user: User, task_id: int, payload: dict) -> VocabularyTaskReview | None:
    item_id = payload.get("queue_item_id")
    if item_id not in (None, ""):
        try:
            return VocabularyTaskReview.query.filter_by(
                id=int(item_id), student_id=user.id, task_id=task_id
            ).with_for_update().first()
        except (TypeError, ValueError) as error:
            raise VocabularyMasteryError("invalid_queue_item_id", 400) from error
    word_id = payload.get("word_id")
    dimension = str(payload.get("dimension") or "").strip().lower()
    if word_id and dimension in DIMENSIONS:
        return VocabularyTaskReview.query.filter_by(
            student_id=user.id,
            task_id=task_id,
            word_id=int(word_id),
            dimension=dimension,
        ).with_for_update().first()
    return None


def _grade_recall(item: VocabularyTaskReview, answer: str) -> bool:
    expected = _safe_json(item.answer_payload_json)
    answer_type = expected.get("answer_type")
    if answer_type == "chinese":
        return is_chinese_answer_correct(answer, expected.get("answer") or "")
    return is_english_answer_correct(
        answer,
        expected.get("answer") or "",
        accepted_answers=expected.get("accepted_answers") or [],
    )


def _refresh_global_mastery(mastery, now: datetime):
    if all(
        int(getattr(mastery, f"{dimension}_stage") or 0) >= 6
        for dimension in DIMENSIONS
    ):
        if mastery.long_term_mastered_at is None:
            mastery.long_term_mastered_at = now
    else:
        mastery.long_term_mastered_at = None


def required_dimensions_long_term(mastery, goal: str) -> bool:
    return all(
        int(getattr(mastery, f"{dimension}_stage") or 0) >= 6
        for dimension in dimensions_for_goal(goal)
    )


def _bootstrap_unstarted_dimensions(mastery, dimensions, now: datetime):
    """Schedule untouched target dimensions after the first successful answer."""

    for dimension in dimensions or ():
        if dimension == "context_use":
            continue
        if _dimension_stage(mastery, dimension) == 0 and _dimension_due(mastery, dimension) is None:
            setattr(
                mastery,
                f"{dimension}_next_due_at",
                now + timedelta(days=REVIEW_INTERVALS_DAYS[0]),
            )


def _apply_dimension_answer(
    mastery,
    dimension: str,
    is_correct: bool,
    now: datetime,
    *,
    bootstrap_dimensions=(),
):
    stage_attr = f"{dimension}_stage"
    due_attr = f"{dimension}_next_due_at"
    last_attr = f"{dimension}_last_answered_at"
    long_attr = f"{dimension}_long_term_at"
    stage = int(getattr(mastery, stage_attr) or 0)
    due = getattr(mastery, due_attr)
    setattr(mastery, last_attr, now)
    if not is_correct:
        setattr(mastery, stage_attr, 0)
        setattr(mastery, due_attr, now + timedelta(days=1))
        setattr(mastery, long_attr, None)
        # A failed dimension invalidates the aggregate status, but leaves the
        # other dimensions' long-term timestamps untouched.
        mastery.long_term_mastered_at = None
        return {
            "advanced": False,
            "stage": 0,
            "next_due_at": getattr(mastery, due_attr),
        }

    # A correct answer before the scheduled window is recorded but cannot
    # accelerate the interval chain. Initial exposure has no due date and is
    # the one intentional exception.
    if stage > 0 and due is not None and now < due:
        return {"advanced": False, "stage": stage, "next_due_at": due}

    next_stage = min(6, stage + 1)
    setattr(mastery, stage_attr, next_stage)
    next_due = now + timedelta(days=REVIEW_INTERVALS_DAYS[next_stage - 1])
    setattr(mastery, due_attr, next_due)
    if next_stage >= 6:
        setattr(mastery, long_attr, now)
    _refresh_global_mastery(mastery, now)

    # Context is intentionally scheduled seven days after the first successful
    # non-context exposure, while its row existed from initialization.
    if dimension != "context_use":
        if "context_use" in bootstrap_dimensions:
            context_due = mastery.context_use_next_due_at
            if (
                int(mastery.context_use_stage or 0) == 0
                and context_due is None
            ):
                mastery.context_use_next_due_at = now + timedelta(days=CONTEXT_FIRST_DELAY_DAYS)
        _bootstrap_unstarted_dimensions(mastery, bootstrap_dimensions, now)
    return {"advanced": True, "stage": next_stage, "next_due_at": next_due}


def _serialize_answer(item, record, mastery, *, idempotent=False):
    answer_payload = _safe_json(item.answer_payload_json)
    public_snapshot = _safe_json(item.question_snapshot_json)
    revealed_answer = answer_payload.get("answer")
    revealed_answer_option_id = None
    if answer_payload.get("answer_type") == "option_id":
        revealed_answer_option_id = answer_payload.get("answer_option_id")
        correct_option = next(
            (
                option
                for option in public_snapshot.get("options") or []
                if str(option.get("id")) == str(revealed_answer_option_id)
            ),
            None,
        )
        # The public options were frozen before the attempt. It is safe to
        # resolve the server-only option id after submission, while keeping it
        # absent from the queue response.
        revealed_answer = correct_option.get("label") if correct_option else None
    return {
        "ok": True,
        "is_correct": bool(record.is_correct),
        "first_attempt": bool(record.is_first_attempt),
        "student_answer": record.student_answer,
        "first_attempt_id": item.first_attempt_id,
        "first_attempt_is_correct": item.first_is_correct,
        "first_attempt_answer": item.first_answer,
        "idempotent": bool(idempotent),
        "attempt_id": record.attempt_id,
        "queue_item_id": item.id,
        "word_id": item.word_id,
        "question_id": item.question_id,
        "dimension": item.dimension,
        "revealed_answer": revealed_answer,
        "revealed_answer_option_id": revealed_answer_option_id,
        "next_due_at": getattr(mastery, f"{item.dimension}_next_due_at", None).isoformat()
        if mastery and getattr(mastery, f"{item.dimension}_next_due_at", None)
        else None,
        "stage": int(getattr(mastery, f"{item.dimension}_stage", 0) or 0)
        if mastery
        else 0,
    }


def submit_vocabulary_answer(user: User, payload: dict, *, now: datetime | None = None) -> dict:
    now = utc_naive(now)
    try:
        task_id = int(payload.get("task_id"))
    except (TypeError, ValueError) as error:
        raise VocabularyMasteryError("invalid_task_id", 400) from error
    task = Task.query.filter_by(id=task_id).first()
    if not task:
        raise VocabularyMasteryError("task_not_found", 404)
    if not _task_owner(task, user):
        raise VocabularyMasteryError("forbidden", 403)
    if not is_vocabulary_v2_task(task):
        raise VocabularyMasteryError("task_not_vocabulary_v2", 409)

    raw_attempt_id = str(payload.get("attempt_id") or "").strip()
    if len(raw_attempt_id) > 96:
        raise VocabularyMasteryError("attempt_id_too_long", 400, max_length=96)
    if raw_attempt_id:
        existing_record = DictationRecord.query.filter_by(
            student_id=user.id,
            attempt_id=raw_attempt_id,
        ).first()
        if existing_record and existing_record.vocabulary_task_review_id:
            item = db.session.get(VocabularyTaskReview, existing_record.vocabulary_task_review_id)
            if item and item.task_id == task_id:
                mastery = _mastery_for(user.id, item.sense_id)
                return _serialize_answer(item, existing_record, mastery, idempotent=True)
        if existing_record:
            raise VocabularyMasteryError("attempt_id_conflict", 409)

    item = _find_item(user, task_id, payload)
    if not item:
        raise VocabularyMasteryError("question_not_in_queue", 409)
    try:
        supplied_word_id = int(payload.get("word_id"))
    except (TypeError, ValueError) as error:
        raise VocabularyMasteryError("invalid_word_id", 400) from error
    supplied_dimension = str(payload.get("dimension") or "").strip().lower()
    if supplied_word_id != item.word_id or supplied_dimension != item.dimension:
        raise VocabularyMasteryError("question_not_in_queue", 409)
    if str(payload.get("question_id") or "").strip() != item.question_id:
        raise VocabularyMasteryError("question_changed", 409)
    answer = str(payload.get("answer") or "").strip()
    if not answer or len(answer) > 200:
        raise VocabularyMasteryError("missing_answer", 400)

    snapshot = _safe_json(item.question_snapshot_json)
    try:
        requested_input = payload.get("input_mode")
        input_mode, input_grant_id = resolve_submission_input(
            user,
            snapshot.get("mode") or "en_to_zh",
            requested_input,
            task_id=task_id,
            now=now,
        )
    except ValueError as error:
        raise VocabularyMasteryError("invalid_input_mode", 400) from error
    if item.dimension == "context_use":
        is_correct = grade_context_answer(
            snapshot,
            _safe_json(item.answer_payload_json),
            answer,
        )
    else:
        is_correct = _grade_recall(item, answer)
    is_first = item.first_attempt_id is None
    attempt_id = raw_attempt_id
    if is_first:
        attempt_id = attempt_id or f"v2:{user.id}:{task_id}:{item.id}"
    else:
        attempt_id = attempt_id or f"v2-retry:{user.id}:{task_id}:{item.id}:{now.timestamp()}"

    record = DictationRecord(
        student_id=user.id,
        task_id=task_id,
        book_id=item.book_id,
        word_id=item.word_id,
        student_answer=answer[:100],
        is_correct=is_correct,
        input_mode=input_mode,
        input_grant_id=input_grant_id,
        attempt_id=attempt_id,
        is_first_attempt=is_first,
        vocabulary_task_review_id=item.id,
        vocabulary_dimension=item.dimension,
        vocabulary_question_id=item.question_id,
    )
    try:
        with db.session.begin_nested():
            db.session.add(record)
            db.session.flush()
    except IntegrityError as error:
        duplicate = DictationRecord.query.filter_by(
            student_id=user.id,
            attempt_id=attempt_id,
        ).first()
        if duplicate and duplicate.vocabulary_task_review_id == item.id:
            mastery = _mastery_for(user.id, item.sense_id)
            return _serialize_answer(item, duplicate, mastery, idempotent=True)
        raise VocabularyMasteryError("attempt_id_conflict", 409) from error

    mastery = _mastery_for(user.id, item.sense_id)
    if mastery is None:
        mastery = ensure_mastery(user, item.word, item.sense)
    if is_first:
        item.first_attempt_id = attempt_id
        item.first_is_correct = is_correct
        item.first_answer = answer[:100]
        # If this word/dimension was due before the teacher snapshot was
        # created, the independent review session owns that due window.  The
        # teacher task may still be answered, but it cannot consume or reset
        # the autonomous schedule.
        teacher_snapshot_was_due = bool(
            item.mastery_due_at and item.mastery_due_at <= now
        )
        if not teacher_snapshot_was_due:
            _apply_dimension_answer(
                mastery,
                item.dimension,
                is_correct,
                now,
                bootstrap_dimensions=dimensions_for_goal(task.vocabulary_goal),
            )
            item.state_applied = True
        else:
            item.state_applied = True
    return _serialize_answer(item, record, mastery)


def _vocabulary_queue_missing(items):
    return [item.id for item in items if not item.first_attempt_id]


def finalize_vocabulary_task(user: User, task_id: int, payload: dict, *, now=None) -> dict:
    now = utc_naive(now)
    task = Task.query.filter_by(id=task_id).with_for_update().first()
    if not task:
        raise VocabularyMasteryError("task_not_found", 404)
    if not _task_owner(task, user):
        raise VocabularyMasteryError("forbidden", 403)
    if not is_vocabulary_v2_task(task):
        raise VocabularyMasteryError("task_not_vocabulary_v2", 409)
    settlement = VocabularyTaskSettlement.query.filter_by(
        student_id=user.id,
        task_id=task.id,
    ).with_for_update().first()
    if settlement:
        return _safe_json(settlement.result_json)
    items = (
        VocabularyTaskReview.query.filter_by(student_id=user.id, task_id=task.id)
        .order_by(VocabularyTaskReview.queue_index.asc())
        .with_for_update()
        .all()
    )
    if not items:
        raise VocabularyMasteryError("queue_not_initialized", 409)
    expected_token = _queue_token(items)
    supplied_token = str(payload.get("queue_token") or "").strip()
    if supplied_token and supplied_token != expected_token:
        raise VocabularyMasteryError("queue_changed", 409)
    missing = _vocabulary_queue_missing(items)
    if missing:
        raise VocabularyMasteryError(
            "queue_incomplete",
            409,
            missing_queue_item_ids=missing,
            total_count=len(items),
        )
    records = []
    for item in items:
        record = DictationRecord.query.filter_by(
            student_id=user.id,
            vocabulary_task_review_id=item.id,
            is_first_attempt=True,
            attempt_id=item.first_attempt_id,
        ).first()
        if not record:
            raise VocabularyMasteryError(
                "queue_incomplete",
                409,
                missing_queue_item_ids=[item.id],
                total_count=len(items),
            )
        records.append(record)
    # Apply deferred due-review correct answers exactly once, immediately
    # before settlement is persisted. Repeated finalize calls return the
    # settlement row and cannot advance a second time.
    for item in items:
        if item.state_applied or not item.first_is_correct:
            continue
        mastery = _mastery_for(user.id, item.sense_id)
        if mastery is None:
            mastery = ensure_mastery(user, item.word, item.sense)
        _apply_dimension_answer(
            mastery,
            item.dimension,
            True,
            now,
            bootstrap_dimensions=dimensions_for_goal(task.vocabulary_goal),
        )
        item.state_applied = True
    duration = payload.get("duration_seconds")
    try:
        duration = max(0, int(duration)) if duration is not None else None
    except (TypeError, ValueError) as error:
        raise VocabularyMasteryError("invalid_duration", 400) from error

    correct_count = sum(bool(record.is_correct) for record in records)
    by_dimension = {}
    for item, record in zip(items, records, strict=True):
        bucket = by_dimension.setdefault(item.dimension, {"correct": 0, "total": 0})
        bucket["total"] += 1
        bucket["correct"] += int(bool(record.is_correct))
    accuracy = round(correct_count / len(records) * 100, 1) if records else 0.0
    result = {
        "ok": True,
        "server_scored": True,
        "vocabulary_goal": normalize_goal(task.vocabulary_goal),
        "correct_count": correct_count,
        "total_count": len(records),
        "accuracy": accuracy,
        "dimensions": by_dimension,
        "queue_token": expected_token,
    }
    if duration is not None:
        task.actual_seconds = duration
    task.student_submitted = True
    task.submitted_at = now
    task.accuracy = accuracy
    task.completion_rate = 100.0
    task.status = "done"
    settlement = VocabularyTaskSettlement(
        student_id=user.id,
        task_id=task.id,
        queue_token=expected_token,
        result_json=json.dumps(result, ensure_ascii=False, sort_keys=True),
        settled_at=now,
    )
    db.session.add(settlement)
    try:
        db.session.flush()
    except IntegrityError as error:
        db.session.rollback()
        existing = VocabularyTaskSettlement.query.filter_by(
            student_id=user.id, task_id=task.id
        ).first()
        if existing:
            return _safe_json(existing.result_json)
        raise VocabularyMasteryError("settlement_conflict", 409) from error
    return result


def list_vocabulary_due(user: User, limit: int = 100) -> dict:
    """Expose due v2 states without leaking any question answer."""

    rows = StudentVocabularyMastery.query.filter(
        StudentVocabularyMastery.student_id == user.id
    ).order_by(StudentVocabularyMastery.updated_at.asc()).all()
    items = []
    now = datetime.utcnow()
    for mastery in rows:
        for dimension in DIMENSIONS:
            due = _dimension_due(mastery, dimension)
            if not due or due > now:
                continue
            word = mastery.representative_word
            if not word:
                continue
            items.append(
                {
                    "word_id": word.id,
                    "sense_id": mastery.sense_id,
                    "book_id": word.book_id,
                    "dimension": dimension,
                    "stage": _dimension_stage(mastery, dimension),
                    "next_due_at": due.isoformat(),
                }
            )
            if len(items) >= max(1, min(int(limit or 100), 200)):
                return {"ok": True, "count": len(items), "items": items}
    return {"ok": True, "count": len(items), "items": items}


def ensure_vocabulary_schema(engine, logger=None) -> None:
    """Idempotently add v2 columns/tables and fill only empty book defaults."""

    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    def add_columns(table_name: str, columns: dict[str, str]):
        if table_name not in tables:
            return
        existing = {column["name"] for column in inspect(engine).get_columns(table_name)}
        for name, ddl in columns.items():
            if name in existing:
                continue
            try:
                with engine.begin() as connection:
                    connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {name} {ddl}"))
                existing.add(name)
            except Exception as exc:  # pragma: no cover - production safeguard
                if logger:
                    logger.warning("Failed to add %s.%s: %s", table_name, name, exc)

    add_columns("task", {"vocabulary_goal": "VARCHAR(32)"})
    add_columns(
        "dictation_book",
        {
            "default_vocabulary_goal": "VARCHAR(32)",
            "course_system": "VARCHAR(32)",
        },
    )
    add_columns("dictation_word", {"sense_id": "INTEGER"})
    add_columns(
        "vocabulary_task_review",
        {"review_date": "DATE", "mastery_due_at": "DATETIME"},
    )
    add_columns(
        "dictation_record",
        {
            "vocabulary_task_review_id": "INTEGER",
            "vocabulary_dimension": "VARCHAR(32)",
            "vocabulary_question_id": "VARCHAR(96)",
            "vocabulary_phase": "VARCHAR(32)",
            "vocabulary_score_eligible": "BOOLEAN",
            "vocabulary_mastery_applied": "BOOLEAN",
        },
    )
    add_columns(
        "student_vocabulary_mastery",
        {
            "representative_word_id": "INTEGER",
            "representative_book_id": "INTEGER",
            **{
                f"{dimension}_stage": "INTEGER NOT NULL DEFAULT 0"
                for dimension in DIMENSIONS
            },
            **{
                f"{dimension}_next_due_at": "DATETIME"
                for dimension in DIMENSIONS
            },
            **{
                f"{dimension}_last_answered_at": "DATETIME"
                for dimension in DIMENSIONS
            },
            "review_related_dimension": "VARCHAR(32)",
            "review_related_due_at": "DATETIME",
            "review_remediation_date": "DATE",
            "review_remediation_count": "INTEGER NOT NULL DEFAULT 0",
            **{
                f"{dimension}_long_term_at": "DATETIME"
                for dimension in DIMENSIONS
            },
            "long_term_mastered_at": "DATETIME",
        },
    )
    # The group-flow tables were introduced after the first v2 snapshot. A
    # checkfirst create does not upgrade an already existing SQLite table, so
    # keep these additions idempotent for local/dev databases that already
    # contain an earlier shape.
    add_columns(
        "vocabulary_learning_flow",
        {
            "diagnostics_json": "TEXT NOT NULL DEFAULT '[]'",
            "group_results_json": "TEXT NOT NULL DEFAULT '[]'",
            "context_applied_json": "TEXT NOT NULL DEFAULT '{}'",
            "retry_question_ids_json": "TEXT NOT NULL DEFAULT '[]'",
            "related_source_question_ids_json": "TEXT NOT NULL DEFAULT '[]'",
            "weak_word_ids_json": "TEXT NOT NULL DEFAULT '[]'",
            "current_group_index": "INTEGER NOT NULL DEFAULT 0",
            "phase": "VARCHAR(32) NOT NULL DEFAULT 'familiarity'",
            "phase_index": "INTEGER NOT NULL DEFAULT 0",
            "remediation_wave": "INTEGER NOT NULL DEFAULT 1",
            "pending_correction_question_id": "INTEGER",
            "viewed_word_ids_json": "TEXT NOT NULL DEFAULT '[]'",
            "queue_token": "VARCHAR(96) NOT NULL DEFAULT 'pending'",
            "status": "VARCHAR(16) NOT NULL DEFAULT 'active'",
            "state_version": "INTEGER NOT NULL DEFAULT 0",
            "completed_at": "DATETIME",
        },
    )
    add_columns(
        "vocabulary_learning_question",
        {
            "context_role": "VARCHAR(20)",
            "score_eligible": "BOOLEAN NOT NULL DEFAULT 1",
            "mastery_applied": "BOOLEAN NOT NULL DEFAULT 0",
            "first_attempt_id": "VARCHAR(96)",
            "first_is_correct": "BOOLEAN",
            "first_answer": "VARCHAR(200)",
            "retry_attempt_id": "VARCHAR(96)",
            "retry_is_correct": "BOOLEAN",
            "retry_answer": "VARCHAR(200)",
            "correction_attempt_id": "VARCHAR(96)",
            "correction_is_correct": "BOOLEAN",
            "correction_answer": "VARCHAR(200)",
            "correction_count": "INTEGER NOT NULL DEFAULT 0",
            "remediation_kind": "VARCHAR(24)",
            "source_question_id": "INTEGER",
            "formal_ordinal": "INTEGER",
            "deferred_to_review": "BOOLEAN NOT NULL DEFAULT 0",
        },
    )
    add_columns(
        "vocabulary_review_item",
        {
            "correction_attempt_id": "VARCHAR(96)",
            "correction_is_correct": "BOOLEAN",
            "correction_answer": "VARCHAR(200)",
            "correction_count": "INTEGER NOT NULL DEFAULT 0",
            "correction_exhausted": "BOOLEAN NOT NULL DEFAULT 0",
            "remediation_kind": "VARCHAR(24)",
            "deferred_to_review": "BOOLEAN NOT NULL DEFAULT 0",
        },
    )
    add_columns(
        "vocabulary_review_attempt",
        {"attempt_kind": "VARCHAR(16) NOT NULL DEFAULT 'first'"},
    )

    for model in (
        VocabularySense,
        StudentVocabularyMastery,
        VocabularyTaskReview,
        VocabularyTaskSettlement,
        VocabularyReviewSession,
        VocabularyReviewItem,
        VocabularyReviewAttempt,
        VocabularyReviewSettlement,
        VocabularyLearningFlow,
        VocabularyLearningQuestion,
    ):
        try:
            model.__table__.create(bind=engine, checkfirst=True)
        except Exception as exc:  # pragma: no cover - production safeguard
            if logger:
                logger.warning("Failed to ensure vocabulary table %s: %s", model.__tablename__, exc)

    # SQLite ALTER TABLE does not materialize the ``index=True`` declarations
    # on columns added to legacy tables. Create the operational indexes
    # explicitly, including a partial unique guard for concurrent first-answer
    # submissions. Existing legacy records all have a NULL review id.
    index_statements = (
        ("task", {"vocabulary_goal"}, "CREATE INDEX IF NOT EXISTS ix_task_vocabulary_goal ON task (vocabulary_goal)"),
        (
            "dictation_book",
            {"default_vocabulary_goal"},
            "CREATE INDEX IF NOT EXISTS ix_dictation_book_default_vocabulary_goal "
            "ON dictation_book (default_vocabulary_goal)",
        ),
        (
            "dictation_book",
            {"course_system"},
            "CREATE INDEX IF NOT EXISTS ix_dictation_book_course_system "
            "ON dictation_book (course_system)",
        ),
        (
            "dictation_word",
            {"sense_id"},
            "CREATE INDEX IF NOT EXISTS ix_dictation_word_sense_id "
            "ON dictation_word (sense_id)",
        ),
        (
            "dictation_record",
            {"student_id", "vocabulary_task_review_id", "is_first_attempt", "attempt_id"},
            "CREATE INDEX IF NOT EXISTS ix_dictation_record_vocabulary_review_first "
            "ON dictation_record "
            "(student_id, vocabulary_task_review_id, is_first_attempt, attempt_id)",
        ),
        (
            "dictation_record",
            {"vocabulary_dimension"},
            "CREATE INDEX IF NOT EXISTS ix_dictation_record_vocabulary_dimension "
            "ON dictation_record (vocabulary_dimension)",
        ),
        (
            "dictation_record",
            {"vocabulary_question_id"},
            "CREATE INDEX IF NOT EXISTS ix_dictation_record_vocabulary_question_id "
            "ON dictation_record (vocabulary_question_id)",
        ),
        (
            "dictation_record",
            {"vocabulary_task_review_id", "is_first_attempt"},
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_dictation_record_vocabulary_first "
            "ON dictation_record (vocabulary_task_review_id) "
            "WHERE vocabulary_task_review_id IS NOT NULL AND is_first_attempt = 1",
        ),
        (
            "vocabulary_review_attempt",
            {"item_id", "is_first_attempt"},
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_vocabulary_review_attempt_first "
            "ON vocabulary_review_attempt (item_id) "
            "WHERE is_first_attempt = 1",
        ),
    )
    existing_tables = set(inspect(engine).get_table_names())
    for table_name, required_columns, statement in index_statements:
        if table_name not in existing_tables:
            continue
        existing_columns = {
            column["name"] for column in inspect(engine).get_columns(table_name)
        }
        if not required_columns.issubset(existing_columns):
            continue
        try:
            with engine.begin() as connection:
                connection.execute(text(statement))
        except Exception as exc:  # pragma: no cover - production safeguard
            if logger:
                logger.warning(
                    "Failed to ensure vocabulary index on %s: %s", table_name, exc
                )

    if "dictation_book" in tables or "dictation_book" in inspect(engine).get_table_names():
        mappings = (
            (2, 39, "listening"),
            (40, 165, "reading"),
            (166, 173, "comprehensive"),
            (175, 187, "comprehensive"),
            (188, 188, "writing"),
            (192, 192, "listening"),
            (194, 194, "reading"),
        )
        course_mappings = (
            (2, 39, "IELTS"),
            (40, 165, "TOEFL"),
            (166, 173, "general"),
            (175, 187, "general"),
            (188, 188, "TOEFL"),
            (192, 192, "TOEFL"),
            (194, 194, "TOEFL"),
        )
        try:
            with engine.begin() as connection:
                for lower, upper, goal in mappings:
                    connection.execute(
                        text(
                            "UPDATE dictation_book SET default_vocabulary_goal = :goal "
                            "WHERE id BETWEEN :lower AND :upper "
                            "AND (default_vocabulary_goal IS NULL OR default_vocabulary_goal = '')"
                        ),
                        {"goal": goal, "lower": lower, "upper": upper},
                    )
                for lower, upper, course_system in course_mappings:
                    connection.execute(
                        text(
                            "UPDATE dictation_book SET course_system = :course_system "
                            "WHERE id BETWEEN :lower AND :upper "
                            "AND (course_system IS NULL OR course_system = '')"
                        ),
                        {
                            "course_system": course_system,
                            "lower": lower,
                            "upper": upper,
                        },
                    )
        except Exception as exc:  # pragma: no cover - production safeguard
            if logger:
                logger.warning("Failed to backfill empty dictation book goals: %s", exc)
