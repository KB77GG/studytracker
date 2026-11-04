"""Offline argument enum-validation probe; no credentials or network.

Run with --repo pointing to the reviewed tree. It records behavior rather than
asserting the defect, so rerun JSON can be compared after a fix.
"""
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
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    sys.path.insert(0, str(args.repo.resolve()))
    from tools.ielts_writing_ai import argument, realcheck, review
    from tools.ielts_writing_ai.config import Settings
    from tools.ielts_writing_ai.llm import FakeClient
    from tools.ielts_writing_ai.tests.test_review import evaluation, submission

    logging.disable(logging.CRITICAL)
    rows = []
    for section, field in (
        ("paragraphs", "role"),
        ("paragraphs", "verdict"),
        ("problems", "type"),
    ):
        for value in ("unknown_enum", [], {}):
            raw = evaluation()
            raw["argument"][section][0][field] = copy.deepcopy(value)
            row = {"section": section, "field": field, "input": value}
            try:
                result = review.normalize_evaluation(raw, submission())
                row.update(outcome="normalized", dropped=result["argument"]["dropped"])
            except Exception as error:
                row.update(outcome="exception", exception=type(error).__name__, message=str(error))
            rows.append(row)

    class MalformedFirstClient(FakeClient):
        def __init__(self):
            super().__init__()
            self.call_count = 0

        def complete(self, messages, **kwargs):
            self.call_count += 1
            result = super().complete(messages, **kwargs)
            if self.call_count == 1:
                raw = json.loads(result.text)
                raw["argument"]["paragraphs"][0]["role"] = ["introduction"]
                result.text = json.dumps(raw)
            return result

    client = MalformedFirstClient()
    settings = Settings(llm_provider="fake", vision_provider="none")
    run_data = realcheck.run(
        settings,
        realcheck.load_samples("builtin")[:1],
        client=client,
        kinds=("evaluate",),
        max_calls=2,
    )
    generation = run_data["samples"][0]["generations"]["evaluate"]
    first_call = run_data["calls"][0]
    assert first_call["ok"] is True and first_call["json_ok"] is True
    assert first_call["response_received"] is True and first_call["http_status"] == 200
    assert json.loads(first_call["text"])["argument"]["paragraphs"][0]["role"] == ["introduction"]
    assert len(client.calls) == client.call_count
    control = realcheck.run(
        settings,
        realcheck.load_samples("builtin")[:1],
        client=FakeClient(),
        kinds=("evaluate",),
        max_calls=2,
    )
    control_generation = control["samples"][0]["generations"]["evaluate"]
    assert control_generation["status"] == "ready"

    # Distinguish the full model quote from the intentionally truncated display.
    prefix = "Public transport helps people travel safely. " * 12
    original = prefix + "This is the original ending."
    quote = prefix + "This invented ending does not occur in the essay."
    normalized = argument.normalize(
        {"paragraphs": [{"role": "body", "verdict": "supports", "main_point": quote}]},
        original,
    )
    truncation = {
        "raw_quote_exists": quote in original,
        "displayed_quote_exists": normalized["paragraphs"][0]["main_point"] in original,
        "displayed_length": len(normalized["paragraphs"][0]["main_point"]),
        "dropped": normalized["dropped"],
        "interpretation": "Full raw quote was not verified, but no invented suffix is displayed; not a separate blocking finding.",
    }
    report = {
        "source_head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=args.repo, text=True
        ).strip(),
        "network_calls": 0,
        "enum_cases": rows,
        "pipeline": {
            "first_response": "otherwise valid FakeClient JSON with role: [introduction]",
            "second_response_if_requested": "valid FakeClient JSON",
            "actual_fake_calls": client.call_count,
            "recorded_response": {
                key: first_call[key]
                for key in ("ok", "error", "json_ok", "response_received", "http_status", "usage")
            },
            "recorded_first_role": json.loads(first_call["text"])["argument"]["paragraphs"][0]["role"],
            "unmodified_fake_control": {
                "status": control_generation["status"],
                "calls": len(control["calls"]),
            },
            "status": generation["status"],
            "error_code": generation.get("error_code"),
            "error_message": generation.get("error_message"),
        },
        "truncation_observation": truncation,
    }
    text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
