"""Export counts only after completed, bound blind judgments. Never export fixed text."""

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

repo = Path("/private/tmp/studytracker-iwa-holdout-review-20261111")
sys.path.insert(0, str(repo))
from tools.ielts_writing_ai import blindtally

base = Path("/Users/zhouxin/iwa-compare-real-20261112")
summary = json.loads((base / "summary.json").read_text())
out = {}
fields = list(blindtally.LABELS)
for group in ["teacher", "rated_t2", "lowband"]:
    folder = base / f"compare-{group}"
    if not blindtally.current(folder):
        raise SystemExit("Stale tally " + group)
    tally = json.loads((folder / "blind_tally.json").read_text())
    if not tally["complete"]:
        raise SystemExit("Incomplete tally " + group)
    key = json.loads((folder / "blind_key.json").read_text())
    manifest = {r["id"]: r for r in key["rows"]}
    counts = defaultdict(
        lambda: {"flash": Counter({k: 0 for k in fields}), "pro": Counter({k: 0 for k in fields})}
    )
    for cells in blindtally._sheet_rows((folder / "blind_review.md").read_text()):
        row = manifest[cells[0]]
        if "#r" in row["sample"] or row["kind"] == "context":
            continue
        side = key["samples"][row["sample"]][row["side"]]
        model = key["conditions"][side]["model"]
        m = "flash" if model == "deepseek-flash" else "pro"
        metric = row["category"] if row["kind"] == "count" else blindtally.verdict_key(cells[5])
        counts[row["sample"]][m][metric] += int(cells[5]) if row["kind"] == "count" else 1
    status = {
        m: {
            s["id"]: s["statuses"].get("evaluate") == "ready"
            for s in summary["groups"][group]["runs"][m]["final"]["per_sample"]
        }
        for m in ["flash", "pro"]
    }
    for sid, row in counts.items():
        for m in ["flash", "pro"]:
            row[m]["evaluation_ready"] = status[m].get(sid, False)
            row[m]["false_positive_123"] = sum(
                row[m][k] for k in ["misread", "changed_meaning", "polish_as_error"]
            )
            row[m]["judgment_errors_1234"] = (
                row[m]["false_positive_123"] + row[m]["missed_both_raters"]
            )
    common = [
        sid for sid in counts if all(counts[sid][m]["evaluation_ready"] for m in ["flash", "pro"])
    ]

    def aggregate(ids, counts=counts):
        return {
            m: {
                k: sum(counts[s][m][k] for s in ids)
                for k in fields + ["false_positive_123", "judgment_errors_1234"]
            }
            for m in ["flash", "pro"]
        }

    all_totals = aggregate(counts)
    for side in ["a", "b"]:
        m = "flash" if key["conditions"][side]["model"] == "deepseek-flash" else "pro"
        if any(all_totals[m][k] != tally["models"][side][k] for k in fields):
            raise SystemExit("Tally mismatch")
    out[group] = {
        "unique_essays": len(counts),
        "per_sample": counts,
        "all_first_attempts": all_totals,
        "common_successful_essays": len(common),
        "common_successful_counts": aggregate(common),
    }
print(
    json.dumps(
        {
            "method": "First-pass AI blind review; only first independent run; uncertain separate; count category 4 means verified supplied reference list, not proven dual-rater consensus.",
            "groups": out,
        },
        ensure_ascii=False,
        indent=2,
    )
)
