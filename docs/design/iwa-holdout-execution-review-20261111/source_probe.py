"""Offline request isolation / shared-chart audit. Synthetic essays and fake clients only."""
from __future__ import annotations

import argparse
import copy
import json
import sys
import tempfile
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()
    sys.path.insert(0, str(args.repo))
    sys.dont_write_bytecode = True

    def block_network(event, _args):
        if event in {"socket.connect", "socket.getaddrinfo"}:
            raise RuntimeError("This offline audit forbids network access")

    sys.addaudithook(block_network)
    from tools.ielts_writing_ai import realcheck, realcheck_compare
    from tools.ielts_writing_ai.llm import FakeClient, LLMResult
    from tools.ielts_writing_ai.tests.helpers import settings_for, PNG_BYTES

    class Spy(FakeClient):
        def __init__(self, model):
            super().__init__(model=model)
            self.requests = []

        def complete(self, messages, **kwargs):
            self.requests.append((copy.deepcopy(messages), copy.deepcopy(kwargs)))
            return super().complete(messages, **kwargs)

    class FirstUnreadable(Spy):
        def complete(self, messages, **kwargs):
            if not self.requests:
                self.requests.append((copy.deepcopy(messages), copy.deepcopy(kwargs)))
                return LLMResult("The uploaded image is unreadable.", self.model, 1)
            return super().complete(messages, **kwargs)

    rows = []
    def check(name, actual, expected):
        rows.append(dict(name=name, actual=actual, expected=expected, ok=actual == expected))

    text = (
        "Universities can make education available to more people. I support public funding "
        "because some families cannot pay the fees.\n"
        "However, funding every place requires a budget. Governments should explain how "
        "they will cover the cost without reducing essential services.\n"
        "In conclusion, assistance should focus on students who need it most."
    )
    item = dict(id="synthetic-privacy", task_type="task2", prompt="Should university education be publicly funded?", essay=text)
    marks = ["PRIVATE_RATER_A_MARKER", "PRIVATE_TEACHER_COMMENT_MARKER", "PRIVATE_GROUP_MARKER", "PRIVATE_CONDITION_MARKER"]
    annotated = dict(item, teacher={"overall": 8.5}, teachers=[{"rater": marks[0], "overall": 8.5}], teacher_comment=marks[1], teacher_comment_unmapped=marks[1], teacher_findings=[{"quote": "Universities can make education available to more people.", "note": marks[1]}], group=marks[2], nominal_band=8.5, conditions=marks[3])
    with tempfile.TemporaryDirectory(prefix="iwa-source-review-") as tmp:
        tmp = Path(tmp)
        def settings(name, model="fake-flash"):
            return settings_for(str(tmp / name), llm_model=model, evaluate_thinking="high", evaluate_thinking_max_tokens=32000, evaluate_thinking_timeout=300)
        plain, rich, pro = Spy("fake-flash"), Spy("fake-flash"), Spy("fake-pro")
        a = realcheck.run(settings("plain"), [item], client=plain, kinds=("evaluate",))
        b = realcheck.run(settings("rich"), realcheck.expand_repeats([annotated], 2), client=rich, kinds=("evaluate",))
        c = realcheck.run(settings("pro", "fake-pro"), realcheck.expand_repeats([annotated], 2), client=pro, kinds=("evaluate",))
        check("metadata_does_not_change_model_messages", [realcheck._messages_sha(m) for m, _ in rich.requests], [realcheck._messages_sha(plain.requests[0][0])] * 2)
        check("model_change_does_not_change_messages", [realcheck._messages_sha(m) for m, _ in pro.requests], [realcheck._messages_sha(plain.requests[0][0])] * 2)
        check("no_private_markers_in_messages_or_context", any(marker in json.dumps(rich.requests) for marker in marks), False)
        check("metadata_preserved_for_local_review", b["samples"][0]["teacher"]["overall"], 8.5)
        for name, client in (("flash", rich), ("pro", pro)):
            check(f"{name}.request_options", [{k: opts.get(k) for k in ("thinking", "max_tokens", "timeout", "json_mode", "retries")} for _, opts in client.requests], [{"thinking": "high", "max_tokens": 32000, "timeout": 300, "json_mode": True, "retries": 0}] * 2)
        check("repeat_distinct_ids", [s["id"] for s in b["samples"]], ["synthetic-privacy", "synthetic-privacy#r2"])
        check("repeat_input_fingerprint_equal", len(set(c["input_sha256"] for c in b["calls"])), 1)

        chart = tmp / "chart.png"
        chart.write_bytes(PNG_BYTES)
        t1 = dict(id="synthetic-chart", task_type="task1", prompt="Describe the chart.", essay="The chart compares four museums. Museum C has the greatest number of visitors, while Museum D has the fewest. Museum A is ahead of Museum B.", image=str(chart))
        images = Spy("fake-vision")
        good = realcheck.run(settings("good"), realcheck.expand_repeats([t1], 2), client=Spy("fake-flash"), vision_client=images, kinds=("evaluate",))
        check("successful_vision_once_per_essay", len(images.requests), 1)
        good_dir = tmp / "good-out"
        realcheck.write_report(good, realcheck.build_report(good), good_dir)
        later = realcheck.expand_repeats([t1], 2)
        check("all_successful_readings_reused", realcheck.apply_image_descriptions(later, good_dir / "image_descriptions.json"), 2)
        good_pro = realcheck.run(settings("good-pro", "fake-pro"), later, client=Spy("fake-pro"), kinds=("evaluate",))
        good_pro_dir = tmp / "good-pro-out"
        realcheck.write_report(good_pro, realcheck.build_report(good_pro), good_pro_dir)
        check("successful_vision_model_messages_equal", [c["input_sha256"] for c in good["calls"] if c["kind"] == "evaluate"], [c["input_sha256"] for c in good_pro["calls"]])
        check("successful_vision_pro_zero_calls", sum(c["kind"] == "describe_image" for c in good_pro["calls"]), 0)
        check("successful_vision_compare_samples", len(realcheck_compare.compare(good_dir, good_pro_dir, allow_model_change=True)["samples"]), 2)

        unreliable = FirstUnreadable("fake-vision")
        changed = realcheck.run(settings("changing"), realcheck.expand_repeats([t1], 2), client=Spy("fake-flash"), vision_client=unreliable, kinds=("evaluate",), max_calls=6)
        changed_dir = tmp / "changing-out"
        realcheck.write_report(changed, realcheck.build_report(changed), changed_dir)
        reused = realcheck.expand_repeats([t1], 2)
        realcheck.apply_image_descriptions(reused, changed_dir / "image_descriptions.json")
        changed_pro = realcheck.run(settings("changing-pro", "fake-pro"), reused, client=Spy("fake-pro"), kinds=("evaluate",))
        changed_pro_dir = tmp / "changing-pro-out"
        realcheck.write_report(changed_pro, realcheck.build_report(changed_pro), changed_pro_dir)
        try:
            realcheck_compare.compare(changed_dir, changed_pro_dir, allow_model_change=True)
            compare_errors = []
        except realcheck_compare.CompareError as exc:
            compare_errors = [str(exc)]
        vision_boundary = dict(vision_calls=len(unreliable.requests), expected_unique_essay_reads=1, flash_image_statuses=[s["image_status"] for s in changed["samples"]], pro_image_statuses=[s["image_status"] for s in changed_pro["samples"]], flash_input_hashes=[c["input_sha256"] for c in changed["calls"] if c["kind"] == "evaluate"], pro_input_hashes=[c["input_sha256"] for c in changed_pro["calls"]], compare_errors=compare_errors, text_calls_before_rejection=sum(c["kind"] == "evaluate" for c in changed["calls"] + changed_pro["calls"]))
        check("vision_failure_boundary_reproduced", vision_boundary["vision_calls"] == 2 and vision_boundary["flash_image_statuses"] == ["failed", "ready"] and bool(compare_errors), True)
    result = dict(repo=str(args.repo), paid_calls=0, network_forbidden=True, checks=rows, passed=sum(r["ok"] for r in rows), total=len(rows), vision_failure_boundary=vision_boundary)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k:result[k] for k in ("passed","total","paid_calls","vision_failure_boundary")}, ensure_ascii=False))
    return 0 if all(r["ok"] for r in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
