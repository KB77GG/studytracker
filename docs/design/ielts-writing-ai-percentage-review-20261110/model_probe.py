"""Offline request/compare audit; synthetic data and in-memory HTTP stub only."""

from __future__ import annotations

import argparse
import copy
import dataclasses
import io
import json
import socket
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    sys.dont_write_bytecode = True
    sys.path.insert(0, str(args.repo))
    from tools.ielts_writing_ai import llm, realcheck, realcheck_compare, review
    from tools.ielts_writing_ai.config import load_settings

    checks, observations = [], {}

    def check(name, condition):
        checks.append({"name": name, "ok": bool(condition)})

    def no_network(*_args, **_kwargs):
        raise AssertionError("Network forbidden in this offline probe")

    with (
        tempfile.TemporaryDirectory(prefix="iwa-pro-wire-") as temporary,
        patch.object(socket.socket, "connect", no_network),
        patch.object(socket.socket, "connect_ex", no_network),
    ):
        tmp = Path(temporary)
        settings = load_settings(
            env={
                "IWA_LLM_PROVIDER": "deepseek",
                "IWA_LLM_MODEL": "deepseek-v4-pro",
                "IWA_LLM_API_KEY": "synthetic-stub-key",
                "IWA_EVALUATE_THINKING": "high",
                "IWA_DATA_DIR": str(tmp / "config-only"),
            },
            env_file=tmp / "does-not-exist.env",
        )
        settings.validate()
        check("model_config_unrestricted", settings.llm_model == "deepseek-v4-pro")
        captured = []
        client = llm.build_client(settings)

        def stub_open(request, timeout=None):
            captured.append({"body": json.loads(request.data), "timeout": timeout})
            response = {
                "model": "deepseek-v4-pro",
                "choices": [{"message": {"content": '{"ok":true}'}, "finish_reason": "stop"}],
                "usage": {"prompt_tokens": 10, "completion_tokens": 10},
            }
            return io.BytesIO(json.dumps(response).encode())

        generator = review.Generator(None, settings, client)
        with patch.object(client, "_open", stub_open):
            for kind in ("evaluate", "refine", "rewrite"):
                generator._call(
                    [{"role": "user", "content": "synthetic input"}],
                    kind,
                    {"kind": kind},
                    0,
                    4500,
                )
        body = captured[0]["body"]
        for name, expected in (
            ("model", "deepseek-v4-pro"),
            ("thinking", {"type": "enabled"}),
            ("reasoning_effort", "high"),
            ("max_tokens", 32000),
            ("response_format", {"type": "json_object"}),
        ):
            check("evaluate_" + name, body.get(name) == expected)
        check("evaluate_timeout_300", captured[0]["timeout"] == 300)
        for i, kind in enumerate(("refine", "rewrite"), 1):
            check(kind + "_unchanged_off", captured[i]["body"]["thinking"] == {"type": "disabled"})
            check(kind + "_ordinary_budget", captured[i]["body"]["max_tokens"] == 4500)
            check(kind + "_ordinary_timeout", captured[i]["timeout"] is None)
        observations["wire"] = captured

        items = realcheck.load_samples("builtin")[:1]
        duplicate_refused = False
        try:
            realcheck.run(settings, items + items, client=llm.FakeClient(), kinds=("evaluate",))
        except realcheck.RealCheckError as exc:
            duplicate_refused = "id 重复" in str(exc)
        check("duplicate_ids_refused_before_generation", duplicate_refused)

        a = realcheck.run(
            dataclasses.replace(settings, llm_model="deepseek-flash"),
            items,
            client=llm.FakeClient(model="deepseek-flash"),
            kinds=("evaluate",),
            max_calls=2,
        )
        b = realcheck.run(
            settings,
            items,
            client=llm.FakeClient(model="deepseek-v4-pro"),
            kinds=("evaluate",),
            max_calls=2,
        )
        for data in (a, b):
            check(
                "synthetic_generation_ready",
                data["samples"][0]["generations"]["evaluate"]["status"] == "ready",
            )
            call = data["calls"][0]
            call["usage"] = {
                "prompt_tokens": 1000,
                "completion_tokens": 2000,
                "prompt_cache_hit_tokens": 800,
                "prompt_cache_miss_tokens": 200,
            }
            result = data["samples"][0]["generations"]["evaluate"]["result"]
            for criterion in result["criteria"]:
                key = criterion["key"]
                criterion["summary"] = key + "_SUMMARY_SENTINEL"
                criterion["issues"] = [
                    {
                        "quote": "synthetic quote",
                        "comment": key + "_ISSUE_SENTINEL",
                        "suggestion": key + "_SUGGESTION_SENTINEL",
                    }
                ]
            result["overall_comment"] = "OVERALL_SENTINEL"
            result["priorities"] = ["PRIORITY_SENTINEL"]

        a_report = realcheck.build_report(a, price_in=1, price_out=4)
        b_report = realcheck.build_report(b, price_in=4.5, price_out=13.5)
        realcheck.write_report(a, a_report, tmp / "a")
        realcheck.write_report(b, b_report, tmp / "b")
        ca = realcheck_compare.conditions(realcheck_compare.load_run(tmp / "a"))
        cb = realcheck_compare.conditions(realcheck_compare.load_run(tmp / "b"))
        errors, _warnings = realcheck_compare.check_same_conditions(ca, cb)
        check("different_model_refused_without_flag", bool(errors))
        errors, warnings = realcheck_compare.check_same_conditions(ca, cb, allow_model_change=True)
        check("different_model_allowed_with_flag", not errors and bool(warnings))
        for key in ("prompt_version", "samples", "evaluate_inputs"):
            changed = copy.deepcopy(cb)
            if key == "prompt_version":
                changed[key] = "different-version"
            else:
                sid = next(iter(changed[key]))
                changed[key][sid] = "different"
            errs, _ = realcheck_compare.check_same_conditions(ca, changed, allow_model_change=True)
            check("reject_changed_" + key, bool(errs))
        changed = copy.deepcopy(cb)
        changed["evaluate_max_tokens"] = [16000]
        errors, warnings = realcheck_compare.check_same_conditions(
            ca, changed, allow_model_change=True
        )
        observations["different_budget_not_rejected"] = not errors
        check("request_budget_requires_external_guard", not errors)
        cmp = realcheck_compare.compare(tmp / "a", tmp / "b", allow_model_change=True)
        manual = realcheck_compare.render_manual_review(cmp)
        omissions = [
            s
            for s in (
                "grammar_SUMMARY_SENTINEL",
                "grammar_ISSUE_SENTINEL",
                "lexical_ISSUE_SENTINEL",
                "coherence_SUGGESTION_SENTINEL",
                "OVERALL_SENTINEL",
                "PRIORITY_SENTINEL",
            )
            if s not in manual
        ]
        observations["manual_omitted_markers"] = omissions
        observations["manual_is_unblinded"] = all(
            m in manual for m in ("deepseek-flash", "deepseek-v4-pro")
        )
        check("manual_omission_reproduced", len(omissions) == 6)
        check("manual_model_identity_visible", observations["manual_is_unblinded"])
        check(
            "manual_TR_CC_issue_positive_controls",
            "task_ISSUE_SENTINEL" in manual and "coherence_ISSUE_SENTINEL" in manual,
        )
        check(
            "compare_no_price_ignores_saved_cost",
            cmp["summary"]["a"]["estimated_cost"] is None
            and cmp["summary"]["b"]["estimated_cost"] is None,
        )
        priced = realcheck_compare.compare(
            tmp / "a", tmp / "b", allow_model_change=True, price_in=4.5, price_out=13.5
        )
        check(
            "compare_same_prices_applied_to_both",
            priced["summary"]["a"]["estimated_cost"]
            == priced["summary"]["b"]["estimated_cost"]
            == 0.0315,
        )
        observations["cost"] = {
            "same_usage": {"prompt": 1000, "hit": 800, "miss": 200, "output": 2000},
            "realcheck_simple_prices_flash": a_report["estimated_cost"],
            "realcheck_simple_prices_pro": b_report["estimated_cost"],
            "cache_aware_flash_if_rates_hit_002_miss_1_output_4": 0.008216,
            "cache_aware_pro_if_rates_hit_015_miss_45_output_135": 0.02802,
            "compare_with_pro_rates_both_sides": priced["summary"]["a"]["estimated_cost"],
        }

    result = {
        "repo": str(args.repo),
        "head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=args.repo, text=True
        ).strip(),
        "checks": checks,
        "passed": sum(c["ok"] for c in checks),
        "total": len(checks),
        "observations": observations,
        "real_requests": 0,
        "read_key_env_or_student_files": False,
        "changed_product": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({"passed": result["passed"], "total": result["total"], "real_requests": 0}))
    return 0 if result["passed"] == result["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
