"""Offline synthetic metrics/complete-blind recheck; no keys, essays, or network.

Usage: .venv/bin/python metrics_independent.py --repo TREE --out JSON
The exit status covers regression contracts; separately recorded findings are
unfixed adjacent cases rather than assertions of the old implementation.
"""
from __future__ import annotations

import argparse
import copy
import json
import sys
import tempfile
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo", type=Path, required=True)
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    sys.path.insert(0, str(args.repo))
    from tools.ielts_writing_ai import batch, blindtally, ledger, prompts
    from tools.ielts_writing_ai import realcheck as rc
    from tools.ielts_writing_ai import realcheck_compare as cmp

    checks = {}

    def sample(name, band, **extra):
        result = None if band is None else {
            "overall_band": band,
            "criteria": [{"key": k, "band": band, "summary": "", "issues": []}
                         for k in rc.CRITERION_KEYS],
        }
        return {"id": name, "task_type": "task2",
                "submission": {"essay_text": "Claim sentence. Support sentence."},
                "generations": {"evaluate": {"status": "failed" if result is None else "ready",
                                             "result": result}}, **extra}

    a = {"samples": [sample("common", 7.5, teachers=[{"overall": 7}, {"overall": 7}]),
                     sample("a_only", 8, teachers=[{"overall": 6}, {"overall": 8}]),
                     sample("b_only", None, teachers=[{"overall": 4}, {"overall": 8}])]}
    b = {"samples": [sample("common", 7, teachers=[{"overall": 7}, {"overall": 7}]),
                     sample("a_only", None, teachers=[{"overall": 6}, {"overall": 8}]),
                     sample("b_only", 6, teachers=[{"overall": 4}, {"overall": 8}])]}
    common = cmp.common_rater_agreement(a, b)
    checks["common_population_exact_intersection"] = (
        common["essays"] == 1 and common["a"]["overall"]["rater_gap"] == 0
        and common["a"]["overall"]["ai_gap"] == .5
        and common["b"]["overall"]["ai_gap"] == 0)
    failed = rc.rater_agreement([sample("fail", None, teachers=[{"overall": 6}, {"overall": 8}])])["overall"]
    checks["all_failed_has_no_conditional_gap"] = (
        failed["scored"] == 0 and failed["failed"] == 1
        and failed["rater_gap"] is None and failed["ai_gap"] is None
        and failed["rater_gap_all"] == 2)

    def order(top, bottom):
        return rc._ordering({"samples": [sample("top", top, group="g", nominal_band=8),
                                         sample("mid", 6.5, group="g", nominal_band=6),
                                         sample("bottom", bottom, group="g", nominal_band=4)]})["g"]
    checks["missing_either_endpoint_null"] = all(order(t, l)["spread"] is None
                                                for t, l in [(None, 4), (8, None), (None, None)])
    checks["complete_endpoints_retained"] = order(8, 4)["spread"] == 4
    repeated = rc._ordering({"samples": [sample("top", 8, group="g", nominal_band=8),
                                        sample("top#r2", None, group="g", nominal_band=8),
                                        sample("bottom", 4, group="g", nominal_band=4)]})["g"]
    checks["failed_repeat_counted_separately"] = repeated["missing"] == 1 and repeated["spread"] == 4

    s = sample("synthetic", 7)
    result = s["generations"]["evaluate"]["result"]
    result["argument"] = {"position": {"consistent": True}, "improvements": [{
        "quote": "Claim sentence.", "comment": "Optional clarification.",
        "from_type": "unsupported", "support": ["Support sentence."],
        "suggestion": "SYNTHETIC_REVERSED_MEANING"}]}
    v = cmp.sample_view({"calls": []}, s)
    other = copy.deepcopy(s)
    other_item = other["generations"]["evaluate"]["result"]["argument"]["improvements"][0]
    del other_item["from_type"]
    del other_item["support"]
    other_view = cmp.sample_view({"calls": []}, other)
    sheet, key = cmp.render_blind_review({
        "samples": [{"a": v, "b": other_view}],
        "conditions": {"a": {"model": "SYNTHETIC_MODEL_A"}, "b": {"model": "SYNTHETIC_MODEL_B"}},
    }, seed=1)
    checks["blind_sheet_omits_model_condition_names"] = (
        "SYNTHETIC_MODEL_A" not in sheet and "SYNTHETIC_MODEL_B" not in sheet
        and set(key["samples"]["synthetic"].values()) == {"a", "b"})
    rows = cmp.feedback_rows(v)
    duplicated = [row for row in rows if row[0] == cmp.JUDGED and row[4] == "SYNTHETIC_REVERSED_MEANING"]

    def fill(sheet, *, wrong_suggestion=False):
        out = []
        for line in sheet.splitlines():
            if line.startswith("|") and not line.startswith("|---"):
                cells = [c.strip() for c in line.strip().strip("|").split("|")]
                if len(cells) >= 6 and cells[0] != "位置" and cells[4] != "参考":
                    cells[4] = ("0" if cells[0] in blindtally.COUNT_ROWS else
                                "②" if wrong_suggestion and cells[3] == "SYNTHETIC_REVERSED_MEANING"
                                else "正确")
                    line = "| " + " | ".join(cells) + " |"
            out.append(line)
        return "\n".join(out) + "\n"

    complete_sheet = fill(sheet)
    good = blindtally.tally(complete_sheet, key)
    checks["full_filled_sheet_complete"] = good["complete"]
    checks["blank_sheet_rows_incomplete"] = not blindtally.tally(sheet, key)["complete"]
    strict_cells = {}
    for value in ("0.5", "1–2", "-1", "+1", "one", ""):
        bad = complete_sheet.replace("| 其他漏报 | — | — | — | 0 |", f"| 其他漏报 | — | — | — | {value} |", 1)
        strict_cells[value] = blindtally.tally(bad, key)["complete"]
    checks["invalid_counts_never_complete"] = not any(strict_cells.values())
    repeated_sheet = complete_sheet + sheet.replace("## synthetic\n", "## synthetic#r2\n")
    repeated_key = copy.deepcopy(key)
    repeated_key["samples"]["synthetic#r2"] = key["samples"]["synthetic"]
    checks["optional_repeat_blank_allowed"] = blindtally.tally(repeated_sheet, repeated_key)["complete"]
    checks["all_repeats_blank_incomplete"] = not blindtally.tally(repeated_sheet, repeated_key, all_repeats=True)["complete"]

    missing_b = complete_sheet.split("### 乙", 1)[0]
    reference_bypass = complete_sheet.replace("| 其他漏报 | — | — | — | 0 |", "| 其他漏报 | — | — | — | 参考 |", 1)
    partial_states = {"empty": blindtally.tally("", key),
                      "missing_entire_yi": blindtally.tally(missing_b, key),
                      "count_replaced_by_reference": blindtally.tally(reference_bypass, key)}
    double_tally = blindtally.tally(fill(sheet, wrong_suggestion=True), key)

    private_marker = "SYNTHETIC_PRIVATE_NOTE_DO_NOT_EXPORT"
    exported = batch._quality({"per_sample": [{"id": "s", "scores": {"overall": 7, "extra": private_marker},
                                                "teacher": {"overall": 6.5, "comment": private_marker},
                                                "statuses": {"evaluate": "ready"}}],
                               "teacher_findings": {"covered": 1, "total": 1, "findings": [private_marker]},
                               "ordering": {"g": {"rows": [{"id": private_marker, "nominal": 8, "ai": 7}], "spread": 1}},
                               "repeat_spread": {"samples": [private_marker], "essays": 1}})
    checks["numeric_export_drops_attached_text"] = private_marker not in json.dumps(exported)
    checks["numeric_export_keeps_scores"] = exported["per_sample"][0]["teacher"] == {"overall": 6.5}

    with tempfile.TemporaryDirectory(prefix="iwa-metrics-recheck-") as temp:
        root = Path(temp)
        book = ledger.Ledger(root / "ledger-main.jsonl", text_cap=10, vision_cap=0,
                             run="dev-flash", code_sha256=rc.code_fingerprint(), prompt_version=prompts.PROMPT_VERSION)
        for n in range(4):
            rid = book.reserve(sample="synthetic", kind="evaluate", model="synthetic-model", attempt=n)
            if n != 1:
                book.complete(rid, ok=n != 2, error=None if n != 2 else "synthetic-error",
                              usage={"prompt_tokens": 1000, "completion_tokens": 2000, "prompt_cache_hit_tokens": 0})
        (root / "batch-main.json").write_text(json.dumps({"prices": {"flash": {"in": 1, "out": 1}}}))
        (root / "dev-flash.incomplete-synthetic").mkdir()
        collected = batch.collect(root)
        attempts = collected["groups"]["dev"]["runs"]["flash"]["attempts"]
        checks["ledger_counts_unknown_and_failed_archives"] = (
            attempts["requests"] == 4 and attempts["unknown"] == 1
            and attempts["estimated_cost"] == .009 and attempts["cost_is_lower_bound"])
        checks["unfinished_run_no_final_quality"] = "final" not in collected["groups"]["dev"]["runs"]["flash"]

    output = {"network_calls": 0, "private_inputs_read": False, "checks": checks,
              "passed": all(checks.values()), "findings": {
                  "incomplete_sheet_marked_complete": {
                      case: {"complete": tally["complete"], "models": tally["models"]}
                      for case, tally in partial_states.items()},
                  "one_reclassified_advice_has_two_judged_rows": {
                      "source_improvements": 1, "judged_rows_with_same_advice": len(duplicated),
                      "positions": [r[1] for r in duplicated],
                      "changed_meaning_count_per_model": {k: v["changed_meaning"] for k, v in double_tally["models"].items()}}}}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(output, ensure_ascii=False))
    return 0 if output["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
