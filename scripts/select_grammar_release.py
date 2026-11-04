#!/usr/bin/env python3
"""Pick the first Cambridge release set from the grammar candidates and a check sample.

Reads output/grammar_items/candidates_v0_2.jsonl (run generate_grammar_candidates.py first).
Release pool (user decision 2026-11-04): Cambridge auto_pass items from "clean" sentences,
i.e. sentences none of whose items needs review. Four templates are capped at 1,500 items,
at most one per sentence, spread over the books in proportion to the pool; clause boundaries
and adverbial relations are taken whole.

Writes the chosen item ids and a Markdown summary to data/grammar_items/ (the full items go to
output/grammar_items/release_v0_2_cambridge.jsonl until the set has passed its check), plus a
check sample (up to 100 per template) as CSV batches in output/grammar_items/release_check/
for an outside cross-check before anything goes live.
"""

import argparse
import csv
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.export_grammar_needs_review import BATCH_SIZE, HEADERS, review_row  # noqa: E402
from scripts.grammar_items.review_batch import SHEET_NAMES, largest_remainder  # noqa: E402
from scripts.grammar_items.templates import TEMPLATES  # noqa: E402

QUOTAS = {
    "main_verb_tap": 1500,
    "clause_boundary": None,
    "clause_type_classify": 1500,
    "adverbial_relation": None,
    "subject_span": 1500,
    "finite_or_not": 1500,
}
CHECK_PER_TEMPLATE = 100
# The check sample has no reasons to show: every item passed the machine checks.
CHECK_HEADERS = tuple(h for h in HEADERS if h not in ("待复核原因", "原因码"))


def sentence_key(item):
    return item["source"]["passage_id"], item["source"]["sentence_id"]


def book(item):
    return item["source"]["passage_id"].split("_", 1)[0]


def release_pool(candidates):
    """Cambridge auto_pass items whose sentence has no needs_review item at all."""
    cambridge = [i for i in candidates if i["source"]["passage_id"].startswith("ielts")]
    flagged = {sentence_key(i) for i in cambridge if i["status"] == "needs_review"}
    return [i for i in cambridge if i["status"] == "auto_pass" and sentence_key(i) not in flagged]


def pick(items, quota, rng):
    """At most one item per sentence, then a per-book share of the quota."""
    if quota is None:
        return items
    by_sentence = defaultdict(list)
    for item in sorted(items, key=lambda i: i["item_id"]):
        by_sentence[sentence_key(item)].append(item)
    singles = [rng.choice(group) for _, group in sorted(by_sentence.items())]
    if quota >= len(singles):
        return singles
    by_book = defaultdict(list)
    for item in singles:
        by_book[book(item)].append(item)
    shares = largest_remainder({b: len(group) for b, group in by_book.items()}, quota)
    chosen = []
    for b, group in sorted(by_book.items()):
        chosen += rng.sample(group, shares[b])
    return chosen


def select(candidates, seed):
    rng = random.Random(seed)
    pool = release_pool(candidates)
    release = []
    for template in TEMPLATES:
        items = [i for i in pool if i["template"] == template]
        release += pick(items, QUOTAS[template], rng)
    order = {t: n for n, t in enumerate(TEMPLATES)}
    release.sort(key=lambda i: (order[i["template"]], *sentence_key(i), i["item_id"]))
    check = []
    for template in TEMPLATES:
        items = [i for i in release if i["template"] == template]
        check += rng.sample(items, min(CHECK_PER_TEMPLATE, len(items)))
    check.sort(key=lambda i: (order[i["template"]], *sentence_key(i), i["item_id"]))
    return pool, release, check


def summary(pool, release, check, seed):
    pool_counts = Counter(i["template"] for i in pool)
    counts = Counter(i["template"] for i in release)
    check_counts = Counter(i["template"] for i in check)
    lines = [
        "# 剑桥首批上线题（v0.2）",
        "",
        "由 `scripts/select_grammar_release.py` 生成（种子 "
        f"{seed}）。题库：剑桥自动通过题中，整句所有题都自动通过的句子；四种题型各取 1,500 道，"
        "同一句同一题型最多 1 道，按书按比例分配；从句边界、状语关系全部保留。",
        "",
        "| 题型 | 可选（干净句子） | 入选 | 验收抽查 |",
        "|---|---:|---:|---:|",
    ]
    for template in TEMPLATES:
        lines.append(
            f"| {SHEET_NAMES[template]} | {pool_counts[template]:,} | {counts[template]:,} "
            f"| {check_counts[template]} |"
        )
    lines.append(f"| 合计 | {len(pool):,} | {len(release):,} | {len(check)} |")
    books = Counter(book(i) for i in release)
    difficulty = Counter(i["difficulty"] for i in release)
    lines += [
        "",
        f"句子数：{len({sentence_key(i) for i in release}):,}；"
        f"篇章数：{len({i['source']['passage_id'] for i in release}):,}。",
        "",
        "难度：" + "、".join(f"{k} {difficulty[k]:,}" for k in ("easy", "medium", "hard")) + "。",
        "",
        "按书："
        + "、".join(f"{b} {n}" for b, n in sorted(books.items(), key=lambda kv: int(kv[0][5:]))),
        "",
        "上线前须先完成验收抽查；这份清单本身不代表已通过人工验收。",
        "",
    ]
    return "\n".join(lines)


def write_check(check, directory):
    directory.mkdir(parents=True, exist_ok=True)
    for old in directory.glob("release_check_*.csv"):
        old.unlink()
    keep = [HEADERS.index(h) for h in CHECK_HEADERS]
    for start in range(0, len(check), BATCH_SIZE):
        path = directory / f"release_check_{start // BATCH_SIZE + 1:03d}.csv"
        with path.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(CHECK_HEADERS)
            for index, item in enumerate(check[start : start + BATCH_SIZE], start + 1):
                row = review_row(index, item)
                writer.writerow([row[k] for k in keep])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--seed", type=int, default=20261104)
    parser.add_argument(
        "--candidates", type=Path, default=ROOT / "output/grammar_items/candidates_v0_2.jsonl"
    )
    args = parser.parse_args(argv)
    candidates = [json.loads(line) for line in args.candidates.open(encoding="utf-8")]
    pool, release, check = select(candidates, args.seed)
    data, output = ROOT / "data/grammar_items", ROOT / "output/grammar_items"
    with (output / "release_v0_2_cambridge.jsonl").open("w", encoding="utf-8") as handle:
        for item in release:
            handle.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")
    checked = {item["item_id"] for item in check}
    with (data / "release_v0_2_cambridge_ids.csv").open(
        "w", encoding="utf-8", newline=""
    ) as handle:
        writer = csv.writer(handle)
        writer.writerow(("item_id", "template", "passage_id", "sentence_id", "in_check_sample"))
        for item in release:
            writer.writerow(
                (
                    item["item_id"],
                    item["template"],
                    *sentence_key(item),
                    int(item["item_id"] in checked),
                )
            )
    (data / "release_v0_2_cambridge.md").write_text(
        summary(pool, release, check, args.seed), encoding="utf-8"
    )
    write_check(check, output / "release_check")
    print(f"pool {len(pool)}, release {len(release)}, check {len(check)}")


if __name__ == "__main__":
    main()
