"""Independently audit this private 3-vision/16-text batch; export numeric facts only.

Uses only the Python standard library, reads saved artifacts, and never loads the
application/configuration or makes network/model calls. Full run data stays private;
essay, reading, response and reasoning strings are never included in the export.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import statistics
import subprocess
from collections import Counter, defaultdict
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

HEAD = "18f5f08ffb0019f602ad64ec2565d8bd19fb31e9"
PROMPT = "iwa-2026-11-13.15"
OFFICIAL = {
    "official-1A-A": 5.0,
    "official-1A-B": 6.0,
    "official-1B-A": 6.0,
    "official-1C-A": 5.0,
}
REMAINING = set(OFFICIAL) - {"official-1B-A"}
CRITERIA = ("task", "coherence", "lexical", "grammar")
MODELS = {"deepseek-flash", "deepseek-v4-pro"}
CST = ZoneInfo("Asia/Shanghai")
MILLION = Decimal(1_000_000)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def text_digest(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_lines(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]


def numeric(value):
    return type(value) in (int, float) and math.isfinite(value)


def token_count(value):
    return type(value) is int and value >= 0


def bare_object(value):
    """Whole response is a JSON object, without stripping any wrapper."""
    try:
        parsed = json.loads((value or "").strip())
    except (ValueError, TypeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def strict_object(value):
    """Independently match the product's exact one-object/one-fence contract.

    Only a single complete bare/json/JSON code fence may wrap the object. There
    is no substring extraction, brace repair, or acceptance of surrounding prose.
    A response rejected here remains a format observation, even if a later
    validation retry yields a complete, valid evaluation.
    """
    text = (value or "").strip()
    fenced = re.fullmatch(r"```(?:json|JSON)?[ \t]*\r?\n(.*?)\r?\n[ \t]*```", text, re.S)
    return bare_object(fenced.group(1) if fenced else text)


def cache_hit(usage):
    for value in (
        usage.get("prompt_cache_hit_tokens"),
        (usage.get("prompt_tokens_details") or {}).get("cached_tokens"),
    ):
        if token_count(value):
            return value
    return None


def usage_summary(calls):
    known = {"prompt": 0, "completion": 0}
    complete = dict.fromkeys(known, True)
    unknown, hits, hit_complete = 0, 0, bool(calls)
    for call in calls:
        usage = call.get("usage") or {}
        this_complete = True
        for key, field in (("prompt", "prompt_tokens"), ("completion", "completion_tokens")):
            value = usage.get(field)
            if token_count(value):
                known[key] += value
            else:
                complete[key] = False
                this_complete = False
        unknown += not this_complete
        hit = cache_hit(usage)
        hits += hit or 0
        hit_complete = hit_complete and hit is not None
    return {
        "calls": len(calls),
        "unknown_usage_calls": unknown,
        "complete": unknown == 0,
        "tokens": {key: known[key] if complete[key] else None for key in known},
        "known_tokens": known,
        "cache_hit_tokens": hits if hit_complete else None,
    }


def calibration(rows):
    diffs = [row["error_ai_minus_official"] for row in rows if row["overall"] is not None]
    return (
        {
            "n": len(diffs),
            "mae": round(statistics.fmean(abs(v) for v in diffs), 3),
            "bias": round(statistics.fmean(diffs), 3),
            "within_0_5": round(sum(abs(v) <= 0.5 for v in diffs) / len(diffs), 3),
            "exact": round(sum(v == 0 for v in diffs) / len(diffs), 3),
        }
        if diffs
        else None
    )


def source_fingerprint(source):
    result = hashlib.sha256()
    for path in sorted((source / "tools/ielts_writing_ai").glob("*.py")):
        result.update(path.name.encode() + b"\0" + path.read_bytes() + b"\0")
    return result.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--private-root", required=True, type=Path, help="Directory containing run/"
    )
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--out", type=Path, default=Path(__file__).with_name("audit.json"))
    parser.add_argument("--phase", choices=("images", "complete"), default="complete")
    args = parser.parse_args()
    private, source = args.private_root.resolve(), args.source.resolve()
    root = private / "run"
    inputs = {}

    def load(relative, *, lines=False, parent=False):
        path = (private if parent else root) / relative
        inputs[str(path)] = digest(path)
        return read_lines(path) if lines else read_json(path)

    manifest = load("manifest.json")
    authorized = load("authorization.json", parent=True)["preceding_plan"]
    prices = load("pricing.json", parent=True)
    events = load("ledger-t1.jsonl", lines=True)
    stages = ["readremaining"] + (["evaluate"] if args.phase == "complete" else [])
    runs = {stage: load(f"{stage}/run_data.json") for stage in stages}
    reports = {stage: load(f"{stage}/report.json") for stage in stages}
    checks = {}

    def check(name, value):
        checks[name] = bool(value)

    def require(name, value):
        check(name, value)
        if not value:
            raise ValueError(name)

    check(
        "authorized_weekend_rates",
        prices["idle"]
        == {
            "deepseek-flash": {"input_miss": 1, "input_hit": 0.02, "output": 4},
            "deepseek-v4-pro": {"input_miss": 4.5, "input_hit": 0.15, "output": 13.5},
        },
    )

    check(
        "manifest_head_prompt_caps",
        (manifest["head"], manifest["prompt_version"], manifest["text_cap"], manifest["vision_cap"])
        == (HEAD, PROMPT, 16, 3),
    )
    check(
        "explicit_authorization_matches",
        authorized["text_request_cap_including_validation_retry"] == 16
        and authorized["new_vision_request_cap"] == 3
        and authorized["repeat"] == 2
        and set(authorized["sample_ids"]) == set(OFFICIAL)
        and authorized["kinds"] == ["evaluate"]
        and authorized["reuse_old_reading_id"] == "official-1B-A",
    )
    check(
        "manifest_sealed",
        load("manifest-sha256.json")["sha256"] == inputs[str(root / "manifest.json")],
    )
    check(
        "source_head_unchanged",
        subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=source, text=True).strip()
        == HEAD,
    )
    fingerprint = source_fingerprint(source)
    check("source_fingerprint_unchanged", fingerprint == manifest["source_code_sha256"])
    for relative, expected in manifest["snapshot_hashes"].items():
        check("snapshot:" + relative, digest(root / relative) == expected)
    check("original_input_unchanged", digest(manifest["input_path"]) == manifest["input_sha256"])
    for number, (path, expected) in enumerate(manifest["reused_source_hashes"].items()):
        check(f"closed_old_batch_source_{number}_unchanged", digest(path) == expected)
    check("runner_frozen", digest(private / "runner.py") == manifest["wrapper_sha256"])
    for stage in stages:
        check(
            stage + ":exit0",
            load(f"{stage}/exit_status.json")["code"] == 0
            and load(f"{stage}.done.json")["code"] == 0,
        )
        check(
            stage + ":source_and_prompt",
            runs[stage]["code_sha256"] == fingerprint
            and reports[stage]["prompt_version"] == PROMPT,
        )
        check(
            stage + ":no_abort",
            runs[stage].get("aborted") is None and reports[stage].get("aborted") is None,
        )
    headers = [event for event in events if event.get("type") == "header"]
    reserves = [event for event in events if event.get("type") == "reserve"]
    done_rows = [event for event in events if event.get("type") == "done"]
    require("unique_reserve_ids", len({v["id"] for v in reserves}) == len(reserves))
    require("unique_done_ids", len({v["id"] for v in done_rows}) == len(done_rows))
    check(
        "one_matching_header",
        len(headers) == 1
        and headers[0].get("code_sha256") == fingerprint
        and headers[0].get("prompt_version") == PROMPT,
    )
    check(
        "known_ledger_event_types",
        all(v.get("type") in {"header", "reserve", "done"} for v in events),
    )
    by_reserve, done = ({v["id"]: v for v in rows} for rows in (reserves, done_rows))
    check("all_reservations_completed", set(by_reserve) == set(done))
    event_positions = {(v.get("type"), v.get("id")): n for n, v in enumerate(events)}
    check(
        "reserves_precede_completions",
        all(
            event_positions[("reserve", rid)] < event_positions[("done", rid)]
            for rid in set(done) & set(by_reserve)
        ),
    )
    counts = Counter(v.get("category") for v in reserves)
    check("caps_not_exceeded", counts["vision"] <= 3 and counts["text"] <= 16)
    check(
        "all_reservations_keep_fixed_caps",
        all(v.get("cap") == {"vision": 3, "text": 16}.get(v.get("category")) for v in reserves),
    )
    check(
        "vision_once_each_remaining_id",
        Counter(v["sample"] for v in reserves if v["category"] == "vision") == Counter(REMAINING),
    )
    check(
        "no_new_1b_vision",
        all(v["sample"] != "official-1B-A" for v in reserves if v["category"] == "vision"),
    )
    allowed_samples = set(OFFICIAL) | {name + "#r2" for name in OFFICIAL}
    calls = [call for run in runs.values() for call in run["calls"]]
    require(
        "known_call_samples_models",
        all(c.get("sample") in allowed_samples and c.get("model") in MODELS for c in calls),
    )
    require("unique_call_ledger_ids", len({c.get("ledger_id") for c in calls}) == len(calls))
    check("calls_match_all_reservations", {c.get("ledger_id") for c in calls} == set(by_reserve))
    call_rows, costs, model_costs = [], [], defaultdict(list)
    for index, call in enumerate(calls, 1):
        prefix = f"call_{index}"
        reserve = by_reserve.get(call.get("ledger_id"), {})
        finished = done.get(call.get("ledger_id"), {})
        check(
            prefix + ":identity",
            all(
                call.get(field) == reserve.get(field)
                for field in ("sample", "kind", "attempt", "model")
            ),
        )
        check(
            prefix + ":kind_category",
            (call["kind"], reserve.get("category"))
            in {("describe_image", "vision"), ("evaluate", "text")},
        )
        check(
            prefix + ":success",
            call.get("ok") is True
            and call.get("http_status") == 200
            and call.get("error") is None
            and finished.get("ok") is True,
        )
        is_vision = call["kind"] == "describe_image"
        check(
            prefix + ":model_options",
            (call["model"], call.get("thinking"), call.get("max_tokens"))
            == (
                ("deepseek-flash", "off", 2000) if is_vision else ("deepseek-v4-pro", "high", 32000)
            ),
        )
        check(prefix + ":json_mode", call.get("json_mode") is (not is_vision))
        u = call.get("usage") or {}
        inp, output, hit = u.get("prompt_tokens"), u.get("completion_tokens"), cache_hit(u)
        known = token_count(inp) and token_count(output) and token_count(hit) and hit <= inp
        check(prefix + ":usage_known", known)
        check(
            prefix + ":usage_matches_ledger",
            all(
                u.get(k) == finished.get("tokens", {}).get(k)
                for k in ("prompt_tokens", "completion_tokens")
            )
            and hit == finished.get("tokens", {}).get("prompt_cache_hit_tokens"),
        )
        check(prefix + ":usage_total", known and u.get("total_tokens") == inp + output)
        check(
            prefix + ":miss_consistent",
            u.get("prompt_cache_miss_tokens") is None
            or (known and u["prompt_cache_miss_tokens"] == inp - hit),
        )
        reasoning = call.get("reasoning_tokens")
        check(
            prefix + ":reasoning_not_double_counted",
            is_vision or (known and token_count(reasoning) and reasoning <= output),
        )
        check(prefix + ":below_output_cap", known and output < call["max_tokens"])
        started = datetime.fromisoformat(reserve["time"]).astimezone(CST)
        ended = datetime.fromisoformat(finished["time"]).astimezone(CST)
        weekend = started.weekday() >= 5 and ended.weekday() >= 5
        # This authorized batch is a weekend run. Do not invent a holiday calendar
        # or silently use a weekend price if a future invocation crosses into a weekday.
        check(prefix + ":weekend_idle_interval", weekend and started <= ended)
        rates = prices["idle"][call["model"]]
        cost = (
            (
                (
                    Decimal(inp - hit) * Decimal(str(rates["input_miss"]))
                    + Decimal(hit) * Decimal(str(rates["input_hit"]))
                    + Decimal(output) * Decimal(str(rates["output"]))
                )
                / MILLION
            )
            if known and weekend
            else None
        )
        costs.append(cost)
        model_costs[call["model"]].append(cost)
        parsed = strict_object(call.get("text"))
        check(
            prefix + ":json_flag_recomputed",
            call.get("json_ok") is ((parsed is not None) if call.get("json_mode") else None),
        )
        # Vision has no validation retry and all three readings must be ready.
        # Text format failures are observed below and independently reconciled
        # with first-attempt metrics. A successful retry is allowed; the final
        # raw response and all eight scored results are still required to pass.
        if is_vision:
            check(prefix + ":ready_image_response_is_single_json_object", parsed is not None)
        call_rows.append(
            {
                "number": index,
                "sample": call["sample"],
                "kind": call["kind"],
                "attempt": call["attempt"],
                "model": call["model"],
                "input_sha256": call.get("input_sha256"),
                "response_sha256": text_digest(call.get("text") or ""),
                "raw_single_json": bare_object(call.get("text")) is not None,
                "accepted_single_json": parsed is not None,
                "single_fence_recovered": parsed is not None
                and bare_object(call.get("text")) is None,
                "json_mode": call.get("json_mode"),
                "recorded_json_ok": call.get("json_ok"),
                "reserved_at_beijing": started.isoformat(),
                "completed_at_beijing": ended.isoformat(),
                "latency_ms": call.get("latency_ms"),
                "input_tokens": inp,
                "cache_hit_tokens": hit,
                "cache_miss_tokens": inp - hit if known else None,
                "output_tokens_including_reasoning": output,
                "reasoning_tokens": reasoning,
                "estimated_cny": str(cost) if cost is not None else None,
            }
        )
    for stage in stages:
        stage_calls, report = runs[stage]["calls"], reports[stage]
        check(
            stage + ":report_counts",
            report["calls"] == len(stage_calls)
            and report["vision_calls"] == sum(c["kind"] == "describe_image" for c in stage_calls),
        )
        for kind in ("total", "text", "vision"):
            selected = [
                c
                for c in stage_calls
                if kind == "total" or (c["kind"] == "describe_image") == (kind == "vision")
            ]
            check(stage + ":usage_" + kind, report["usage"][kind] == usage_summary(selected))
        expected_models = [
            {
                "provider": "deepseek",
                "model": model,
                **usage_summary([c for c in stage_calls if c["model"] == model]),
            }
            for model in sorted({c["model"] for c in stage_calls})
        ]
        check(stage + ":usage_by_model", report["usage"]["by_model"] == expected_models)
    image_run = runs["readremaining"]
    saved_images = load("readremaining/image_descriptions.json")
    check(
        "saved_image_outcomes_match_run",
        saved_images.get("version") == 2
        and saved_images.get("images") == image_run["image_outcomes"],
    )
    check(
        "image_stage_hash_sealed",
        load("readremaining.done.json").get("image_descriptions_sha256")
        == inputs[str(root / "readremaining/image_descriptions.json")],
    )
    check(
        "exact_3_new_vision_calls",
        len(image_run["calls"]) == 3
        and all(c["kind"] == "describe_image" and c["attempt"] == 0 for c in image_run["calls"]),
    )
    check(
        "three_ready_image_outcomes",
        set(image_run["image_outcomes"]) == REMAINING
        and all(v["status"] == "ready" for v in image_run["image_outcomes"].values()),
    )
    rows, repeat_rows, ordering = [], [], None
    if args.phase == "complete":
        data, report = runs["evaluate"], reports["evaluate"]
        check("batch_closed", load("batch-closed.json")["status"] == "closed")
        checked_file = root / "image_descriptions.checked.json"
        checked = load("image_descriptions.checked.json")["images"]
        check(
            "checked_file_sealed", load("seal.done.json")["checked_sha256"] == digest(checked_file)
        )
        frozen = load("frozen/image_descriptions.json")["images"]
        check("four_checked_readings", set(checked) == set(OFFICIAL))
        for sample_id in OFFICIAL:
            value, record = checked[sample_id], checked[sample_id]["check"]
            check(
                sample_id + ":reading_bound",
                record["status"] == "confirmed"
                and record["reading_sha256"] == text_digest(value["description"])
                and record["image_sha256"] == manifest["images"][sample_id]["sha256"],
            )
            check(
                sample_id + ":original_reading_retained",
                (
                    record.get("model_description") == frozen[sample_id]["description"]
                    if record.get("edited")
                    else value["description"] == frozen[sample_id]["description"]
                ),
            )
        require(
            "exact_eight_sample_ids",
            len(data["samples"]) == 8 and {s["id"] for s in data["samples"]} == allowed_samples,
        )
        check(
            "8_to_16_text_calls_no_new_vision",
            8 <= len(data["calls"]) <= 16 and all(c["kind"] == "evaluate" for c in data["calls"]),
        )
        calls_by_sample = defaultdict(list)
        for call in data["calls"]:
            calls_by_sample[call["sample"]].append(call)
        for sample in data["samples"]:
            sid = sample["id"]
            base = sid.split("#r")[0]
            gen = sample["generations"]["evaluate"]
            result = gen.get("result") or {}
            criteria = result.get("criteria") or []
            bands = {c["key"]: c.get("band") for c in criteria}
            valid = (
                len(criteria) == 4
                and set(bands) == set(CRITERIA)
                and all(numeric(v) and 0 <= v <= 9 and v * 2 == int(v * 2) for v in bands.values())
            )
            check(
                sid + ":ready_four_scored_criteria",
                gen["status"] == "ready"
                and valid
                and all(c["state"] == "scored" for c in criteria),
            )
            overall = result.get("overall_band")
            check(
                sid + ":overall_recomputed",
                valid and math.floor(sum(bands.values()) / 4 * 2 + 0.5 + 1e-9) / 2 == overall,
            )
            check(
                sid + ":official_label", sample.get("teacher", {}).get("overall") == OFFICIAL[base]
            )
            description = sample["submission"].get("image_description") or ""
            bound = text_digest(description)
            check(
                sid + ":current_confirmed_reading",
                bound == checked[base]["check"]["reading_sha256"]
                and result.get("chart_reading") == {"checked": True, "sha256": bound},
            )
            attempts = calls_by_sample[sid]
            check(
                sid + ":at_most_one_validation_retry",
                [c["attempt"] for c in attempts] in ([0], [0, 1]),
            )
            raw = strict_object(attempts[-1].get("text")) if attempts else None
            raw_criteria = (raw.get("criteria") or raw) if raw else {}
            check(
                sid + ":bands_match_final_raw",
                valid
                and all(
                    isinstance(raw_criteria.get(k), dict)
                    and numeric(raw_criteria[k].get("band"))
                    and math.floor(raw_criteria[k]["band"] * 2 + 0.5) / 2 == bands[k]
                    for k in CRITERIA
                ),
            )
            rows.append(
                {
                    "id": sid,
                    "base_id": base,
                    "repeat": 2 if "#r2" in sid else 1,
                    "bands": bands,
                    "overall": overall,
                    "official_overall": OFFICIAL[base],
                    "error_ai_minus_official": (
                        overall - OFFICIAL[base] if numeric(overall) else None
                    ),
                    "ready": gen["status"] == "ready",
                    "attempts": len(attempts),
                    "reading_sha256": bound,
                    "essay_sha256": text_digest(sample["submission"]["essay_text"]),
                    "result_sha256": hashlib.sha256(
                        json.dumps(result, sort_keys=True, ensure_ascii=False).encode()
                    ).hexdigest(),
                }
            )
        check("calibration_independent", report["calibration"] == {"overall": calibration(rows)})
        for base in OFFICIAL:
            pair = sorted(
                [row for row in rows if row["base_id"] == base], key=lambda row: row["repeat"]
            )
            values = {
                key: [row["overall"] if key == "overall" else row["bands"].get(key) for row in pair]
                for key in ("overall",) + CRITERIA
            }
            spread = {
                key: round(max(v) - min(v), 3)
                for key, v in values.items()
                if all(numeric(x) for x in v)
            }
            repeat_rows.append(
                {
                    "id": base,
                    "runs": 2,
                    "ready": sum(row["ready"] for row in pair),
                    "overall": values["overall"],
                    "spread": spread,
                }
            )
            check(
                base + ":repeat_same_reading_and_essay",
                len({row["reading_sha256"] for row in pair})
                == len({row["essay_sha256"] for row in pair})
                == 1,
            )
            first_hashes = {
                c["input_sha256"]
                for row in pair
                for c in calls_by_sample[row["id"]]
                if c["attempt"] == 0
            }
            check(base + ":repeat_same_first_input", len(first_hashes) == 1)
        overall_spreads = [v["spread"]["overall"] for v in repeat_rows if "overall" in v["spread"]]
        spread_summary = {
            "samples": repeat_rows,
            "overall_spread_mean": (
                round(statistics.fmean(overall_spreads), 3) if overall_spreads else None
            ),
            "overall_spread_max": max(overall_spreads) if overall_spreads else None,
            "any_failed": sum(row["ready"] < row["runs"] for row in repeat_rows),
        }
        check("repeat_spread_independent", report["repeat_spread"] == spread_summary)
        lower = [row["overall"] for row in rows if row["base_id"] == "official-1A-A"]
        upper = [row["overall"] for row in rows if row["base_id"] == "official-1A-B"]
        ordering = {
            "lower_official": 5.0,
            "higher_official": 6.0,
            "lower_ai": lower,
            "higher_ai": upper,
            "pairs": len(lower) * len(upper),
            "inversions": sum(hi < lo for hi in upper for lo in lower),
            "ties": sum(hi == lo for hi in upper for lo in lower),
            "spread": round(statistics.fmean(upper) - statistics.fmean(lower), 3),
        }
        matching = [
            value
            for value in (report.get("ordering") or {}).values()
            if {v["id"].split("#r")[0] for v in value["rows"]} == {"official-1A-A", "official-1A-B"}
        ]
        check(
            "ordering_independent",
            len(matching) == 1
            and all(
                matching[0][key] == ordering[key]
                for key in ("pairs", "inversions", "ties", "spread")
            ),
        )
        metrics = report["kinds"]["evaluate"]
        first = [c for c in data["calls"] if c["attempt"] == 0]
        check(
            "report_attempt_counts",
            metrics["calls"] == len(data["calls"]) and metrics["first_attempts"] == len(first) == 8,
        )
        check(
            "report_first_json",
            metrics["first_attempt_json_ok"]
            == round(sum(strict_object(c.get("text")) is not None for c in first) / len(first), 3),
        )
        # For eight ready evaluations, the runner retries exactly when the
        # preceding response is rejected by its content/JSON validator.
        check(
            "report_first_valid_from_retry_path",
            all(row["ready"] for row in rows)
            and metrics["first_attempt_valid"]
            == round(sum(row["attempts"] == 1 for row in rows) / 8, 3),
        )
        check(
            "report_json_problem_attempts",
            Counter((item["sample"], item["attempt"]) for item in metrics["json_problems"])
            == Counter(
                (call["sample"], call["attempt"])
                for call in data["calls"]
                if call.get("ok")
                and call.get("json_mode")
                and strict_object(call.get("text")) is None
            ),
        )
        check(
            "report_final_ready",
            metrics["final_ready"] == round(sum(row["ready"] for row in rows) / 8, 3),
        )
        check(
            "report_no_truncation_timeout",
            metrics["truncated"] == sum(c.get("error") == "truncated" for c in data["calls"])
            and metrics["timeouts"] == sum(c.get("error") == "timeout" for c in data["calls"]),
        )
    check(
        "audited_private_inputs_unchanged",
        all(digest(path) == value for path, value in inputs.items()),
    )
    complete_cost = all(value is not None for value in costs)
    cost_total = sum((v for v in costs if v is not None), Decimal(0))
    output = {
        "audit_script_sha256": digest(Path(__file__)),
        "audit_contract": "observations-plus-final-ready-v2",
        "source_head": HEAD,
        "source_code_sha256": fingerprint,
        "prompt_version": PROMPT,
        "phase": args.phase,
        "caps": {"text": 16, "new_vision": 3},
        "counts": {
            "text_reserved": counts["text"],
            "vision_reserved": counts["vision"],
            "ledger_done": len(done_rows),
            "ledger_failed": sum(v.get("ok") is not True for v in done_rows),
            "ledger_unknown": len(set(by_reserve) - set(done)),
            "evaluations": len(rows),
            "validation_retries": sum(c["attempt"] > 0 for c in calls if c["kind"] == "evaluate"),
        },
        "scores": rows,
        "calibration": calibration(rows),
        "ordering_1a": ordering,
        "repeat_spread": repeat_rows,
        "usage_total": usage_summary(calls),
        "usage_by_model": [
            {"model": model, **usage_summary([c for c in calls if c["model"] == model])}
            for model in sorted({c["model"] for c in calls})
        ],
        "cost_estimate_cny": {
            "total": str(cost_total) if complete_cost else None,
            "known_subtotal": str(cost_total),
            "unknown_cost_calls": sum(v is None for v in costs),
            "by_model": {
                model: str(sum(v, Decimal(0))) if all(x is not None for x in v) else None
                for model, v in sorted(model_costs.items())
            },
            "rates_per_million": prices["idle"],
            "weekend_request_times_verified": all(
                checks[name] for name in checks if name.endswith(":weekend_idle_interval")
            ),
            "is_bill": False,
        },
        "calls": call_rows,
        "json_observations": {
            "bare_single_json_calls": sum(row["raw_single_json"] for row in call_rows),
            "accepted_single_json_calls": sum(row["accepted_single_json"] for row in call_rows),
            "single_fence_recovered_calls": sum(row["single_fence_recovered"] for row in call_rows),
            "invalid_format_calls": sum(not row["accepted_single_json"] for row in call_rows),
            "first_text_invalid_format": sum(
                row["kind"] == "evaluate"
                and row["attempt"] == 0
                and not row["accepted_single_json"]
                for row in call_rows
            ),
            "surrounding_prose_or_brace_repair_allowed": False,
        },
        "artifact_sha256": {
            str(Path(path).relative_to(private)): value for path, value in inputs.items()
        },
        "checks": checks,
        "passed": sum(checks.values()),
        "total": len(checks),
        "failed": [name for name, passed in checks.items() if not passed],
        "private_text_exported": False,
        "paid_calls_by_audit": 0,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "passed": output["passed"],
                "total": output["total"],
                "failed": output["failed"],
                "counts": output["counts"],
                "estimated_cny": output["cost_estimate_cny"]["total"],
            },
            ensure_ascii=False,
        )
    )
    return int(bool(output["failed"]))


if __name__ == "__main__":
    raise SystemExit(main())
