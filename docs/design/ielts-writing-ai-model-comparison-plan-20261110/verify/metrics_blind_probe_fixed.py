"""The cases of review 7b222c8's metrics_blind_probe.py, re-run against the fixed code
with the expected (fixed) behaviour. The original probe imported the docs/design
scripts, which moved into the tool (batch.py, blindtally.py), and asserted the old
behaviour so the defects stayed reproducible; it is not modified.

Usage: python metrics_blind_probe_fixed.py --repo <tree> --out <result.json>
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
import tempfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.repo))
    from tools.ielts_writing_ai import batch, blindtally, ledger, prompts
    from tools.ielts_writing_ai import realcheck as rc
    from tools.ielts_writing_ai import realcheck_compare as cmp

    def sample(sample_id, score, **extra):
        result = (
            None
            if score is None
            else {
                "overall_band": score,
                "criteria": [
                    {"key": k, "band": score, "summary": "", "issues": []}
                    for k in rc.CRITERION_KEYS
                ],
            }
        )
        return {
            "id": sample_id,
            "task_type": "task2",
            "submission": {"essay_text": "First quote. Other quote. Support quote."},
            "generations": {
                "evaluate": {"status": "failed" if result is None else "ready", "result": result}
            },
            **extra,
        }

    checks = {}

    mixed = {
        "samples": [
            sample("scored", 7.5, teachers=[{"overall": 7}, {"overall": 7}]),
            sample("failed", None, teachers=[{"overall": 6}, {"overall": 8}]),
        ]
    }
    whole = rc._rater_agreement(mixed)["overall"]
    checks["rater_same_population"] = (
        whole["rater_gap"] == 0
        and whole["ai_gap"] == 0.5
        and whole["rater_gap_all"] == 1
        and (whole["essays"], whole["scored"], whole["failed"]) == (2, 1, 1)
        and not whole["ai_gap"] <= whole["rater_gap"]
    )

    all_scored = {
        "samples": [
            sample("hi", 8, group="g", nominal_band=9),
            sample("mid", 7, group="g", nominal_band=8),
            sample("lo", 6, group="g", nominal_band=7),
        ]
    }
    full = rc._ordering(all_scored)["g"]
    missing_top = copy.deepcopy(all_scored)
    missing_top["samples"][0] = sample("hi", None, group="g", nominal_band=9)
    missing = rc._ordering(missing_top)["g"]
    one = rc._ordering(
        {"samples": [all_scored["samples"][0], sample("lo", None, group="g", nominal_band=7)]}
    )["g"]
    checks["ordering_endpoints"] = (
        (full["spread"], full["pairs"]) == (2, 3)
        and (missing["spread"], missing["missing"]) == (None, 1)
        and (one["spread"], one["pairs"]) == (None, 0)
    )

    marked = sample("blind-synthetic", 7)
    result = marked["generations"]["evaluate"]["result"]
    result["argument"] = {
        "position": {"consistent": False},
        "notes": ["SYNTHETIC_ARGUMENT_NOTE"],
        "problems": [
            {
                "type": "contradiction",
                "label": "Contradiction",
                "quote": "First quote.",
                "conflicts_with": "SYNTHETIC_CONFLICT_PARTNER",
                "needs_review": True,
                "p": 3,
                "comment": "Synthetic comment.",
                "suggestion": "Synthetic suggestion.",
            }
        ],
        "improvements": [
            {
                "quote": "Support quote.",
                "comment": "Synthetic optional comment.",
                "from_type": "unsupported",
                "support": ["SYNTHETIC_SUPPORT_EVIDENCE"],
                "suggestion": "Synthetic optional suggestion.",
            }
        ],
    }
    result["count_corrections"] = ["SYNTHETIC_COUNT_CORRECTION"]
    result["criteria"][3]["summary"] = "SYNTHETIC_GRAMMAR_SUMMARY"
    result["criteria"][3]["issues"] = [
        {
            "quote": "Other quote.",
            "comment": "SYNTHETIC_GRAMMAR_COMMENT",
            "suggestion": "SYNTHETIC_REVISED_SENTENCE",
        }
    ]
    view = cmp.sample_view({"calls": []}, marked)
    sheet, _key = cmp.render_blind_review(
        {"samples": [{"a": view, "b": copy.deepcopy(view)}]}, seed=3
    )
    fields = {
        "grammar_summary": "SYNTHETIC_GRAMMAR_SUMMARY",
        "grammar_issue": "SYNTHETIC_GRAMMAR_COMMENT",
        "revised_sentence": "SYNTHETIC_REVISED_SENTENCE",
        "conflicting_quote": "SYNTHETIC_CONFLICT_PARTNER",
        "argument_note": "SYNTHETIC_ARGUMENT_NOTE",
        "reclassification_support": "SYNTHETIC_SUPPORT_EVIDENCE",
        "count_correction": "SYNTHETIC_COUNT_CORRECTION",
        "needs_manual_review": "需人工确认",
        "paragraph_number": "第 3 段",
        "position_inconsistent": "前后不一致",
    }
    included = {name: token in sheet for name, token in fields.items()}
    checks["blind_evidence_complete"] = all(included.values())

    # Since 76276d9 every row has an id and the key lists the expected rows.
    minimal_key = {
        "samples": {"one": {"甲": "a", "乙": "b"}},
        "rows": [{"id": "one/甲/01", "sample": "one", "side": "甲", "kind": "count"}],
    }

    def count_cell(value):
        sheet = f"## one\n### 甲\n| one/甲/01 | 其他漏报 | — | — | — | {value} |  |\n"
        return blindtally.tally(sheet, minimal_key)

    cells = {cell: count_cell(cell) for cell in ("2", "", "0.5", "1–2", "-1")}
    checks["tally_whole_numbers_only"] = (
        cells["2"]["complete"]
        and cells["2"]["models"]["a"]["missed_other"] == 2
        and all(
            not cells[c]["complete"] and cells[c]["models"]["a"]["missed_other"] == 0
            for c in ("", "0.5", "1–2", "-1")
        )
    )

    exported = batch._scores_only({"overall": 6.5, "comment": "SYNTHETIC_PRIVATE_COMMENT"})
    checks["summary_scores_whitelisted"] = "SYNTHETIC_PRIVATE_COMMENT" not in json.dumps(exported)

    with tempfile.TemporaryDirectory(prefix="iwa-summary-synthetic-") as scratch:
        out = Path(scratch)
        book = ledger.Ledger(
            out / "ledger-main.jsonl",
            text_cap=100,
            vision_cap=0,
            run="dev-flash",
            code_sha256=rc.code_fingerprint(),
            prompt_version=prompts.PROMPT_VERSION,
        )
        usage = {"prompt_tokens": 1000, "completion_tokens": 1000}
        for n in range(24):  # 20 by the interrupted attempt, 4 by the finished one
            rid = book.reserve(sample="s", kind="evaluate", model="m", attempt=0)
            if n != 19:  # one request of the interrupted attempt never completed
                book.complete(rid, ok=True, error=None, usage=usage)
        (out / "batch-main.json").write_text(
            json.dumps({"prices": {"flash": {"in": 1, "cached_in": 1, "out": 1}}, "caps": []})
        )
        attempts = batch.collect(out)["groups"]["dev"]["runs"]["flash"]["attempts"]
        checks["summary_counts_all_attempts"] = (
            attempts["requests"] == 24
            and attempts["unknown"] == 1
            and attempts["cost_is_lower_bound"]
            and attempts["estimated_cost"] == 0.046
        )

    result = {"network_calls": 0, "private_inputs_read": False, "checks": checks}
    result["passed"] = all(checks.values())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False))
    raise SystemExit(0 if result["passed"] else 1)


if __name__ == "__main__":
    main()
