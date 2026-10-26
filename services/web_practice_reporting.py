"""Read saved website results for a parent's already-authorized task.

This module never starts an attempt, re-grades answers, or infers a writing
attempt from a student's latest practice of the same exercise.
"""

import json
from datetime import timezone

from models import QuestionTypePracticeAttempt, StudentProfile, WritingTypingAttempt
from services.writing_assignments import snapshot_from_task, typing_attempt_ids

UTC_TIMEZONE = timezone.utc  # noqa: UP017 - production Python 3.10


def _object(raw):
    try:
        value = json.loads(raw or "{}")
    except (TypeError, ValueError):
        return {}
    return value if isinstance(value, dict) else {}


def _timestamp(value):
    if value is None:
        return None
    return value.replace(tzinfo=UTC_TIMEZONE).isoformat().replace("+00:00", "Z")


def _summary(total=0, attempted=0, correct=0, wrong=0):
    return {
        "assigned_total": total,
        "attempted_total": attempted,
        "correct_total": correct,
        "wrong_total": wrong,
        "pending_total": 0,
        "mastered_total": 0,
    }


def _writing_result(attempt, include_text):
    result = {
        "attempt_id": attempt.id,
        "band": attempt.band,
        "typed_word_count": attempt.typed_word_count,
        "target_word_count": attempt.target_word_count,
        "speed_wpm": attempt.speed_wpm,
        "duration_seconds": attempt.duration_seconds,
        "accuracy": attempt.accuracy,
        "completed_at": _timestamp(attempt.completed_at),
    }
    if include_text:
        result["typed_text"] = attempt.typed_text or ""
    return result


def _writing_report(task, include_items):
    snapshot = snapshot_from_task(task) or {}
    topic = snapshot.get("writing_resource_type") == "mother_topic"
    completed = task.status == "done"
    report = {
        "kind": "writing_mother_topic" if topic else "writing_typing",
        "summary": _summary(),
        "items": [],
        "accuracy": None,
        "accuracy_label": "打字准确率" if not topic else "",
        "writing_result": None,
    }
    if topic:
        saved = snapshot.get("writing_topic_result")
        if completed and isinstance(saved, dict):
            report["writing_result"] = {
                "completed_at": saved.get("completed_at"),
                "duration_seconds": saved.get("duration_seconds"),
            }
        report["summary_text"] = (
            "写作母题学习已完成" if completed else "请前往刷题网页学习，完成后同步学习记录"
        )
        return report

    attempts = (
        WritingTypingAttempt.query.join(StudentProfile)
        .filter(
            WritingTypingAttempt.id.in_(typing_attempt_ids(task)),
            StudentProfile.full_name == task.student_name,
            WritingTypingAttempt.exercise_id == snapshot.get("writing_resource_id"),
            WritingTypingAttempt.status == WritingTypingAttempt.STATUS_COMPLETED,
            WritingTypingAttempt.completed_at.isnot(None),
        )
        .order_by(WritingTypingAttempt.completed_at.desc(), WritingTypingAttempt.id.desc())
        .all()
    )
    if attempts:
        latest = attempts[0]
        report["writing_result"] = _writing_result(latest, include_items)
        report["accuracy"] = latest.accuracy
        report["summary_text"] = (
            f"打字练习已完成 · {latest.typed_word_count or 0} 词 · "
            f"打字准确率 {latest.accuracy:.1f}%"
            if latest.accuracy is not None
            else f"打字练习已完成 · {latest.typed_word_count or 0} 词"
        )
        if include_items:
            report["writing_history"] = [_writing_result(row, True) for row in attempts]
    elif completed:
        report["accuracy"] = task.accuracy
        report["summary_text"] = "打字练习已完成；历史记录未绑定打字明细，仅展示任务已保存的结果"
    else:
        report["summary_text"] = "打字练习尚未提交，暂无成绩；请前往刷题网页练习"
    return report


def _question_prompts(snapshot, clean_text):
    prompts = {}
    payload = snapshot.get("payload") or {}
    key = "sections" if snapshot.get("subject") == "listening" else "passages"
    for unit in payload.get(key) or []:
        for group in unit.get("groups") or []:
            fallback = (
                group.get("question_title")
                or group.get("title")
                or group.get("desc")
                or group.get("collect")
                or ""
            )
            for question in group.get("questions") or []:
                prompt = clean_text(question.get("title") or fallback)
                for identifier in (question.get("id"), question.get("number")):
                    if identifier is not None:
                        prompts[str(identifier)] = prompt
    return prompts


def _question_items(rows, prompts):
    items = []
    for index, row in enumerate(rows):
        numbers = row.get("numbers") or []
        identifiers = row.get("ids") or [row.get("id")]
        number = row.get("q") or ",".join(str(value) for value in numbers) or str(index + 1)
        prompt = next(
            (prompts[str(value)] for value in identifiers + numbers if str(value) in prompts), ""
        )
        status = row.get("status") or ("correct" if row.get("correct") else "incorrect")
        answer_text = _answer_display(row.get("value"))
        result_status = (
            "unanswered"
            if not answer_text
            else "correct" if status == "correct" else "partial" if status == "partial" else "wrong"
        )
        items.append(
            {
                "id": f"specialty-{index}",
                "number": number,
                "prompt": prompt or f"第 {number} 题",
                "student_answer": answer_text or "未作答",
                "correct_answer": _answer_display(row.get("answer")) or "暂无参考答案",
                "result_status": result_status,
                "result_label": (
                    "未作答"
                    if not answer_text
                    else row.get("status_label")
                    or {"correct": "正确", "partial": "部分正确", "wrong": "错误"}[result_status]
                ),
                "marks": row.get("marks") or 1,
                "awarded": row.get("awarded") or 0,
            }
        )
    return items


def _answer_display(value):
    """Format stored values for display, without normalizing or scoring them."""
    if isinstance(value, list):
        return "、".join(str(item) for item in value if str(item).strip())
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return str(value or "").strip()


def _question_type_report(task, include_items, clean_text):
    snapshot = _object(task.question_ids)
    attempt = QuestionTypePracticeAttempt.query.filter_by(
        task_id=task.id,
        student_name=task.student_name,
    ).first()
    total = max(0, int(snapshot.get("question_count") or 0))
    report = {
        "kind": "question_type_practice",
        "summary": _summary(total),
        "items": [],
        "accuracy": None,
        "accuracy_label": "正确率",
        "summary_text": "题型专项尚未提交，暂无成绩；请前往刷题网页练习",
    }
    if (
        not attempt
        or attempt.status != QuestionTypePracticeAttempt.STATUS_SUBMITTED
        or not attempt.submitted_at
    ):
        if task.status == "done":
            report["summary_text"] = "题型专项已完成，暂无可核对的逐题记录"
        return report
    result = _object(attempt.results_json)
    rows = [row for row in result.get("results") or [] if isinstance(row, dict)]
    total = attempt.total_count
    correct = attempt.correct_count
    attempted = sum(int(row.get("marks") or 1) for row in rows if _answer_display(row.get("value")))
    report.update(
        {
            "accuracy": attempt.accuracy,
            "summary": _summary(total, attempted, correct, max(0, total - correct)),
            "summary_text": f"题型专项已提交 · 共 {total} 题 · 已答 {attempted} · 正确 {correct} · 错误 {max(0, total - correct)}",
            "submitted_at": _timestamp(attempt.submitted_at),
            "duration_seconds": attempt.duration_seconds,
        }
    )
    if include_items:
        report["items"] = _question_items(rows, _question_prompts(snapshot, clean_text))
    return report


def web_practice_task_report(task, *, include_items=False, clean_text=str):
    """Return a website report, or None for another task type."""
    if task.grading_mode == "writing_practice":
        return _writing_report(task, include_items)
    if task.grading_mode == "question_type_practice":
        return _question_type_report(task, include_items, clean_text)
    return None
