"""刷题目录的纯聚合逻辑（零 DB / Flask 依赖）。"""

from __future__ import annotations

import math
from datetime import UTC, datetime
from urllib.parse import quote


def _accuracy_value(status: dict) -> float | None:
    value = status.get("accuracy")
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def summarize_book_progress(books: list[dict]) -> None:
    """原地给每本书附加完成数、总数与已完成 Test 的平均正确率。"""
    for book in books:
        tests = book.get("tests") or []
        completed = [test for test in tests if test.get("practice_status")]
        accuracies = [
            accuracy
            for test in completed
            if (accuracy := _accuracy_value(test["practice_status"])) is not None
        ]
        book["progress"] = {
            "done": len(completed),
            "total": len(tests),
            "avg_accuracy": round(sum(accuracies) / len(accuracies)) if accuracies else None,
        }


def _submitted_timestamp(value) -> float:
    if not value:
        return float("-inf")
    try:
        submitted_at = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return float("-inf")
    if submitted_at.tzinfo is None:
        submitted_at = submitted_at.replace(tzinfo=UTC)
    return submitted_at.timestamp()


def _series_key(book: dict) -> str:
    return str(book.get("series") or "cambridge")


def _book_label(book: dict) -> str:
    if book.get("label"):
        return str(book["label"])
    prefix = "9分达人" if _series_key(book) == "jfdr" else "剑雅"
    return f"{prefix} {book.get('book')}"


def _practice_url(test: dict) -> str:
    if test.get("url"):
        return str(test["url"])
    test_id = str(test.get("id") or "")
    is_reading = test_id.endswith("_reading") or "passage_count" in test
    prefix = "/reading/test/" if is_reading else "/listening/test/"
    return f"{prefix}{quote(test_id, safe='')}"


def _target_payload(book: dict, test: dict, *, include_accuracy: bool) -> dict:
    target = {
        "label": _book_label(book),
        "test": test.get("test"),
        "url": _practice_url(test),
    }
    if include_accuracy:
        status = test.get("practice_status") or {}
        target["accuracy"] = status.get("accuracy")
    return target


def pick_continue_target(books: list[dict]) -> dict | None:
    """返回最近已刷 Test，以及同系列中按目录向后的首个未刷 Test。"""
    latest = None
    for book_index, book in enumerate(books):
        for test_index, test in enumerate(book.get("tests") or []):
            status = test.get("practice_status")
            if not status:
                continue
            candidate_key = (
                _submitted_timestamp(status.get("submitted_at")),
                book_index,
                test_index,
            )
            if latest is None or candidate_key > latest[0]:
                latest = (candidate_key, book_index, test_index, book, test)

    if latest is None:
        return None

    _key, book_index, test_index, last_book, last_test = latest
    next_book = None
    next_test = None

    for test in (last_book.get("tests") or [])[test_index + 1 :]:
        if not test.get("practice_status"):
            next_book, next_test = last_book, test
            break

    if next_test is None:
        current_series = _series_key(last_book)
        for book in books[book_index + 1 :]:
            if _series_key(book) != current_series:
                continue
            first_unfinished = next(
                (test for test in book.get("tests") or [] if not test.get("practice_status")),
                None,
            )
            if first_unfinished is not None:
                next_book, next_test = book, first_unfinished
                break

    return {
        "last": _target_payload(last_book, last_test, include_accuracy=True),
        "next": (
            _target_payload(next_book, next_test, include_accuracy=False)
            if next_test is not None
            else None
        ),
    }
