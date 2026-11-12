"""Focused, synthetic-only verification of fixed versus editable blind-sheet columns."""
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
    from tools.ielts_writing_ai import blindtally
    from tools.ielts_writing_ai import realcheck_compare as cmp

    sample = {
        "id": "synthetic-edit", "task_type": "task2",
        "submission": {"essay_text": "Synthetic source sentence."},
        "generations": {"evaluate": {"status": "ready", "result": {
            "overall_band": 6,
            "criteria": [{"key": k, "band": 6, "summary": "", "issues": []}
                         for k in cmp.CRITERIA],
            "argument": {"position": {"consistent": True}},
            "overall_comment": "Synthetic comment.",
        }}},
    }
    view = cmp.sample_view({"calls": []}, sample)
    sheet, key = cmp.render_blind_review({"samples": [{"a": view, "b": copy.deepcopy(view)}]}, seed=8)
    lines = []
    for line in sheet.splitlines():
        if line.startswith("|") and not line.startswith("|---"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if len(cells) >= 7 and cells[0] != "编号":
                cells[5] = "0" if cells[1] in cmp.COUNT_ROWS else "正确"
                cells[6] = "Synthetic reviewer note，人工备注。"
                line = "| " + " | ".join(cells) + " |"
        lines.append(line)
    filled = "\n".join(lines) + "\n"
    first_id = next(r["id"] for r in key["rows"] if r["kind"] == "judged")

    def edited(column, value):
        out = []
        for line in filled.splitlines():
            if line.startswith(f"| {first_id} |"):
                cells = [c.strip() for c in line.strip().strip("|").split("|")]
                cells[column] = value
                line = "| " + " | ".join(cells) + " |"
            out.append(line)
        return "\n".join(out) + "\n"

    checks = {"judgments_and_remarks_accepted": blindtally.tally(filled, key)["complete"]}
    for column, label in enumerate(("id", "position", "quote", "explanation", "suggestion")):
        checks[f"changed_fixed_{label}_rejected"] = not blindtally.tally(
            edited(column, "SYNTHETIC_CHANGED"), key)["complete"]
    revised_verdict = edited(5, "① 误读原文")
    verdict_tally = blindtally.tally(revised_verdict, key)
    checks["changed_valid_verdict_accepted"] = verdict_tally["complete"]
    checks["changed_valid_verdict_counted_once"] = sum(
        model["misread"] for model in verdict_tally["models"].values()) == 1
    revised_remark = edited(6, "Another synthetic review note，备注可以改。")
    notes_tally = blindtally.tally(revised_remark, key)
    checks["remarks_do_not_change_counts"] = (
        notes_tally["complete"]
        and notes_tally["models"] == blindtally.tally(filled, key)["models"])

    with tempfile.TemporaryDirectory(prefix="iwa-fixed-columns-") as tmp:
        folder = Path(tmp)
        (folder / "blind_key.json").write_text(json.dumps(key, ensure_ascii=False))
        (folder / "blind_review.md").write_text(filled)
        first = blindtally.run(folder)
        checks["initial_tally_current"] = first["complete"] and blindtally.current(folder)
        (folder / "blind_review.md").write_text(revised_verdict)
        checks["valid_verdict_edit_stales_old_tally"] = not blindtally.current(folder)
        updated = blindtally.run(folder)
        checks["retally_valid_edit_complete_and_current"] = updated["complete"] and blindtally.current(folder)
        (folder / "blind_review.md").write_text(revised_remark)
        checks["remark_edit_stales_old_tally"] = not blindtally.current(folder)

    result = {"network_calls": 0, "private_inputs_read": False, "checks": checks,
              "passed_checks": sum(checks.values()), "total_checks": len(checks),
              "passed": all(checks.values())}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
