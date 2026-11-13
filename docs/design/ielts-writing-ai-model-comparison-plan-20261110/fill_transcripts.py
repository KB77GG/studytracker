"""Fill a template's empty essays with a transcription pasted as plain text.

Usage (on the Mac, from the repository root):

    .venv/bin/python docs/design/ielts-writing-ai-model-comparison-plan-20261110/fill_transcripts.py \\
        --template ~/iwa-calibration/official_lowband_template.jsonl \\
        --text ~/iwa-calibration/official_lowband_transcript.txt

The text file is the transcription exactly as written for Claude on 2026-11-12: each
script starts with a heading such as "Task 1A · Script A · 5.0 分（第 9 页）", followed by
its paragraphs (one paragraph per line, blank lines allowed). Lines containing Chinese
(the transcriber's notes, e.g. what the chart shows) are not part of any essay and are
skipped. An uncertain word written as "[word?]" is kept as "word" and listed in the
item's "transcription_note". Nothing in the text is otherwise changed: spelling and
grammar errors are the evidence the official band was given for.

Writes <template dir>/official_lowband_t1.jsonl (Task 1) and official_lowband_t2.jsonl
(Task 2) next to the template (the image paths are relative to that folder), checks them
with realcheck.load_samples and prints ids, word counts and sha256 only - never the text.
Template fields such as "copied_from_question" / "copied_source" (confirmed copying of the
question, 2026-11-13) are carried through; their word counts are printed too.
The files contain a published sample and stay out of Git.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

HEADING = re.compile(r"Task\s*(\d[A-C])\s*[·.\-–]\s*Script\s*([A-C])", re.I)
CJK = re.compile(r"[㐀-鿿＀-￯]")
UNCERTAIN = re.compile(r"\[([^\[\]]+?)\?\]")


def parse(text: str) -> dict[str, dict]:
    """{id: {"essay": str, "notes": [str]}} from the pasted transcription."""
    scripts: dict[str, dict] = {}
    current = None
    for raw in text.splitlines():
        line = raw.strip()
        heading = HEADING.search(line)
        if heading and CJK.search(line):  # "Task 1A · Script A · 5.0 分（第 9 页）"
            current = f"official-{heading.group(1).upper()}-{heading.group(2).upper()}"
            if current in scripts:
                raise SystemExit(f"{current} 出现了两次")
            scripts[current] = {"paragraphs": [], "notes": []}
            continue
        if current is None or not line or CJK.search(line):
            continue  # before the first script, blank, or the transcriber's note
        notes = [f"字迹不清：“{m.group(1)}”" for m in UNCERTAIN.finditer(line)]
        scripts[current]["notes"] += notes
        scripts[current]["paragraphs"].append(UNCERTAIN.sub(r"\1", line))
    return {
        sid: {"essay": "\n".join(s["paragraphs"]), "notes": s["notes"]}
        for sid, s in scripts.items()
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--template", required=True, type=Path)
    ap.add_argument("--text", required=True, type=Path)
    args = ap.parse_args()
    template = args.template.expanduser()
    rows = [json.loads(line) for line in template.read_text(encoding="utf-8").splitlines() if line]
    scripts = parse(args.text.expanduser().read_text(encoding="utf-8"))
    ids = [r["id"] for r in rows]
    missing = [i for i in ids if not scripts.get(i, {}).get("essay")]
    extra = [i for i in scripts if i not in ids]
    if missing or extra:
        raise SystemExit(f"转录稿和模板对不上：缺 {missing or '无'}，多出 {extra or '无'}")
    outputs = {}
    for row in rows:
        row["essay"] = scripts[row["id"]]["essay"]
        if scripts[row["id"]]["notes"]:
            row["transcription_note"] = "；".join(scripts[row["id"]]["notes"])
        outputs.setdefault(row["task_type"], []).append(row)
    sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
    from tools.ielts_writing_ai import essay, realcheck  # noqa: E402

    for task_type, items in outputs.items():
        path = template.with_name(f"official_lowband_{task_type.replace('task', 't')}.jsonl")
        path.write_text(
            "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in items), encoding="utf-8"
        )
        loaded = realcheck.load_samples(str(path))
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        print(f"{path.name}：{len(loaded)} 篇，sha256 {digest}")
        for item in items:
            note = f"（{item['transcription_note']}）" if item.get("transcription_note") else ""
            if item.get("copied_from_question"):
                # Counted the way the tool counts (essay.count_words), never printed.
                spans = essay.resolve_copied(item["essay"], item["copied_from_question"])
                copied = sum(essay.count_words(s["text"]) for s in spans)
                total = essay.count_words(item["essay"])
                note += f"（已确认抄题：第 {'、'.join(str(s['p']) for s in spans)} 段 {copied} 词，自写 {total - copied} 词）"
            print(
                f"  {item['id']}：{len(item['essay'].split())} 词，{item['essay'].count(chr(10)) + 1} 段{note}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
