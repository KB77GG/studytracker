"""Pure rules for homework answer timelines (作答过程分析).

The mini program records, for one answering session, when each question was
answered and when the student left / came back to the page.  These helpers
clean that client payload and derive conservative "needs attention" flags for
teachers.  Nothing here blocks or changes a submission or its grade: flags are
hints for a human, never an automatic verdict.

Timeline wire format (``v`` = 1)::

    {
        "v": 1,
        "mode": "practice" | "redo_wrong" | "redo_all",
        "submitted_offset_ms": 312000,
        "events": [[offset_ms, "a", "<question key>"], [offset_ms, "h"], [offset_ms, "s"], ...]
    }

``a`` = an answer was chosen/edited, ``h`` = page hidden (left the app or the
page), ``s`` = page shown again.  Offsets are milliseconds since the answering
session started on the client.
"""

from __future__ import annotations

import math

TIMELINE_VERSION = 1
MAX_EVENTS = 800
MAX_QUESTION_KEY_LENGTH = 40
MODES = {"practice", "redo_wrong", "redo_all"}

LEVEL_NONE = "none"
LEVEL_INFO = "info"
LEVEL_MEDIUM = "medium"
LEVEL_HIGH = "high"
_LEVEL_RANK = {LEVEL_NONE: 0, LEVEL_INFO: 1, LEVEL_MEDIUM: 2, LEVEL_HIGH: 3}
LEVEL_LABELS = {
    LEVEL_NONE: "正常",
    LEVEL_INFO: "留意",
    LEVEL_MEDIUM: "需关注",
    LEVEL_HIGH: "高度可疑",
}

# Seconds per question below which answering is implausible for real work.
# ``high``: faster than copying answers needs; ``medium``: unusually fast.
SOURCE_PACE_SECONDS = {
    "cambridge_reading": {"high": 6.0, "medium": 10.0},
    "material_reading": {"high": 6.0, "medium": 10.0},
    "reading_vocab": {"high": 1.5, "medium": 3.0},
    "grammar_choice": {"high": 2.0, "medium": 4.0},
}
DEFAULT_PACE_SECONDS = {"high": 2.0, "medium": 4.0}
SOURCE_LABELS = {
    "cambridge_reading": "剑雅阅读",
    "material_reading": "阅读题",
    "reading_vocab": "阅读词汇选择",
    "grammar_choice": "语法选择",
    "translation_choice": "翻译练习",
}
# Material bank types answered on the mini program choice-practice page.
MATERIAL_TYPE_SOURCES = {
    "ielts_reading_practice": "material_reading",
    "reading_vocab_choice": "reading_vocab",
    "grammar": "grammar_choice",
    "translation": "translation_choice",
}


def source_for_material_type(material_type: str | None) -> str:
    return MATERIAL_TYPE_SOURCES.get(material_type or "", "reading_vocab")


MIN_QUESTIONS_FOR_PACE = 5
BURST_SHARE = 0.8
CLUSTER_SHARE = 0.4
RETURN_WINDOW_SECONDS = 60.0
RETURN_MIN_HIDDEN_SECONDS = 20.0
BASELINE_MIN_ATTEMPTS = 3
BASELINE_JUMP_POINTS = 30.0


def _as_int(value) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(number):
        return None
    return int(number)


def sanitize_timeline(raw, *, duration_seconds: int | None = None) -> dict | None:
    """Return a cleaned timeline, or ``None`` when the payload is unusable.

    Offsets are clamped to ``[0, end]`` where ``end`` is the client's own
    submit offset (or the reported duration).  Unknown event types, malformed
    rows and excess events are dropped rather than rejected, so an odd client
    can never make a submission fail.
    """
    if not isinstance(raw, dict):
        return None
    if _as_int(raw.get("v")) != TIMELINE_VERSION:
        return None
    raw_events = raw.get("events")
    if not isinstance(raw_events, list):
        return None

    end_ms = _as_int(raw.get("submitted_offset_ms"))
    if end_ms is None or end_ms < 0:
        end_ms = max(0, int(duration_seconds or 0)) * 1000
    mode = raw.get("mode") if raw.get("mode") in MODES else "practice"

    events: list[list] = []
    for row in raw_events[:MAX_EVENTS]:
        if not isinstance(row, (list, tuple)) or len(row) < 2:
            continue
        offset = _as_int(row[0])
        kind = row[1]
        if offset is None or kind not in ("a", "h", "s"):
            continue
        offset = min(max(offset, 0), end_ms) if end_ms else max(offset, 0)
        if kind == "a":
            if len(row) < 3:
                continue
            key = str(row[2] or "").strip()[:MAX_QUESTION_KEY_LENGTH]
            if not key:
                continue
            events.append([offset, "a", key])
        else:
            events.append([offset, kind])
    events.sort(key=lambda item: item[0])
    end_ms = max([end_ms] + [item[0] for item in events])
    return {"v": TIMELINE_VERSION, "mode": mode, "submitted_offset_ms": end_ms, "events": events}


def _hidden_intervals(events: list[list], end_ms: int) -> list[tuple[int, int]]:
    intervals: list[tuple[int, int]] = []
    hidden_at: int | None = None
    for event in events:
        if event[1] == "h" and hidden_at is None:
            hidden_at = event[0]
        elif event[1] == "s" and hidden_at is not None:
            intervals.append((hidden_at, event[0]))
            hidden_at = None
    if hidden_at is not None:
        intervals.append((hidden_at, end_ms))
    return intervals


def _first_answer_offsets(events: list[list]) -> list[int]:
    seen: set[str] = set()
    offsets: list[int] = []
    for event in events:
        if event[1] == "a" and event[2] not in seen:
            seen.add(event[2])
            offsets.append(event[0])
    return offsets


def _final_revision_offsets(events: list[list]) -> list[int]:
    """Offset of the last edit of every question that was changed after its first answer."""
    first: dict[str, int] = {}
    last: dict[str, int] = {}
    for event in events:
        if event[1] != "a":
            continue
        if event[2] in first:
            last[event[2]] = event[0]
        else:
            first[event[2]] = event[0]
    return sorted(last.values())


def _tightest_window(offsets: list[int], count: int) -> int | None:
    """Smallest span in ms that contains ``count`` consecutive offsets."""
    if count <= 1 or len(offsets) < count:
        return None
    return min(offsets[i + count - 1] - offsets[i] for i in range(len(offsets) - count + 1))


def _cluster_size(question_count: int, answered: int) -> int:
    """How many questions make a 'batch' worth flagging (40% of the paper, at least 3)."""
    return max(3, math.ceil(CLUSTER_SHARE * max(question_count, answered)))


def timeline_metrics(timeline: dict, *, question_count: int = 0) -> dict:
    events = timeline["events"]
    end_ms = int(timeline["submitted_offset_ms"])
    first_offsets = _first_answer_offsets(events)
    revision_offsets = _final_revision_offsets(events)
    answer_events = sum(1 for event in events if event[1] == "a")
    hidden = _hidden_intervals(events, end_ms)
    hidden_ms = sum(stop - start for start, stop in hidden)
    answered = len(first_offsets)
    burst_count = math.ceil(answered * BURST_SHARE) if answered else 0
    burst_ms = _tightest_window(first_offsets, burst_count)
    revision_count = _cluster_size(question_count, answered)
    revision_ms = _tightest_window(revision_offsets, revision_count)

    returns = []
    for start, stop in hidden:
        if stop >= end_ms or (stop - start) < RETURN_MIN_HIDDEN_SECONDS * 1000:
            continue
        after = [
            offset
            for offset in first_offsets
            if stop <= offset <= stop + RETURN_WINDOW_SECONDS * 1000
        ]
        returns.append(
            {
                "hidden_seconds": round((stop - start) / 1000, 1),
                "answered_within_60s": len(after),
                # Time from coming back to the last of those answers, per answer.
                "pace_seconds": round((after[-1] - stop) / 1000 / len(after), 1) if after else None,
            }
        )

    return {
        "duration_seconds": round(end_ms / 1000, 1),
        "answered_count": answered,
        "answer_event_count": answer_events,
        "revisit_count": max(0, answer_events - answered),
        "revised_question_count": len(revision_offsets),
        "first_answer_seconds": round(first_offsets[0] / 1000, 1) if first_offsets else None,
        "last_answer_seconds": round(first_offsets[-1] / 1000, 1) if first_offsets else None,
        "leave_count": len(hidden),
        "hidden_seconds": round(hidden_ms / 1000, 1),
        "active_seconds": round(max(0, end_ms - hidden_ms) / 1000, 1),
        "burst_count": burst_count,
        "burst_seconds": round(burst_ms / 1000, 1) if burst_ms is not None else None,
        "revision_burst_count": revision_count,
        "revision_burst_seconds": round(revision_ms / 1000, 1) if revision_ms is not None else None,
        "returns": returns,
    }


def _flag(code: str, level: str, message: str) -> dict:
    return {"code": code, "level": level, "message": message}


def _pace_level(pace: float, thresholds: dict) -> str | None:
    if pace < thresholds["high"]:
        return LEVEL_HIGH
    if pace < thresholds["medium"]:
        return LEVEL_MEDIUM
    return None


def _cap(level: str, ceiling: str) -> str:
    return level if _LEVEL_RANK[level] <= _LEVEL_RANK[ceiling] else ceiling


def _fmt_seconds(seconds: float) -> str:
    seconds = max(0, int(round(seconds)))
    if seconds < 60:
        return f"{seconds} 秒"
    minutes, rest = divmod(seconds, 60)
    return f"{minutes} 分 {rest} 秒" if rest else f"{minutes} 分钟"


def _pace_flags(metrics: dict, thresholds: dict) -> list[dict]:
    answered = metrics["answered_count"]
    if answered < MIN_QUESTIONS_FOR_PACE:
        return []
    active = metrics["active_seconds"]
    overall_level = _pace_level(active / answered, thresholds)
    if overall_level:
        return [
            _flag(
                "too_fast",
                overall_level,
                f"在作答页面内共 {_fmt_seconds(active)} 答了 {answered} 题，"
                f"平均每题 {active / answered:.1f} 秒。",
            )
        ]
    count, burst = metrics["burst_count"], metrics["burst_seconds"]
    if burst is None:
        return []
    pace = burst / max(1, count - 1)
    burst_level = _pace_level(pace, thresholds)
    duration = metrics["duration_seconds"]
    if burst_level and duration >= 2 * burst + 60:
        # Entering answers prepared elsewhere (reading first, working on paper)
        # looks the same as copying, so a burst alone is never "high".
        return [
            _flag(
                "padded_burst",
                _cap(burst_level, LEVEL_MEDIUM),
                f"{count} 题的首次作答集中在 {_fmt_seconds(burst)} 内完成（平均每题 {pace:.1f} 秒），"
                f"交卷总用时 {_fmt_seconds(duration)}。可能是先读完/在纸上做好再统一录入，"
                f"也可能是对照答案填写，建议抽问核实。",
            )
        ]
    return []


def _revision_flags(metrics: dict, thresholds: dict) -> list[dict]:
    count, window = metrics["revision_burst_count"], metrics["revision_burst_seconds"]
    if window is None:
        return []
    pace = window / max(1, count - 1)
    level = _pace_level(pace, thresholds)
    if not level:
        return []
    return [
        _flag(
            "revision_burst",
            level,
            f"{count} 道已作答的题在 {_fmt_seconds(window)} 内被集中改掉答案"
            f"（平均每题 {pace:.1f} 秒），常见于先随意占位、最后统一改成答案。",
        )
    ]


def _leave_flags(metrics: dict, question_count: int, thresholds: dict) -> list[dict]:
    flags: list[dict] = []
    needed = _cluster_size(question_count, metrics["answered_count"])
    for item in metrics["returns"]:
        if item["answered_within_60s"] < needed or item["pace_seconds"] is None:
            continue
        level = _pace_level(item["pace_seconds"], thresholds)
        if not level:
            continue
        if item["hidden_seconds"] < 60:
            level = _cap(level, LEVEL_MEDIUM)
        flags.append(
            _flag(
                "left_then_burst",
                level,
                f"离开作答页面 {_fmt_seconds(item['hidden_seconds'])}，"
                f"回来后 1 分钟内连续答了 {item['answered_within_60s']} 题"
                f"（平均每题 {item['pace_seconds']:.1f} 秒）。",
            )
        )
        break
    hidden, duration = metrics["hidden_seconds"], metrics["duration_seconds"]
    long_absence = hidden >= 120 and hidden >= 0.3 * duration and not flags
    if metrics["leave_count"] >= 3 or long_absence:
        flags.append(
            _flag(
                "frequent_leave",
                LEVEL_MEDIUM,
                f"作答中离开页面 {metrics['leave_count']} 次，累计 {_fmt_seconds(hidden)}。",
            )
        )
    return flags


def _accuracy_flags(
    metrics: dict,
    *,
    accuracy: float | None,
    question_count: int,
    baseline_accuracy: float | None,
) -> list[dict]:
    if accuracy is None:
        return []
    flags: list[dict] = []
    if baseline_accuracy is not None and accuracy - baseline_accuracy >= BASELINE_JUMP_POINTS:
        flags.append(
            _flag(
                "above_baseline",
                LEVEL_MEDIUM,
                f"正确率 {accuracy:.0f}%，明显高于该生同类作业近期平均 {baseline_accuracy:.0f}%。",
            )
        )
    if question_count >= 8 and accuracy >= 95 and metrics["revisit_count"] == 0:
        flags.append(_flag("perfect_no_revision", LEVEL_INFO, "全对且没有修改过任何一题。"))
    return flags


def overall_level(flags: list[dict]) -> str:
    level = LEVEL_NONE
    for item in flags:
        if _LEVEL_RANK.get(item.get("level"), 0) > _LEVEL_RANK[level]:
            level = item["level"]
    return level


def analyze_timeline(
    source: str,
    timeline: dict | None,
    *,
    question_count: int,
    accuracy: float | None,
    baseline_accuracy: float | None = None,
) -> dict:
    """Return ``{"metrics", "flags", "level"}`` for one cleaned timeline."""
    if timeline is None:
        flags = [
            _flag(
                "no_timeline",
                LEVEL_INFO,
                "这次提交没有作答过程记录（网页端或旧版小程序提交）。",
            )
        ]
        return {"metrics": None, "flags": flags, "level": overall_level(flags)}

    thresholds = SOURCE_PACE_SECONDS.get(source, DEFAULT_PACE_SECONDS)
    metrics = timeline_metrics(timeline, question_count=question_count)
    if timeline.get("mode", "practice") != "practice":
        # Redoing after the answers/explanations were shown: speed and accuracy
        # say nothing about honesty, so only keep leave facts as low-level notes.
        flags = [
            dict(flag, level=LEVEL_INFO)
            for flag in _leave_flags(metrics, question_count, thresholds)
        ]
        return {"metrics": metrics, "flags": flags, "level": overall_level(flags)}

    flags = _pace_flags(metrics, thresholds)
    flags += _revision_flags(metrics, thresholds)
    flags += _leave_flags(metrics, question_count, thresholds)
    flags += _accuracy_flags(
        metrics,
        accuracy=accuracy,
        question_count=question_count,
        baseline_accuracy=baseline_accuracy,
    )
    return {"metrics": metrics, "flags": flags, "level": overall_level(flags)}
