#!/usr/bin/env python3
"""Independently reproduce the numeric audit without importing the main analyzer.

From the main repository:
  .venv/bin/python -B docs/design/ielts-writing-ai-model-comparison-20261112-results/independent/recheck_numeric.py

Only authorization.json, launcher_exit.json, ledger-main.jsonl, the ten named
report.json files and the existing public numeric_summary.json are read.
Never opens data/config, raw_calls, run_data, summary.json, compare or blind files.
Output is numeric/boolean only; sample IDs are private in-memory join keys.

Ledger wall-time timestamps have one-second precision. Evaluation duration is
last completion minus first reservation, including validation retries. Common
repeat comparisons require two numeric overall scores in BOTH models. Repeated
evaluations are not independent essays. Cost uses Beijing Mon-Fri 09-12/14-18
peak rates and half price otherwise; a crossed boundary gives a half/full range.
It is a usage estimate, not a bill; reasoning tokens are already in completion.
This completed-batch check refuses unknown outcomes or usage instead of pricing
them as zero. It neither writes inputs nor reruns model requests.
"""

import argparse
import json
import math
from collections import Counter, defaultdict
from datetime import datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from statistics import mean
from zoneinfo import ZoneInfo

GROUPS = ("dev", "teacher", "rated_t2", "ordering", "lowband")
MODELS = ("flash", "pro")
CRITERIA = ("overall", "task", "coherence", "lexical", "grammar")
TOKEN_FIELDS = ("prompt_tokens", "completion_tokens", "prompt_cache_hit_tokens")
ZONE = ZoneInfo("Asia/Shanghai")
HERE = Path(__file__).resolve().parent


def load(root, relative):
    allowed = {"authorization.json", "launcher_exit.json"}
    allowed.update(f"{group}-{model}/report.json" for group in GROUPS for model in MODELS)
    assert relative in allowed
    path = root / relative
    assert path.resolve() == path and not path.is_symlink()
    return json.loads(path.read_text(encoding="utf-8"))


def numeric(value):
    return type(value) in (int, float) and math.isfinite(value)


def percentile(values, p):
    return sorted(values)[math.ceil(len(values) * p) - 1]


def duration_stats(values):
    return {
        "n": len(values),
        "p50": percentile(values, 0.5),
        "p90": percentile(values, 0.9),
        "max": max(values),
    }


def is_peak(at):
    return at.weekday() < 5 and (9 <= at.hour < 12 or 14 <= at.hour < 18)


def crosses_boundary(start, end):
    day = start.date()
    while day <= end.date():
        if day.weekday() < 5:
            for hour in (9, 12, 14, 18):
                if start < datetime.combine(day, time(hour), ZONE) <= end:
                    return True
        day += timedelta(days=1)
    return False


def independent_requests(root, public):
    auth = load(root, "authorization.json")
    ended = load(root, "launcher_exit.json")
    ledger_path = root / "ledger-main.jsonl"
    assert not ledger_path.is_symlink() and ledger_path.resolve() == ledger_path
    rows = [
        json.loads(line)
        for line in ledger_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    reserved = [r for r in rows if r["type"] == "reserve"]
    completed = [r for r in rows if r["type"] == "done"]
    done = {r["id"]: r for r in completed}
    assert ended["code"] == 0 and len(reserved) == len({r["id"] for r in reserved})
    assert len(done) == len(completed) == len(reserved)
    assert set(done) == {r["id"] for r in reserved}
    assert len(reserved) <= auth["authorized_text_request_cap"] == 184
    by_model, evaluations = defaultdict(list), defaultdict(list)
    for row in reserved:
        model = row["run"].rsplit("-", 1)[1]
        assert model in MODELS and row["kind"] == "evaluate"
        result = done[row["id"]]
        start = datetime.fromisoformat(row["time"]).astimezone(ZONE)
        end = datetime.fromisoformat(result["time"]).astimezone(ZONE)
        assert end >= start
        by_model[model].append((row, result, start, end))
        evaluations[(model, row["run"], row["sample"])].append((start, end))
    out = {
        "exit_code": ended["code"],
        "reservations": len(reserved),
        "completed": len(done),
        "authorized_cap": 184,
        "models": {},
    }
    for model, calls in by_model.items():
        prices = [Decimal(str(v)) for v in auth["peak_CNY_per_million"][model]]
        assert all(
            Decimal(str(v)) == prices[i] / 2
            for i, v in enumerate(auth["off_peak_CNY_per_million"][model])
        )
        costs = dict.fromkeys(("peak", "lower", "upper"), Decimal(0))
        bands, usage, wall = Counter(), Counter(), []
        for _, result, start, end in calls:
            tokens = result["tokens"]
            assert all(type(tokens.get(k)) is int and tokens[k] >= 0 for k in TOKEN_FIELDS)
            prompt, completion, hit = [tokens[k] for k in TOKEN_FIELDS]
            assert hit <= prompt
            usage.update({key: tokens[key] for key in TOKEN_FIELDS})
            cost = (
                (prompt - hit) * prices[0] + hit * prices[1] + completion * prices[2]
            ) / Decimal(1000000)
            cross = crosses_boundary(start, end)
            bands["cross_boundary" if cross else "peak" if is_peak(start) else "off_peak"] += 1
            costs["peak"] += cost
            costs["lower"] += cost * (Decimal(".5") if cross or not is_peak(start) else 1)
            costs["upper"] += cost * (1 if cross or is_peak(start) else Decimal(".5"))
            wall.append((end - start).total_seconds())
        evaluation_wall = [
            (max(e for _, e in v) - min(s for s, _ in v)).total_seconds()
            for key, v in evaluations.items()
            if key[0] == model
        ]
        expected = public["totals"][model]
        checks = [
            len(calls) == expected["actual_reserved_requests"],
            dict(usage) == expected["tokens_complete_total"],
            abs(
                float(costs["peak"]) - expected["cost_cny"]["fixed_peak_known_usage_upper_estimate"]
            )
            < 1e-8,
            abs(float(costs["lower"]) - expected["cost_cny"]["total_lower_bound"]) < 1e-8,
            abs(float(costs["upper"]) - expected["cost_cny"]["total_upper_bound"]) < 1e-8,
        ]
        assert all(checks)
        out["models"][model] = {
            "request_count": len(calls),
            "evaluation_count": len(evaluation_wall),
            "time_bands": {key: bands[key] for key in ("peak", "off_peak", "cross_boundary")},
            "tokens": dict(usage),
            "estimated_cost_cny": {k: float(v) for k, v in costs.items()},
            "is_provider_bill": False,
            "request_seconds": duration_stats(wall),
            "evaluation_seconds_including_retry": duration_stats(evaluation_wall),
            "comparison_checks": len(checks),
            "comparison_checks_passed": sum(checks),
        }
    return out


def score_and_repeat_checks(root, public):
    score_out, repeat_out, total_checks = {}, {}, 0
    for group in GROUPS:
        projected, repeat_pairs = {}, {}
        for model in MODELS:
            report = load(root, f"{group}-{model}/report.json")
            projected[model], pairs = {}, defaultdict(list)
            for row in report["per_sample"]:
                if row["statuses"].get("evaluate") != "ready":
                    continue
                sid = row["id"]
                assert sid not in projected[model]
                projected[model][sid] = {
                    "scores": {
                        k: row["scores"].get(k) for k in CRITERIA if numeric(row["scores"].get(k))
                    },
                    "teacher": {
                        k: row["teacher"].get(k) for k in CRITERIA if numeric(row["teacher"].get(k))
                    },
                }
                overall = projected[model][sid]["scores"].get("overall")
                if overall is not None:
                    pairs[sid.split("#r")[0]].append(overall)
            repeat_pairs[model] = {k: max(v) - min(v) for k, v in pairs.items() if len(v) == 2}
        if group != "ordering":
            common_pairs = set(repeat_pairs["flash"]) & set(repeat_pairs["pro"])
            repeat_out[group] = {"common_paired_essays": len(common_pairs)}
            for model in MODELS:
                values = [repeat_pairs[model][sid] for sid in common_pairs]
                repeat_out[group][model] = {
                    "mean_overall_difference": round(mean(values), 6) if values else None,
                    "max_overall_difference": max(values) if values else None,
                }
        if group not in ("teacher", "rated_t2"):
            continue
        common = set(projected["flash"]) & set(projected["pro"])
        result = {
            "common_evaluations": len(common),
            "distinct_essays": len({sid.split("#r")[0] for sid in common}),
            "criteria": {},
        }
        checks = []
        for key in CRITERIA:
            ids = [
                sid
                for sid in common
                if all(
                    key in projected[m][sid]["scores"] and key in projected[m][sid]["teacher"]
                    for m in MODELS
                )
            ]
            if not ids:
                continue
            item = {"common_evaluations": len(ids)}
            expected = public["groups"][group]["common_teacher_scores"][key]
            for model in MODELS:
                delta = [
                    projected[model][sid]["scores"][key] - projected[model][sid]["teacher"][key]
                    for sid in ids
                ]
                item[model] = {
                    "mae": round(mean(abs(d) for d in delta), 6),
                    "bias": round(mean(delta), 6),
                }
                checks.extend(
                    (
                        item[model]["mae"] == expected[model]["mae"],
                        item[model]["bias"] == expected[model]["bias"],
                        len(ids) == expected["common_successful_evaluations"],
                    )
                )
            result["criteria"][key] = item
        assert all(checks)
        result.update(comparison_checks=len(checks), comparison_checks_passed=sum(checks))
        score_out[group] = result
        total_checks += len(checks)
    return {
        "common_repeat_pairs": repeat_out,
        "common_scoring": score_out,
        "common_scoring_comparison_checks": total_checks,
        "common_scoring_comparison_checks_passed": total_checks,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--private-root", type=Path, default=Path("/Users/zhouxin/iwa-compare-real-20261112")
    )
    parser.add_argument(
        "--check", action="store_true", help="compare with evidence without writing it"
    )
    args = parser.parse_args()
    try:
        public = json.loads(
            (HERE.parent / "numeric/numeric_summary.json").read_text(encoding="utf-8")
        )
        assert public["provisional"] is False
        result = {
            "schema_version": 1,
            "timestamp_resolution_seconds": 1,
            "requests": independent_requests(args.private_root.resolve(), public),
            **score_and_repeat_checks(args.private_root.resolve(), public),
        }
        evidence = HERE / "independent_numeric_evidence.json"
        assert not evidence.is_symlink()
        if args.check:
            assert json.loads(evidence.read_text(encoding="utf-8")) == result
        else:
            evidence.write_text(
                json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                encoding="utf-8",
            )
        print(
            json.dumps(
                {
                    "ok": True,
                    "reservations": result["requests"]["reservations"],
                    "common_scoring_checks": result["common_scoring_comparison_checks"],
                }
            )
        )
        return 0
    except Exception:
        # Do not include arbitrary private parse errors, fields, IDs or text.
        print('{"ok":false}')
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
