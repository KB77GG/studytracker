#!/usr/bin/env python3
"""Return the next missing Reading Study passage for a deterministic worker lane."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from validate_reading_study import DEFAULT_OUTPUT, load_source_passages


def passage_number(passage: dict) -> int:
    try:
        return int(passage.get("passage") or 0)
    except (TypeError, ValueError):
        return 0


def difficulty_for(passage: dict) -> str:
    return {1: "simple", 2: "medium", 3: "complex"}.get(passage_number(passage), "medium")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lane", type=int, required=True)
    parser.add_argument("--lanes", type=int, default=2)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--reverse",
        action="store_true",
        help="scan the queue from the tail (lane partition unchanged), "
        "so reverse workers never collide with forward workers",
    )
    args = parser.parse_args()
    if args.lanes < 1 or args.lane < 0 or args.lane >= args.lanes:
        parser.error("lane must satisfy 0 <= lane < lanes")

    source_passages = load_source_passages()
    entries = sorted(
        source_passages.items(),
        key=lambda item: (
            0 if item[1]["source_kind"] == "reading_test" else 1,
            item[1]["source_path"].name,
            passage_number(item[1]["passage"]),
            item[0],
        ),
    )
    indexed = list(enumerate(entries))
    if args.reverse:
        indexed.reverse()
    for index, (passage_id, meta) in indexed:
        if index % args.lanes != args.lane:
            continue
        output_path = args.output_dir / f"{passage_id}.json"
        if output_path.exists():
            continue
        print(
            json.dumps(
                {
                    "lane": args.lane,
                    "lanes": args.lanes,
                    "passage_id": passage_id,
                    "source_kind": meta["source_kind"],
                    "source_path": str(meta["source_path"].relative_to(Path.cwd())),
                    "test_id": meta["test_id"],
                    "difficulty": difficulty_for(meta["passage"]),
                    "output_path": str(output_path.relative_to(Path.cwd())),
                },
                ensure_ascii=False,
            )
        )
        return 0
    print(json.dumps({"lane": args.lane, "lanes": args.lanes, "complete": True}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
