"""Read-only offline audit and numeric-only export; never calls a model."""

import argparse
import hashlib
import json
import math
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-run", type=Path, required=True)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    root = args.private_run
    data = json.loads((root / "official-t2/run_data.json").read_text())
    report = json.loads((root / "official-t2/report.json").read_text())
    authorization = json.loads((root / "authorization.json").read_text())
    events = [json.loads(line) for line in (root / "ledger-t2.jsonl").read_text().splitlines()]
    reserves = [e for e in events if e["type"] == "reserve"]
    completed = [e for e in events if e["type"] == "done"]
    checks = {}

    def check(name, value):
        checks[name] = bool(value)
        if not value:
            raise AssertionError(name)

    check("exit_zero", json.loads((root / "launcher_exit.json").read_text())["code"] == 0)
    check(
        "cap_four_vision_zero", authorization["text_cap"] == 4 and authorization["vision_cap"] == 0
    )
    check(
        "two_calls_two_reservations_two_completions",
        len(data["calls"]) == len(reserves) == len(completed) == 2,
    )
    check("no_unknown_requests", {e["id"] for e in reserves} == {e["id"] for e in completed})
    check(
        "all_reserved_before_completion",
        all(
            next(
                i for i, e in enumerate(events) if e.get("id") == r["id"] and e["type"] == "reserve"
            )
            < next(
                i for i, e in enumerate(events) if e.get("id") == r["id"] and e["type"] == "done"
            )
            for r in reserves
        ),
    )
    check(
        "evaluate_only_cap_four",
        all(
            e["category"] == "text" and e["kind"] == "evaluate" and e["cap"] == 4 for e in reserves
        ),
    )
    check("same_message_fingerprint", len({c["input_sha256"] for c in data["calls"]}) == 1)
    check(
        "same_sample_repeated_twice",
        [s["id"] for s in data["samples"]] == ["official-2B-A", "official-2B-A#r2"],
    )
    check(
        "input_snapshot_hash",
        hashlib.sha256((root / "source-input.private.jsonl").read_bytes()).hexdigest()
        == authorization["sample_file_sha256"],
    )
    check("no_vision", report["vision_calls"] == 0 and not data["image_outcomes"])
    check("no_abort", report["aborted"] is None)
    files = subprocess.check_output(
        ["git", "ls-files", "tools/ielts_writing_ai"], cwd=args.source, text=True
    ).splitlines()
    check(
        "product_files_unchanged",
        all(
            (args.source / name).read_bytes()
            == subprocess.check_output(
                ["git", "show", authorization["source_head"] + ":" + name], cwd=args.source
            )
            for name in files
        ),
    )
    rows = []
    costs = []
    for sample, call, reserved, done in zip(
        data["samples"], data["calls"], reserves, completed, strict=True
    ):
        result = sample["generations"]["evaluate"]
        check(sample["id"] + ":ready", result["status"] == "ready")
        check(
            sample["id"] + ":first_attempt_json",
            call["ok"] and call["json_ok"] and call["attempt"] == 0,
        )
        check(
            sample["id"] + ":pro_high_32000",
            call["model"] == "deepseek-v4-pro"
            and call["thinking"] == "high"
            and call["max_tokens"] == 32000,
        )
        check(sample["id"] + ":ledger_identity", call["ledger_id"] == reserved["id"] == done["id"])
        check(
            sample["id"] + ":offpeak", all("2026-11-13T08:" in e["time"] for e in (reserved, done))
        )
        u = call["usage"]
        check(
            sample["id"] + ":usage_matches_ledger",
            all(
                u[k] == done["tokens"][k]
                for k in ("prompt_tokens", "completion_tokens", "prompt_cache_hit_tokens")
            ),
        )
        check(
            sample["id"] + ":usage_total",
            u["total_tokens"] == u["prompt_tokens"] + u["completion_tokens"],
        )
        check(
            sample["id"] + ":reasoning_in_output",
            0 <= call["reasoning_tokens"] <= u["completion_tokens"] < call["max_tokens"],
        )
        bands = {c["key"]: c["band"] for c in result["result"]["criteria"]}
        overall = result["result"]["overall_band"]
        check(
            sample["id"] + ":overall_server_rounding",
            math.floor(sum(bands.values()) / 4 * 2 + 0.5) / 2 == overall,
        )
        miss = u["prompt_tokens"] - u["prompt_cache_hit_tokens"]
        cost = (
            miss * 4.5 + u["prompt_cache_hit_tokens"] * 0.15 + u["completion_tokens"] * 13.5
        ) / 1_000_000
        costs.append(cost)
        rows.append(
            {
                "id": sample["id"],
                "status": result["status"],
                "official_overall": 5.5,
                "bands": bands,
                "overall": overall,
                "error_ai_minus_official": overall - 5.5,
                "latency_ms": call["latency_ms"],
                "input_tokens": u["prompt_tokens"],
                "cached_input_tokens": u["prompt_cache_hit_tokens"],
                "uncached_input_tokens": miss,
                "output_tokens_including_reasoning": u["completion_tokens"],
                "reasoning_tokens": call["reasoning_tokens"],
                "estimated_cny": round(cost, 9),
                "reserved_at": reserved["time"],
                "completed_at": done["time"],
                "input_sha256": call["input_sha256"],
            }
        )
    mae = sum(abs(r["error_ai_minus_official"]) for r in rows) / len(rows)
    bias = sum(r["error_ai_minus_official"] for r in rows) / len(rows)
    check("calibration_mae", report["calibration"]["overall"]["mae"] == mae == 0.25)
    check("calibration_bias", report["calibration"]["overall"]["bias"] == bias == -0.25)
    check("cost_matches_report", math.isclose(sum(costs), report["estimated_cost"], abs_tol=1e-9))
    check(
        "no_truncation_timeout_retry",
        report["kinds"]["evaluate"]["truncated"] == report["kinds"]["evaluate"]["timeouts"] == 0
        and all(c["attempt"] == 0 for c in data["calls"]),
    )
    check(
        "first_and_final_pass",
        report["kinds"]["evaluate"]["first_attempt_valid"]
        == report["kinds"]["evaluate"]["final_ready"]
        == 1,
    )
    check("total_input_tokens", sum(r["input_tokens"] for r in rows) == report["tokens"]["prompt"])
    check(
        "total_output_tokens",
        sum(r["output_tokens_including_reasoning"] for r in rows) == report["tokens"]["completion"],
    )
    output = {
        k: report[k]
        for k in (
            "started_at",
            "provider",
            "model",
            "prompt_version",
            "evaluate_thinking",
            "demo",
            "samples",
            "calls",
            "max_calls",
            "aborted",
            "connectivity",
            "kinds",
            "vision_calls",
            "evidence",
            "argument",
            "calibration",
            "ordering",
            "repeat_spread",
            "tokens",
            "usage",
            "estimated_cost",
            "cost_estimate",
            "prices",
            "served_models",
            "code_sha256",
        )
    }
    output.update(
        independent_essays=1,
        repeated_evaluations=2,
        numeric_rows=rows,
        source_head=authorization["source_head"],
        price_currency="CNY",
        price_per_tokens=1_000_000,
        reasoning_already_in_completion=True,
        price_source=authorization["price_source"],
        official_reference_has_subscores=False,
    )
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "numeric-summary.json").write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n"
    )
    (args.out / "audit.json").write_text(
        json.dumps(
            {
                "passed": len(checks),
                "failed": 0,
                "checks": checks,
                "product_files_checked": len(files),
                "paid_calls_by_audit": 0,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
    # This ledger contains IDs, timestamps and numeric usage only; no response bodies.
    (args.out / "ledger-t2.jsonl").write_bytes((root / "ledger-t2.jsonl").read_bytes())
    (args.out / "exit-status.json").write_bytes((root / "launcher_exit.json").read_bytes())
    print(
        json.dumps(
            {
                "checks_passed": len(checks),
                "calls": len(rows),
                "estimated_cny": round(sum(costs), 9),
                "scores": [r["overall"] for r in rows],
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
