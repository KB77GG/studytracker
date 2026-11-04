"""Offline regression review of argument validation; no credentials or network."""
from __future__ import annotations

import argparse
import copy
import json
import logging
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.repo.resolve()))
    from tools.ielts_writing_ai import argument, realcheck, review
    from tools.ielts_writing_ai.config import Settings
    from tools.ielts_writing_ai.llm import FakeClient
    from tools.ielts_writing_ai.tests.test_review import evaluation, submission

    logging.disable(logging.CRITICAL)
    expected_band = review.normalize_evaluation(evaluation(), submission())["overall_band"]
    rows = []
    for section, field in (("paragraphs", "role"), ("paragraphs", "verdict"), ("problems", "type")):
        for value in ("unknown_enum", [], {}, ["body"], {"role": "body"}, None, 3, True, 1.5):
            raw = evaluation()
            raw["argument"][section][0][field] = copy.deepcopy(value)
            result = review.normalize_evaluation(raw, submission())
            assert result["argument"]["dropped"] == 1
            assert result["overall_band"] == expected_band
            rows.append({"section": section, "field": field, "input": value,
                         "dropped": 1, "score_unchanged": True})

    class MutatedClient(FakeClient):
        def __init__(self, mode):
            super().__init__()
            self.mode = mode
            self.call_count = 0

        def complete(self, messages, **kwargs):
            self.call_count += 1
            result = super().complete(messages, **kwargs)
            raw = json.loads(result.text)
            if self.mode == "one_bad_first" and self.call_count == 1:
                raw["argument"]["paragraphs"][0]["role"] = ["introduction"]
            if self.mode == "all_bad_always" or (self.mode == "all_bad_first" and self.call_count == 1):
                for paragraph in raw["argument"]["paragraphs"]:
                    paragraph["role"] = ["body"]
            result.text = json.dumps(raw)
            return result

    settings = Settings(llm_provider="fake", vision_provider="none")
    pipeline = []
    for mode, expected_calls, expected_status in (
        ("control", 1, "ready"),
        ("one_bad_first", 1, "ready"),
        ("all_bad_first", 2, "ready"),
        ("all_bad_always", 2, "failed"),
    ):
        client = MutatedClient(mode)
        data = realcheck.run(settings, realcheck.load_samples("builtin")[:1],
                             client=client, kinds=("evaluate",), max_calls=2)
        generation = data["samples"][0]["generations"]["evaluate"]
        assert generation["status"] == expected_status
        assert client.call_count == len(client.calls) == len(data["calls"]) == expected_calls
        for call in data["calls"]:
            assert call["ok"] and call["json_ok"] and call["response_received"]
            assert call["http_status"] == 200
        first_role = json.loads(data["calls"][0]["text"])["argument"]["paragraphs"][0]["role"]
        if mode != "control":
            assert isinstance(first_role, list)
        if mode == "all_bad_always":
            assert generation["error_code"] == "invalid_output"
        if mode == "one_bad_first":
            assert generation["result"]["argument"]["dropped"] == 1
        report = realcheck.build_report(data)
        markdown = realcheck.render_markdown(report)
        assert "## 合格率" in markdown
        if expected_status == "ready":
            assert "## 论证结构" in markdown
        pipeline.append({
            "mode": mode, "calls": client.call_count, "status": generation["status"],
            "error_code": generation.get("error_code"), "first_role": first_role,
            "all_responses_successful_json": True,
            "first_attempt_valid": report["kinds"]["evaluate"]["first_attempt_valid"],
            "rejected_for_argument": report["argument"]["attempts_rejected_for_argument"],
            "report_rendered": True,
            "argument_section_visible": "## 论证结构" in markdown,
        })

    prefix = "Public transport helps people travel safely. " * 12
    original = prefix + "This is the original ending."
    false_quote = prefix + "This invented ending does not occur in the essay."
    para = {"role": "body", "verdict": "supports", "main_point": false_quote}
    try:
        argument.normalize({"paragraphs": [para]}, original)
    except argument.ArgumentInvalid as error:
        rejected_reason = str(error)
    else:
        raise AssertionError("invented ending in the only paragraph was accepted")
    legit_para = {"role": "body", "verdict": "supports", "main_point": original}
    verified = argument.normalize({"paragraphs": [legit_para]}, original)
    assert len(verified["paragraphs"][0]["main_point"]) == 400
    assert verified["dropped"] == 0
    for slot in ("position", "paragraph", "problem"):
        raw = {"paragraphs": [legit_para]}
        if slot == "position":
            raw["position"] = {"quote": false_quote, "consistent": True}
        elif slot == "paragraph":
            raw["paragraphs"].append(para)
        else:
            raw["problems"] = [{"type": "unsupported", "quote": false_quote, "comment": "c"}]
        mapped = argument.normalize(raw, original)
        assert mapped["dropped"] == 1
        assert len(mapped["paragraphs"]) == 1
        assert not mapped["position"] and not mapped["problems"]
    evidence = review._evidence_items(
        [{"quote": false_quote, "comment": "c"}, {"quote": original, "comment": "c"}],
        original, limit=4, with_suggestion=False,
    )
    assert [row["quote_found"] for row in evidence] == [False, True]
    assert all(len(row["quote"]) == 300 for row in evidence)
    summary = {
        "source_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=args.repo, text=True).strip(),
        "network_calls": 0, "passed": True, "enum_cases": rows, "pipeline": pipeline,
        "full_quote_verification": {
            "single_false_paragraph_rejected": rejected_reason,
            "position_paragraph_problem_false_suffix_dropped": True,
            "real_long_argument_quote_display_length": 400,
            "criterion_fake_real_quote_found": [False, True],
            "criterion_display_length": 300,
        },
    }
    text = json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
    args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
