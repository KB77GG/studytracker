"""Offline request / image-freeze audit. Synthetic inputs; network denied.

This probe asserts desired behavior, so a false check is a remaining finding.
Product code is never modified. All fake runs and ledger files are temporary.
"""
from __future__ import annotations

import argparse
import copy
import io
import json
import os
import subprocess
import sys
import tempfile
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.repo))
    sys.dont_write_bytecode = True

    def deny(event, _args):
        if event in {"socket.connect", "socket.getaddrinfo"}:
            raise RuntimeError("Offline source probe forbids network")

    sys.addaudithook(deny)
    from tools.ielts_writing_ai import __main__ as cli
    from tools.ielts_writing_ai import batch, ledger, realcheck, realcheck_compare
    from tools.ielts_writing_ai.config import load_settings
    from tools.ielts_writing_ai.llm import FakeClient, LLMResult
    from tools.ielts_writing_ai.tests.helpers import PNG_BYTES, settings_for

    class Spy(FakeClient):
        def __init__(self, model="fake-flash"):
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

    checks, observations = [], {}

    def check(name, actual, expected):
        checks.append(dict(name=name, actual=actual, expected=expected, ok=actual == expected))

    def hashes(client):
        return [realcheck._messages_sha(m) for m, _ in client.requests]

    text = (
        "Universities can make education available to more people. I support public funding "
        "because some families cannot pay the fees.\n"
        "However, funding every place requires a budget. Governments should explain how "
        "they will cover the cost without reducing essential services.\n"
        "In conclusion, assistance should focus on students who need it most."
    )
    item = dict(id="synthetic-privacy", task_type="task2", prompt="Should university education be publicly funded?", essay=text)
    marks = ["LOCAL_RATER_MARKER", "LOCAL_TEACHER_COMMENT_MARKER", "LOCAL_GROUP_MARKER", "LOCAL_CONDITION_MARKER"]
    annotated = dict(item, teacher={"overall": 8.5}, teachers=[{"rater": marks[0], "overall": 8.5}], teacher_comment=marks[1], teacher_comment_unmapped=marks[1], teacher_findings=[{"quote": text.split(". ")[0]+".", "note": marks[1]}], group=marks[2], nominal_band=8.5, conditions=marks[3])
    with tempfile.TemporaryDirectory(prefix="iwa-source-recheck-") as rawtmp:
        tmp = Path(rawtmp)

        def settings(name, model="fake-flash"):
            return settings_for(str(tmp / name), llm_model=model, evaluate_thinking="high", evaluate_thinking_max_tokens=32000, evaluate_thinking_timeout=300)

        def save(data, folder):
            realcheck.write_report(data, realcheck.build_report(data), folder)

        plain, rich, pro = Spy(), Spy(), Spy("fake-pro")
        realcheck.run(settings("plain"), [item], client=plain, kinds=("evaluate",))
        rich_data = realcheck.run(settings("rich"), realcheck.expand_repeats([annotated], 2), client=rich, kinds=("evaluate",))
        realcheck.run(settings("pro", "fake-pro"), realcheck.expand_repeats([annotated], 2), client=pro, kinds=("evaluate",))
        check("teacher_metadata_absent_from_messages_and_context", any(m in json.dumps(rich.requests) for m in marks), False)
        check("labels_do_not_change_model_messages", hashes(rich), hashes(plain) * 2)
        check("models_and_repeats_receive_identical_messages", hashes(pro), hashes(plain) * 2)
        check("teacher_score_retained_locally", rich_data["samples"][0]["teacher"]["overall"], 8.5)
        for name, client in (("flash", rich), ("pro", pro)):
            check(f"{name}.options", [{k: v.get(k) for k in ("thinking", "max_tokens", "timeout", "json_mode", "retries")} for _, v in client.requests], [dict(thinking="high", max_tokens=32000, timeout=300, json_mode=True, retries=0)] * 2)

        image = tmp / "chart.png"
        image.write_bytes(PNG_BYTES)
        t1 = dict(id="synthetic-chart", task_type="task1", prompt="Describe the chart.", essay="The chart compares four museums. Museum C has the greatest number of visitors, while Museum D has the fewest. Museum A is ahead of Museum B.", image=str(image))
        vision = Spy("fake-vision")
        good = realcheck.run(settings("good"), realcheck.expand_repeats([t1], 2), client=Spy(), vision_client=vision, kinds=("evaluate",))
        save(good, tmp / "good-out")
        reused = realcheck.expand_repeats([t1], 2)
        check("ready_image_reused_for_both_repeats", realcheck.apply_image_descriptions(reused, tmp / "good-out/image_descriptions.json", require_ready=True), 2)
        good_pro = realcheck.run(settings("good-pro", "fake-pro"), reused, client=Spy("fake-pro"), kinds=("evaluate",))
        save(good_pro, tmp / "good-pro-out")
        check("ready_image_read_once", len(vision.requests), 1)
        check("ready_image_pro_zero_vision_calls", sum(c["kind"] == "describe_image" for c in good_pro["calls"]), 0)
        check("ready_image_messages_equal", [c["input_sha256"] for c in good["calls"] if c["kind"] == "evaluate"], [c["input_sha256"] for c in good_pro["calls"]])
        check("ready_image_compare_accepts", len(realcheck_compare.compare(tmp / "good-out", tmp / "good-pro-out", allow_model_change=True)["samples"]), 2)

        unreliable = FirstUnreadable("fake-vision")
        bad = realcheck.run(settings("bad"), realcheck.expand_repeats([t1], 2), client=Spy(), vision_client=unreliable, kinds=("evaluate",))
        save(bad, tmp / "bad-out")
        reused = realcheck.expand_repeats([t1], 2)
        realcheck.apply_image_descriptions(reused, tmp / "bad-out/image_descriptions.json")
        bad_pro = realcheck.run(settings("bad-pro", "fake-pro"), reused, client=Spy("fake-pro"), kinds=("evaluate",))
        save(bad_pro, tmp / "bad-pro-out")
        check("unreadable_then_readable_reads_once", len(unreliable.requests), 1)
        check("unreadable_result_frozen_across_repeats", [s["image_status"] for s in bad["samples"]], ["failed", "failed"])
        check("unreadable_result_frozen_across_models", [s["image_status"] for s in bad_pro["samples"]], ["failed", "failed"])
        check("unreadable_actual_messages_identical", [c["input_sha256"] for c in bad["calls"] if c["kind"] == "evaluate"], [c["input_sha256"] for c in bad_pro["calls"]])
        try:
            realcheck_compare.compare(tmp / "bad-out", tmp / "bad-pro-out", allow_model_change=True)
            compare_errors = []
        except realcheck_compare.CompareError as exc:
            compare_errors = [str(exc)]
        observations["failed_reading_comparison"] = {"error": compare_errors, "first_description": bad["samples"][0]["submission"]["image_description"], "repeat_description": bad["samples"][1]["submission"]["image_description"], "pro_description": bad_pro["samples"][0]["submission"]["image_description"]}
        check("unreadable_frozen_comparison_accepts_identical_messages", compare_errors, [])

        # Poisoned inherited IWA settings must not influence either child.
        env_file = tmp / "fake.env"
        env_file.write_text("IWA_LLM_PROVIDER=fake\nIWA_VISION_PROVIDER=fake\n")
        poisoned = {"IWA_LLM_PROVIDER":"qwen", "IWA_LLM_MODEL":"poison", "IWA_LLM_BASE_URL":"https://example.invalid/v1", "IWA_EVALUATE_THINKING":"off", "IWA_EVALUATE_THINKING_MAX_TOKENS":"3", "IWA_EVALUATE_THINKING_TIMEOUT":"4", "IWA_VISION_PROVIDER":"none", "IWA_DATA_DIR":str(tmp / "must-not-write")}
        with mock.patch.dict(os.environ, poisoned):
            for key in ("flash", "pro"):
                child = batch.child_env(key, dry=True, env_file=env_file, out=tmp / "env-out")
                conf = load_settings(env=child, env_file=child["IWA_ENV_FILE"])
                check(f"{key}.inherited_env_isolated", (conf.llm_provider, conf.llm_model, conf.evaluate_thinking, conf.evaluate_thinking_max_tokens, conf.evaluate_thinking_timeout, conf.vision_provider), ("fake", f"fake-{key}", "high", 32000, 300, "fake"))
            child = batch.child_env("pro", dry=False, env_file=env_file, out=tmp / "env-paid-shape")
            conf = load_settings(env=child, env_file=env_file)
            check("paid_request_config_forced_without_any_request", (conf.llm_provider, conf.llm_model, conf.llm_base_url, conf.evaluate_thinking, conf.evaluate_thinking_max_tokens, conf.evaluate_thinking_timeout), ("deepseek", "deepseek-v4-pro", batch.OFFICIAL_ENDPOINT, "high", 32000, 300))
        check("poisoned_data_dir_not_created", (tmp / "must-not-write").exists(), False)

        # Each category is refused before dispatch, independent of total max_calls.
        def book(name, text_cap, vision_cap):
            return ledger.Ledger(tmp / (name + ".jsonl"), text_cap=text_cap, vision_cap=vision_cap, run=name, code_sha256=realcheck.code_fingerprint(), prompt_version=realcheck.review.prompts.PROMPT_VERSION)
        capped_text = Spy()
        capped = realcheck.run(settings("text-capped"), realcheck.expand_repeats([item], 2), client=capped_text, kinds=("evaluate",), max_calls=50, ledger=book("text-cap", 1, 0))
        check("text_cap_blocks_before_second_dispatch", (len(capped_text.requests), capped["aborted"]["code"]), (1, "ledger_cap"))
        capped_vision = Spy("fake-vision")
        capped = realcheck.run(settings("image-capped"), [t1], client=Spy(), vision_client=capped_vision, kinds=(), max_calls=50, ledger=book("vision-cap", 3, 0))
        check("vision_cap_zero_blocks_before_dispatch", (len(capped_vision.requests), capped["aborted"]["code"]), (0, "ledger_cap"))

        # Pinned code/model/mode/price conditions are enforced before any child.
        manifest_out = tmp / "manifest"
        manifest_out.mkdir()
        manifest_args = SimpleNamespace(dry=True)
        batch._record_batch(manifest_out, "vision", manifest_args, {}, 8)
        batch._record_batch(manifest_out, "vision", manifest_args, {}, 9)
        check("authorized_cap_change_has_history", [c["cap"] for c in json.loads((manifest_out / "batch-vision.json").read_text())["caps"]], [8, 9])
        try:
            batch._record_batch(manifest_out, "vision", manifest_args, {"flash": {"in": 2}}, 9)
            changed_price = 0
        except batch.Stop as exc:
            changed_price = exc.code
        check("changed_price_condition_refused", changed_price, 2)

        # The actual batch/CLI paths run with an in-process fake child transport.
        # CLI options, environment, persistent ledger and result files remain real.
        data = tmp / "batch-data"
        data.mkdir()
        source = data / "holdout_rated_t1.jsonl"
        source.write_text(json.dumps(t1) + "\n")

        def stage(out, vision_client=None, stop_pro=False):
            text_spies, launched = [], []
            def factory(conf, vision=False):
                if vision:
                    return vision_client or Spy("fake-vision")
                s = Spy(conf.llm_model)
                text_spies.append(s)
                return s
            def child(command, **kw):
                run_name = Path(command[command.index("--out") + 1]).name
                launched.append(run_name)
                if stop_pro and run_name.endswith("-pro"):
                    return subprocess.CompletedProcess(command, -15)
                with mock.patch.dict(os.environ, kw["env"], clear=True):
                    code = cli.main(["--env-file", kw["env"]["IWA_ENV_FILE"], *command[3:]])
                return subprocess.CompletedProcess(command, code)
            argv = SimpleNamespace(stage="vision", data=str(data), out=str(out), dry=True, cap=8, price=None, env_file=str(env_file))
            stdout, stderr = io.StringIO(), io.StringIO()
            with mock.patch.object(batch.subprocess, "run", side_effect=child), mock.patch.object(realcheck, "build_client", side_effect=factory), redirect_stdout(stdout), redirect_stderr(stderr):
                code = batch.run_stage(argv)
            counts = ledger.summarize(ledger.read(out / "ledger-vision.jsonl"))
            return {"exit": code, "launched": launched, "text_sent": sum(len(s.requests) for s in text_spies), "text_reserved": counts["text"]["reserved"], "vision_reserved": counts["vision"]["reserved"], "stderr": stderr.getvalue()}

        fail_out = tmp / "failed-batch"
        bad_vision = FirstUnreadable("fake-vision")
        failed_stage = stage(fail_out, bad_vision)
        check("images_only_failure_stops_stage", failed_stage["exit"], 5)
        check("images_only_failure_sends_zero_text", failed_stage["text_sent"], 0)
        check("images_only_failure_reads_once", len(bad_vision.requests), 1)
        check("failed_stage_ledger_categories", (failed_stage["text_reserved"], failed_stage["vision_reserved"]), (0, 1))
        check("failed_stage_has_no_done", list(fail_out.glob("*/.done")), [])
        frozen = json.loads((fail_out / "rated_t1-images/image_descriptions.json").read_text())
        check("failed_reading_saved_to_version2_file", (frozen["version"], frozen["images"][t1["id"]]["status"]), (2, "failed"))
        fail_resume = stage(fail_out, bad_vision)
        check("failed_image_resume_refused_before_request", (fail_resume["exit"], fail_resume["launched"], len(bad_vision.requests)), (2, [], 1))
        observations["failed_stage"] = failed_stage
        observations["failed_stage_resume"] = fail_resume

        success_out = tmp / "success-batch"
        success_stage = stage(success_out)
        check("successful_vision_stage_counts", (success_stage["exit"], success_stage["text_reserved"], success_stage["vision_reserved"]), (0, 4, 1))
        success_resume = stage(success_out)
        check("unchanged_resume_no_calls", (success_resume["exit"], success_resume["launched"], success_resume["text_sent"]), (0, [], 0))
        source.write_text(json.dumps(dict(t1, essay=t1["essay"] + " The exhibition was open every weekend.")) + "\n")
        changed_complete = stage(success_out)
        observations["completed_input_changed"] = changed_complete
        check("completed_resume_refuses_changed_source", changed_complete["exit"], 2)
        check("completed_resume_no_paid_calls", changed_complete["text_sent"], 0)

        source.write_text(json.dumps(t1) + "\n")
        partial_out = tmp / "partial-batch"
        interrupted = stage(partial_out, stop_pro=True)
        check("partial_setup_stopped_after_flash", (interrupted["exit"], interrupted["text_reserved"], interrupted["vision_reserved"]), (3, 2, 1))
        source.write_text(json.dumps(dict(t1, essay=t1["essay"] + " The exhibition was open every weekend.")) + "\n")
        changed_partial = stage(partial_out)
        observations["partial_input_changed"] = changed_partial
        check("partial_resume_refuses_changed_source_before_calls", (changed_partial["exit"], changed_partial["text_sent"]), (2, 0))

    result = dict(repo=str(args.repo), paid_calls=0, network_forbidden=True, checks=checks, passed=sum(c["ok"] for c in checks), total=len(checks), observations=observations)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2, default=str) + "\n")
    print(json.dumps({"passed": result["passed"], "total": result["total"], "failures": [c for c in checks if not c["ok"]]}, ensure_ascii=False, default=str))
    return 0 if all(c["ok"] for c in checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
