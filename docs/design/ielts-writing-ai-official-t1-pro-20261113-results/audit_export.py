"""Read private first-image artifacts and export a numeric whitelist only.

No model calls, configuration loading, private-file mutation, essay export, full
image description export, or reasoning access. Manual chart estimates below are
approximate visual observations, not official exact values or automated OCR.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

EXPECTED_HEAD = "fd8e910b3d5f5a5385af5a99d073c3824bbe74b2"
EXPECTED_PROMPT = "iwa-2026-11-13.14"


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path):
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-root", required=True, type=Path)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--out", type=Path, default=Path(__file__).with_name("vision_review.json"))
    args = parser.parse_args()
    root, source = args.private_root.resolve(), args.source.resolve()
    sys.path.insert(0, str(source))
    from tools.ielts_writing_ai import visual
    from tools.ielts_writing_ai.llm import parse_strict_json

    manifest = read_json(root / "manifest.json")
    entries = read_jsonl(root / "ledger-t1.jsonl")
    run = read_json(root / "first/run_data.json")
    raw = read_jsonl(root / "first/raw_calls.jsonl")
    frozen_file = root / "first/image_descriptions.json"
    frozen = read_json(frozen_file)
    exit_status = read_json(root / "first/exit_status.json")
    checks = []

    def check(name, passed):
        checks.append({"check": name, "passed": bool(passed)})

    check(
        "recorded_head_and_prompt",
        manifest.get("head") == EXPECTED_HEAD and manifest.get("prompt_version") == EXPECTED_PROMPT,
    )
    check(
        "authorized_caps16plus4", (manifest.get("text_cap"), manifest.get("vision_cap")) == (16, 4)
    )
    calls = run.get("calls", [])
    check("one_recorded_call", len(calls) == len(raw) == 1)
    if len(calls) != 1 or len(raw) != 1:
        raise ValueError("Expected one first-stage call")
    call = calls[0]
    check(
        "one_flash_image_call",
        (call.get("kind"), call.get("model"), call.get("provider"))
        == ("describe_image", "deepseek-flash", "deepseek"),
    )
    check(
        "thinking_off_tokens2000", call.get("thinking") == "off" and call.get("max_tokens") == 2000
    )
    check("vision_timeout180", run.get("settings", {}).get("vision_timeout") == 180)
    check(
        "successful_transport_and_exit",
        call.get("ok") is True
        and call.get("http_status") == 200
        and call.get("error") is None
        and exit_status.get("code") == 0,
    )
    check("raw_and_run_response_same", raw[0].get("text") == call.get("text"))
    parsed = parse_strict_json(raw[0].get("text"))
    check("raw_json_parsed", isinstance(parsed, dict))
    if not isinstance(parsed, dict):
        raise ValueError("Expected structured original image response")
    reading = visual.assess(raw[0]["text"])
    saved = frozen.get("images", {}).get("official-1B-A", {})
    check(
        "structural_ready",
        frozen.get("version") == 2 and saved.get("status") == "ready" and reading.sufficient,
    )
    check("renderer_preserved_model_description", reading.description == saved.get("description"))

    def numeric_point(label, occurrence):
        selected = [point for point in parsed.get("data_points", []) if point.get("label") == label]
        value = selected[occurrence].get("value")
        numbers = re.findall(r"\d+(?:\.\d+)?", str(value))
        if len(numbers) != 1:
            raise ValueError("Unexpected selected value format")
        return float(numbers[0])

    # Duplicated 12-hour clock labels are resolved by their order in the original
    # day-to-next-morning data list. No original prose is included in the export.
    comparisons = [
        {
            "series": "television",
            "time_24h": "16:00",
            "model_percent": numeric_point("Television, 4:00", 0),
            "manual_visual_percent_approx": 22,
            "manual_visual_range_percent": [21, 23],
            "material_mismatch": True,
        },
        {
            "series": "television",
            "time_24h": "22:00",
            "model_percent": numeric_point("Television, 10:00", 1),
            "manual_visual_percent_approx": 40,
            "manual_visual_range_percent": [38, 41],
            "material_mismatch": True,
        },
        {
            "series": "television",
            "time_24h": "20:00",
            "model_percent": numeric_point("Television, 8:00", 1),
            "manual_visual_percent_approx": 45.5,
            "manual_visual_range_percent": [45, 46],
            "material_mismatch": False,
        },
    ]
    check(
        "raw_model_has_14_and_45",
        [point["model_percent"] for point in comparisons[:2]] == [14.0, 45.0],
    )
    check(
        "two_material_mismatches_against_manual_ranges",
        all(
            not point["manual_visual_range_percent"][0]
            <= point["model_percent"]
            <= point["manual_visual_range_percent"][1]
            for point in comparisons[:2]
        ),
    )
    for point in comparisons:
        point["model_minus_manual_midpoint_percentage_points"] = round(
            point["model_percent"] - point["manual_visual_percent_approx"], 1
        )

    reservations = [entry for entry in entries if entry.get("type") == "reserve"]
    completed = {entry["id"]: entry for entry in entries if entry.get("type") == "done"}
    categories = Counter(entry.get("category") for entry in reservations)
    unknown = sum(entry["id"] not in completed for entry in reservations)
    failed = sum(
        not completed.get(entry["id"], {}).get("ok", False)
        for entry in reservations
        if entry["id"] in completed
    )
    check(
        "ledger_one_image_zero_text",
        len(reservations) == categories["vision"] == 1 and categories["text"] == 0,
    )
    check("ledger_no_unknown_or_failed", unknown == failed == 0)
    check(
        "ledger_exact_first_id",
        len(reservations) == 1
        and reservations[0].get("sample") == "official-1B-A"
        and reservations[0].get("cap") == 4,
    )
    check(
        "later_paid_stages_not_started",
        not (root / "rest.started.json").exists() and not (root / "evaluate.started.json").exists(),
    )
    check("manual_first_approval_absent", not (root / "first-approved.json").exists())

    usage = call.get("usage") or {}
    input_tokens = usage.get("prompt_tokens")
    output_tokens = usage.get("completion_tokens")
    cached = usage.get("prompt_cache_hit_tokens")
    uncached = usage.get("prompt_cache_miss_tokens")
    check(
        "usage824uncached958output",
        (input_tokens, uncached, cached, output_tokens) == (824, 824, 0, 958),
    )
    check(
        "usage_consistent",
        input_tokens == uncached + cached
        and usage.get("total_tokens") == input_tokens + output_tokens,
    )
    ledger_tokens = completed[reservations[0]["id"]].get("tokens", {})
    check(
        "ledger_usage_matches_response",
        ledger_tokens.get("prompt_tokens") == input_tokens
        and ledger_tokens.get("completion_tokens") == output_tokens
        and ledger_tokens.get("prompt_cache_hit_tokens") == cached,
    )
    # Rates were supplied for this authorized batch. No price lookup/network occurs.
    input_price, output_price = Decimal("2"), Decimal("8")
    input_cost = Decimal(uncached) * input_price / Decimal(1000000)
    output_cost = Decimal(output_tokens) * output_price / Decimal(1000000)
    total_cost = input_cost + output_cost
    check("decimal_cost0_009312", total_cost == Decimal("0.009312"))
    check("latency5430ms", call.get("latency_ms") == 5430)
    started = datetime.fromisoformat(run["started_at"]).astimezone(ZoneInfo("Asia/Shanghai"))
    check("first_stage1119_beijing", started.strftime("%Y-%m-%d %H:%M") == "2026-11-13 11:19")

    output = {
        "source_head": manifest["head"],
        "prompt_version": manifest["prompt_version"],
        "source_code_sha256": manifest.get("source_code_sha256"),
        "image_descriptions_sha256": digest(frozen_file),
        "sample_id": "official-1B-A",
        "started_at_beijing": started.isoformat(),
        "decision": "stop_after_first_image_manual_review_failed",
        "structural_result": "ready",
        "human_factual_result": "unacceptable_for_Task_Achievement_grounding",
        "attribution": "incorrect values already occur in original model data_points; renderer reproduces the original structured reading",
        "visual_observation_limit": "Values and time positions are approximate manual readings of graph axes and curves, not official exact numeric annotations or automated OCR.",
        "comparisons": comparisons,
        "correct_high_level_features": {
            "two_series_and_units": True,
            "radio_morning_peak": True,
            "television_evening_peak": True,
            "overnight_low_audiences": True,
        },
        "television_peak_manual_approx": {"time_24h": "19:30", "percent": 47},
        "counts": {
            "text_reserved": categories["text"],
            "vision_reserved": categories["vision"],
            "completed": len(completed),
            "failed": failed,
            "unknown": unknown,
            "evaluations": 0,
            "automatic_retries": 0,
        },
        "authorized_caps": {"text": 16, "vision": 4},
        "unused_authorization_not_consumed": {"text": 16, "vision": 3},
        "usage": {
            "input_tokens": input_tokens,
            "uncached_input_tokens": uncached,
            "cached_input_tokens": cached,
            "output_tokens": output_tokens,
            "total_tokens": usage.get("total_tokens"),
        },
        "latency_ms": call["latency_ms"],
        "cost_estimate": {
            "currency": "CNY",
            "price_basis": "batch-supplied peak rates; estimate, not bill",
            "per_tokens": 1000000,
            "uncached_input_price": str(input_price),
            "output_price": str(output_price),
            "uncached_input_cost": str(input_cost),
            "output_cost": str(output_cost),
            "total": str(total_cost),
        },
        "model": {
            "provider": call["provider"],
            "model": call["model"],
            "thinking": call["thinking"],
            "max_tokens": call["max_tokens"],
            "timeout_seconds": run["settings"]["vision_timeout"],
        },
        "checks": checks,
        "passed": sum(item["passed"] for item in checks),
        "total": len(checks),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "passed": output["passed"],
                "total": output["total"],
                "counts": output["counts"],
                "estimated_cost_cny": str(total_cost),
            },
            ensure_ascii=False,
        )
    )
    return 0 if output["passed"] == output["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
