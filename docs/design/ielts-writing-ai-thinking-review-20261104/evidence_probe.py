#!/usr/bin/env python3
"""Independent offline checks; imports pure normalizers only, never reads config/keys.

Historical real outputs are immutable inputs. Support fields and the fallback case
are explicitly synthetic mutations, not claims about a new real model response.

Usage: python evidence_probe.py --repo /path/to/checkout --output /path/to/result.json
"""
import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--repo", required=True, type=Path, help="Feature checkout to review")
parser.add_argument("--output", required=True, type=Path, help="Write the offline evidence JSON here")
args = parser.parse_args()
REPO = args.repo.resolve()
OUT = args.output.resolve()
sys.path.insert(0, str(REPO))
from tools.ielts_writing_ai import argument, copytext, essay, figures, review
from tools.ielts_writing_ai.llm import parse_strict_json

fixture_path = REPO / "tools/ielts_writing_ai/tests/fixtures/realcheck_20261104d.json"
fx = json.loads(fixture_path.read_text())
historical = REPO / "docs/design/ielts-writing-ai-figures-recheck-20261104"
raw_calls = [json.loads(line) for line in (historical / "raw_calls.jsonl").read_text().splitlines()]
old_run = json.loads((historical / "run_data.json").read_text())
checks = []


def check(name, ok, evidence=None):
    checks.append({"name": name, "passed": bool(ok), "evidence": evidence})
    assert ok, name


def raw(sid):
    return parse_strict_json(fx["evaluation_attempts"][sid][0])


def normalized(sid, data=None):
    return review.normalize_evaluation(raw(sid) if data is None else data, fx["submissions"][sid])


raw_by_sample = {c["sample"]: c for c in raw_calls}
old_samples = {s["id"]: s for s in old_run["samples"]}
check("fixture_has_exactly_seven_real_outputs", len(raw_by_sample) == len(fx["evaluation_attempts"]) == 7)
for sid, attempts in fx["evaluation_attempts"].items():
    record = raw_by_sample[sid]
    check(f"fixture_raw_authentic:{sid}", attempts == [record["text"]] and record["ok"] and record["http_status"] == 200,
          {"sha256": hashlib.sha256(attempts[0].encode()).hexdigest(), "old_prompt": old_run["settings"].get("prompt_version")})
    check(f"fixture_original_essay_prompt:{sid}", all(fx["submissions"][sid][k] == old_samples[sid]["submission"][k]
          for k in ("essay_text", "prompt_text", "task_type")))

results = {sid: normalized(sid) for sid in fx["submissions"]}
under = raw("t2-under-length")
targets = [i["suggestion"] for i in under["criteria"]["task"]["issues"]] + under["priorities"]
targets = [t for t in targets if "260" in t]
under_text = copytext.evaluation_text(results["t2-under-length"], {})
check("both_real_260_targets_visible_in_copy", len(targets) == 2 and all(t in under_text for t in targets), targets)
check("real_batch_removes_no_advice_after_target_fix", all(r["suggestions_removed"]["total"] == 0 for r in results.values()))

numeric_cases = [
    ("No numbers.", "扩写到260词以上", []),
    ("No numbers.", "全文扩写到260-300 words", []),
    ("No numbers.", "字数达到260以上", []),
    ("No numbers.", "增加260次班车", ["260"]),
    ("No numbers.", "减少百分之8", ["百分之8"]),
    ("No numbers.", "减少百分之八十", ["百分之八十"]),
    ("Percentage is 80%.", "减少百分之八十", []),
    ("降低百分之八十一", "减少百分之八十", ["百分之八十"]),
    ("Percentage is 81%.", "减少百分之八十一", []),
    ("The year was 1980.", "减少80%", ["80%"]),
    ("There are 180 buses.", "减少80%", ["80%"]),
]
for index, (source, advice, expected) in enumerate(numeric_cases):
    actual = figures.Sources(source).unsourced(advice)
    check(f"numeric_control:{index}", actual == expected, {"source": source, "advice": advice, "unsourced": actual})

contexts = {
    "t2-weak": ("So goverment should make it cheap and more fast.",
                "If the bus is more better, people will use it more and the traffic will be less."),
    "t2-mid": ("For example, after my city opened a new metro line, the main road to the city centre became much less crowded during rush hour.",
               "If buses and trains are frequent, cheap and reliable, many drivers will choose them, which will reduce traffic jams."),
    "t2-under-length": ("However, new roads are still useful in the countryside, where there are not many buses.",
                       "where there are not many buses"),
}
for sid, (quote, support) in contexts.items():
    data = raw(sid)
    item = next(p for p in data["argument"]["problems"] if p["quote"].startswith(quote[:40]))
    item["support_found"] = [support]
    out = normalized(sid, data)
    mapped = out["argument"]
    moved = mapped["improvements"][0]
    check(f"injected_valid_support_reclassified:{sid}", mapped["reclassified"] == 1 and
          len(mapped["problems"]) == len(results[sid]["argument"]["problems"]) - 1 and
          moved["support"] == [support] and moved["from_type"] == item["type"], moved)
    check(f"support_copy_provenance:{sid}", f'原判“{argument.PROBLEM_TYPES[item["type"]]}”，同段已有' in copytext.evaluation_text(out, {}))
    check(f"counts_conserved:{sid}", mapped["returned"] == sum(mapped[k] for k in ("kept", "dropped", "duplicates", "over_limit")))

quote, support = contexts["t2-weak"]
for label, invalid in (
    ("same_quote", [quote]),
    ("invented", ["Every bus is always on time."]),
    ("different_paragraph", ["In conclusion, I think goverment should spend more money for public transport"]),
    ("wrong_type", {"quote": support}),
):
    data = raw("t2-weak")
    item = next(p for p in data["argument"]["problems"] if p["quote"].startswith(quote[:40]))
    item["support_found"] = invalid
    check(f"bad_support_not_reclassified:{label}", normalized("t2-weak", data)["argument"]["reclassified"] == 0)

t1 = results["t1-no-image"]
t1essay = fx["submissions"]["t1-no-image"]["essay_text"]
t1copy = copytext.evaluation_text(t1, {})
check("task1_actual_counts", len(essay.split_paragraphs(t1essay)) == 5 and len(re.findall(r"\bfigure\b", t1essay, re.I)) == 1)
check("task1_two_corrections_visible", len(t1["count_corrections"]) == 2 and all(n in t1["warnings"] and n in t1copy for n in t1["count_corrections"]), t1["count_corrections"])
check("task1_ac_contradiction_preserved", len(t1["consistency_issues"]) == 1, t1["consistency_issues"])
check("task1_no_image_not_assessable", t1["overall_band"] is None and t1["criteria"][0]["band"] is None)
check("task2_no_spurious_corrections", all(not r["count_corrections"] for sid, r in results.items() if sid.startswith("t2")))

# New edge on a new path: a filtered suggestion is replaced by an unfiltered
# comment, and that comment is now displayed as an optional suggestion.
data = raw("t2-weak")
item = next(p for p in data["argument"]["problems"] if p["quote"].startswith(quote[:40]))
item.update({
    "support_found": [support],
    "comment": "论证仍可补充更具体的数据，例如公交能减少80%的排放，使观点更加有力。",
    "suggestion": "增加公交能减少80%排放的数据作为支撑。",
})
out = normalized("t2-weak", data)
moved = out["argument"]["improvements"][0]
copy_output = copytext.evaluation_text(out, {})
fallback_bug = bool(out["suggestions_removed"]["argument"] == 1 and
                    "80%" in moved["suggestion"] and moved["suggestion"] in copy_output and
                    figures.for_submission(fx["submissions"]["t2-weak"]).unsourced(moved["suggestion"]))

fallback_controls = []
for bad_comment, bad_suggestion in ((True, True), (False, True), (True, False), (False, False)):
    controlled = raw("t2-weak")
    controlled_item = next(p for p in controlled["argument"]["problems"] if p["quote"].startswith(quote[:40]))
    controlled_item.update({
        "support_found": [support],
        "comment": item["comment"] if bad_comment else "同段已有理由，可以进一步说明成本如何影响乘客的出行选择。",
        "suggestion": item["suggestion"] if bad_suggestion else "进一步说明票价如何影响乘客的出行选择。",
    })
    controlled_out = normalized("t2-weak", controlled)
    controlled_moved = controlled_out["argument"]["improvements"][0]
    controlled_copy = copytext.evaluation_text(controlled_out, {})
    has_80 = "80%" in controlled_copy
    check(f"fallback_control:comment_{bad_comment}_suggestion_{bad_suggestion}",
          controlled_out["argument"]["reclassified"] == 1 and
          controlled_out["suggestions_removed"]["argument"] == int(bad_suggestion) and
          has_80 == (bad_comment and bad_suggestion))
    fallback_controls.append({
        "comment_has_80": bad_comment, "suggestion_has_80": bad_suggestion,
        "same_verified_support": support,
        "normalized_suggestion": controlled_moved["suggestion"],
        "suggestions_removed": controlled_out["suggestions_removed"],
        "80_percent_in_evaluation_copy": has_80,
    })

report = {
    "repo": str(REPO),
    "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=REPO, text=True).strip(),
    "scope": "Offline normalizers only. No credentials, config, network, model call, or business edits.",
    "checks": checks,
    "passed_checks": len(checks),
    "new_defects": [{
        "id": "reclassified_comment_fallback_bypasses_suggestion_filter",
        "reproduced": fallback_bug,
        "severity_suggestion": "P2",
        "source": "tools/ielts_writing_ai/argument.py:233",
        "synthetic_mutation": item,
        "normalized_improvement": moved,
        "removed_metrics": out["suggestions_removed"],
        "unsourced_advice_reappears_in_copy": fallback_bug,
        "controls": fallback_controls,
        "explanation": "The primary suggestion is correctly removed, then suggestion or comment places the unfiltered comment back in the suggestion field. UI and copy render that field as advice despite the removal warning.",
    }],
    "limits": [
        "Historical raw outputs are byte-identical to all seven local real responses, but use prompt .5; they do not establish live .6 behavior.",
        "support_found cases are explicitly offline mutations. Same-paragraph presence establishes provenance, not logical support.",
        "Count corrections append warnings; they intentionally do not rewrite model comments or recalculate scores.",
        "No independent expert scores or comprehensive semantic-quality pass are asserted.",
    ],
}
OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"passed_checks": len(checks), "fallback_defect_reproduced": fallback_bug, "report": str(OUT)}, ensure_ascii=False))
