"""Offline .12 boundary recheck; public synthetic samples only, no model calls."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import subprocess
import sys
import types
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline", default="fba35562")
    args = parser.parse_args()
    repo = args.repo.resolve()
    sys.path.insert(0, str(repo))
    sys.dont_write_bytecode = True

    def no_network(event, _args):
        if event in {"socket.connect", "socket.bind", "socket.getaddrinfo"}:
            raise RuntimeError("Offline boundary probe forbids network")

    sys.addaudithook(no_network)
    from tools.ielts_writing_ai import essay, prompts, samples

    def git(*argv):
        return subprocess.check_output(["git", *argv], cwd=repo, text=True)

    old = types.ModuleType("tools.ielts_writing_ai._boundary_baseline")
    old.__package__ = "tools.ielts_writing_ai"
    baseline_text = git("show", f"{args.baseline}:tools/ielts_writing_ai/prompts.py")
    exec(compile(baseline_text, "<baseline prompt>", "exec"), old.__dict__)
    checks = []

    def check(name, passed):
        checks.append({"name": name, "passed": bool(passed)})

    cases = []
    for sample in samples.SAMPLES:
        cases.append(
            (
                sample["id"],
                {
                    "task_type": sample["task_type"],
                    "prompt_text": sample["prompt"],
                    "essay_text": sample["essay"],
                    "word_count": essay.count_words(sample["essay"]),
                    "image_status": "none",
                    "target_band": 7.0,
                },
            )
        )
    pictured = copy.deepcopy(cases[-1][1])
    assert pictured["task_type"] == "task1"
    pictured.update(image_status="ready", image_description="Synthetic readable chart.")
    cases.append(("task1-ready-control", pictured))

    banned = (
        "task relevance and argument quality belong to Task Response",
        "never a reason for a Coherence",
        "Reflect real problems in the task and coherence summaries",
        "a diagnosis that explains Task Response and Coherence & Cohesion",
    )
    general = (
        "optional, is not an issue",
        "never add facts, causes, figures, multipliers or trends",
        "check that it does not already use one",
        "Call development brief when a point is explained briefly",
        "criterion may have no issues at all",
        "never invent one to fill the list",
    )
    observations = []
    for name, sub in cases:
        before = copy.deepcopy(sub)
        sentences = essay.split_sentences(sub["essay_text"])
        current, context = prompts.build_evaluate(sub, sentences)
        previous, prior_context = old.build_evaluate(sub, sentences)
        system = current[0]["content"]
        check(f"{name}.input_unmodified", sub == before)
        check(f"{name}.user_message_unchanged", current[1] == previous[1])
        check(f"{name}.context_unchanged", context == prior_context)
        check(
            f"{name}.correct_task_boundary",
            prompts.CRITERION_BOUNDARIES[sub["task_type"]] in system,
        )
        check(f"{name}.one_boundary", system.count("Criterion boundaries:") == 1)
        check(f"{name}.language_evidence", prompts.LANGUAGE_BOUNDARY in system)
        check(
            f"{name}.cc_positive_features",
            "logical progression, paragraphing, cohesive links and referencing under Coherence & Cohesion"
            in system,
        )
        for index, text in enumerate(banned):
            check(f"{name}.old_conflict_absent.{index}", text not in system)
        for index, text in enumerate(general):
            check(f"{name}.generic_feedback_preserved.{index}", text in system)
        if sub["task_type"] == "task2":
            check(
                f"{name}.tr_features",
                "development and support of ideas under Task Response" in system,
            )
            check(
                f"{name}.per_finding_mapping",
                "whichever each one evidences" in system
                and "in the summary of the criterion it evidences" in system,
            )
            check(
                f"{name}.no_mechanical_duplication",
                "without repeating the same finding mechanically in both" in system,
            )
            check(f"{name}.no_ta_boundary", prompts.CRITERION_BOUNDARIES["task1"] not in system)
            check(f"{name}.baseline_conflict_present", banned[0] in previous[0]["content"])
        else:
            check(
                f"{name}.ta_features",
                "overview, the selection and accuracy of key features and data under Task Achievement"
                in system,
            )
            check(f"{name}.no_argument_check", "Argument check (Task 2)" not in system)
            check(f"{name}.no_tr_boundary", prompts.CRITERION_BOUNDARIES["task2"] not in system)
            check(
                f"{name}.visual_guard",
                ("Task Achievement CANNOT be assessed" in system)
                == (sub["image_status"] != "ready"),
            )
        for kind in ("refine", "rewrite"):
            check(
                f"{name}.{kind}_unchanged",
                getattr(prompts, "build_" + kind)(sub, sentences)
                == getattr(old, "build_" + kind)(sub, sentences),
            )
        observations.append(
            {
                "sample": name,
                "task": sub["task_type"],
                "system_sha256": hashlib.sha256(system.encode()).hexdigest(),
            }
        )

    for task, visual in (("task2", True), ("task1", True), ("task1", False)):
        check(
            f"schema_unchanged.{task}.{visual}",
            prompts.evaluate_example(task, visual) == old.evaluate_example(task, visual),
        )
    for name in ("llm.py", "review.py", "argument.py", "jsonshape.py", "config.py", "samples.py"):
        path = "tools/ielts_writing_ai/" + name
        check(
            f"runtime_unchanged.{name}",
            git("show", f"{args.baseline}:{path}") == (repo / path).read_text(),
        )

    failed = [item["name"] for item in checks if not item["passed"]]
    output = {
        "head": git("rev-parse", "HEAD").strip(),
        "baseline": args.baseline,
        "prompt_version": prompts.PROMPT_VERSION,
        "real_model_requests": 0,
        "passed": len(checks) - len(failed),
        "total": len(checks),
        "failed": failed,
        "findings": [],
        "observations": observations,
        "checks": checks,
        "limit": "Prompt construction and unchanged runtime only; not evidence of real model grading accuracy.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {key: output[key] for key in ("passed", "total", "failed", "real_model_requests")},
            ensure_ascii=False,
        )
    )
    return int(bool(failed))


if __name__ == "__main__":
    raise SystemExit(main())
