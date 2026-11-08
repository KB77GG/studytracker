#!/usr/bin/env python3
"""Offline deletion-intent review; synthetic committed fixtures, no model calls.

Run with --repo PATH --output PATH. Exit 1 denotes a desired-behaviour failure.
The historical 189-check probe is run unchanged in a temporary output directory.
"""

import argparse
import copy
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    repo = args.repo.resolve()
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(repo))
    from tools.ielts_writing_ai import copytext, deletion, essay, review

    inherited = repo / "docs/design/ielts-writing-ai-prompt10-review-20261108/deletion_probe.py"
    with tempfile.TemporaryDirectory(prefix="iwa-intent-inherited-") as temporary:
        destination = Path(temporary) / "inherited.json"
        completed = subprocess.run(
            [sys.executable, str(inherited), "--repo", str(repo), "--output", str(destination)],
            cwd=repo, text=True, capture_output=True,
            env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        )
        historical = json.loads(destination.read_text())

    bundle = repo / "docs/design/ielts-writing-ai-prompt9-high-20261107/continuation"
    data_path, calls_path = bundle / "run_data.json", bundle / "raw_calls.jsonl"
    data = json.loads(data_path.read_text())
    submission = next(s["submission"] for s in data["samples"] if s["id"] == "t1-no-image")
    calls = [json.loads(line) for line in calls_path.read_text().splitlines()]
    raw = json.loads(next(c["text"] for c in calls if c["sample"] == "t1-no-image"))
    paragraphs = essay.split_paragraphs(submission["essay_text"])
    quote = paragraphs[-1]
    total, last_words = essay.count_words(submission["essay_text"]), essay.count_words(quote)
    checks, cases = [], []

    def check(name, ok, details=None):
        checks.append({"name": name, "passed": bool(ok), "details": details})

    check("historical_189_closed", completed.returncode == 0 and historical["passed"] == historical["total"] == 189)
    check("fixture_counts", total == 172 and last_words == 23 and essay.count_words("In summary") == 2)
    scenarios = [
        ("whole_paragraph_en", "Delete this paragraph.", 23, "control"),
        ("whole_sentence_en", "Remove this sentence.", 23, "control"),
        ("whole_paragraph_cn", "删去这一结尾段。", 23, "control"),
        ("negative_cn", "不要删掉这段。", 0, "control"),
        ("negative_do_not", "Do not delete this paragraph.", 0, "control"),
        ("negative_should_not", "You should not delete this paragraph.", 0, "control"),
        ("negative_dont_ascii", "Don't delete this paragraph.", 0, "control"),
        ("negative_dont_curly", "Don’t delete this paragraph.", 0, "negation"),
        ("negative_shouldnt_ascii", "You shouldn't delete this paragraph.", 0, "negation"),
        ("negative_shouldnt_curly", "You shouldn’t delete this paragraph.", 0, "negation"),
        ("two_words_ascii_double", 'Remove only "In summary" from this sentence.', 2, "control"),
        ("two_words_curly_double", "Remove only “In summary” from this sentence.", 2, "control"),
        ("two_words_ascii_single", "Remove only 'In summary' from this sentence.", 2, "single_quote"),
        ("two_words_curly_single", "Remove only ‘In summary’ from this sentence.", 2, "single_quote"),
        ("two_words_cn_double", "删去句中的“In summary”两个词。", 2, "control"),
        ("two_words_cn_single", "删去句中的‘In summary’两个词。", 2, "control"),
        ("rejected_advice_double", 'Ignore the advice "delete this paragraph" and keep it.', 0, "control"),
        ("rejected_advice_single", "Ignore the advice 'delete this paragraph' and keep it.", 0, "single_quote"),
        ("rejected_advice_curly_single", "Ignore the advice ‘delete this paragraph’ and keep it.", 0, "single_quote"),
        ("negative_cn_unnecessary", "无需删除这一段，应保留比较信息。", 0, "control"),
        ("negative_cn_bie", "别删去这一段，应保留比较信息。", 0, "negation"),
        ("word_edit_then_negative", 'Remove only "In summary" from this sentence; don\'t delete the whole sentence.', 2, "control"),
    ]

    for name, advice, expected_removed_words, group in scenarios:
        value, sub = copy.deepcopy(raw), copy.deepcopy(submission)
        for criterion in ("task", "coherence", "lexical", "grammar"):
            if isinstance(value.get(criterion), dict):
                value[criterion]["issues"] = []
        value["priorities"] = ["保留原稿的关键对照信息。"]
        value["coherence"]["issues"] = [{
            "quote": quote,
            "comment": "这段内容需要保留关键比较，因此应先判断具体删改范围。",
            "suggestion": advice,
        }]
        before = copy.deepcopy((value, sub))
        normalized = review.normalize_evaluation(value, sub)
        copied = copytext.evaluation_text(normalized, {})
        shown = next(c for c in normalized["criteria"] if c["key"] == "coherence")["issues"][0]["suggestion"]
        length_warnings = [w for w in normalized["warnings"] if "条建议提到删去" in w]
        expected_remaining = total - expected_removed_words
        expected_note = int(expected_remaining < 150)
        start = len(checks)
        check(name + ":note_count", normalized["length_notes"] == expected_note, normalized["length_notes"])
        check(name + ":exact_note_in_output", (f"约剩 {expected_remaining} 词" in shown) if expected_note else "约剩" not in shown, shown)
        check(name + ":copy_contract", copied.count("约剩 149 词") == expected_note)
        check(name + ":top_warning", len(length_warnings) == expected_note, length_warnings)
        check(name + ":advice_preserved", shown.startswith(advice))
        check(name + ":no_numeric_filter", normalized["suggestions_removed"]["total"] == 0)
        check(name + ":source_unmodified", (value, sub) == before)
        check(name + ":scores_unmodified", [c["band"] for c in normalized["criteria"]] == [None, 7.0, 7.5, 7.5])
        diagnostic = deletion.analyse(advice, quote, sub["essay_text"])
        cases.append({
            "id": name, "group": group, "sample": "t1-no-image",
            "input_advice": advice, "input_quote": quote,
            "expected_removed_words_from_literal_instruction": expected_removed_words,
            "expected_remaining": expected_remaining, "expected_length_notes": expected_note,
            "normalized_advice": shown, "length_notes": normalized["length_notes"],
            "top_length_warnings": length_warnings,
            "copy_relevant_lines": [line for line in copied.splitlines() if advice in line or "约剩" in line or "条建议提到删去" in line],
            "diagnostic_not_used_as_oracle": None if diagnostic is None else {
                "texts": diagnostic.texts(sub["essay_text"]),
                "words": diagnostic.words(sub["essay_text"]), "unsure": diagnostic.unsure,
            },
            "failed_checks": [c["name"] for c in checks[start:] if not c["passed"]],
        })

    findings = []
    definitions = [
        ("negation", "Common Chinese and English negations are treated as affirmative deletion", [33, 35, 36, 168],
         "Don’t and shouldn't are not recognized as negation. 别删去 also fails: the 别 lookahead requires the deletion verb, but analyse searches only the substring before that verb. The otherwise identical Don't / do not / should not / 不要 / 无需 controls pass. Normalization and copy add a definite 149-word warning although the advice deletes nothing."),
        ("single_quote", "Single-quoted wording and quoted rejected advice are treated as whole-unit deletion", [39, 101, 122, 168],
         "Only double quotation marks are masked. A two-word deletion in single quotes selects the later sentence noun, counts 23 words and reports 149 rather than the actual 170. Single-quoted advice being rejected also triggers deletion; the double-quoted controls do not."),
    ]
    for group, title, lines, description in definitions:
        failures = [c["id"] for c in cases if c["group"] == group and c["failed_checks"]]
        if failures:
            findings.append({"priority": "P2", "title": title, "file": "tools/ielts_writing_ai/deletion.py", "lines": lines,
                             "description": description, "case_ids": failures})
    output = {
        "source_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip(),
        "source_status": subprocess.check_output(["git", "status", "--short", "--branch"], cwd=repo, text=True).strip(),
        "source_files_sha256": {str(p.relative_to(repo)): hashlib.sha256(p.read_bytes()).hexdigest() for p in (inherited, data_path, calls_path, repo / "tools/ielts_writing_ai/deletion.py")},
        "privacy_scope": "Committed redacted synthetic formal responses only; no credentials, reasoning, models or network.",
        "historical_probe": {"exit_code": completed.returncode, "passed": historical["passed"], "total": historical["total"], "all_checks_passed": historical["all_checks_passed"]},
        "sample_counts": {"words": total, "last_paragraph_words": last_words, "quoted_phrase_words": 2},
        "cases": cases, "checks": checks,
        "passed": sum(c["passed"] for c in checks), "total": len(checks),
        "all_checks_passed": all(c["passed"] for c in checks), "findings": findings,
        "limits": [
            "This is a targeted intent/scope check, not exhaustive natural-language coverage or semantic grading.",
            "The expected removal is specified from the literal instruction; helper diagnostics are not the oracle.",
            "All product findings go through normalize_evaluation and production evaluation_text. The probes do not render a browser or replace a full suite.",
            "The Chinese single-quote short edit checks absence of a false warning, not successful recognition of that edit.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"historical": output["historical_probe"], "passed": output["passed"], "total": output["total"], "cases": len(cases), "findings": len(findings), "output": str(args.output)}, ensure_ascii=False))
    return 0 if output["all_checks_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
