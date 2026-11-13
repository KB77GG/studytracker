"""Decide whether a vision model's reading of a Task 1 visual is good enough to
score Task Achievement.

A successful HTTP call proves nothing: a model can answer "I cannot read this
image" or describe a blank picture. The vision model must return a structured
reading, and the server - not the model - decides sufficiency from what was
actually extracted. Only a sufficient reading upgrades the image to ``ready``;
anything else leaves TA and the overall band not assessable.

A sufficient reading is only well formed, not correct: the first real reading
(2026-11-13) had two clearly wrong values. TA is scored only after a person has
compared the reading with the image (prompts.visual_available); check_text gives the
form shown for that check.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from .llm import parse_strict_json

DATA_TYPES = {"bar_chart", "line_graph", "pie_chart", "table", "mixed_chart"}
TYPE_LABELS = {
    "bar_chart": "柱状图",
    "line_graph": "折线图",
    "pie_chart": "饼图",
    "table": "表格",
    "mixed_chart": "组合图",
    "map": "地图",
    "process": "流程图",
}
MIN_DATA_POINTS = 3  # chart/table: at least this many legible label/value pairs
MIN_MAP_FEATURES = 2  # map: changes/locations described
MIN_PROCESS_STAGES = 3  # process: ordered stages

# A reading that says it could not see anything is never sufficient, whatever
# "readability" value the model chose.
UNREADABLE_RE = re.compile(
    r"cannot read|can't read|can not read|unable to (?:read|see|make out|determine|identify)|"
    r"illegible|unreadable|not legible|too (?:blurry|small|dark)|blurry|"
    r"\bblank\b|\bempty (?:image|picture)|"
    r"no (?:readable|visible|legible) (?:chart|graph|diagram|table|map|data|text|values?)\b|"
    r"\bno (?:chart|graph|diagram|table)\b|not (?:a|any) (?:chart|graph|diagram)|"
    r"无法|看不清|读不出|空白|模糊",
    re.IGNORECASE,
)
UNCLEAR_VALUE_RE = re.compile(r"unclear|unknown|illegible|n/?a|\?|不清|未知", re.IGNORECASE)


@dataclass
class VisualReading:
    sufficient: bool
    code: str  # "ok" | "unstructured" | "insufficient"
    reason: str  # Chinese, shown to the user when not sufficient
    description: str  # text rendering of what was read (prompt + page)


def _clean(value, limit: int = 300) -> str:
    return str(value).strip()[:limit] if isinstance(value, (str, int, float)) else ""


def _clean_list(value, limit_items: int = 30) -> list[str]:
    if not isinstance(value, list):
        return []
    return [text for text in (_clean(v) for v in value) if text][:limit_items]


def parse_json(text: str) -> dict | None:
    """Only a reply that is entirely one JSON object (or one fenced JSON block)."""
    return parse_strict_json(text)


def _render(reading: dict, points: list[tuple[str, str]], features, unclear) -> str:
    vtype = reading.get("visual_type")
    lines = [f"Type: {vtype or 'unknown'}"]
    for key, label in (("title", "Title"), ("units", "Units")):
        if _clean(reading.get(key)):
            lines.append(f"{label}: {_clean(reading.get(key))}")
    for key, label in (("categories", "Categories"), ("periods", "Periods")):
        values = _clean_list(reading.get(key))
        if values:
            lines.append(f"{label}: {', '.join(values)}")
    if points:
        lines.append("Data: " + "; ".join(f"{label} = {value}" for label, value in points))
    if features:
        lines.append("Main features:")
        lines += [f"- {feature}" for feature in features]
    if unclear:
        lines.append("Unclear: " + "; ".join(unclear))
    summary = _clean(reading.get("summary"), 1200)
    if summary:
        lines.append(f"Summary: {summary}")
    return "\n".join(lines)


def assess(raw_text: str) -> VisualReading:
    reading = parse_json(raw_text)
    if reading is None:
        excerpt = " ".join((raw_text or "").split())[:400]
        return VisualReading(
            False,
            "unstructured",
            "识图模型没有返回结构化读图结果",
            f"识图模型原始输出：{excerpt}" if excerpt else "",
        )

    points: list[tuple[str, str]] = []
    for item in reading.get("data_points") if isinstance(reading.get("data_points"), list) else []:
        if not isinstance(item, dict):
            continue
        label, value = _clean(item.get("label"), 120), _clean(item.get("value"), 60)
        if label and value and re.search(r"\d", value) and not UNCLEAR_VALUE_RE.search(value):
            points.append((label, value))
    features = _clean_list(reading.get("main_features"), 12)
    unclear = _clean_list(reading.get("unclear"), 12)
    description = _render(reading, points, features, unclear)

    def insufficient(reason: str) -> VisualReading:
        return VisualReading(False, "insufficient", reason, description)

    readability = _clean(reading.get("readability")).lower()
    if readability == "unreadable":
        return insufficient("识图模型判定题图无法读取")
    if readability == "partial":
        return insufficient("识图模型只读出了部分数据")
    if readability != "sufficient":
        return insufficient("识图结果没有给出可读性判定")

    claims = " ".join([_clean(reading.get("summary"), 1200), *features])
    if UNREADABLE_RE.search(claims):
        return insufficient("识图描述表明题图空白或看不清")

    vtype = _clean(reading.get("visual_type")).lower()
    if vtype in DATA_TYPES:
        if len(points) < MIN_DATA_POINTS:
            return insufficient(
                f"只读出 {len(points)} 个带数值的数据点（至少需要 {MIN_DATA_POINTS} 个）"
            )
        if len(unclear) >= len(points):
            return insufficient("读不清的数据多于读清的数据")
        if not features:
            return insufficient("没有读出主要趋势或对比")
    elif vtype == "map":
        if len(features) < MIN_MAP_FEATURES:
            return insufficient("地图题没有读出足够的位置或变化信息")
    elif vtype == "process":
        if len(features) < MIN_PROCESS_STAGES:
            return insufficient(f"流程图只读出 {len(features)} 个步骤")
    else:
        return insufficient("没有识别出 Task 1 图表类型")
    return VisualReading(True, "ok", "", description)


CHECK_MAX_CHARS = 2500


def check_text(description: str | None) -> str:
    """The reading with one data point per line, for a person to compare with the image."""
    lines = []
    for line in (description or "").replace("\r\n", "\n").split("\n"):
        if line.startswith("Data: "):
            lines.append("Data:")
            lines += [f"- {point.strip()}" for point in line[6:].split("; ") if point.strip()]
        else:
            lines.append(line.rstrip())
    return "\n".join(lines).strip()


def same_reading(a: str | None, b: str | None) -> bool:
    """Equal apart from layout (the check form vs. the stored form)."""

    def flat(text):
        return " ".join(check_text(text).replace("\n- ", "; ").split())

    return flat(a) == flat(b)
