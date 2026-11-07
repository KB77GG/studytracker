#!/usr/bin/env python3
"""Synthetic normalize -> generation view/copy -> JS DOM-double render probe.

No app is created, no DB/config/private model output is read, and no HTTP call is
made. Run with a Python containing the trial dependencies and Node on PATH:
  .venv/bin/python docs/design/iwa-prompt9-recheck-20261107/ui_evidence_probe.py \
    --repo /private/tmp/studytracker-iwa-realcheck-review-20261103

The companion JS executes unmodified function bodies extracted from iwa.js in
a minimal DOM test double. It is not a browser, CSS/layout, or clipboard OS test.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", default="/private/tmp/studytracker-iwa-realcheck-review-20261103")
    parser.add_argument("--output", type=Path, default=Path(__file__).with_suffix(".json"))
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    for name in list(os.environ):
        if name.startswith("IWA_"):
            del os.environ[name]
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(repo))
    from tools.ielts_writing_ai.essay import CRITERIA, count_words
    from tools.ielts_writing_ai.review import normalize_evaluation
    from tools.ielts_writing_ai.web import _generation_view

    values = [f"{n}.5%" for n in range(1, 36)]
    claim = "Country A was the highest."
    evil = '<img src=x onerror="alert(1)"> 42%'
    definitions = [
        ("zero", [], [], 0),
        ("thirty", values[:30], values[:30], 0),
        ("thirty_one", values[:31], values[:30], 1),
        ("thirty_five", values, values[:30], 5),
        ("duplicates_at_thirty", values[:30] + [" 1.5% ", "2.5%", 17, "invented 99%", claim, ""], values[:30], 0),
        ("duplicates_at_thirty_one", values[:31] + [" 1.5% ", "2.5%", 17, "invented 99%", claim, ""], values[:30], 1),
        ("case_and_space_duplicates", ["About 5%", " about   5% ", "ABOUT 5%"], ["About 5%"], 0),
        ("html_as_text", [evil, evil], [evil], 0),
    ]
    fixtures, summaries, checks = [], [], []

    def check(case, name, ok):
        checks.append({"case": case, "check": name, "ok": bool(ok)})

    for name, raw_figures, expected, omitted in definitions:
        available = values + ["About 5%", evil]
        text = claim + " Values: " + "; ".join(available) + ". "
        text += "A synthetic sentence supplies neutral language evidence for this isolated test. " * 20
        comment = "对照数字可用于复查此处比较结论是否成立。"
        if name == "html_as_text":
            comment += '<b onclick="alert(2)">只是文字</b>'
        criteria = {key: {"band": 6, "summary": "这段合成语言提供了能够核实的完整理由，仅用于测试数据传递。",
                          "strengths": [{"quote": claim, "comment": "这句合成原文可用于核实引文匹配。"}],
                          "issues": []} for key in CRITERIA}
        raw = {"criteria": criteria, "overall_comment": "这份合成输入只用于检查边界值和证据显示，不用于评价真实作文。",
               "priorities": ["复核比较所引用的完整数据。"],
               "comparisons": [{"claim": claim, "holds": False, "figures": raw_figures, "comment": comment}]}
        submission = {"task_type": "task1", "essay_text": text, "word_count": count_words(text),
                      "image_status": "none", "prompt_text": "Synthetic chart prompt."}
        result = normalize_evaluation(raw, submission)
        generation = {"id": name, "status": "ready", "kind": "evaluate", "result": result,
                      "created_at": "2026-11-07T00:00:00+00:00", "model": "synthetic-no-api",
                      "prompt_version": "probe"}
        view = _generation_view(generation, submission)
        issues = result["consistency_issues"]
        actual = issues[0]["figures"] if issues else []
        actual_omitted = issues[0].get("figures_omitted", 0) if issues else 0
        copy = view["copy"]["evaluation"]
        suffix = f"（另有 {omitted} 个数字未列出）" if omitted else ""
        contrast = "    对照：" + "；".join(f"“{f}”" for f in expected) + suffix if expected else None
        copy_lines = [line for line in copy.splitlines() if line.startswith("    对照：")]
        check(name, "normalized_figures_exact_order", actual == expected)
        check(name, "omitted_count_after_unique_verified_filter", actual_omitted == omitted)
        check(name, "copy_contrast_exact", copy_lines == ([contrast] if contrast else []))
        check(name, "copy_omission_notice_iff_truncated", ("未列出" in copy) == bool(omitted))
        check(name, "zero_evidence_drops_unsupported_comparison", bool(issues) == bool(expected))
        check(name, "missing_chart_remains_unassessable", result["overall_band"] is None and result["criteria"][0]["band"] is None)
        summaries.append({"name": name, "input_count": len(raw_figures), "kept": actual,
                          "figures_omitted": actual_omitted, "copy_contrast": contrast})
        fixtures.append({"name": name, "generation": view, "expected_figures": expected,
                         "expected_omitted": omitted, "expected_comment": comment})

    node = subprocess.run(["node", str(Path(__file__).with_suffix(".js")), "--repo", str(repo)],
                          input=json.dumps({"cases": fixtures}, ensure_ascii=False), text=True,
                          capture_output=True, check=False)
    if node.returncode:
        raise RuntimeError(f"DOM probe did not complete: {node.stderr}")
    dom = json.loads(node.stdout)
    checks += dom["checks"]
    failures = [c for c in checks if not c["ok"]]
    source = repo / "tools/ielts_writing_ai/static/iwa.js"
    output = {"repo": str(repo),
              "head": subprocess.check_output(["git", "-C", str(repo), "rev-parse", "HEAD"], text=True).strip(),
              "iwa_js_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
              "evidence_levels": {
                  "backend": "Executed real normalize_evaluation and web._generation_view/copytext on synthetic data.",
                  "dom": "Executed original iwa.js renderer/helper/copy function bodies in Node with a minimal DOM test double and stub clipboard.",
                  "real_browser": "Not run. No layout, browser parser, native clipboard or end-to-end authentication claim.",
                  "external": "No model calls, app startup, database, .env or private reasoning reads."},
              "summary": {"cases": len(fixtures), "checks": len(checks), "passed": len(checks)-len(failures), "failed": len(failures)},
              "cases": summaries, "dom": dom["cases"], "checks": checks, "failures": failures}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), **output["summary"]}, ensure_ascii=False))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
