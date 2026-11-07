"""Read-only Cambridge listening stem structural candidate scan."""

from __future__ import annotations

import collections
import hashlib
import html
import json
import re
import subprocess
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
RAW = Path("/Users/zhouxin/Desktop/studytracker/data/idictation_xyy_listening/raw.json")
BLANK = re.compile(r"【[^】]*】|_{3,}")
PLACEHOLDER = re.compile(r"\$([^$\s]+)\$")
BASE = "40cd8225db1b0a5da188b1dd99d4521dc5853328"


def baseline_grading_examples():
    source = subprocess.check_output(
        ["git", "show", f"{BASE}:services/ielts_practice_scoring.py"], cwd=ROOT, text=True
    )
    namespace = {}
    exec(compile(source, "production_scoring_baseline.py", "exec"), namespace)
    rows = []
    for test_id, number, values in [
        ("ielts4_test1", 11, ["coal and firewood", "firewood and coal"]),
        ("ielts6_test1", 7, ["10", "4.30", "10, 4.30", "10 to 4.30"]),
        ("ielts6_test1", 19, ["Monday", "Thursday", "Monday and Thursday"]),
        ("ielts6_test1", 32, ["metal", "leather", "metal and leather"]),
        ("ielts6_test3", 36, ["water sand", "water and sand"]),
        ("ielts9_test1", 33, ["plants fish", "plants or fish"]),
        ("ielts9_test2", 12, ["Friday", "Friday Sunday", "Friday and Sunday"]),
    ]:
        payload = json.loads(
            subprocess.check_output(
                ["git", "show", f"{BASE}:static/listening_tests/{test_id}.json"],
                cwd=ROOT,
                text=True,
            )
        )
        q = next(
            q
            for section in payload["sections"]
            for group in section["groups"]
            for q in group["questions"]
            if q["number"] == number
        )
        rows.append(
            {
                "test": test_id,
                "number": number,
                "answer": q["answer"],
                "baseline_awarded": {
                    value: namespace["grade_answer"](q["answer"], value)["awarded"]
                    for value in values
                },
            }
        )
    return rows


def plain(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub("<[^>]+>", " ", str(s or "")))).strip()


def strings(value):
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [s for x in value for s in strings(x)]
    if isinstance(value, dict):
        return [s for x in value.values() for s in strings(x)]
    return []


def main():
    raw = json.loads(RAW.read_text())["parts"]
    candidates = collections.defaultdict(list)
    stats = collections.Counter()
    inventories = []
    image_inventory = []
    for path in sorted((ROOT / "static/listening_tests").glob("ielts*.json")):
        data = json.loads(path.read_text())
        stats["tests"] += 1
        all_numbers = []
        for section in data["sections"]:
            stats["sections"] += 1
            raw_part = raw[str(section["part_id"])]
            raw_part = raw_part.get("values") or raw_part.get("data") or raw_part
            source_q = {str(q["id"]): q for g in raw_part["question"] for q in g["list"]}
            source_groups = {str(g["group_id"]): g for g in raw_part["question"]}
            for group in section["groups"]:
                stats["groups"] += 1
                questions = group["questions"]
                numbers = [q["number"] for q in questions]
                all_numbers.extend(numbers)
                ref = {
                    "test": data["id"],
                    "section": section["section"],
                    "group": group["group_id"],
                    "type": group["type"],
                    "numbers": numbers,
                }
                local = {
                    **ref,
                    "title": group["title"],
                    "desc": group["desc"],
                    "collect": group["collect"],
                    "table": group["table"],
                    "img_local": group["img_local"],
                    "img_url": group["img_url"],
                    "collect_option": group["collect_option"],
                    "questions": [
                        {k: q[k] for k in ("id", "number", "title", "answer", "options")}
                        for q in questions
                    ],
                }
                inventories.append(local)

                def flag(kind, reference=ref, **detail):
                    candidates[kind].append({**reference, **detail})

                source_group = source_groups[str(group["group_id"])]
                for key in ["desc", "collect", "table", "img_url", "collect_option"]:
                    default = {} if key == "collect_option" else None if key == "table" else ""
                    if (source_group.get(key) or default) != group.get(key):
                        flag(
                            "group_structure_changed_from_source",
                            field=key,
                            source=source_group.get(key),
                            current=group.get(key),
                        )

                titles = collections.defaultdict(list)
                ids = {str(q["id"]) for q in questions}
                placeholders = [
                    x
                    for s in strings([group["collect"], group["table"]])
                    for x in PLACEHOLDER.findall(s)
                ]
                if placeholders:
                    unknown = sorted(set(placeholders) - ids)
                    missing = sorted(ids - set(placeholders))
                    if unknown:
                        flag("unknown_placeholders", ids=unknown)
                    if missing:
                        flag("missing_placeholders", ids=missing)
                    duplicate = {
                        k: v for k, v in collections.Counter(placeholders).items() if v > 1
                    }
                    if duplicate:
                        flag("duplicate_placeholders", ids=duplicate)
                desc = plain(group["desc"])
                m = re.search(r"Questions?\s+(\d+)\s*([-–—]|to|and)\s*(\d+)", desc, re.I)
                if m:
                    expected = (
                        [int(m[1]), int(m[3])]
                        if m[2].lower() == "and"
                        else list(range(int(m[1]), int(m[3]) + 1))
                    )
                    if expected != numbers:
                        flag("instruction_question_range", expected=expected, desc=desc)
                elif not re.search(r"Question", desc, re.I):
                    flag("no_question_range", desc=desc)
                image_path = group["img_local"]
                if image_path:
                    stats["image_groups"] += 1
                    p = ROOT / "static" / image_path
                    if not p.exists():
                        flag("missing_local_image", path=str(p))
                    else:
                        try:
                            with Image.open(p) as img:
                                image_inventory.append(
                                    {**ref, "path": image_path, "size": list(img.size)}
                                )
                                img.verify()
                        except Exception as e:
                            flag("invalid_local_image", error=str(e), path=str(p))
                if group["type"] in [6, 7] and not image_path:
                    flag("map_without_local_image", remote=group["img_url"])
                bank = (group.get("collect_option") or {}).get("list") or []
                if bank:
                    letters = [str(o.get("title") or "") for o in bank]
                    if len(set(letters)) != len(letters) or "" in letters:
                        flag("bank_option_keys", keys=letters)
                limit = re.search(r"(?:NO MORE THAN\s+)?(ONE|TWO|THREE)\s+WORDS?", desc, re.I)
                for q in questions:
                    stats["questions"] += 1
                    stats["type_" + str(group["type"])] += 1
                    title = plain(q["title"])
                    titles[title].append(q["number"])
                    blank_count = len(BLANK.findall(title))
                    if blank_count > 1:
                        flag(
                            "multi_blank_title",
                            number=q["number"],
                            blank_count=blank_count,
                            title=title,
                        )
                    if not title:
                        stats["empty_titles"] += 1
                        if (
                            not group["title"]
                            and not group["question_title"]
                            and not image_path
                            and not placeholders
                        ):
                            flag("empty_title_no_shared_context", number=q["number"])
                    if not title and group["type"] != 2:
                        flag("empty_non_combined_title", number=q["number"])
                    if re.search(r"\d+\s*【", title):
                        flag("number_before_blank", number=q["number"], title=title)
                    if re.search(r"【\s*\d+\s*】", title):
                        flag("numbered_blank_title", number=q["number"], title=title)
                    if re.search(r"(?:\$[^$]+\$|<[^>]+>)", q["title"]):
                        flag("raw_markup_in_title", number=q["number"], title=q["title"])
                    opts = q["options"] or bank
                    if opts:
                        letters = [str(o.get("title") or "") for o in opts]
                        if len(set(letters)) != len(letters) or "" in letters:
                            flag("option_keys", number=q["number"], keys=letters)
                        for o in opts:
                            if not plain(o.get("content")):
                                flag(
                                    "empty_option_content",
                                    number=q["number"],
                                    option=o.get("title"),
                                )
                        answer_letters = [x.strip() for x in re.split(r"[,/]", q["answer"])]
                        if any(x not in letters for x in answer_letters):
                            flag(
                                "answer_not_in_options",
                                number=q["number"],
                                answer=q["answer"],
                                keys=letters,
                            )
                    elif group["type"] in [1, 2, 8, 9]:
                        flag("choice_without_options", number=q["number"], title=title)
                    if limit and not opts:
                        maximum = {"ONE": 1, "TWO": 2, "THREE": 3}[limit[1].upper()]
                        variants = [s.strip() for s in q["answer"].split("/")]
                        counts = [
                            len(re.findall(r"[A-Za-z]+(?:[-’'][A-Za-z]+)*", s)) for s in variants
                        ]
                        if counts and min(counts) > maximum:
                            flag(
                                "all_answer_variants_exceed_word_limit",
                                number=q["number"],
                                title=title,
                                answer=q["answer"],
                                limit=maximum,
                                counts=counts,
                                desc=desc,
                            )
                    source = source_q[str(q["id"])]
                    source_options = [
                        {
                            "title": str(option.get("title") or "").strip(),
                            "content": str(option.get("content") or "").strip(),
                        }
                        for option in source.get("option") or []
                    ]
                    if q["number"] != source["number"] or q["options"] != source_options:
                        flag("number_or_options_changed_from_source", number=q["number"])
                    if title != plain(source.get("title")):
                        flag(
                            "title_changed_from_source",
                            number=q["number"],
                            title=title,
                            source=source.get("title"),
                        )
                for title, ns in titles.items():
                    if title and len(ns) > 1:
                        flag(
                            "duplicate_title",
                            numbers=ns,
                            title=title,
                            blank_count=len(BLANK.findall(title)),
                        )
        if all_numbers != list(range(1, 41)):
            candidates["test_number_sequence"].append({"test": data["id"], "numbers": all_numbers})
    out = Path(__file__).with_suffix(".json")
    out.write_text(
        json.dumps(
            {
                "stats": dict(stats),
                "baseline": BASE,
                "raw_sha256": hashlib.sha256(RAW.read_bytes()).hexdigest(),
                "candidate_counts": {k: len(v) for k, v in candidates.items()},
                "candidates": candidates,
                "groups": inventories,
                "images": image_inventory,
                "baseline_grading_examples": baseline_grading_examples(),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
    print(
        json.dumps(
            {"stats": dict(stats), "candidate_counts": {k: len(v) for k, v in candidates.items()}},
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
