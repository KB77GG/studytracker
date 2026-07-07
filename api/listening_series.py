"""听力书目系列注册表（纯函数，只依赖标准库）。

系统最初只有剑桥雅思一套命名（ielts{book}_test{test} / ..._s{section}），
目录代码在 app.py 三处 + api/miniprogram.py 一处各写各的正则。新增书目
系列（9分达人听力6 → jfdr6_test{N} / jfdr6_test{N}_s{S}）后，四处统一
从这里解析，新系列只需在 _SERIES 加一条注册。

约定：
- 同一系列内 book 为数字（剑雅 4-20、9分达人 6），跨系列 book 数字可能
  重复（剑雅6 vs 9分达人6），因此目录分组键必须是 (series, book)。
- sort_key() 提供稳定排序：剑雅在前、9分达人在后，各自按 book/test 递增。
"""

from __future__ import annotations

import re

_SERIES: list[dict] = [
    {
        "key": "cambridge",
        "order": 0,
        "test_re": re.compile(r"^ielts(?P<book>\d+)_test(?P<test>\d+)$", re.IGNORECASE),
        "intensive_re": re.compile(
            r"^ielts(?P<book>\d+)_test(?P<test>\d+)_s(?P<section>\d+)$", re.IGNORECASE
        ),
        "book_label": "剑雅 {book}",
        "test_title": "Cambridge IELTS {book} Test {test} Listening",
        "intensive_title": "Cambridge IELTS {book} Test {test} Section {section}",
        "test_key": "ielts{book}_test{test}",
        "search_terms": "ielts {book} cambridge {book} 剑{book}",
    },
    {
        "key": "jfdr",
        "order": 1,
        "test_re": re.compile(r"^jfdr(?P<book>\d+)_test(?P<test>\d+)$", re.IGNORECASE),
        "intensive_re": re.compile(
            r"^jfdr(?P<book>\d+)_test(?P<test>\d+)_s(?P<section>\d+)$", re.IGNORECASE
        ),
        "book_label": "9分达人 {book}",
        "test_title": "9分达人听力{book} Test {test} Listening",
        "intensive_title": "9分达人听力{book} Test {test} Part {section}",
        "test_key": "jfdr{book}_test{test}",
        "search_terms": "jfdr {book} 9分达人 九分达人",
    },
]


def _match(stem: str, re_field: str) -> dict | None:
    stem = str(stem or "").strip()
    for series in _SERIES:
        match = series[re_field].match(stem)
        if not match:
            continue
        info = {
            "series": series["key"],
            "order": series["order"],
            "book": int(match.group("book")),
            "test": int(match.group("test")),
        }
        if "section" in match.groupdict() and match.group("section") is not None:
            info["section"] = int(match.group("section"))
        info["label"] = series["book_label"].format(**info)
        info["test_key"] = series["test_key"].format(**info)
        title_field = "intensive_title" if "section" in info else "test_title"
        info["title"] = series[title_field].format(**info)
        info["search_terms"] = series["search_terms"].format(**info)
        return info
    return None


def parse_test_id(stem: str) -> dict | None:
    """整卷听力 id（如 ielts18_test1 / jfdr6_test1）→ 系列信息 dict，不匹配返回 None。"""
    return _match(stem, "test_re")


def parse_intensive_id(stem: str) -> dict | None:
    """精听 section id（如 ielts18_test1_s1 / jfdr6_test1_s2）→ 系列信息 dict。"""
    return _match(stem, "intensive_re")


def series_sort_key(info: dict) -> tuple:
    """按 系列顺序 → book → test → section 稳定排序。"""
    return (
        info.get("order", 99),
        info.get("book", 0),
        info.get("test", 0),
        info.get("section", 0),
    )
