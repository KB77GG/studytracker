"""Validate teacher-assigned word ranges against actual book contents."""

from bisect import bisect_right

from sqlalchemy import func

from models import DictationBook, DictationWord, db


def dictation_range_error(book_id, raw_start=None, raw_end=None):
    """Return a staff-safe error before any Task/PlanItem is created."""

    book = db.session.get(DictationBook, book_id)
    if book is None:
        return "所选词书不存在，请重新选择。"
    try:
        start = int(raw_start) if raw_start not in (None, "") else 1
        end = int(raw_end) if raw_end not in (None, "") else None
    except (TypeError, ValueError):
        return "词汇范围必须填写整数。"
    if start < 1 or (end is not None and end < start):
        return "词汇起始位置必须大于等于 1，结束位置不能小于起始位置。"
    words = DictationWord.query.filter_by(book_id=book_id)
    last_sequence = db.session.query(func.max(DictationWord.sequence)).filter_by(
        book_id=book_id
    ).scalar()
    if last_sequence is None:
        return "所选词书暂无单词，请重新选择。"
    if start > last_sequence or (end is not None and end > last_sequence):
        return f"《{book.title}》最后一个词的序号为 {last_sequence}，请调整词汇范围。"
    selected = words.filter(DictationWord.sequence >= start)
    if end is not None:
        selected = selected.filter(DictationWord.sequence <= end)
    if selected.first() is None:
        return "所选范围内没有单词，请调整词汇范围。"
    return None


def build_dictation_range_hints(tasks):
    """Suggest a real next word; never advance past the end of a book.

    The caller supplies latest-first history. Sequence gaps are supported and
    the book's cached word_count is deliberately not used as a sequence bound.
    """

    tasks = list(tasks)
    book_ids = {task.dictation_book_id for task in tasks if task.dictation_book_id}
    sequences = {}
    if book_ids:
        for book_id, sequence in (
            db.session.query(DictationWord.book_id, DictationWord.sequence)
            .filter(DictationWord.book_id.in_(book_ids))
            .order_by(DictationWord.sequence)
        ):
            sequences.setdefault(book_id, []).append(sequence)
    hints = {}
    for task in tasks:
        student = (task.student_name or "").strip()
        if not student or not task.dictation_book_id:
            continue
        student_hints = hints.setdefault(student, {})
        book_key = str(task.dictation_book_id)
        if book_key in student_hints:
            continue
        end = int(task.dictation_word_end) if task.dictation_word_end else None
        book_sequences = sequences.get(task.dictation_book_id, [])
        index = bisect_right(book_sequences, end) if end is not None else len(book_sequences)
        next_start = book_sequences[index] if index < len(book_sequences) else None
        student_hints[book_key] = {
            "start": int(task.dictation_word_start or 1),
            "end": end,
            "next_start": next_start,
            "exhausted": next_start is None,
            "last_date": task.date,
        }
    return hints
