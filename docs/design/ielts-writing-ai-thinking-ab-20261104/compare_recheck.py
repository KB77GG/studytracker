#!/usr/bin/env python3
"""Offline comparison/report recheck; no model or network access.

Usage: python compare_recheck.py --repo /path/to/repo --output compare_recheck.json
Fork of the prior comparison probe; this file asserts the corrected behavior and
uses the new object-valued Task 1 consistency view. The old probe stays unchanged.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    repo = args.repo.resolve()
    sys.path.insert(0, str(repo))

    def audit(event, _args):
        if event == "socket.connect":
            raise RuntimeError("Offline probe forbids network connections")

    sys.addaudithook(audit)
    from tools.ielts_writing_ai import realcheck, realcheck_compare as compare
    from tools.ielts_writing_ai.config import Settings
    from tools.ielts_writing_ai.llm import FakeClient

    class CaptureClient(FakeClient):
        def __init__(self):
            super().__init__()
            self.requests = []

        def complete(self, messages, **kwargs):
            self.requests.append({"messages": copy.deepcopy(messages), "options": copy.deepcopy(kwargs)})
            result = super().complete(messages, **kwargs)
            result.usage = {"prompt_tokens": 100, "completion_tokens": 200, "total_tokens": 300}
            return result

    class VisionClient(FakeClient):
        def __init__(self, value):
            super().__init__(model="offline-vision-fixture")
            self.value = value

        def complete(self, messages, **kwargs):
            result = super().complete(messages, **kwargs)
            data = json.loads(result.text)
            data["data_points"][0]["value"] = self.value
            result.text = json.dumps(data, ensure_ascii=False)
            return result

    source_head = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=repo, text=True).strip()
    out = {"source_head": source_head, "network_calls": 0, "actual_model_requests": 0, "observations": {}}
    with tempfile.TemporaryDirectory(prefix="iwa-compare-probe-") as tmp_string:
        tmp = Path(tmp_string)
        samples = realcheck.load_samples("builtin")
        png = tmp / "synthetic.png"
        png.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)
        task1 = next(copy.deepcopy(s) for s in samples if s["task_type"] == "task1")
        task1["image"] = str(png)

        def run(name, thinking, items, vision=None):
            settings = Settings(data_dir=tmp / (name + "-unused-data"), job_mode="inline", evaluate_thinking=thinking)
            client = CaptureClient()
            data = realcheck.run(settings, items, client=client, vision_client=vision, kinds=("evaluate",), max_calls=4)
            report = realcheck.build_report(data)
            directory = tmp / name
            realcheck.write_report(data, report, directory)
            return data, report, client, directory

        a_data, a_report, a_client, a_dir = run("visual-a", "off", [task1], VisionClient("140"))
        b_data, b_report, b_client, b_dir = run("visual-b", "high", [task1], VisionClient("141"))
        assert a_data["samples"][0]["image_status"] == b_data["samples"][0]["image_status"] == "ready"
        a_messages = a_client.requests[0]["messages"]
        b_messages = b_client.requests[0]["messages"]
        assert a_messages != b_messages, "Fixture must change the actual evaluation input"
        assert "Museum A = 140" in a_messages[1]["content"]
        assert "Museum A = 141" in b_messages[1]["content"]
        def digest(value):
            return hashlib.sha256(json.dumps(value, ensure_ascii=False).encode()).hexdigest()

        loaded_a = compare.load_run(a_dir)
        loaded_b = compare.load_run(b_dir)
        cond_a, cond_b = compare.conditions(loaded_a), compare.conditions(loaded_b)
        errors, warnings = compare.check_same_conditions(cond_a, cond_b)
        accepted = False
        rejection = None
        try:
            compare.compare(a_dir, b_dir)
            accepted = True
        except compare.CompareError as exc:
            rejection = str(exc)
        assert not accepted, "Different actual evaluation inputs must be refused"
        assert any("实际发送给评价模型的输入不同" in error for error in errors)
        assert "image_description" in a_data["samples"][0]["submission"]
        out["observations"]["different_visual_prompt"] = {
            "description": "Two actual offline realcheck runs: same image/sample ID/essay, different successful vision reading changes evaluation input.",
            "actual_evaluation_message_sha256": {"a": digest(a_messages), "b": digest(b_messages)},
            "visual_values": {"a": "Museum A = 140", "b": "Museum A = 141"},
            "sample_fingerprints": {"a": cond_a["samples"], "b": cond_b["samples"]},
            "errors": errors, "warnings": warnings, "compare_accepted": accepted,
            "compare_rejection": rejection,
            "exported_submission_fields": sorted(a_data["samples"][0]["submission"]),
            "call_kinds": {"a": [c["kind"] for c in a_data["calls"]], "b": [c["kind"] for c in b_data["calls"]]},
            "scope": "Regression now refused even when the same sample/image yields differing vision readings.",
        }

        changed = copy.deepcopy(loaded_a)
        changed["run_data"]["samples"][0]["submission"]["essay_text"] += " This is a changed essay."
        essay_errors, _ = compare.check_same_conditions(cond_a, compare.conditions(changed))
        changed = copy.deepcopy(loaded_a)
        changed["report"]["prompt_version"] = "deliberately-other-prompt"
        version_errors, _ = compare.check_same_conditions(cond_a, compare.conditions(changed))
        assert essay_errors and version_errors, "Existing guards should reject these controls"
        assert len(essay_errors) == len(version_errors) == 1, "Positive controls must isolate one changed condition"
        out["observations"]["positive_controls"] = {"changed_essay_errors": essay_errors, "changed_prompt_version_errors": version_errors}

        # Actual messages must remain identical when only the permitted request
        # options (off/high, output budget, timeout) change.
        opt_a, _, opt_client_a, opt_dir_a = run("options-off", "off", [samples[0]])
        opt_b, _, opt_client_b, opt_dir_b = run("options-high", "high", [samples[0]])
        assert opt_client_a.requests[0]["messages"] == opt_client_b.requests[0]["messages"]
        opt_sha_a, opt_sha_b = opt_a["calls"][0]["input_sha256"], opt_b["calls"][0]["input_sha256"]
        assert opt_sha_a == opt_sha_b
        opt_cmp = compare.compare(opt_dir_a, opt_dir_b)
        assert not opt_cmp["warnings"]
        assert opt_a["calls"][0]["max_tokens"] == 4500
        assert opt_b["calls"][0]["max_tokens"] == 16000
        out["observations"]["only_thinking_options_differ"] = {
            "compare_accepted": True,
            "messages_identical": True,
            "input_sha256": opt_sha_a,
            "modes": [opt_a["calls"][0]["thinking"], opt_b["calls"][0]["thinking"]],
            "max_tokens": [opt_a["calls"][0]["max_tokens"], opt_b["calls"][0]["max_tokens"]],
            "timeout_options": [opt_client_a.requests[0]["options"].get("timeout"), opt_client_b.requests[0]["options"].get("timeout")],
            "warnings": opt_cmp["warnings"],
        }

        legacy_a = compare.load_run(opt_dir_a)
        legacy_b = compare.load_run(opt_dir_b)
        for call in legacy_b["run_data"]["calls"]:
            call.pop("input_sha256", None)
        legacy_errors, legacy_warnings = compare.check_same_conditions(compare.conditions(legacy_a), compare.conditions(legacy_b))
        assert not legacy_errors
        assert any("缺少实际输入的指纹" in warning for warning in legacy_warnings)
        out["observations"]["legacy_report"] = {"errors": legacy_errors, "warnings": legacy_warnings}

        # Rendering fixtures exercise normalized fields, not model/validator semantics.
        t2_data, t2_report, _client, _dir = run("manual-base", "off", [samples[0]])
        t2 = copy.deepcopy(t2_data["samples"][0])
        result = t2["generations"]["evaluate"]["result"]
        assert isinstance(result, dict), "Need a successful real pipeline result for rendering fixture"
        result["argument"]["problems"] = [{
            "type": "position_inconsistent", "label": "立场前后不一致",
            "quote": "FIRST_CLAIM_MARKER", "comment": "两处立场需人工对照。",
            "conflicts_with": "PAIRED_CONFLICT_MARKER", "needs_review": True,
            "p": 2,
        }]
        result["argument"]["notes"] = ["ARGUMENT_NOTE_MARKER"]
        result["argument"]["position"]["consistent"] = False
        task1_sample = copy.deepcopy(a_data["samples"][0])
        t1_result = task1_sample["generations"]["evaluate"]["result"]
        assert isinstance(t1_result, dict), "Need successful Task 1 fixture"
        t1_result["consistency_issues"] = [{
            "quote": "TASK1_CONTRADICTION_MARKER", "comment": "最高的说法与文内数值矛盾。",
            "figures": ["FIGURE_A_MARKER", "FIGURE_C_MARKER"],
        }]
        t1_result["comparisons_checked"] = 3
        t2_view = compare.sample_view(t2_data, t2)
        t1_view = compare.sample_view(a_data, task1_sample)
        cmp_fixture = {
            "conditions": {"a": {"evaluate_thinking": "off"}, "b": {"evaluate_thinking": "high"}},
            "samples": [{"a": t2_view, "b": copy.deepcopy(t2_view)}, {"a": t1_view, "b": copy.deepcopy(t1_view)}],
        }
        sheet = compare.render_manual_review(cmp_fixture)
        assert "FIRST_CLAIM_MARKER" in sheet, "Primary problem must actually render"
        out["observations"]["manual_review_completeness"] = {
            "fixture_kind": "Synthetic accepted-field rendering fixture, not a judgment accuracy test",
            "first_claim_rendered": "FIRST_CLAIM_MARKER" in sheet,
            "paired_conflict_preserved_in_view": "conflicts_with" in t2_view["problems"][0],
            "needs_review_preserved_in_view": "needs_review" in t2_view["problems"][0],
            "paired_conflict_rendered": "PAIRED_CONFLICT_MARKER" in sheet,
            "task1_issue_preserved_in_view": any(issue.get("quote") == "TASK1_CONTRADICTION_MARKER" for issue in t1_view["consistency_issues"]),
            "task1_issue_rendered": "TASK1_CONTRADICTION_MARKER" in sheet,
            "task1_figures_preserved_in_view": "FIGURE_A_MARKER" in json.dumps(t1_view["consistency_issues"]),
            "task1_figures_rendered": "FIGURE_A_MARKER" in sheet,
            "task1_comment_rendered": "最高的说法与文内数值矛盾。" in sheet,
            "task1_comparisons_rendered": "核对了 3 条比较说法，指出矛盾 1 条" in sheet,
            "paragraph_rendered": "论证问题（第 2 段）" in sheet,
            "needs_review_rendered": "需人工确认" in sheet,
            "argument_note_rendered": "ARGUMENT_NOTE_MARKER" in sheet,
            "position_inconsistent_rendered": "前后不一致" in sheet,
            "scope": "Previously omitted evidence is now preserved and rendered for both evaluation task types.",
        }
        for name, value in out["observations"]["manual_review_completeness"].items():
            if isinstance(value, bool):
                assert value, f"Missing manual-review evidence: {name}"
        out["passed"] = True

    payload = json.dumps(out, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
