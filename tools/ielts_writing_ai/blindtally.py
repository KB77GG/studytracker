"""Count the verdicts of a filled blind review sheet (`realcheck-tally`).

realcheck-compare --blind writes blind_review.md (甲 / 乙 shuffled per sample) and
blind_key.json (which side is which, and every row the sheet must contain: its id and
kind - judged, context or count). Fill the 判断 column first:

- judged rows: 正确 / ① / ② / ③ / 不确定 (the full labels also work, e.g. "① 误读原文");
- context rows are pre-marked 参考 and are not counted;
- count rows ("④ 漏掉评委都指出的明确错误", "其他漏报"): a whole non-negative number, 0 if none.

The sheet is checked against the key's row list (review 76276d9: an empty sheet, a
sheet cut off before 乙, or a count row changed to 参考 had been reported complete).
A missing, duplicated or unknown row, a blank or unrecognized verdict, or a count that
is not a whole non-negative number makes the tally incomplete. Only the first run of
each essay is required unless all_repeats (ids containing "#r" are later runs of
--repeat); rows of later runs that were filled anyway are ignored.

The tally records the sha256 of the sheet and key it counted, so a summary can tell
when the sheet changed afterwards. Only counts are written, no quotes.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

LABELS = {
    "correct": "正确",
    "misread": "① 误读原文",
    "changed_meaning": "② 改句改变原意或逻辑",
    "polish_as_error": "③ 可选润色说成错误",
    "uncertain": "不确定",
    "missed_both_raters": "④ 漏掉评委都指出的明确错误（条）",
    "missed_other": "其他漏报（条）",
}
COUNT_KEYS = {"④ 漏掉评委都指出的明确错误": "missed_both_raters", "其他漏报": "missed_other"}
CONTEXT = "参考"
_WHOLE_NUMBER = re.compile(r"\d+")


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def verdict_key(cell: str) -> str | None:
    """The verdict of a judged row; None when blank, "unrecognized" when invalid."""
    cell = cell.strip()
    if not cell:
        return None
    if cell.startswith("正确"):
        return "correct"
    marks = [
        key
        for mark, key in (("①", "misread"), ("②", "changed_meaning"), ("③", "polish_as_error"))
        if mark in cell
    ]
    if len(marks) == 1:
        return marks[0]
    if not marks and cell.startswith("不确定"):
        return "uncertain"
    return "unrecognized"


def _sheet_rows(sheet: str) -> list[list[str]]:
    rows = []
    for line in sheet.splitlines():
        if not line.startswith("|") or line.startswith("|---"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) >= 7 and cells[0] != "编号":
            rows.append(cells)
    return rows


def tally(sheet: str, key: dict, *, all_repeats: bool = False) -> dict:
    counts = {
        side: dict.fromkeys(list(LABELS) + ["filled", "blank", "unrecognized"], 0)
        for side in ("a", "b")
    }
    problems = []
    expected = {row["id"]: row for row in key.get("rows") or []}
    if not expected:
        problems.append("对应关系文件里没有行清单（旧版盲评表），无法确认表格完整")
    seen: dict[str, int] = {}
    for cells in _sheet_rows(sheet):
        row_id, position, verdict = cells[0], cells[1], cells[5]
        seen[row_id] = seen.get(row_id, 0) + 1
        row = expected.get(row_id)
        if row is None:
            problems.append(f"{row_id}：表里有、清单里没有的行")
            continue
        if seen[row_id] > 1:
            problems.append(f"{row_id}：重复的行")
            continue
        if "#r" in row["sample"] and not all_repeats:
            continue
        side = key["samples"][row["sample"]][row["side"]]
        bucket = counts[side]
        if row["kind"] == "context":
            continue  # evidence; whatever it says is not counted
        if row["kind"] == "count":
            count_key = COUNT_KEYS.get(position)
            if count_key is None:
                bucket["unrecognized"] += 1
                problems.append(f"{row_id}：漏报行的“位置”被改动了")
            elif not verdict:
                bucket["blank"] += 1
                problems.append(f"{row_id} {position}：未填写")
            elif _WHOLE_NUMBER.fullmatch(verdict):
                bucket[count_key] += int(verdict)
                bucket["filled"] += 1
            else:
                bucket["unrecognized"] += 1
                problems.append(f"{row_id} {position}：“{verdict}”不是非负整数")
            continue
        found = verdict_key(verdict)
        if found is None:
            bucket["blank"] += 1
            problems.append(f"{row_id} {position}：未填写")
        elif found == "unrecognized":
            bucket["unrecognized"] += 1
            problems.append(f"{row_id} {position}：无法识别“{verdict}”")
        else:
            bucket[found] += 1
            bucket["filled"] += 1
    missing = [
        row_id
        for row_id, row in expected.items()
        if row_id not in seen and (all_repeats or "#r" not in row["sample"])
    ]
    if missing:
        shown = "、".join(missing[:10]) + ("……" if len(missing) > 10 else "")
        problems.append(f"表里缺少 {len(missing)} 行：{shown}")
    return {
        "labels": LABELS,
        "models": counts,
        "complete": not problems,
        "problems": problems,
        "missing_rows": len(missing),
        "repeats_counted": all_repeats,
    }


def run(folder, *, all_repeats: bool = False) -> dict:
    folder = Path(folder)
    sheet = (folder / "blind_review.md").read_text(encoding="utf-8")
    key_text = (folder / "blind_key.json").read_text(encoding="utf-8")
    key = json.loads(key_text)
    result = tally(sheet, key, all_repeats=all_repeats)
    result["conditions"] = {
        side: {k: (key.get("conditions") or {}).get(side, {}).get(k) for k in ("model",)}
        for side in ("a", "b")
    }
    result["sheet_sha256"] = sha256_text(sheet)
    result["key_sha256"] = sha256_text(key_text)
    (folder / "blind_tally.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    return result


def current(folder) -> bool:
    """Whether blind_tally.json still describes the sheet and key in the folder."""
    folder = Path(folder)
    try:
        tally_data = json.loads((folder / "blind_tally.json").read_text(encoding="utf-8"))
        sheet = (folder / "blind_review.md").read_text(encoding="utf-8")
        key_text = (folder / "blind_key.json").read_text(encoding="utf-8")
    except (OSError, ValueError):
        return False
    return (tally_data.get("sheet_sha256"), tally_data.get("key_sha256")) == (
        sha256_text(sheet),
        sha256_text(key_text),
    )
