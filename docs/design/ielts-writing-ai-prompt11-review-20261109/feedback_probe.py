"""Offline inspection of .11 evaluation instructions; never calls an LLM.

An exit code of 1 means a contradictory instruction was reproduced, not a model
failure. Word overlap is reported as development-set exposure, not as proof of
causal overfitting or a semantic quality score.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import types
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--baseline", default="436ad2f2")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    repo = args.repo.resolve()
    sys.path.insert(0, str(repo))
    from tools.ielts_writing_ai import essay, prompts, samples

    before = types.ModuleType("tools.ielts_writing_ai._feedback_baseline")
    before.__package__ = "tools.ielts_writing_ai"
    source = subprocess.check_output(
        ["git", "show", f"{args.baseline}:tools/ielts_writing_ai/prompts.py"],
        cwd=repo,
        text=True,
    )
    exec(compile(source, "<baseline prompts.py>", "exec"), before.__dict__)
    checks = []

    def check(name: str, passed: bool) -> None:
        checks.append({"name": name, "passed": bool(passed)})

    snippets = {
        "blanket_exclusion": (
            "task relevance and argument quality belong to Task Response and are never "
            "a reason for a Coherence, Lexical or Grammar band"
        ),
        "argument_explains_cc": (
            "a diagnosis that explains Task Response and Coherence & Cohesion"
        ),
        "argument_reflects_cc": ("Reflect real problems in the task and coherence summaries"),
    }
    general_rules = [
        "an off-topic essay can still use varied, accurate grammar",
        "Language feedback has three kinds",
        "Accurate, neutral everyday wording is neither an error nor impolite",
        "optional, is not an issue, and if mentioned must be called optional",
        "check that it does not already use one",
        "Call development brief when a point is explained briefly",
        "say it is not explained only when no reason or example is given at all",
        "never invent one to fill the list",
    ]
    new_run_phrases = ["old people", "elderly", "carbon emissions", "everybody", "transported by"]
    known_exposure = [
        "much less crowded",
        "cannot afford a car",
        "a bus carrying forty passengers",
        "the figure for Country B",
        "the lion's share of funding",
        "mostly public transport, but roads where necessary",
    ]
    contexts = []
    for sample in samples.SAMPLES:
        submission = {
            "task_type": sample["task_type"],
            "prompt_text": sample["prompt"],
            "essay_text": sample["essay"],
            "word_count": essay.count_words(sample["essay"]),
            "image_status": "none",
            "target_band": 7,
        }
        sentences = essay.split_sentences(sample["essay"])
        current = prompts.build_evaluate(submission, sentences)[0][0]["content"]
        old = before.build_evaluate(submission, sentences)[0][0]["content"]
        conflict = all(fragment in current for fragment in snippets.values())
        old_conflict = all(fragment in old for fragment in snippets.values())
        if sample["task_type"] == "task2":
            check(sample["id"] + ".no_conflicting_cc_rules", not conflict)
            check(sample["id"] + ".baseline_has_no_same_conflict", not old_conflict)
        for number, rule in enumerate(general_rules, 1):
            check(sample["id"] + f".general_rule_{number}", rule in current)
        for phrase in new_run_phrases:
            check(sample["id"] + ".new_rule_no_literal_" + phrase, phrase not in current)
        contexts.append(
            {
                "sample_id": sample["id"],
                "task_type": sample["task_type"],
                "cc_conflict": conflict,
                "baseline_cc_conflict": old_conflict,
                "known_development_examples_in_system": [
                    phrase for phrase in known_exposure if phrase in current
                ],
            }
        )
    exposure = []
    for phrase in known_exposure:
        originals = [s["id"] for s in samples.SAMPLES if phrase in s["essay"]]
        fixtures = [
            str(path.relative_to(repo))
            for path in sorted((repo / "tools/ielts_writing_ai/tests/fixtures").glob("*.json"))
            if phrase in path.read_text(encoding="utf-8")
        ]
        exposure.append(
            {
                "phrase": phrase,
                "exact_original_matches": originals,
                "fixture_files_with_exact_text": fixtures,
                "interpretation": (
                    "original phrase"
                    if originals
                    else "prior feedback or topic-specific example; not an exact original phrase"
                ),
            }
        )
    result = {
        "repo": str(repo),
        "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip(),
        "baseline": args.baseline,
        "prompt_version": prompts.PROMPT_VERSION,
        "actual_model_requests": 0,
        "total_checks": len(checks),
        "passed": sum(row["passed"] for row in checks),
        "checks": checks,
        "contexts": contexts,
        "findings": [
            {
                "id": "P2-CC-contradictory-instructions",
                "source": "tools/ielts_writing_ai/prompts.py:260-263;38-39;81-82",
                "evidence": snippets,
                "reproduced": any(row["cc_conflict"] for row in contexts),
                "introduced_since_baseline": not any(
                    row["baseline_cc_conflict"] for row in contexts
                ),
                "limit": "Contradictory generated instructions only; no claim about actual model score changes.",
            }
        ],
        "sample_exposure": exposure,
        "limits": [
            "Presence tests prove instructions are emitted, not that the model obeys them.",
            "The seven repeatedly reviewed samples are a development/regression set.",
            "Removing their literal phrases cannot retroactively make that set independent.",
            "No API, private reasoning, credentials or student materials were read.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                key: result[key]
                for key in (
                    "head",
                    "prompt_version",
                    "actual_model_requests",
                    "total_checks",
                    "passed",
                    "findings",
                )
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if all(row["passed"] for row in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
