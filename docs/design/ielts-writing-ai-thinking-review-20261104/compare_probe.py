#!/usr/bin/env python3
"""Offline comparison/report audit; no model or network access.

Usage: python compare_probe.py --repo /path/to/repo --output compare_probe.json
Observations record current behavior, so fixed implementations can be rerun without
changing expected-defect assertions. Harness invariants alone use assert.
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
        out["observations"]["different_visual_prompt"] = {
            "description": "Two actual offline realcheck runs: same image/sample ID/essay, different successful vision reading changes evaluation input.",
            "actual_evaluation_message_sha256": {"a": digest(a_messages), "b": digest(b_messages)},
            "visual_values": {"a": "Museum A = 140", "b": "Museum A = 141"},
            "sample_fingerprints": {"a": cond_a["samples"], "b": cond_b["samples"]},
            "errors": errors, "warnings": warnings, "compare_accepted": accepted,
            "compare_rejection": rejection,
            "exported_submission_fields": sorted(a_data["samples"][0]["submission"]),
            "call_kinds": {"a": [c["kind"] for c in a_data["calls"]], "b": [c["kind"] for c in b_data["calls"]]},
            "scope": "General comparison weakness; authorized seven built-ins have no vision call, so this input difference does not occur in that batch.",
        }

        changed = copy.deepcopy(loaded_b)
        changed["run_data"]["samples"][0]["submission"]["essay_text"] += " This is a changed essay."
        essay_errors, _ = compare.check_same_conditions(cond_a, compare.conditions(changed))
        changed = copy.deepcopy(loaded_b)
        changed["report"]["prompt_version"] = "deliberately-other-prompt"
        version_errors, _ = compare.check_same_conditions(cond_a, compare.conditions(changed))
        assert essay_errors and version_errors, "Existing guards should reject these controls"
        out["observations"]["positive_controls"] = {"changed_essay_errors": essay_errors, "changed_prompt_version_errors": version_errors}

        # Rendering fixtures exercise normalized fields, not model/validator semantics.
        t2_data, t2_report, _client, _dir = run("manual-base", "off", [samples[0]])
        t2 = copy.deepcopy(t2_data["samples"][0])
        result = t2["generations"]["evaluate"]["result"]
        assert isinstance(result, dict), "Need a successful real pipeline result for rendering fixture"
        result["argument"]["problems"] = [{
            "type": "position_inconsistent", "label": "立场前后不一致",
            "quote": "FIRST_CLAIM_MARKER", "comment": "两处立场需人工对照。",
            "conflicts_with": "PAIRED_CONFLICT_MARKER", "needs_review": True,
        }]
        task1_sample = copy.deepcopy(a_data["samples"][0])
        t1_result = task1_sample["generations"]["evaluate"]["result"]
        assert isinstance(t1_result, dict), "Need successful Task 1 fixture"
        t1_result["consistency_issues"] = [{
            "quote": "TASK1_CONTRADICTION_MARKER", "comment": "最高的说法与文内数值矛盾。",
            "figures": ["FIGURE_A_MARKER", "FIGURE_C_MARKER"],
        }]
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
            "task1_issue_preserved_in_view": "TASK1_CONTRADICTION_MARKER" in t1_view["consistency_issues"],
            "task1_issue_rendered": "TASK1_CONTRADICTION_MARKER" in sheet,
            "task1_figures_preserved_in_view": "FIGURE_A_MARKER" in json.dumps(t1_view["consistency_issues"]),
            "task1_figures_rendered": "FIGURE_A_MARKER" in sheet,
            "scope": "Applies to the planned evaluation-only Task 1 and Task 2 human comparison; raw run files retain omitted fields.",
        }

    payload = json.dumps(out, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(payload, encoding="utf-8")
    print(payload)


if __name__ == "__main__":
    main()
