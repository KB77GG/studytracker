"""Normalize IELTS practice-table data into a renderer-safe layout.

The imported Cambridge and jijing data uses coordinate pairs such as ``[1, 0]``
to mean "this slot belongs to the cell at row 1, column 0".  Some older files
also wrap a header row in one extra list or omit the repeated slots for a
full-width title.  Renderers should not have to understand those source quirks.
"""

from __future__ import annotations

import copy
import re
from collections import defaultdict
from typing import Any


_HEADER_TAG_RE = re.compile(r"<\s*(?:b|bc)\s*>", re.IGNORECASE)


def _is_coordinate(value: Any) -> bool:
    return (
        isinstance(value, list)
        and len(value) == 2
        and all(isinstance(part, int) and not isinstance(part, bool) for part in value)
    )


def _source_rows(table: dict) -> list[list[Any]]:
    rows = table.get("content")
    if not isinstance(rows, list):
        return []

    normalized = []
    for row_index, row in enumerate(rows):
        cells = row if isinstance(row, list) else [row]
        # One jijing source accidentally stores its header as [["A", "B"]].
        if len(cells) == 1 and isinstance(cells[0], list) and not _is_coordinate(cells[0]):
            cells = cells[0]
        # A small set of jijing imports shifted full-row merge references one
        # row upward (for example [3, 1] beside a section label on row 4).
        # When every trailing slot is a reference, the only non-reference cell
        # on the current row is the intended full-width origin.
        if (
            len(cells) > 1
            and not _is_coordinate(cells[0])
            and all(_is_coordinate(cell) for cell in cells[1:])
            and any(cell[0] < row_index for cell in cells[1:])
        ):
            cells = [cells[0], *[[row_index, 0] for _ in cells[1:]]]
        normalized.append(list(cells))
    return normalized


def _cell_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    return ""


def normalize_practice_table(table: Any) -> Any:
    """Return a copy of *table* with a canonical ``render`` layout.

    The original ``content`` is preserved for grading/debugging compatibility.
    ``render.rows`` contains only origin cells and carries explicit row/column
    spans, so coordinate references never leak into the UI.
    """

    if not isinstance(table, dict):
        return table

    result = copy.deepcopy(table)
    raw_rows = table.get("content") if isinstance(table.get("content"), list) else []
    nested_header_rows = {
        row_index
        for row_index, row in enumerate(raw_rows)
        if (
            isinstance(row, list)
            and len(row) == 1
            and isinstance(row[0], list)
            and not _is_coordinate(row[0])
        )
    }
    rows = _source_rows(table)
    if not rows:
        result["render"] = {"version": 1, "column_count": 0, "rows": []}
        return result

    column_count = max((len(row) for row in rows), default=0)
    if not column_count:
        result["render"] = {"version": 1, "column_count": 0, "rows": []}
        return result

    grid: list[list[Any]] = []
    for row_index, row in enumerate(rows):
        current = list(row)
        if len(current) == 1 and column_count > 1 and row_index == 0:
            current.extend([[0, 0] for _ in range(column_count - 1)])
        elif len(current) < column_count:
            current.extend(["" for _ in range(column_count - len(current))])
        grid.append(current)

    row_count = len(grid)

    def resolve(position: tuple[int, int], trail: set[tuple[int, int]] | None = None) -> tuple[int, int]:
        row_index, column_index = position
        if not (0 <= row_index < row_count and 0 <= column_index < column_count):
            return position
        value = grid[row_index][column_index]
        if not _is_coordinate(value):
            return position
        target = (value[0], value[1])
        if not (0 <= target[0] < row_count and 0 <= target[1] < column_count):
            return position
        seen = set(trail or ())
        if position in seen or target == position:
            return position
        seen.add(position)
        return resolve(target, seen)

    positions_by_origin: dict[tuple[int, int], list[tuple[int, int]]] = defaultdict(list)
    for row_index in range(row_count):
        for column_index in range(column_count):
            origin = resolve((row_index, column_index))
            positions_by_origin[origin].append((row_index, column_index))

    header_rows = set()
    for row_index, row in enumerate(grid):
        texts = [
            _cell_text(value)
            for value in row
            if not _is_coordinate(value) and _cell_text(value).strip()
        ]
        if len(texts) >= 2 and all(_HEADER_TAG_RE.search(text) for text in texts):
            header_rows.add(row_index)

    render_rows: list[list[dict]] = [[] for _ in range(row_count)]
    for (row_index, column_index), positions in sorted(positions_by_origin.items()):
        value = grid[row_index][column_index]
        # An invalid/cyclic reference is not meaningful display content.
        text = "" if _is_coordinate(value) else _cell_text(value)
        min_row = min(position[0] for position in positions)
        max_row = max(position[0] for position in positions)
        min_column = min(position[1] for position in positions)
        max_column = max(position[1] for position in positions)
        expected = {
            (r, c)
            for r in range(min_row, max_row + 1)
            for c in range(min_column, max_column + 1)
        }
        actual = set(positions)
        rectangular = actual == expected and (row_index, column_index) == (min_row, min_column)
        rowspan = max_row - min_row + 1 if rectangular else 1
        colspan = max_column - min_column + 1 if rectangular else 1
        is_header = bool(
            _HEADER_TAG_RE.search(text)
            or row_index in nested_header_rows
            or (row_index == 0 and colspan == column_count and column_count > 1)
        )
        scope = ""
        if is_header:
            if colspan > 1:
                scope = "colgroup"
            elif row_index in header_rows or row_index in nested_header_rows:
                scope = "col"
            elif column_index == 0:
                scope = "row"

        render_rows[row_index].append({
            "key": f"r{row_index}c{column_index}",
            "row_index": row_index,
            "column_index": column_index,
            "text": text,
            "rowspan": rowspan,
            "colspan": colspan,
            "is_header": is_header,
            "scope": scope,
        })

    result["render"] = {
        "version": 1,
        "column_count": column_count,
        "rows": render_rows,
    }
    return result


def normalize_practice_tables(payload: Any) -> Any:
    """Recursively add canonical render layouts to every table in a payload."""

    if isinstance(payload, list):
        return [normalize_practice_tables(item) for item in payload]
    if not isinstance(payload, dict):
        return payload

    normalized = {}
    for key, value in payload.items():
        if key == "table":
            normalized[key] = normalize_practice_table(value)
        else:
            normalized[key] = normalize_practice_tables(value)
    return normalized
