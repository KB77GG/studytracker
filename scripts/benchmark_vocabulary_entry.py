"""Reproduce choice-only review entry cost using isolated synthetic SQLite.

Run this same script with --repo pointing at baseline/candidate source trees.
No application config, production database, student data, or network is used.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import sys
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch


def _digest(value):
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True).encode()
    ).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo", type=Path, default=Path(__file__).resolve().parents[1]
    )
    parser.add_argument("--size", type=int, default=1000)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.repo.resolve()))
    from models import DictationWord, StudentVocabularyMastery, db
    from services import vocabulary_autonomous_review as review

    spec = importlib.util.spec_from_file_location(
        "entry_benchmark_fixture", args.repo / "scripts/benchmark_vocabulary_review.py"
    )
    fixture = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fixture)
    results = []
    app = fixture._make_app()
    with app.app_context():
        for case in (
            "meaning",
            "context_direct",
            "context_choice",
            "context_choice_duplicates",
        ):
            db.session.remove()
            db.drop_all()
            db.create_all()
            user, task = fixture._seed(args.size)
            if case != "meaning":
                StudentVocabularyMastery.query.update(
                    {
                        "meaning_recall_next_due_at": fixture.BENCHMARK_NOW
                        + timedelta(days=1),
                        "context_use_next_due_at": fixture.BENCHMARK_NOW
                        - timedelta(days=1),
                    }
                )
            if case.startswith("context_choice"):
                DictationWord.query.update(
                    {
                        "example_en": "This is a complete classroom example sentence.",
                        "usage_pattern": "",
                    }
                )
            if case == "context_choice_duplicates":
                for entry in DictationWord.query.order_by(DictationWord.id).all():
                    entry.core_meaning_zh = f"重复释义{entry.sequence // 2}"
            db.session.commit()
            db.session.expire_all()
            captured = {}
            original_due = review._due_candidates
            original_question = review._question_for
            question_builds = 0

            def capture_due(
                *positional, _original=original_due, _captured=captured, **keywords
            ):
                result = _original(*positional, **keywords)
                _captured["candidates"] = result
                return result

            def count_question(*positional, _original=original_question, **keywords):
                nonlocal question_builds
                question_builds += 1
                return _original(*positional, **keywords)

            with patch.object(review, "_due_candidates", new=capture_due), patch.object(
                review, "_question_for", new=count_question
            ):
                response, elapsed, queries, _ = fixture._timed_call(
                    lambda user=user, task=task: review.review_preflight(
                        user, task.id, now=fixture.BENCHMARK_NOW
                    )
                )
            candidates = captured["candidates"]
            selection = [
                [
                    item["word"].id,
                    item["mastery"].sense_id,
                    item["dimension"],
                    item["stage"],
                    item["remediation_kind"],
                ]
                for item in candidates
            ]
            batch = review._materialize_due_candidates(candidates, 20)
            snapshots = [[item["public"], item["answer"]] for item in batch]
            results.append(
                {
                    "case": case,
                    "catalog_size": args.size,
                    "elapsed_ms": round(elapsed, 3),
                    "query_count": queries,
                    "eligibility_question_builds": question_builds,
                    "due_count": len(candidates),
                    "selection_sha256": _digest(selection),
                    "preflight_sha256": _digest(response),
                    "batch_size": len(batch),
                    "batch_snapshots_sha256": _digest(snapshots),
                }
            )
            print(json.dumps(results[-1]), flush=True)
        db.session.remove()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            {
                "repo": str(args.repo.resolve()),
                "synthetic_only": True,
                "results": results,
            },
            indent=2,
        )
        + "\n"
    )


if __name__ == "__main__":
    main()
