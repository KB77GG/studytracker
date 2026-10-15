"""Display persisted dictation actions in existing answer history surfaces."""

from __future__ import annotations

def dictation_attempt_display(attempts: list) -> dict:
    """Keep a forgotten action visible even when a later retry was correct."""
    latest = attempts[-1] if attempts else None
    kind = (getattr(latest, "response_kind", None) or "answer") if latest else None
    answer = (latest.student_answer or "") if latest else ""
    forgot_count = sum(
        (getattr(attempt, "response_kind", None) or "answer") == "forgot"
        for attempt in attempts
    )
    if kind == "forgot":
        displayed = f"忘了（已输入：{answer}）" if answer else "忘了"
    else:
        displayed = answer or "未作答"
        if forgot_count:
            displayed += "（曾点忘了）"
    return {
        "student_answer": displayed,
        "response_kind": kind,
        "first_response_kind": (
            getattr(attempts[0], "response_kind", None) or "answer"
            if attempts
            else None
        ),
        "forgot_count": forgot_count,
    }
