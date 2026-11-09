"""Offline .12 development-example and input-preservation audit; no model calls."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import subprocess
import sys
import types
from pathlib import Path

PHRASES = (
    "much less crowded",
    "do not have cars",
    "cannot afford a car",
    "a steady climb",
    "forty passengers",
    "full bus",
    "Country B",
    "Country A",
    "lion's share",
    "public transport",
    "roads where necessary",
    "in both years",
    "only assertions",
    "touched on",
    "old people",
    "elderly",
    "carbon emissions",
    "everybody",
    "transported by",
)


def grams(text: str, length: int = 5) -> set[str]:
    words = re.findall(r"[A-Za-z]+(?:'[A-Za-z]+)?", text.lower())
    return {" ".join(words[i : i + length]) for i in range(len(words) - length + 1)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline", default="fba35562")
    args = parser.parse_args()
    repo = args.repo.resolve()
    sys.path.insert(0, str(repo))
    sys.dont_write_bytecode = True

    def offline(event, _args):
        if event in {"socket.connect", "socket.bind", "socket.getaddrinfo"}:
            raise RuntimeError("Exposure audit forbids network")

    sys.addaudithook(offline)
    from tools.ielts_writing_ai import essay, prompts, samples

    def git(*arguments):
        return subprocess.check_output(["git", *arguments], cwd=repo, text=True).strip()

    before = types.ModuleType("tools.ielts_writing_ai._exposure_baseline")
    before.__package__ = "tools.ielts_writing_ai"
    baseline_source = git("show", f"{args.baseline}:tools/ielts_writing_ai/prompts.py")
    exec(compile(baseline_source, "<baseline prompts>", "exec"), before.__dict__)
    checks, observations = [], []

    def check(name, value):
        checks.append({"name": name, "passed": bool(value)})

    check("seven_development_samples", len(samples.SAMPLES) == 7)
    check("nineteen_predeclared_phrases", len(PHRASES) == 19)
    check(
        "samples_unchanged",
        git("rev-parse", f"{args.baseline}:tools/ielts_writing_ai/samples.py")
        == git("rev-parse", "HEAD:tools/ielts_writing_ai/samples.py"),
    )
    fixture_paths = git("ls-files", "tools/ielts_writing_ai/tests/fixtures").splitlines()
    old_fixture_paths = git(
        "ls-tree", "-r", "--name-only", args.baseline, "tools/ielts_writing_ai/tests/fixtures"
    ).splitlines()
    check("all_eight_historical_fixtures_retained", len(fixture_paths) == 8)
    check("fixture_path_set_unchanged", fixture_paths == old_fixture_paths)
    fixture_blobs = []
    for path in fixture_paths:
        old_blob = git("rev-parse", f"{args.baseline}:{path}")
        new_blob = git("rev-parse", f"HEAD:{path}")
        working_blob = git("hash-object", path)
        check("fixture_unchanged." + Path(path).name, old_blob == new_blob == working_blob)
        fixture_blobs.append({"path": path, "blob": new_blob})

    for sample in samples.SAMPLES:
        sid = sample["id"]
        sub = {
            "task_type": sample["task_type"],
            "prompt_text": sample["prompt"],
            "essay_text": sample["essay"],
            "word_count": essay.count_words(sample["essay"]),
            "image_status": "none",
            "target_band": 7.0,
        }
        snapshot = copy.deepcopy(sub)
        sentences = essay.split_sentences(sub["essay_text"])
        for kind, builder in prompts.BUILDERS.items():
            label = sid + "." + kind
            messages, context = builder(sub, sentences)
            previous, previous_context = before.BUILDERS[kind](sub, sentences)
            system, user = messages[0]["content"], messages[1]["content"]
            old_system = previous[0]["content"]
            hits = [phrase for phrase in PHRASES if phrase.lower() in system.lower()]
            old_hits = [phrase for phrase in PHRASES if phrase.lower() in old_system.lower()]
            check("system_examples_removed." + label, not hits)
            check("user_input_unchanged." + label, user == previous[1]["content"])
            check("context_unchanged." + label, context == previous_context)
            payload, _ = json.JSONDecoder().raw_decode(user.partition("\n")[2])
            check("question_retained." + label, payload["question"] == sample["prompt"])
            if kind == "evaluate" and sample["task_type"] == "task2":
                actual = [item["text"] for item in payload["essay_paragraphs"]]
                expected = essay.split_paragraphs(sample["essay"])
            elif kind == "refine":
                actual = payload["sentences"]
                expected = [{"i": sentence.index, "text": sentence.text} for sentence in sentences]
            else:
                actual, expected = payload["essay"], sample["essay"]
            check("essay_retained." + label, actual == expected)
            if kind == "evaluate":
                check("evaluation_rules_changed." + label, system != old_system)
            else:
                check("non_evaluation_messages_unchanged." + label, messages == previous)
            observations.append(
                {
                    "sample": sid,
                    "kind": kind,
                    "baseline_system_phrase_hits": old_hits,
                    "current_system_phrase_hits": hits,
                    "five_word_overlap_with_essay": sorted(grams(system) & grams(sample["essay"])),
                    "system_sha256": hashlib.sha256(system.encode()).hexdigest(),
                    "user_input_sha256": hashlib.sha256(user.encode()).hexdigest(),
                    "limit": "No literal overlap is not proof of semantic independence.",
                }
            )
        current_notes = prompts.build_rewrite_notes(sub, sample["essay"], "offline check")
        previous_notes = before.build_rewrite_notes(sub, sample["essay"], "offline check")
        check("rewrite_notes_unchanged." + sid, current_notes == previous_notes)
        check("input_not_mutated." + sid, sub == snapshot)

    image_sub = {"prompt_text": "Describe this synthetic chart."}
    image_data = "data:image/png;base64,c3ludGhldGlj"
    check(
        "image_builder_unchanged",
        prompts.build_describe_image(image_sub, image_data)
        == before.build_describe_image(image_sub, image_data),
    )
    changed_paths = git("diff", "--name-only", args.baseline, "HEAD", "tools/ielts_writing_ai")
    check(
        "no_runtime_module_changed_except_prompt",
        all(
            path == "tools/ielts_writing_ai/prompts.py"
            or path == "tools/ielts_writing_ai/README.md"
            or path.startswith("tools/ielts_writing_ai/tests/")
            for path in changed_paths.splitlines()
        ),
    )
    report = {
        "head": git("rev-parse", "HEAD"),
        "baseline": git("rev-parse", args.baseline),
        "prompt_version": prompts.PROMPT_VERSION,
        "actual_model_requests": 0,
        "scope": "Published synthetic development samples and code only; no teacher material.",
        "passed": sum(row["passed"] for row in checks),
        "total": len(checks),
        "failed": [row["name"] for row in checks if not row["passed"]],
        "checks": checks,
        "fixture_blobs": fixture_blobs,
        "observations": observations,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({key: report[key] for key in ("passed", "total", "failed")}))
    return int(bool(report["failed"]))


if __name__ == "__main__":
    raise SystemExit(main())
