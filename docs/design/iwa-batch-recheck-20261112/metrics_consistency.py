"""Offline, synthetic-only recheck of blind manifest, mapping and tally freshness."""
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

    checks = {}

    def sample(marker):
        return {
            "id": "synthetic", "task_type": "task2",
            "submission": {"essay_text": "A synthetic sentence.", "prompt_text": "Synthetic prompt."},
            "generations": {"evaluate": {"status": "ready", "result": {
                "overall_band": 6,
                "criteria": [{"key": k, "band": 6, "summary": "", "issues": []}
                             for k in ("task", "coherence", "lexical", "grammar")],
                "argument": {"position": {"consistent": True}},
                "overall_comment": marker,
                "count_corrections": ["SYNTHETIC_CONTEXT"],
            }}},
        }

    def transform(sheet, fn):
        lines = []
        for line in sheet.splitlines():
            if line.startswith("|") and not line.startswith("|---"):
                cells = [c.strip() for c in line.strip().strip("|").split("|")]
                if len(cells) >= 7 and cells[0] != "编号":
                    cells = fn(cells)
                    if cells is None:
                        continue
                    line = "| " + " | ".join(cells) + " |"
            lines.append(line)
        return "\n".join(lines) + "\n"

    def fill(cells):
        if cells[5] == "参考":
            return cells
        cells[5] = "0" if cells[1] in cmp.COUNT_ROWS else "②" if cells[3] == "SYNTHETIC_BAD" else "正确"
        return cells

    with tempfile.TemporaryDirectory(prefix="iwa-blind-consistency-") as tmp:
        root = Path(tmp)
        for side, model in (("a", "flash"), ("b", "pro")):
            run = root / f"dev-{model}"
            run.mkdir()
            (run / "run_data.json").write_text(json.dumps({
                "samples": [sample("SYNTHETIC_BAD" if side == "a" else "SYNTHETIC_GOOD")],
                "calls": [], "kinds": ["evaluate"], "settings": {"evaluate_thinking": "high"},
            }))
            (run / "report.json").write_text(json.dumps({
                "provider": "demo", "model": f"synthetic-{model}", "prompt_version": "synthetic",
                "code_sha256": "synthetic-code", "kinds": {"evaluate": {"max_tokens": [32000]}},
            }))
        compared = cmp.compare(root / "dev-flash", root / "dev-pro", allow_model_change=True)
        folder = root / "compare-dev"
        cmp.write(compared, folder, blind_seed=0)
        blank = (folder / "blind_review.md").read_text()
        key_text = (folder / "blind_key.json").read_text()
        key = json.loads(key_text)
        filled = transform(blank, fill)
        good = blindtally.tally(filled, key)
        checks["full_control_complete_and_correctly_attributed"] = (
            good["complete"] and good["models"]["a"]["changed_meaning"] == 1
            and good["models"]["b"]["changed_meaning"] == 0)
        checks["empty_rejected"] = not blindtally.tally("", key)["complete"]
        checks["missing_side_rejected"] = not blindtally.tally(filled.split("### 乙", 1)[0], key)["complete"]
        first_judged = next(r["id"] for r in key["rows"] if r["kind"] == "judged")
        first_count = next(r["id"] for r in key["rows"] if r["kind"] == "count")
        for name, rid in (("judged", first_judged), ("count", first_count)):
            edited = transform(filled, lambda c: c[:5] + ["参考"] + c[6:] if c[0] == rid else c)
            checks[f"{name}_cannot_become_reference"] = not blindtally.tally(edited, key)["complete"]
        first_line = next(line for line in filled.splitlines() if line.startswith(f"| {first_judged} |"))
        checks["duplicate_row_rejected"] = not blindtally.tally(filled + first_line + "\n", key)["complete"]
        checks["unknown_row_rejected"] = not blindtally.tally(filled + first_line.replace(first_judged, "unknown/id") + "\n", key)["complete"]
        checks["old_key_without_manifest_rejected"] = not blindtally.tally(filled, {"samples": key["samples"]})["complete"]

        (folder / "blind_review.md").write_text(filled)
        blindtally.run(folder)
        checks["fresh_tally_is_current"] = blindtally.current(folder)
        book = ledger.Ledger(root / "ledger-main.jsonl", text_cap=1, vision_cap=0,
                             run="dev-flash", code_sha256=rc.code_fingerprint(), prompt_version=prompts.PROMPT_VERSION)
        rid = book.reserve(sample="synthetic", kind="evaluate", model="demo", attempt=0)
        book.complete(rid, ok=True, error=None, usage={"prompt_tokens": 1, "completion_tokens": 1})
        files_before = {p.name: p.read_bytes() for p in folder.iterdir() if p.is_file()}
        try:
            cmp.write(compared, folder, blind_seed=1)
        except cmp.CompareError:
            rejected = True
        else:
            rejected = False
        checks["explicit_rewrite_refused_before_any_files_change"] = (
            rejected and files_before == {p.name: p.read_bytes() for p in folder.iterdir() if p.is_file()})

        (folder / "blind_review.md").write_text(filled + "\n")
        stale_sheet = batch.collect(root)
        checks["edited_sheet_marks_summary_stale"] = (
            not stale_sheet["groups"]["dev"]["blind_tally"]["current"]
            and "已过期" in batch.markdown(stale_sheet))
        (folder / "blind_review.md").write_text(filled)
        checks["restored_sheet_current_again"] = blindtally.current(folder)
        mutated_key = copy.deepcopy(key)
        mutated_key["samples"]["synthetic"] = {"甲": "b", "乙": "a"}
        (folder / "blind_key.json").write_text(json.dumps(mutated_key, ensure_ascii=False))
        stale_key = batch.collect(root)
        checks["edited_mapping_marks_summary_stale"] = (
            not stale_key["groups"]["dev"]["blind_tally"]["current"]
            and "已过期" in batch.markdown(stale_key))
        (folder / "blind_key.json").write_text(key_text)
        checks["restored_mapping_current_again"] = blindtally.current(folder)

        # Adjacent integrity case: keys independently generated with different seeds
        # have identical row IDs and kinds, but reverse the hidden a/b attribution.
        other_sheet, other_key = cmp.render_blind_review(compared, seed=1)
        assert other_key["samples"]["synthetic"] != key["samples"]["synthetic"]
        mixed = blindtally.tally(filled, other_key)
        other_key["conditions"] = compared["conditions"]
        (folder / "blind_key.json").write_text(json.dumps(other_key, ensure_ascii=False))
        mixed_saved = blindtally.run(folder)
        mixed_current = blindtally.current(folder)
        mixed_summary = batch.collect(root)["groups"]["dev"]["blind_tally"]

        # The count row's semantic identity is not stored in the manifest. Renaming
        # one valid count label to the other is accepted and shifts error categories.
        with_two = transform(filled, lambda c: c[:5] + ["2"] + c[6:] if c[0] == first_count else c)
        count_before = blindtally.tally(with_two, key)
        relabeled = transform(with_two, lambda c: [c[0], "其他漏报"] + c[2:] if c[0] == first_count else c)
        count_after = blindtally.tally(relabeled, key)
        counter_side = key["samples"]["synthetic"][next(r["side"] for r in key["rows"] if r["id"] == first_count)]
        checks["mismatched_generated_key_rejected"] = not mixed["complete"]
        checks["retally_mismatch_never_complete_or_current"] = (
            not mixed_saved["complete"] and not mixed_current
            and not (mixed_summary["complete"] and mixed_summary["current"]))
        checks["valid_count_label_substitution_rejected"] = not count_after["complete"]
        result = {
            "network_calls": 0, "private_inputs_read": False,
            "checks": checks, "passed": all(checks.values()),
            "passed_checks": sum(checks.values()), "total_checks": len(checks),
            "findings": {
                "same_shape_wrong_key_accepted": {
                    "original_mapping": key["samples"]["synthetic"],
                    "other_mapping": other_key["samples"]["synthetic"],
                    "row_manifest_equal": key["rows"] == other_key["rows"],
                    "mixed_complete": mixed["complete"],
                    "expected_changed_meaning": {s: good["models"][s]["changed_meaning"] for s in ("a", "b")},
                    "mixed_changed_meaning": {s: mixed["models"][s]["changed_meaning"] for s in ("a", "b")},
                    "saved_mixed_complete": mixed_saved["complete"],
                    "saved_mixed_current": mixed_current,
                    "summary_complete_and_current": mixed_summary["complete"] and mixed_summary["current"],
                },
                "count_identity_not_bound": {
                    "row_id": first_count, "side": counter_side,
                    "before": {k: count_before["models"][counter_side][k] for k in ("missed_both_raters", "missed_other")},
                    "after": {k: count_after["models"][counter_side][k] for k in ("missed_both_raters", "missed_other")},
                    "complete_after_relabel": count_after["complete"],
                },
            },
        }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
