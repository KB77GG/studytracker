"""Offline .11 structure review. Reads public synthetic fixtures; never calls a model."""

from __future__ import annotations

import argparse
import copy
import json
import random
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo", type=Path, required=True)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--baseline", default="436ad2f2")
    args = ap.parse_args()
    repo = args.repo.resolve()
    sys.path.insert(0, str(repo))
    sys.dont_write_bytecode = True

    def deny_network(event, _args):
        if event in {"socket.connect", "socket.bind"}:
            raise RuntimeError("This probe is pure offline: sockets forbidden")

    sys.addaudithook(deny_network)
    from tools.ielts_writing_ai import essay, prompts, review
    from tools.ielts_writing_ai.llm import LLMResult, parse_strict_json

    checks = []

    def check(name, passed, detail=None):
        checks.append({"name": name, "passed": bool(passed), "detail": detail})

    def git(*argv):
        return subprocess.check_output(["git", *argv], cwd=repo, text=True)

    fixtures = repo / "tools/ielts_writing_ai/tests/fixtures"
    fx = json.loads((fixtures / "realcheck_20261109_prompt10.json").read_text())
    calls = [
        json.loads(line)
        for line in (repo / "docs/design/ielts-writing-ai-prompt10-high-20261109/raw_calls.jsonl")
        .read_text()
        .splitlines()
    ]
    for index, row in enumerate(calls):
        fixture_text = fx["attempts"][row["sample"]][row["attempt"]]["text"]
        check(f"fixture_matches_public_response.{index + 1}", row["text"] == fixture_text)

    for rel in ("llm.py", "review.py", "jsonshape.py", "argument.py", "visual.py", "config.py"):
        path = "tools/ielts_writing_ai/" + rel
        check(
            f"runtime_unchanged.{rel}",
            git("show", f"{args.baseline}:{path}") == (repo / path).read_text(),
        )

    for task, visual, sample in (
        ("task2", True, "t2-weak"),
        ("task1", False, "t1-no-image"),
        ("task1", True, "t1-no-image"),
    ):
        label = f"{task}.{visual}"
        example = prompts.evaluate_example(task, visual)
        encoded = json.dumps(example, ensure_ascii=False)
        check(f"schema.parseable.{label}", parse_strict_json(encoded) == example)
        check(
            f"schema.correct_roots.{label}",
            set(example)
            == {
                "criteria",
                "argument" if task == "task2" else "comparisons",
                "overall_comment",
                "priorities",
            },
        )
        for criterion in essay.CRITERIA:
            value = example["criteria"][criterion]
            check(
                f"schema.criterion_order.{label}.{criterion}",
                value is None
                and criterion == "task"
                and not visual
                or isinstance(value, dict)
                and list(value) == ["band", "strengths", "issues", "summary"],
            )
        max_run = max(len(m.group()) for m in re.finditer(r"[\]}]+", re.sub(r"\s+", "", encoded)))
        check(f"schema.max_closing_run.{label}", max_run <= 2, max_run)
        if task == "task2":
            check(
                f"schema.argument_order.{label}",
                list(example["argument"]) == ["paragraphs", "problems", "improvements", "position"],
            )
        sub = copy.deepcopy(fx["submissions"][sample])
        if task == "task1" and visual:
            sub.update(image_status="ready", image_description="A synthetic chart description.")
        messages, _ = prompts.build_evaluate(sub, essay.split_sentences(sub["essay_text"]))
        check(
            f"schema.example_is_actual_prompt.{label}", messages[0]["content"].count(encoded) == 1
        )
        for replaced_band in (False, True):
            candidate = copy.deepcopy(example)
            if replaced_band:
                for criterion in candidate["criteria"].values():
                    if criterion is not None:
                        criterion["band"] = 6.0
            rejected = False
            try:
                review.normalize_evaluation(candidate, sub)
            except review.InvalidOutput:
                rejected = True
            check(f"schema.copied_placeholder_rejected.{label}.{replaced_band}", rejected)

    valid = next(row["text"] for row in calls if row["sample"] == "t2-weak")
    for label, text, accepted in (
        ("plain", valid, True),
        ("one_fence", "```json\n" + valid + "\n```", True),
        ("whitespace", " \n" + valid + "\t", True),
        ("prose_prefix", "无法完整评价，以下仅为示例。" + valid, False),
        ("prose_suffix", valid + "仅为示例。", False),
        ("two_objects", valid + valid, False),
        ("two_fences", "```json\n" + valid + "\n```\n```json\n{}\n```", False),
        ("bare_list", "[" + valid + "]", False),
        ("missing_brace", valid[:-1], False),
    ):
        check(f"strict.{label}", (parse_strict_json(text) is not None) == accepted)

    def shuffled(value, rng):
        if isinstance(value, dict):
            keys = list(value)
            rng.shuffle(keys)
            return {key: shuffled(value[key], rng) for key in keys}
        if isinstance(value, list):
            return [shuffled(item, rng) for item in value]
        return value

    usable = []
    for sample, attempts in fx["attempts"].items():
        raw = parse_strict_json(attempts[-1]["text"])
        if raw is None:
            continue
        usable.append(sample)
        sub = fx["submissions"][sample]
        expected = review.normalize_evaluation(raw, sub)
        for seed in range(8):
            check(
                f"key_order_equivalent.{sample}.{seed}",
                review.normalize_evaluation(shuffled(raw, random.Random(seed)), sub) == expected,
            )
        flat = {**raw["criteria"], **{k: v for k, v in raw.items() if k != "criteria"}}
        check(
            f"legacy_flat_equivalent.{sample}", review.normalize_evaluation(flat, sub) == expected
        )
    check("all_six_usable_replies_including_task1_reordered", len(usable) == 6, usable)

    mid = fx["attempts"]["t2-mid"]
    for index, attempt in enumerate(mid):
        text = attempt["text"]
        check(f"mid.original_rejected.{index + 1}", parse_strict_json(text) is None)
        reason = review.json_problem("evaluate", text, fx["submissions"]["t2-mid"])
        check(
            f"mid.diagnosis.{index + 1}",
            "overall_comment、priorities 被写进了 argument 里面" in reason,
            reason,
        )
        # Diagnostic copy only: proving a single brace at this exact boundary repairs
        # syntax. The original response is never repaired or adopted in the pipeline.
        needle = '"}], "overall_comment"'
        check(f"mid.exact_single_gap.{index + 1}", text.count(needle) == 1)
        diagnostic_copy = text.replace(needle, '"}]}, "overall_comment"', 1)
        repaired = parse_strict_json(diagnostic_copy)
        check(
            f"mid.one_brace_explains_syntax.{index + 1}",
            repaired is not None
            and "overall_comment" in repaired
            and "overall_comment" not in repaired["argument"],
        )

    class Fake:
        provider = model = "offline-stub"

        def __init__(self, texts):
            self.texts = list(texts)
            self.calls = []

        def complete(self, messages, **kwargs):
            self.calls.append((copy.deepcopy(messages), kwargs))
            return LLMResult(self.texts.pop(0), self.model, 1, {})

    settings = SimpleNamespace(
        evaluate_thinking="high",
        evaluate_thinking_timeout=300,
        evaluate_thinking_max_tokens=32000,
        llm_temperature=0.2,
    )
    client = Fake([attempt["text"] for attempt in mid])
    generator = review.Generator(None, settings, client)
    sub = fx["submissions"]["t2-mid"]
    rejected = False
    try:
        generator._generate_valid("evaluate", sub, essay.split_sentences(sub["essay_text"]))
    except review.InvalidOutput:
        rejected = True
    check("pipeline.two_invalid_mid_never_scored", rejected)
    check("pipeline.exactly_two_attempts", len(client.calls) == 2)
    check(
        "pipeline.retry_receives_exact_diagnosis",
        "argument 写完后少了一个 }" in client.calls[1][0][-1]["content"],
    )
    for index, (_messages, options) in enumerate(client.calls):
        check(
            f"pipeline.high_limits.{index + 1}",
            (options["thinking"], options["max_tokens"], options["timeout"], options["json_mode"])
            == ("high", 32000, 300, True),
        )
    client = Fake([mid[0]["text"], valid])
    sub = fx["submissions"]["t2-weak"]
    result, _ = review.Generator(None, settings, client)._generate_valid(
        "evaluate", sub, essay.split_sentences(sub["essay_text"])
    )
    check("pipeline.valid_retry_adopted", len(client.calls) == 2 and result["overall_band"] == 5.5)

    history = []
    for filename in (
        "realcheck_20261106_high.json",
        "realcheck_20261107_prompt9.json",
        "realcheck_20261109_prompt10.json",
    ):
        data = json.loads((fixtures / filename).read_text())
        for sample, attempts in data["attempts"].items():
            for index, attempt in enumerate(attempts):
                text = attempt if isinstance(attempt, str) else attempt["text"]
                if text and parse_strict_json(text) is None:
                    reason = review.json_problem("evaluate", text, data["submissions"][sample])
                    history.append(
                        {
                            "fixture": filename,
                            "sample": sample,
                            "attempt": index + 1,
                            "diagnosis": reason,
                            "missing_brace": "少了一个 }" in reason,
                            "extra_brace": "多了一个 }" in reason,
                        }
                    )
    check(
        "history.six_missing_brace_responses_in_three_batches",
        sum(row["missing_brace"] for row in history) == 6,
    )
    check(
        "history.extra_brace_counterexample_also_exists", any(row["extra_brace"] for row in history)
    )

    report = {
        "repo": str(repo),
        "head": git("rev-parse", "HEAD").strip(),
        "baseline": args.baseline,
        "prompt_version": prompts.PROMPT_VERSION,
        "actual_model_calls": 0,
        "passed": sum(row["passed"] for row in checks),
        "total": len(checks),
        "checks": checks,
        "history": history,
        "limits": [
            "Reordering compatibility and unchanged strict parsing are verified offline; no model reliability improvement is established.",
            "Historical wording 'all six brace errors' omits a distinct extra-brace error in the .8 off-topic response; six is the missing-brace subset.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "passed": report["passed"],
                "total": report["total"],
                "failed": [row for row in checks if not row["passed"]],
            },
            ensure_ascii=False,
        )
    )
    raise SystemExit(0 if report["passed"] == report["total"] else 1)


if __name__ == "__main__":
    main()
