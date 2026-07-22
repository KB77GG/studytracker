"""模考写作科的纯逻辑 helper（不依赖 Flask 请求上下文）。

写作不自动判分：这里只负责词数统计、作文文本清洗、下拉选项与会话字段的组装，
路由层（app.py）只做"收参数 → 调这里 → 写库/返响应"。
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta

# 单篇作文的最大保存长度，防止异常大 payload 撑爆库（远超 250 词上限）。
MAX_ESSAY_CHARS = 20000

_WORD_RE = re.compile(r"\S+")


def count_words(text: str | None) -> int:
    """按空白切分统计词数，与前端 ``text.trim().split(/\\s+/)`` 口径一致。"""
    if not text:
        return 0
    return len(_WORD_RE.findall(text))


def clean_essay(text) -> str:
    """规范化学生提交的作文：转成 str、去掉首尾空白、限制最大长度。"""
    if text is None:
        return ""
    value = str(text).replace("\r\n", "\n").replace("\r", "\n")
    if len(value) > MAX_ESSAY_CHARS:
        value = value[:MAX_ESSAY_CHARS]
    return value.strip()


def build_writing_options(catalog_books: list[dict]) -> list[dict]:
    """把 writing_tests/catalog.json 的 books 结构转成教师配卷下拉选项。"""
    options: list[dict] = []
    for book in catalog_books or []:
        book_no = book.get("book")
        for test in book.get("tests") or []:
            options.append(
                {
                    "id": test["id"],
                    "label": f"剑桥{book_no} Test{test.get('test')} · 写作",
                    "task_count": test.get("task_count"),
                    "has_image": bool(test.get("has_image")),
                }
            )
    return options


def serialize_writing_session(sess) -> dict:
    """会话里写作科的运行态，供 process 页 JS 判断进度。"""
    return {
        "started_at": sess.writing_started_at.isoformat() if sess.writing_started_at else None,
        "deadline_at": sess.writing_deadline_at.isoformat() if sess.writing_deadline_at else None,
        "submitted_at": sess.writing_submitted_at.isoformat() if sess.writing_submitted_at else None,
        "task1_words": sess.writing_task1_words,
        "task2_words": sess.writing_task2_words,
        "auto_submitted": bool(sess.writing_auto_submitted),
    }


def apply_writing_draft(sess, essay1, essay2) -> dict:
    """草稿自动保存：只更新作文文本与词数，不改变提交状态。"""
    text1 = clean_essay(essay1)
    text2 = clean_essay(essay2)
    sess.writing_essay_task1 = text1
    sess.writing_essay_task2 = text2
    sess.writing_task1_words = count_words(text1)
    sess.writing_task2_words = count_words(text2)
    return {"task1_words": sess.writing_task1_words, "task2_words": sess.writing_task2_words}


def finalize_writing_submission(
    sess,
    essay1,
    essay2,
    duration_seconds: int,
    auto_submitted: bool,
    now: datetime | None = None,
) -> dict:
    """写作交卷：写入原文/词数/提交时间，并把会话标记为已完成。"""
    now = now or datetime.utcnow()
    counts = apply_writing_draft(sess, essay1, essay2)
    sess.writing_submitted_at = now
    sess.writing_duration_seconds = max(
        int(sess.writing_duration_seconds or 0), int(duration_seconds or 0)
    )
    sess.writing_auto_submitted = bool(auto_submitted)
    return counts


def is_auto_submitted(deadline_at: datetime | None, now: datetime | None = None) -> bool:
    now = now or datetime.utcnow()
    return bool(deadline_at and now > deadline_at + timedelta(seconds=5))
