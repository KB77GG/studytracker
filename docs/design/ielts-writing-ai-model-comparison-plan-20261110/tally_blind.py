"""Count the verdicts of a filled blind review sheet and map 甲 / 乙 back to the runs.

realcheck-compare --blind writes blind_review.md (甲 / 乙 in a shuffled order per sample)
and blind_key.json (which side is which). Fill the 判断 column of blind_review.md first:

- finding rows: 正确 / ① / ② / ③ / 不确定 (the full labels also work, e.g. "① 误读原文");
- the "④ 漏掉评委都指出的明确错误" and "其他漏报" rows: a number (0 if none).

Only the first run of each essay is counted: sections whose id contains "#r" (the
second run of --repeat) may be left blank; pass --all-repeats to count them too.

Then run: python tally_blind.py <compare dir> [--all-repeats]
It writes blind_tally.json next to the sheet (a = run A, b = run B of the comparison;
run_comparison.sh uses A = Flash, B = Pro) and prints the counts. Only counts are
written - no quotes - so the tally can be shared. Rows left blank are counted as blank,
never as correct.
"""

from __future__ import annotations

import json
import re
import sys
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
MISSED_ROWS = {"④ 漏掉评委都指出的明确错误": "missed_both_raters", "其他漏报": "missed_other"}


def verdict_key(cell: str) -> str | None:
    cell = cell.strip()
    if not cell:
        return None
    if cell.startswith("正确"):
        return "correct"
    for mark, key in (("①", "misread"), ("②", "changed_meaning"), ("③", "polish_as_error")):
        if mark in cell:
            return key
    if cell.startswith("不确定"):
        return "uncertain"
    return "unrecognized"


def tally(sheet: str, key: dict, *, all_repeats: bool = False) -> dict:
    counts = {
        side: dict.fromkeys(list(LABELS) + ["filled", "blank", "unrecognized"], 0)
        for side in ("a", "b")
    }
    per_sample: dict = {}
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
            per_sample.setdefault(sample, {"a": {}, "b": {}})
            continue
        if not (side and line.startswith("|")) or line.startswith("|---"):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) < 6 or cells[0] == "位置":
            continue
        position, verdict = cells[0], cells[4]
        bucket = counts[side]
        row_key = MISSED_ROWS.get(position)
        if row_key:
            if not verdict:
                bucket["blank"] += 1
                continue
            number = re.match(r"\d+", verdict)
            if not number:
                bucket["unrecognized"] += 1
                continue
            bucket[row_key] += int(number.group())
            per_sample[sample][side][row_key] = int(number.group())
            bucket["filled"] += 1
            continue
        found = verdict_key(verdict)
        if found is None:
            bucket["blank"] += 1
        else:
            bucket[found] += 1
            bucket["filled"] += found != "unrecognized"
            per_sample[sample][side][found] = per_sample[sample][side].get(found, 0) + 1
    return {"labels": LABELS, "models": counts, "per_sample": per_sample}


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:] if a != "--all-repeats"]
    if len(args) != 1:
        print(__doc__)
        return 2
    folder = Path(args[0])
    sheet = (folder / "blind_review.md").read_text(encoding="utf-8")
    key = json.loads((folder / "blind_key.json").read_text(encoding="utf-8"))
    result = tally(sheet, key, all_repeats="--all-repeats" in argv)
    result["repeats_counted"] = "--all-repeats" in argv
    result["conditions"] = {
        side: {k: (key.get("conditions") or {}).get(side, {}).get(k) for k in ("model", "dir")}
        for side in ("a", "b")
    }
    (folder / "blind_tally.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    for side in ("a", "b"):
        model = result["conditions"][side]["model"]
        counts = result["models"][side]
        shown = "，".join(f"{LABELS[k]} {counts[k]}" for k in LABELS)
        print(
            f"{side.upper()}（{model}）：{shown}；已判断 {counts['filled']}，未填写 {counts['blank']}，"
            f"无法识别 {counts['unrecognized']}"
        )
    print(f"写入 {folder / 'blind_tally.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
