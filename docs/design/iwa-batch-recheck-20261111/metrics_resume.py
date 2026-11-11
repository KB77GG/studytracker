"""Synthetic Batch.run_group resume probe; no generation, private files or network."""
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.repo))
    from tools.ielts_writing_ai import batch, blindtally

    with tempfile.TemporaryDirectory(prefix="iwa-metrics-resume-") as tmp:
        root = Path(tmp)
        sample = {
            "id": "synthetic", "task_type": "task2",
            "submission": {"essay_text": "A synthetic sentence.", "prompt_text": "Synthetic prompt."},
            "generations": {"evaluate": {"status": "ready", "result": {
                "overall_band": 6,
                "criteria": [{"key": k, "band": 6, "summary": "", "issues": []}
                             for k in ("task", "coherence", "lexical", "grammar")],
                "argument": {"position": {"consistent": True}},
            }}},
        }
        for model in ("flash", "pro"):
            run = root / f"dev-{model}"
            run.mkdir()
            (run / ".done").write_text("synthetic done\n")
            (run / "run_data.json").write_text(json.dumps({
                "samples": [sample], "calls": [], "kinds": ["evaluate"],
                "settings": {"evaluate_thinking": "high"},
            }))
            (run / "report.json").write_text(json.dumps({
                "provider": "demo", "model": f"synthetic-{model}",
                "prompt_version": "synthetic", "code_sha256": "synthetic-code",
                "kinds": {"evaluate": {"max_tokens": [32000]}},
            }))
        runner = batch.Batch(SimpleNamespace(env_file=None, dry=True), "main", root, root, {}, 0)
        row = {"group": batch.STAGES["main"][0], "source": "unused", "worst": 0}
        folder = root / "compare-dev"
        with patch.object(batch.subprocess, "run", side_effect=AssertionError("Must never start generation")) as spawn:
            runner.run_group(row, seed=101)
            lines = []
            for line in (folder / "blind_review.md").read_text().splitlines():
                if line.startswith("|") and not line.startswith("|---"):
                    cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
                    if len(cells) >= 6 and cells[0] != "位置" and cells[4] != "参考":
                        cells[4] = "0" if cells[0] in blindtally.COUNT_ROWS else "正确"
                        cells[5] = "SYNTHETIC_REVIEWER_NOTE"
                        line = "| " + " | ".join(cells) + " |"
                lines.append(line)
            filled_sheet = "\n".join(lines) + "\n"
            (folder / "blind_review.md").write_text(filled_sheet)
            before = blindtally.run(folder)
            tally_bytes = (folder / "blind_tally.json").read_bytes()
            key_bytes = (folder / "blind_key.json").read_bytes()
            runner.run_group(row, seed=101)
            after_sheet = (folder / "blind_review.md").read_text()
            after_key = json.loads((folder / "blind_key.json").read_text())
            recalculated = blindtally.tally(after_sheet, after_key)
            result = {
                "network_calls": 0, "private_inputs_read": False,
                "realcheck_subprocess_calls": spawn.call_count,
                "before_complete": before["complete"],
                "after_sheet_equals_filled": after_sheet == filled_sheet,
                "reviewer_notes_preserved": "SYNTHETIC_REVIEWER_NOTE" in after_sheet,
                "after_sheet_complete_if_recalculated": recalculated["complete"],
                "blind_key_bytes_unchanged_same_seed": (folder / "blind_key.json").read_bytes() == key_bytes,
                "saved_tally_unchanged": (folder / "blind_tally.json").read_bytes() == tally_bytes,
                "saved_tally_still_complete": json.loads((folder / "blind_tally.json").read_text())["complete"],
            }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
