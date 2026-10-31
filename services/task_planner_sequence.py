"""Explicit, bounded book choices for whole-resource learning sequences."""

from __future__ import annotations

import re

from api.listening_series import parse_intensive_id, parse_test_id
from services import task_planner_resources as resources
from services.listening_training import TRAINING_MODE_OPTIONS, VALID_TRAINING_MODES
from services.question_type_practice import cambridge_test_numbers

KINDS = frozenset({"listening_test", "reading_passage", "intensive"})


def _natural(value):
    return tuple(
        (0, int(part)) if part.isdigit() else (1, part.casefold())
        for part in re.split(r"(\d+)", str(value))
    )


def _options(kind, selection):
    if kind not in KINDS:
        raise ValueError("此类型不支持整篇连续安排")
    if not isinstance(selection, dict):
        raise ValueError("连续练习选项必须为对象")
    key = "passage_number" if kind == "reading_passage" else "section_number"
    allowed = {key, "training_mode"} if kind == "intensive" else {key}
    if set(selection) - allowed:
        raise ValueError("连续练习包含不支持的选项")
    number = selection.get(key)
    if number is not None:
        number = resources._integer(
            number,
            "篇章序号" if key == "passage_number" else "Part 序号",
            maximum=3 if key == "passage_number" else 4,
        )
    result = {key: number}
    if kind == "intensive":
        mode = selection.get("training_mode", "system")
        if not isinstance(mode, str) or mode not in VALID_TRAINING_MODES:
            raise ValueError("精听训练方式无效")
        result["training_mode"] = mode
    return result


def _scopes(value):
    if value is None:
        return []
    if (
        not isinstance(value, list)
        or len(value) > 100
        or any(not isinstance(item, str) or not item or len(item) > 160 for item in value)
    ):
        raise ValueError("请选择明确的教材范围列表")
    if len(value) != len(set(value)):
        raise ValueError("教材范围重复，请重新选择")
    return value


def _identity(kind, resource_id, source):
    """A registered book, an explicitly marked reading book, or one exact item."""
    if kind == "intensive":
        info = parse_intensive_id(resource_id)
    elif kind == "listening_test":
        info = parse_test_id(resource_id)
    else:
        numbers = cambridge_test_numbers({"test_id": resource_id})
        info = (
            {
                "series": "cambridge",
                "book": numbers[0],
                "test": numbers[1],
                "order": 0,
                "label": f"剑雅 {numbers[0]}",
            }
            if numbers
            else None
        )
        if not info and source.get("source") == "idictation_reading_jijing":
            try:
                book = resources._integer(source.get("book"), "机经册号")
                test = resources._integer(source.get("test"), "机经试卷号")
            except ValueError:
                pass
            else:
                info = {
                    "series": "reading_jijing",
                    "book": book,
                    "test": test,
                    "order": 2,
                    "label": f"阅读机经 {book}",
                }
    if info:
        return (
            f"{info['series']}:{info['book']}",
            info["label"],
            (info["order"], info["book"], ((0, info["test"]),)),
        )
    prefix = "exercise" if kind == "intensive" else "test"
    return (
        f"{prefix}:{resource_id}",
        source.get("title") or resource_id,
        (99, 0, _natural(resource_id)),
    )


def _paths(kind):
    roots = resources._roots()
    if kind == "reading_passage":
        directories = (roots.reading, roots.reading_jijing)
    elif kind == "listening_test":
        directories = (roots.listening,)
    else:
        directories = (resources._root() / "static/listening",)
    seen = set()
    for directory in directories:
        for path in sorted(directory.glob("*.json")):
            if path.stem not in seen:
                seen.add(path.stem)
                yield path.stem


def _choices(kind, resource_id, options):
    """Enumerate from the existing resource loaders without paginated rescans."""
    if kind == "intensive":
        info = parse_intensive_id(resource_id)
        if not info or (
            options["section_number"] is not None and info["section"] != options["section_number"]
        ):
            return
        if info["section"] not in {1, 2, 3, 4}:
            return
        source = resources._intensive_payload(resource_id)
        yield (
            source,
            resource_id,
            info["section"],
            {
                "exercise_id": resource_id,
                "training_mode": options["training_mode"],
            },
        )
    elif kind == "listening_test":
        source = resources._listening_payload(resource_id)
        number = options["section_number"]
        yield (
            source,
            f"{resource_id}:{number if number is not None else 'all'}",
            number or 0,
            {
                "test_id": resource_id,
                "section_number": number,
            },
        )
    else:
        source = resources._reading_payload(resource_id)
        passages = source["passages"]
        if any(not isinstance(passage, dict) for passage in passages):
            return
        numbers = [
            resources._integer(passage.get("passage") or index, "篇章序号", maximum=3)
            for index, passage in enumerate(passages, 1)
        ]
        if len(numbers) != len(set(numbers)):
            return
        for passage, number in zip(passages, numbers, strict=True):
            if options["passage_number"] is not None and number != options["passage_number"]:
                continue
            groups = passage.get("groups")
            if (
                not isinstance(groups, list)
                or not groups
                or any(
                    not isinstance(group, dict)
                    or not isinstance(group.get("questions"), list)
                    or not group["questions"]
                    or any(not isinstance(question, dict) for question in group["questions"])
                    for group in groups
                )
            ):
                continue
            yield (
                source,
                f"{resource_id}:{number}",
                number,
                {
                    "test_id": resource_id,
                    "passage_number": number,
                },
            )


def sequence_sources(kind, selection, source_scopes=None):
    """Return all finite book choices; only explicitly selected books yield items.

    Each candidate is prepared once. The returned selections are server-derived;
    publication still revalidates the frozen resource through its normal adapter.
    """
    options = _options(kind, selection)
    requested = _scopes(source_scopes)
    candidates, seen = [], set()
    for resource_id in _paths(kind):
        try:
            for source, item_id, unit, choice in _choices(kind, resource_id, options):
                if item_id in seen:
                    continue
                try:
                    prepared = resources.prepare_resource(kind, choice)
                except (ValueError, TypeError, AttributeError, KeyError):
                    continue
                scope, label, order = _identity(kind, resource_id, source)
                item = {
                    "id": item_id,
                    "label": prepared["title"],
                    "selection": prepared["selection"],
                }
                if kind == "reading_passage":
                    passage = next(
                        row
                        for index, row in enumerate(source["passages"], 1)
                        if int(row.get("passage") or index) == unit
                    )
                    item["question_count"] = sum(
                        len(group["questions"]) for group in passage["groups"]
                    )
                elif kind == "listening_test":
                    item["question_count"] = prepared["metadata"]["question_count"]
                else:
                    item["segment_count"] = prepared["metadata"]["segment_count"]
                candidates.append(((*order, unit, _natural(item_id)), scope, label, item))
                seen.add(item_id)
        except (ValueError, TypeError, AttributeError, KeyError):
            # One malformed, hidden or unavailable source must not hide other books.
            continue
    candidates.sort(key=lambda row: row[0])
    sources = {}
    for _order, scope, label, _item in candidates:
        source = sources.setdefault(scope, {"id": scope, "label": label, "count": 0})
        source["count"] += 1
    if any(scope not in sources for scope in requested):
        raise ValueError("部分所选教材不存在、已下线或没有符合当前筛选的内容，请重新选择")
    selected = set(requested)
    result = {
        "sources": list(sources.values()),
        "items": [item for _order, scope, _label, item in candidates if scope in selected],
    }
    if kind == "intensive":
        result["training_modes"] = [
            {"id": row["key"], "label": row["label"]} for row in TRAINING_MODE_OPTIONS
        ]
    return result
