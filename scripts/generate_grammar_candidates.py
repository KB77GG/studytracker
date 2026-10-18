#!/usr/bin/env python3
"""Generate offline grammar candidates, an audit report and a blind review batch.

Run from any directory with .venv-grammar-tools/bin/python. --limit only writes
the ignored candidate/rejection files and prints counts, preserving full-corpus
teacher deliverables until an unrestricted run can satisfy the sample quotas.
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.grammar_items.checks import sentence_reasons
from scripts.grammar_items.parse_view import ParseCache, load_parser
from scripts.grammar_items.reporting import (
    build_report,
    markdown_report,
    template_counts,
    write_json,
    write_jsonl,
)
from scripts.grammar_items.review_batch import sample_batch, write_workbook
from scripts.grammar_items.spans import locate_spans
from scripts.grammar_items.templates import generate_templates


def collect(root, nlp, cache, limit=None):
    candidates, rejections, results = [], [], []
    files = sorted((root / "data/reading_study").glob("*.json"))
    for index, path in enumerate(files[:limit], 1):
        passage = json.loads(path.read_text(encoding="utf-8"))
        for sentence in passage["sentences"]:
            source = {
                "source_kind": passage["source_kind"],
                "test_id": passage["test_id"],
                "passage_id": passage["passage_id"],
                "sentence_id": sentence["id"],
                "sentence": sentence["sentence"],
            }
            spans = locate_spans(sentence["sentence"], sentence["structure"])
            try:
                view = cache.parse(sentence["sentence"], nlp)
            except Exception as error:
                print(
                    f"Parse failure: {passage['passage_id']} {sentence['id']} {type(error).__name__}",
                    file=sys.stderr,
                )
                view = None
            reasons = sentence_reasons(sentence["sentence"], spans, view)
            results.append((source, reasons))
            if reasons:
                rejections.append(
                    {
                        "source": source,
                        "template": "all",
                        "scope": "sentence",
                        "status": "rejected",
                        "reasons": reasons,
                    }
                )
            else:
                items, rejected = generate_templates(source, spans, view)
                candidates.extend(items)
                rejections.extend(rejected)
        if index % 25 == 0:
            print(f"Processed {index} passages / {len(results)} sentences", flush=True)
    ids = [item["item_id"] for item in candidates]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate item_id across corpus")
    return candidates, rejections, results


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=20261018)
    parser.add_argument(
        "--limit", type=int, help="Debug only: first N passages, no formal review batch"
    )
    args = parser.parse_args(argv)
    if args.limit is not None and args.limit < 1:
        parser.error("--limit must be positive")
    nlp, environment = load_parser(args.seed)
    output = ROOT / "output/grammar_items"
    cache = ParseCache(output / "parse_cache_v0_2.jsonl", environment)
    candidates, rejections, results = collect(ROOT, nlp, cache, args.limit)
    write_jsonl(output / "candidates_v0_2.jsonl", candidates)
    write_jsonl(output / "rejections_v0_2.jsonl", rejections)
    if args.limit is not None:
        print(json.dumps(template_counts(candidates, rejections), ensure_ascii=False, indent=2))
        print("Debug limit: formal report/review files were not overwritten.")
        return 0
    batch, stats = sample_batch(candidates, args.seed)
    graph = json.loads(
        (ROOT / "data/grammar_graph/grammar_graph_v0.json").read_text(encoding="utf-8")
    )
    names = {node["id"]: node["name_zh"] for node in graph["nodes"]}
    report = build_report(ROOT, environment, args.seed, candidates, rejections, results, stats)
    deliverables = ROOT / "data/grammar_items"
    write_json(deliverables / "generation_report_v0_2.json", report)
    (deliverables / "generation_report_v0_2.md").write_text(
        markdown_report(report), encoding="utf-8"
    )
    write_jsonl(deliverables / "review_batch_v0_2.jsonl", batch)
    write_workbook(batch, names, deliverables / "review_batch_v0_2.xlsx")
    print(json.dumps(report["counts_by_template"], ensure_ascii=False, indent=2))
    print(f"Review batch: {len(batch)} rows; estimated {len(batch) / 2:g} minutes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
