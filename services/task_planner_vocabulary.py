"""Explicit vocabulary volume choices, ordered and split into native tasks."""

from __future__ import annotations

import re

from models import DictationBook, DictationWord


def natural_key(value):
    return tuple((0, int(part)) if part.isdigit() else (1, part.lower())
                 for part in re.split(r"(\d+)", str(value)))


def book_sort_key(book):
    """Use human chapter numbers, with a stable tie-break for identical titles."""
    return natural_key(book.title), book.id


def selected_books(selection):
    from services.task_planner import TaskPlannerError, _integer

    ids = selection.get("book_ids")
    if not isinstance(ids, list) or not 1 <= len(ids) <= 100:
        raise TaskPlannerError("请选择1至100个词汇分册")
    ids = [_integer(value, "词汇分册") for value in ids]
    if len(ids) != len(set(ids)):
        raise TaskPlannerError("词汇分册重复，请重新选择")
    start_id = _integer(selection.get("book_id"), "起始分册")
    if start_id not in ids:
        raise TaskPlannerError("起始分册必须属于所选词汇分册")
    books = DictationBook.query.filter(DictationBook.id.in_(ids)).all()
    if len(books) != len(ids) or any(book.is_deleted or not book.is_active for book in books):
        raise TaskPlannerError("所选词汇分册不存在、已删除或已停用，请重新选择")
    return sorted(books, key=book_sort_key)


def vocabulary_selections(selection, schedule):
    """Consume actual word rows; split a daily quota at every volume boundary."""
    from services.task_planner import TaskPlannerError, _integer

    books = selected_books(selection)
    start_id = _integer(selection.get("book_id"), "起始分册")
    start = _integer(selection.get("word_start"), "开始词序")
    ids = [book.id for book in books]
    sequences = {book_id: [] for book_id in ids}
    for book_id, sequence in DictationWord.query.with_entities(
        DictationWord.book_id, DictationWord.sequence,
    ).filter(DictationWord.book_id.in_(ids)).order_by(
        DictationWord.book_id, DictationWord.sequence, DictationWord.id,
    ):
        sequences[book_id].append(sequence)
    for book in books:
        values = sequences[book.id]
        if not values:
            raise TaskPlannerError(f"所选分册“{book.title}”没有单词，请重新选择")
        if any(value is None or value < 1 for value in values) or len(values) != len(set(values)):
            raise TaskPlannerError(f"分册“{book.title}”存在无效或重复词序，请先整理后再连续安排")
    if start not in sequences[start_id]:
        raise TaskPlannerError("开始词序在起始分册中不存在")
    remaining_books = books[ids.index(start_id):]
    sequences[start_id] = sequences[start_id][sequences[start_id].index(start):]
    available = sum(len(sequences[book.id]) for book in remaining_books)
    needed = sum(count for _, count in schedule)
    if available < needed:
        raise TaskPlannerError(f"所选起点后仅有{available}词，安排需要{needed}词，缺少{needed-available}词；请补充分册、缩短范围或调整每日数量")
    book_index, offset = 0, 0
    for day, count in schedule:
        left = count
        while left:
            book = remaining_books[book_index]
            values = sequences[book.id]
            size = min(left, len(values) - offset)
            chosen = values[offset:offset + size]
            yield day, size, 0, {
                "book_id": book.id, "word_start": chosen[0], "word_end": chosen[-1],
                "vocabulary_goal": selection.get("vocabulary_goal") or "reading",
                "dictation_mode": selection.get("dictation_mode") or "audio_to_en",
                "dictation_order": selection.get("dictation_order") or "sequence",
            }, [f"{book.title} · 第{chosen[0]}–{chosen[-1]}词"]
            offset += size
            left -= size
            if offset == len(values):
                book_index += 1
                offset = 0
