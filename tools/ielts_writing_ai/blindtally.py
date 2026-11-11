"""Count the verdicts of a filled blind review sheet (`realcheck-tally`).

realcheck-compare --blind writes blind_review.md (甲 / 乙 shuffled per sample) and
blind_key.json (which side is which). Fill the 判断 column first:

- feedback rows: 正确 / ① / ② / ③ / 不确定 (the full labels also work, e.g. "① 误读原文");
- rows marked 参考 are evidence and are not counted;
- the "④ 漏掉评委都指出的明确错误" and "其他漏报" rows: a whole non-negative number, 0 if none.

Only the first run of each essay is counted unless all_repeats: sections whose id
contains "#r" (later runs of --repeat) may be left blank. A blank feedback row, or a
cell that is not one of the values above (for example "0.5" or "1–2" in a count row,
review 2026-11-11), makes the tally incomplete: it is still written, marked
"complete": false, so it is never mistaken for a finished review. Only counts are
written, no quotes.
"""

from __future__ import annotations

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
COUNT_ROWS = {"④ 漏掉评委都指出的明确错误": "missed_both_raters", "其他漏报": "missed_other"}
CONTEXT = "参考"
_WHOLE_NUMBER = re.compile(r"\d+")


def verdict_key(cell: str) -> str | None:
    """The verdict of a feedback row; None when blank, "unrecognized" when invalid."""
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


def tally(sheet: str, key: dict, *, all_repeats: bool = False) -> dict:
    counts = {
        side: dict.fromkeys(list(LABELS) + ["filled", "blank", "unrecognized"], 0)
        for side in ("a", "b")
    }
    problems = []
    sample = side = None
    for line in sheet.splitlines():
        if line.startswith("## "):
            sample, side = line[3:].strip(), None
            continue
        if sample and "#r" in sample and not all_repeats:
            continue
        heading = re.match(r"### (甲|乙)", line)
        if heading:
            side = key["samples"][sample][heading.group(1)]
            continue
        if not (side and line.startswith("|")) or line.startswith("|---"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 6 or cells[0] == "位置":
            continue
        position, verdict = cells[0], cells[4]
        bucket = counts[side]
        if verdict == CONTEXT:
            continue
        if position in COUNT_ROWS:
            if not verdict:
                bucket["blank"] += 1
                problems.append(f"{sample} {position}：未填写")
            elif _WHOLE_NUMBER.fullmatch(verdict):
                bucket[COUNT_ROWS[position]] += int(verdict)
                bucket["filled"] += 1
            else:
                bucket["unrecognized"] += 1
                problems.append(f"{sample} {position}：“{verdict}”不是非负整数")
            continue
        found = verdict_key(verdict)
        if found is None:
            bucket["blank"] += 1
            problems.append(f"{sample} {position}：未填写")
        elif found == "unrecognized":
            bucket["unrecognized"] += 1
            problems.append(f"{sample} {position}：无法识别“{verdict}”")
        else:
            bucket[found] += 1
            bucket["filled"] += 1
    complete = not problems
    return {
        "labels": LABELS,
        "models": counts,
        "complete": complete,
        "problems": problems,
        "repeats_counted": all_repeats,
    }


def run(folder, *, all_repeats: bool = False) -> dict:
    folder = Path(folder)
    sheet = (folder / "blind_review.md").read_text(encoding="utf-8")
    key = json.loads((folder / "blind_key.json").read_text(encoding="utf-8"))
    result = tally(sheet, key, all_repeats=all_repeats)
    result["conditions"] = {
        side: {k: (key.get("conditions") or {}).get(side, {}).get(k) for k in ("model",)}
        for side in ("a", "b")
    }
    (folder / "blind_tally.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    return result
