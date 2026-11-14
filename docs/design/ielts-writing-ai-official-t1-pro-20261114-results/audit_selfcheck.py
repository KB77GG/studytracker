"""Exercise the export audit with synthetic files; no model calls or real samples."""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve().parent
SPEC = importlib.util.spec_from_file_location("batch_audit", HERE / "audit_export.py")
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def summary(calls):
    return {
        "calls": len(calls),
        "unknown_usage_calls": 0,
        "complete": True,
        "tokens": {"prompt": 100 * len(calls), "completion": 50 * len(calls)},
        "known_tokens": {"prompt": 100 * len(calls), "completion": 50 * len(calls)},
        "cache_hit_tokens": 20 * len(calls) if calls else None,
    }


def fixture(private, source, variant):
    run = private / "run"
    private.mkdir(parents=True)
    for name in ("runner.py", "original.jsonl", "old-reading.json"):
        (private / name).write_text("synthetic audit fixture\n")
    fingerprint = AUDIT.source_fingerprint(source)
    manifest = {
        "head": AUDIT.HEAD,
        "prompt_version": AUDIT.PROMPT,
        "text_cap": 16,
        "vision_cap": 3,
        "source_code_sha256": fingerprint,
        "snapshot_hashes": {},
        "input_path": str(private / "original.jsonl"),
        "input_sha256": AUDIT.digest(private / "original.jsonl"),
        "reused_source_hashes": {
            str(private / "old-reading.json"): AUDIT.digest(private / "old-reading.json")
        },
        "wrapper_sha256": AUDIT.digest(private / "runner.py"),
        "images": {key: {"sha256": AUDIT.text_digest(key)} for key in AUDIT.OFFICIAL},
    }
    save(run / "manifest.json", manifest)
    save(run / "manifest-sha256.json", {"sha256": AUDIT.digest(run / "manifest.json")})
    save(
        private / "authorization.json",
        {
            "preceding_plan": {
                "text_request_cap_including_validation_retry": 16,
                "new_vision_request_cap": 3,
                "repeat": 2,
                "sample_ids": list(AUDIT.OFFICIAL),
                "kinds": ["evaluate"],
                "reuse_old_reading_id": "official-1B-A",
            }
        },
    )
    save(
        private / "pricing.json",
        {
            "idle": {
                "deepseek-flash": {"input_miss": 1, "input_hit": 0.02, "output": 4},
                "deepseek-v4-pro": {"input_miss": 4.5, "input_hit": 0.15, "output": 13.5},
            }
        },
    )
    frozen = {key: {"description": "synthetic reading " + key} for key in AUDIT.OFFICIAL}
    checked = copy.deepcopy(frozen)
    for key, value in checked.items():
        value["check"] = {
            "status": "confirmed",
            "edited": False,
            "reading_sha256": AUDIT.text_digest(value["description"]),
            "image_sha256": manifest["images"][key]["sha256"],
        }
    save(run / "frozen/image_descriptions.json", {"version": 2, "images": frozen})
    save(run / "image_descriptions.checked.json", {"version": 2, "images": checked})
    save(
        run / "seal.done.json",
        {"checked_sha256": AUDIT.digest(run / "image_descriptions.checked.json")},
    )
    save(run / "batch-closed.json", {"status": "closed"})
    ledger = [{"type": "header", "code_sha256": fingerprint, "prompt_version": AUDIT.PROMPT}]
    calls = {"readremaining": [], "evaluate": []}

    def add_call(sample, kind, raw, attempt=0):
        vision = kind == "describe_image"
        rid = "synthetic-" + str(len(ledger))
        model = "deepseek-flash" if vision else "deepseek-v4-pro"
        usage = {
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "total_tokens": 150,
            "prompt_cache_hit_tokens": 20,
            "prompt_cache_miss_tokens": 80,
        }
        call = {
            "sample": sample,
            "kind": kind,
            "attempt": attempt,
            "model": model,
            "ledger_id": rid,
            "ok": True,
            "error": None,
            "http_status": 200,
            "thinking": "off" if vision else "high",
            "max_tokens": 2000 if vision else 32000,
            "json_mode": not vision,
            "json_ok": None if vision else AUDIT.strict_object(raw) is not None,
            "usage": usage,
            "reasoning_tokens": 0 if vision else 10,
            "text": raw,
            "input_sha256": AUDIT.text_digest(sample.split("#r")[0]),
            "latency_ms": 1000,
        }
        calls["readremaining" if vision else "evaluate"].append(call)
        ledger.extend(
            [
                {
                    "type": "reserve",
                    "id": rid,
                    "time": "2026-11-14T08:00:00+08:00",
                    "sample": sample,
                    "kind": kind,
                    "attempt": attempt,
                    "model": model,
                    "category": "vision" if vision else "text",
                    "cap": 3 if vision else 16,
                },
                {
                    "type": "done",
                    "id": rid,
                    "time": "2026-11-14T08:00:01+08:00",
                    "ok": True,
                    "error": None,
                    "tokens": usage,
                },
            ]
        )
        return call

    outcomes = {
        key: {"status": "ready", "description": frozen[key]["description"]}
        for key in sorted(AUDIT.REMAINING)
    }
    for key in outcomes:
        add_call(key, "describe_image", '{"synthetic": true}')
    values = {
        "official-1A-A": [5, 5.5],
        "official-1A-B": [6, 6],
        "official-1B-A": [6, 6.5],
        "official-1C-A": [4.5, 5],
    }
    samples = []
    for base, bands in values.items():
        for repeat, band in enumerate(bands):
            sid = base + ("#r2" if repeat else "")
            raw = json.dumps({"criteria": {key: {"band": band} for key in AUDIT.CRITERIA}})
            if sid == "official-1A-A" and variant in {"bad_json_retry", "wrong_json_flag"}:
                first = add_call(sid, "evaluate", '{"criteria":')
                if variant == "wrong_json_flag":
                    first["json_ok"] = True
                add_call(sid, "evaluate", raw, attempt=1)
            else:
                if sid == "official-1A-A" and variant == "single_fence":
                    raw = "```json\n" + raw + "\n```"
                if sid == "official-1A-A" and variant == "invalid_final":
                    raw = '{"criteria":'
                add_call(sid, "evaluate", raw)
            result = {
                "criteria": [
                    {"key": key, "state": "scored", "band": band} for key in AUDIT.CRITERIA
                ],
                "overall_band": band,
                "chart_reading": {
                    "checked": True,
                    "sha256": checked[base]["check"]["reading_sha256"],
                },
            }
            if sid == "official-1A-A" and variant == "wrong_overall":
                result["overall_band"] = 8.0
            if sid == "official-1A-A" and variant == "wrong_reading":
                result["chart_reading"]["sha256"] = "0" * 64
            samples.append(
                {
                    "id": sid,
                    "teacher": {"overall": AUDIT.OFFICIAL[base]},
                    "submission": {
                        "essay_text": "Synthetic essay " + base,
                        "image_description": frozen[base]["description"],
                    },
                    "generations": {"evaluate": {"status": "ready", "result": result}},
                }
            )
    if variant == "wrong_cap":
        ledger[1]["cap"] = 17
    if variant == "weekday":
        ledger[1]["time"] = "2026-11-16T08:00:00+08:00"
        ledger[2]["time"] = "2026-11-16T08:00:01+08:00"
    (run / "ledger-t1.jsonl").write_text("".join(json.dumps(row) + "\n" for row in ledger))
    save(run / "readremaining/image_descriptions.json", {"version": 2, "images": outcomes})
    for stage in calls:
        stage_calls = calls[stage]
        data = {
            "code_sha256": fingerprint,
            "calls": stage_calls,
            "aborted": None,
            "image_outcomes": outcomes if stage == "readremaining" else {},
            "samples": samples if stage == "evaluate" else [],
        }
        report = {
            "prompt_version": AUDIT.PROMPT,
            "calls": len(stage_calls),
            "aborted": None,
            "vision_calls": 3 if stage == "readremaining" else 0,
            "usage": {
                "total": summary(stage_calls),
                "text": summary(stage_calls if stage == "evaluate" else []),
                "vision": summary(stage_calls if stage == "readremaining" else []),
                "by_model": [
                    {
                        "provider": "deepseek",
                        "model": stage_calls[0]["model"],
                        **summary(stage_calls),
                    }
                ],
            },
        }
        if stage == "evaluate":
            first = [c for c in stage_calls if c["attempt"] == 0]
            retry = variant in {"bad_json_retry", "wrong_json_flag"}
            report.update(
                {
                    "calibration": {
                        "overall": {
                            "n": 8,
                            "mae": 0.188,
                            "bias": 0.062,
                            "within_0_5": 1.0,
                            "exact": 0.625,
                        }
                    },
                    "repeat_spread": {
                        "samples": [
                            {
                                "id": base,
                                "runs": 2,
                                "ready": 2,
                                "overall": bands,
                                "spread": {
                                    key: max(bands) - min(bands)
                                    for key in ("overall",) + AUDIT.CRITERIA
                                },
                            }
                            for base, bands in values.items()
                        ],
                        "overall_spread_mean": 0.375,
                        "overall_spread_max": 0.5,
                        "any_failed": 0,
                    },
                    "ordering": {
                        "synthetic": {
                            "rows": [
                                {"id": sid}
                                for sid in (
                                    "official-1A-A",
                                    "official-1A-A#r2",
                                    "official-1A-B",
                                    "official-1A-B#r2",
                                )
                            ],
                            "pairs": 4,
                            "inversions": 0,
                            "ties": 0,
                            "spread": 0.75,
                        }
                    },
                    "kinds": {
                        "evaluate": {
                            "calls": len(stage_calls),
                            "first_attempts": 8,
                            "first_attempt_json_ok": round(sum(c["json_ok"] for c in first) / 8, 3),
                            "first_attempt_valid": 0.875 if retry else 1.0,
                            "json_problems": [
                                {
                                    "sample": c["sample"],
                                    "attempt": c["attempt"],
                                    "problem": "synthetic format failure",
                                }
                                for c in stage_calls
                                if AUDIT.strict_object(c["text"]) is None
                            ],
                            "final_ready": 1.0,
                            "truncated": 0,
                            "timeouts": 0,
                        }
                    },
                }
            )
        save(run / stage / "run_data.json", data)
        save(run / stage / "report.json", report)
        save(run / stage / "exit_status.json", {"code": 0})
        done = {"code": 0}
        if stage == "readremaining":
            done["image_descriptions_sha256"] = AUDIT.digest(
                run / stage / "image_descriptions.json"
            )
        save(run / (stage + ".done.json"), done)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--out", type=Path, default=HERE / "audit-selfcheck.json")
    args = parser.parse_args()
    checks, cases = {}, {}
    expected_failures = {
        "baseline": [],
        "bad_json_retry": [],
        "single_fence": [],
        "wrong_json_flag": ["call_4:json_flag_recomputed", "report_first_json"],
        "invalid_final": ["official-1A-A:bands_match_final_raw"],
        "wrong_cap": ["all_reservations_keep_fixed_caps"],
        "wrong_overall": ["official-1A-A:overall_recomputed"],
        "wrong_reading": ["official-1A-A:current_confirmed_reading"],
        "weekday": ["call_1:weekend_idle_interval"],
    }
    with tempfile.TemporaryDirectory(prefix="iwa-audit-synthetic-", dir="/private/tmp") as tmp:
        for variant, expected in expected_failures.items():
            private = Path(tmp) / variant
            fixture(private, args.source.resolve(), variant)
            out = private / "audit.json"
            result = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(HERE / "audit_export.py"),
                    "--private-root",
                    str(private),
                    "--source",
                    str(args.source),
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
            )
            if not out.exists():
                raise RuntimeError("synthetic audit did not produce output: " + variant)
            data = json.loads(out.read_text())
            checks[variant] = result.returncode == bool(expected) and (
                all(name in data["failed"] for name in expected) if expected else not data["failed"]
            )
            cases[variant] = {
                "passed": data["passed"],
                "total": data["total"],
                "audit_failures": data["failed"],
                "expected_failure_case": bool(expected),
                "counts": data["counts"],
                "json_observations": data["json_observations"],
            }
            if variant == "baseline":
                checks["independent_cost"] = Decimal(data["cost_estimate_cny"]["total"]) == Decimal(
                    ".0091452"
                )
            if variant == "bad_json_retry":
                checks["retry_keeps_first_format_failure"] = (
                    data["json_observations"]["first_text_invalid_format"] == 1
                    and data["counts"]["validation_retries"] == 1
                    and data["counts"]["text_reserved"] == 9
                    and Decimal(data["cost_estimate_cny"]["total"]) == Decimal(".0101832")
                )
            if variant == "single_fence":
                checks["fence_observation_distinct_from_bare"] = (
                    data["json_observations"]["single_fence_recovered_calls"] == 1
                )
            if variant == "weekday":
                checks["weekday_not_silently_idle_priced"] = (
                    data["cost_estimate_cny"]["unknown_cost_calls"] == 1
                )
    checks["surrounding_prose_rejected"] = AUDIT.strict_object('Here is JSON: {"ok": true}') is None
    checks["multiple_objects_rejected"] = AUDIT.strict_object('{"a": 1}\n{"b": 2}') is None
    checks["brace_repair_rejected"] = AUDIT.strict_object('{"a": 1') is None
    output = {
        "checks": checks,
        "passed": sum(checks.values()),
        "total": len(checks),
        "cases": cases,
        "all_fixture_content_synthetic": True,
        "real_model_calls": 0,
        "audit_script_sha256": AUDIT.digest(HERE / "audit_export.py"),
    }
    save(args.out, output)
    print(
        json.dumps(
            {
                "passed": output["passed"],
                "total": output["total"],
                "failed": [key for key, ok in checks.items() if not ok],
            }
        )
    )
    return int(not all(checks.values()))


if __name__ == "__main__":
    raise SystemExit(main())
