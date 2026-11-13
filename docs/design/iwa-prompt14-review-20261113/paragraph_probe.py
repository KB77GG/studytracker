"""Offline .14 paragraph/copy audit, minimally adapted from the .13 probe.

Outputs numbers and booleans only. Confirmed spans come from the current locally
filled official JSONL; original .13 probe and private recorded run stay unchanged.

Reads only calls[*].text and samples[*].submission from the private run JSON.
Never uses its reasoning, existing normalized generations, settings or usage.
No model, trial database, .env or network access; private inputs remain unchanged.
"""

from __future__ import annotations

import argparse
import copy
import difflib
import hashlib
import importlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import types
from pathlib import Path

DOM_PROBE = r"""
const fs = require('fs'), vm = require('vm');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const source = fs.readFileSync(process.argv[1], 'utf8');
class Node {
  constructor(tag) { this.tag = tag; this.children = []; this.attrs = {}; this.events = {}; this.textContent = ''; }
  appendChild(n) { this.children.push(n); return n; }
  setAttribute(k, v) { this.attrs[k] = v; }
  addEventListener(k, v) { this.events[k] = v; }
}
const document = {createElement: tag => new Node(tag), createTextNode: text => {
  const n = new Node('#text'); n.textContent = text; return n;
}};
let copied = null;
const context = {document, copyText: text => copied = text,
  regenButton: () => new Node('button'), band: x => Number(x).toFixed(1)};
vm.createContext(context);
const helpers = source.slice(source.indexOf('  function el('), source.indexOf('  function clear('));
const renderer = source.slice(source.indexOf('    function copyButton('), source.indexOf('    // -- refine'));
if (!helpers || !renderer.includes('function renderEvaluation')) throw Error('renderer not found');
vm.runInContext(helpers + '\n' + renderer, context);
const panel = new Node('main'); context.renderEvaluation(panel, input.generation);
const all = []; function walk(n) { all.push(n); n.children.forEach(walk); } walk(panel);
const texts = all.map(n => n.textContent).filter(Boolean);
const buttons = all.filter(n => n.tag === 'button' && n.textContent === '复制评价');
if (buttons.length === 1) buttons[0].events.click();
const result = {
  paragraph_nodes: all.filter(n => (n.className || '').startsWith('argument__step is-')).length,
  all_paragraph_labels: input.paragraph_numbers.every(p => texts.includes('第 ' + p + ' 段')),
  all_warnings_visible: input.generation.result.warnings.every(w => texts.includes(w)),
  copy_button_enabled: buttons.length === 1 && !Object.hasOwn(buttons[0].attrs, 'disabled'),
  copy_button_exact_text: copied === input.generation.copy.evaluation,
};
process.stdout.write(JSON.stringify(result));
"""


def git(repo, *args):
    return subprocess.check_output(["git", *args], cwd=repo, text=True).strip()


def deny_network(*_args, **_kwargs):
    raise RuntimeError("network forbidden during offline review")


def load_baseline(repo, ref, root):
    """Import exact baseline modules under an isolated package name, without __init__."""
    files = git(repo, "ls-tree", "--name-only", "-r", ref, "tools/ielts_writing_ai").splitlines()
    for name in files:
        relative = Path(name).relative_to("tools/ielts_writing_ai")
        if relative.parent != Path(".") or relative.suffix != ".py":
            continue
        (root / relative).write_text(git(repo, "show", f"{ref}:{name}") + "\n")
    package = types.ModuleType("iwa_review_baseline")
    package.__path__ = [str(root)]
    sys.modules[package.__name__] = package
    return {
        name: importlib.import_module(f"iwa_review_baseline.{name}")
        for name in ("essay", "argument", "prompts", "review")
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--private-run", type=Path, required=True)
    parser.add_argument("--samples-dir", type=Path, required=True)
    parser.add_argument("--baseline", default="abf48d49")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    for name in tuple(os.environ):
        if name.startswith("IWA_"):
            del os.environ[name]
    socket.socket.connect = deny_network
    socket.create_connection = deny_network
    socket.getaddrinfo = deny_network
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(args.repo))
    from tools.ielts_writing_ai import argument, copytext, essay, prompts, realcheck, review
    from tools.ielts_writing_ai.llm import parse_strict_json
    from tools.ielts_writing_ai.web import _generation_view

    checks = {}

    def check(name, value):
        checks[name] = bool(value)

    def accounting(name, value):
        check(
            name,
            value["returned"]
            == sum(value[key] for key in ("kept", "dropped", "duplicates", "over_limit")),
        )

    def counters(value):
        return {k: value[k] for k in ("returned", "kept", "dropped", "duplicates", "over_limit")}

    def digest(value):
        text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(text.encode()).hexdigest()

    def ui_probe(result, submission):
        generation = {
            "id": 1,
            "kind": "evaluate",
            "status": "ready",
            "result": result,
            "model": "offline-replay",
            "prompt_version": prompts.PROMPT_VERSION,
            "created_at": "2026-11-13T00:00:00Z",
        }
        view = _generation_view(generation, submission)
        view_result = view["result"]
        check("api_result_preserves_new_field", view_result == result)
        numbers = [p["p"] for p in result["argument"]["paragraphs"]]
        payload = {"generation": view, "paragraph_numbers": numbers}
        completed = subprocess.run(
            ["node", "-e", DOM_PROBE, str(args.repo / "tools/ielts_writing_ai/static/iwa.js")],
            input=json.dumps(payload, ensure_ascii=False),
            text=True,
            capture_output=True,
            check=False,
        )
        # Avoid printing unexpected JS exception text containing private data.
        check("dom_probe_exit_zero", completed.returncode == 0)
        return json.loads(completed.stdout)

    with tempfile.TemporaryDirectory(prefix="iwa-p14-baseline-") as folder:
        baseline = load_baseline(args.repo, args.baseline, Path(folder))
        official_path = args.samples_dir / "official_lowband_t2.jsonl"
        official_sha = hashlib.sha256(official_path.read_bytes()).hexdigest()
        official = next(
            item
            for item in realcheck.load_samples(str(official_path))
            if item["id"] == "official-2B-A"
        )
        official_text = essay.normalize_newlines(official["essay"]).strip()
        check(
            "official_current_metadata_confirms_two_whole_paragraphs",
            official.get("copied_from_question") == [{"paragraph": 1}, {"paragraph": 2}],
        )
        official_copied = realcheck._copied_spans(official, official_text)
        private_sha = hashlib.sha256(args.private_run.read_bytes()).hexdigest()
        private = json.loads(args.private_run.read_text())
        selected = [
            (call["text"], sample["submission"])
            for call, sample in zip(private["calls"], private["samples"], strict=True)
        ]
        del private
        check("two_offline_replays", len(selected) == 2)
        replay_rows = []
        replay_samples = []
        replay_calls = []
        for index, (text, submission) in enumerate(selected, 1):
            label = f"replay_{index}"
            same_source = (
                submission["essay_text"] == official_text
                and submission["prompt_text"] == official["prompt"].strip()
                and submission["word_count"] == essay.count_words(official_text)
            )
            check(label + "_current_source_matches_recorded_submission", same_source)
            if not same_source:
                raise RuntimeError(
                    "Official input differs from recorded submission; replay refused"
                )
            submission = {**submission, "copied_spans": official_copied}
            raw = parse_strict_json(text)
            check(label + "_strict_json", isinstance(raw, dict))
            result = review.normalize_evaluation(copy.deepcopy(raw), copy.deepcopy(submission))
            old = baseline["review"].normalize_evaluation(
                copy.deepcopy(raw), copy.deepcopy(submission)
            )
            mapped = result["argument"]
            numbers = [p["p"] for p in mapped["paragraphs"]]
            check(label + "_all_nine_paragraphs", numbers == list(range(1, 10)))
            check(label + "_previous_eight", len(old["argument"]["paragraphs"]) == 8)
            accounting(label + "_accounting", mapped)
            check(label + "_no_paragraph_over_limit", mapped["over_limit"] == 0)
            score_keys = ("task", "coherence", "lexical", "grammar")
            bands = {c["key"]: c["band"] for c in result["criteria"]}
            check(
                label + "_raw_scores_unchanged",
                all(bands[k] == raw["criteria"][k]["band"] for k in score_keys),
            )
            check(
                label + "_old_scores_unchanged",
                result["criteria"] == old["criteria"]
                and result["overall_band"] == old["overall_band"],
            )
            copied = result["copied_from_question"]
            copied_words = sum(c["words"] for c in copied)
            own_words = submission["word_count"] - copied_words
            check(label + "_copied_counts", (copied_words, own_words) == (34, 194))
            check(label + "_copied_paragraphs", [c["p"] for c in copied] == [1, 2])
            opening = []
            question_tokens = essay._copy_tokens(submission["prompt_text"])
            similar_sentences = essay.similar_to_prompt(
                submission["essay_text"], submission["prompt_text"]
            )
            for sentence in essay.split_sentences(submission["essay_text"]):
                if sentence.paragraph >= 2:
                    continue
                tokens = essay._copy_tokens(sentence.text)
                blocks = difflib.SequenceMatcher(
                    None, tokens, question_tokens, autojunk=False
                ).get_matching_blocks()
                matched = sum(b.size for b in blocks)
                opening.append(
                    {
                        "p": sentence.paragraph + 1,
                        "words": essay.count_words(sentence.text),
                        "tokens": len(tokens),
                        "matched_tokens": matched,
                        "match_ratio": matched / len(tokens),
                        "longest_run": max(b.size for b in blocks),
                        "similarity_hint": any(
                            c["sentence"] == sentence.text for c in similar_sentences
                        ),
                    }
                )
            request_messages, _ = prompts.build_evaluate(
                submission, essay.split_sentences(submission["essay_text"])
            )
            request_payload = json.JSONDecoder().raw_decode(
                request_messages[1]["content"].split("\n", 1)[1]
            )[0]
            check(
                label + "_request_own_words_194",
                request_payload.get("word_count_without_copied") == 194,
            )
            check(
                label + "_request_confirmed_whole_paragraphs",
                request_payload.get("copied_from_question")
                == essay.resolve_copied(official_text, official["copied_from_question"]),
            )
            check(
                label + "_confirmation_basis_not_sent",
                official["copied_source"].strip()
                not in json.dumps(request_messages, ensure_ascii=False),
            )
            copies = copytext.evaluation_text(result, {})
            check(label + "_all_warnings_in_copy", all(w in copies for w in result["warnings"]))
            check(
                label + "_all_paragraphs_in_copy", all(f"第 {p} 段 · " in copies for p in numbers)
            )
            ui = ui_probe(result, submission)
            check(
                label + "_ui_and_click",
                ui["paragraph_nodes"] == 9
                and all(v for k, v in ui.items() if k != "paragraph_nodes"),
            )
            legacy = copy.deepcopy(result)
            legacy.pop("copied_from_question")
            legacy_ui = ui_probe(legacy, submission)
            check(label + "_legacy_field_absent_compatible", legacy_ui == ui)
            sample = {
                "id": label,
                "task_type": "task2",
                "submission": submission,
                "generations": {"evaluate": {"result": result}},
            }
            check(
                label + "_realcheck_accepts",
                realcheck._first_attempt_problem("evaluate", text, sample) is None,
            )
            replay_samples.append(sample)
            replay_calls.append({"kind": "evaluate", "sample": label, "ok": True, "text": text})
            replay_rows.append(
                {
                    "repeat": index,
                    "paragraphs": len(numbers),
                    "before_paragraphs": len(old["argument"]["paragraphs"]),
                    "counts": counters(mapped),
                    "before_counts": counters(old["argument"]),
                    "bands": bands,
                    "overall_band": result["overall_band"],
                    "confirmed_spans": len(copied),
                    "copied_words": copied_words,
                    "own_words": own_words,
                    "manual_confirmed_copied_words": 34,
                    "manual_confirmed_own_words": 194,
                    "request_own_words": request_payload.get("word_count_without_copied"),
                    "opening_sentence_matching": opening,
                    "sha256": {
                        "submission": digest(submission),
                        "response_text": hashlib.sha256(text.encode()).hexdigest(),
                        "normalized_result": digest(result),
                        "new_request_messages": digest(request_messages),
                    },
                    "ui": ui,
                }
            )
        metrics = realcheck._argument_metrics({"samples": replay_samples, "calls": replay_calls})
        accounting("realcheck_aggregate_accounting", metrics)
        check(
            "realcheck_aggregate_18_paragraphs",
            metrics["paragraphs"] == 18 and metrics["over_limit"] == 0,
        )
        check(
            "realcheck_two_accepts",
            metrics["evaluate_attempts"] == 2 and metrics["attempts_rejected_for_argument"] == 0,
        )
        check(
            "private_run_unchanged",
            hashlib.sha256(args.private_run.read_bytes()).hexdigest() == private_sha,
        )
        check(
            "official_current_sample_unchanged",
            hashlib.sha256(official_path.read_bytes()).hexdigest() == official_sha,
        )

        # Synthetic maps stress the removed cap while retaining the evidence gates.
        paragraphs = [
            f"Synthetic paragraph {n} has a distinct verified claim." for n in range(1, 21)
        ]
        body = "\n".join(paragraphs)
        entries = [
            {"p": n, "role": "body", "main_point": p, "verdict": "supports"}
            for n, p in enumerate(paragraphs, 1)
        ]
        raw_map = {
            "position": {"quote": paragraphs[0], "consistent": True},
            "paragraphs": list(reversed(entries)),
            "problems": [],
            "improvements": [],
        }
        mapped = argument.normalize(raw_map, body)
        check(
            "synthetic_20_sorted_retained",
            [p["p"] for p in mapped["paragraphs"]] == list(range(1, 21)),
        )
        accounting("synthetic_20_accounting", mapped)
        mixed = copy.deepcopy(raw_map)
        mixed["paragraphs"] += [
            entries[0],
            {**entries[2], "p": 999},
            {
                "p": 21,
                "role": "body",
                "verdict": "supports",
                "main_point": "A wholly invented passage.",
            },
            None,
            {**entries[5], "role": []},
        ]
        # Valid quote + wrong/malformed p must relocate, never invent a paragraph.
        for entry in mixed["paragraphs"][:20]:
            entry["p"] = {"bad": True}
        mixed["problems"] = [
            {"type": "circular", "quote": p, "comment": "合成问题。"} for p in paragraphs[:8]
        ]
        mixed["improvements"] = [
            {"quote": p, "suggestion": "补充具体机制。"} for p in paragraphs[:5]
        ]
        mapped_mixed = argument.normalize(mixed, body)
        check(
            "synthetic_bad_hints_relocated",
            [p["p"] for p in mapped_mixed["paragraphs"]] == list(range(1, 21)),
        )
        check(
            "synthetic_duplicates_invalid_caps",
            (
                mapped_mixed["duplicates"],
                mapped_mixed["dropped"],
                mapped_mixed["over_limit"],
                len(mapped_mixed["problems"]),
                len(mapped_mixed["improvements"]),
            )
            == (2, 3, 4, 6, 3),
        )
        accounting("synthetic_mixed_accounting", mapped_mixed)
        repeated = "The same repeated passage provides a clear position."
        repeated_map = {
            "paragraphs": [
                {"p": p, "role": "body", "verdict": "supports", "main_point": repeated}
                for p in range(1, 13)
            ]
        }
        mapped_repeat = argument.normalize(repeated_map, "\n".join([repeated] * 12))
        check(
            "synthetic_repeated_text_hints",
            [p["p"] for p in mapped_repeat["paragraphs"]] == list(range(1, 13)),
        )
        accounting("synthetic_repeated_accounting", mapped_repeat)
        try:
            argument.normalize({"paragraphs": {"p": 1}}, body)
        except argument.ArgumentInvalid:
            rejected_bad_container = True
        else:
            rejected_bad_container = False
        check("synthetic_bad_container_rejected", rejected_bad_container)

        # Use actual baseline build_evaluate, not a hand-reconstructed prompt.
        group_rows = []
        datasets = [
            "builtin",
            "teacher.jsonl",
            "holdout_rated_t1.jsonl",
            "holdout_rated_t2.jsonl",
            "holdout_ordering.jsonl",
            "holdout_lowband.jsonl",
        ]
        for name in datasets:
            path = args.samples_dir / name
            before_hash = (
                hashlib.sha256(path.read_bytes()).hexdigest() if name != "builtin" else None
            )
            items = realcheck.load_samples("builtin" if name == "builtin" else str(path))
            same = no_copy = 0
            for item in items:
                text = essay.normalize_newlines(item["essay"]).strip()
                image = item.get("image_frozen") or {
                    "status": "ready" if item.get("image_description") else "none",
                    "description": item.get("image_description"),
                }
                submission = {
                    "task_type": item["task_type"],
                    "prompt_text": item["prompt"].strip(),
                    "essay_text": text,
                    "word_count": essay.count_words(text),
                    "target_band": float(item.get("target_band") or 7.0),
                    "image_status": image["status"],
                    "image_description": image.get("description"),
                    "copied_spans": realcheck._copied_spans(item, text),
                }
                new_messages, _ = prompts.build_evaluate(submission, essay.split_sentences(text))
                old_messages, _ = baseline["prompts"].build_evaluate(
                    submission, baseline["essay"].split_sentences(text)
                )
                same += new_messages == old_messages
                no_copy += essay.confirmed_copies(submission) is None
            check(name + "_actual_messages_equal", same == len(items))
            check(name + "_no_confirmed_spans", no_copy == len(items))
            if before_hash:
                check(
                    name + "_unchanged",
                    hashlib.sha256(path.read_bytes()).hexdigest() == before_hash,
                )
            group_rows.append(
                {
                    "group": name,
                    "samples": len(items),
                    "identical_messages": same,
                    "no_confirmed_spans": no_copy,
                }
            )

    output = {
        "repo": str(args.repo),
        "head": git(args.repo, "rev-parse", "HEAD"),
        "baseline": git(args.repo, "rev-parse", args.baseline),
        "baseline_prompt_version": baseline["prompts"].PROMPT_VERSION,
        "prompt_version": prompts.PROMPT_VERSION,
        "checks": checks,
        "passed": sum(checks.values()),
        "total": len(checks),
        "official_replay": replay_rows,
        "realcheck": {
            **counters(metrics),
            "paragraphs": metrics["paragraphs"],
            "evaluate_attempts": metrics["evaluate_attempts"],
            "rejected": metrics["attempts_rejected_for_argument"],
        },
        "synthetic": {
            "multi": counters(mapped),
            "mixed": counters(mapped_mixed),
            "repeated_text": counters(mapped_repeat),
        },
        "message_compatibility": group_rows,
        "private_input_hashes": {
            "recorded_run": private_sha,
            "current_official_sample": official_sha,
        },
        "scope": {
            "paid_calls": 0,
            "network_calls": 0,
            "env_files_read": 0,
            "private_content_exported": False,
            "reasoning_used": False,
            "ui_method": "actual renderer functions in Node VM with minimal DOM; copy click exercised; no screenshot claim",
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "passed": sum(checks.values()),
                "total": len(checks),
                "failed": [k for k, v in checks.items() if not v],
                "output": str(args.output),
            }
        )
    )
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
