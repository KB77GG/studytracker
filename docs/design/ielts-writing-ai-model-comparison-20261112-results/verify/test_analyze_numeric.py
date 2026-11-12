"""Synthetic-only checks. No private source is read, no network is used."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

SPEC = importlib.util.spec_from_file_location(
    "audit_numeric", Path(__file__).with_name("analyze_numeric.py")
)
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)


def request(
    start="2026-11-12T08:58:00+08:00", end="2026-11-12T08:59:00+08:00", tokens=None, done=True
):
    reserve = {"attempt": 0, "sample": "PRIVATE_SENTINEL_ID", "time": start}
    result = {
        "ok": True,
        "time": end,
        "tokens": (
            tokens
            if tokens is not None
            else {"prompt_tokens": 1000, "completion_tokens": 2000, "prompt_cache_hit_tokens": 200}
        ),
    }
    return reserve, result if done else None


class NumericChecks(unittest.TestCase):
    def test_peak_weekday_start(self):
        self.assertTrue(AUDIT.peak(AUDIT.timestamp("2026-11-12T09:00:00+08:00")))

    def test_peak_weekday_end_exclusive(self):
        self.assertFalse(AUDIT.peak(AUDIT.timestamp("2026-11-12T12:00:00+08:00")))

    def test_afternoon_peak(self):
        self.assertTrue(AUDIT.peak(AUDIT.timestamp("2026-11-12T14:00:00+08:00")))

    def test_weekend_offpeak(self):
        self.assertFalse(AUDIT.peak(AUDIT.timestamp("2026-11-14T10:00:00+08:00")))

    def test_timezone_conversion(self):
        self.assertEqual(AUDIT.timestamp("2026-11-12T01:00:00+00:00").hour, 9)

    def test_naive_time_not_assumed(self):
        self.assertIsNone(AUDIT.timestamp("2026-11-12T01:00:00"))

    def test_cross_boundary_range(self):
        value = AUDIT.request_stats([request(end="2026-11-12T09:01:00+08:00")], [2, 0.04, 8])
        self.assertEqual(value["time_bands"]["cross_boundary"], 1)
        self.assertAlmostEqual(value["cost_cny"]["total_upper_bound"], 0.017608)
        self.assertAlmostEqual(value["cost_cny"]["total_lower_bound"], 0.008804)

    def test_cross_boundary_at_end_conservative(self):
        band = AUDIT.time_band(
            AUDIT.timestamp("2026-11-12T08:59:00+08:00"),
            AUDIT.timestamp("2026-11-12T09:00:00+08:00"),
        )
        self.assertEqual(band, ("cross_boundary", 0.5, 1.0))

    def test_unknown_request_does_not_cost_zero(self):
        value = AUDIT.request_stats([request(done=False)], [2, 0.04, 8])
        self.assertIsNone(value["cost_cny"]["total_upper_bound"])
        self.assertEqual(value["usage_unknown_requests"], 1)
        self.assertIsNone(value["tokens_complete_total"]["completion_tokens"])
        self.assertIsNone(value["completion_tokens_max_known"])

    def test_partial_usage_keeps_known_subtotal(self):
        value = AUDIT.request_stats([request(tokens={"completion_tokens": 2000})], [2, 0.04, 8])
        self.assertEqual(value["tokens_known_subtotal"]["completion_tokens"], 2000)
        self.assertAlmostEqual(value["cost_cny"]["known_usage_lower"], 0.008)
        self.assertIsNone(value["cost_cny"]["total_upper_bound"])

    def test_unknown_cache_bounds(self):
        value = AUDIT.request_stats(
            [request(tokens={"prompt_tokens": 1000, "completion_tokens": 2000})], [2, 0.04, 8]
        )
        self.assertAlmostEqual(value["cost_cny"]["total_lower_bound"], 0.00802)
        self.assertAlmostEqual(value["cost_cny"]["total_upper_bound"], 0.009)

    def test_cache_cannot_exceed_prompt(self):
        with self.assertRaises(AUDIT.AuditError):
            AUDIT.request_stats(
                [
                    request(
                        tokens={
                            "prompt_tokens": 1,
                            "completion_tokens": 2,
                            "prompt_cache_hit_tokens": 3,
                        }
                    )
                ],
                [2, 0.04, 8],
            )

    def test_retry_denominator(self):
        first, done = request()
        retry = {**first, "attempt": 1}
        stats = AUDIT.request_stats([(first, done), (retry, done)], [2, 0.04, 8])
        self.assertEqual(
            (stats["first_requests"], stats["retry_requests"], stats["evaluations_with_retry"]),
            (1, 1, 1),
        )

    def test_rounded_rate_count(self):
        self.assertEqual(AUDIT.recovered_count(0.929, 14), 13)
        self.assertIsNone(AUDIT.recovered_count(0.8, 3))

    def test_projection_does_not_export_text(self):
        report = {
            "samples": 1,
            "essay": "PRIVATE_SENTINEL_TEXT",
            "per_sample": [
                {
                    "id": "PRIVATE_SENTINEL_ID",
                    "scores": {"overall": 7, "comment": "PRIVATE_SENTINEL_TEXT"},
                    "teacher": {"overall": 6.5, "rater": "PRIVATE_SENTINEL_NAME"},
                    "statuses": {"evaluate": "ready"},
                }
            ],
            "kinds": {
                "evaluate": {
                    "first_attempts": 1,
                    "first_attempt_json_ok": 1,
                    "first_attempt_valid": 1,
                    "final_ready": 1,
                    "json_problems": [{"problem": "PRIVATE_SENTINEL_TEXT"}],
                }
            },
            "ordering": {
                "PRIVATE_SENTINEL_TOPIC": {
                    "rows": [{"id": "PRIVATE_SENTINEL_ID", "nominal": 9, "ai": None}],
                    "missing": 1,
                    "spread": None,
                    "inversions": 0,
                }
            },
        }
        projected, _ = AUDIT.project_report(report)
        self.assertNotIn("PRIVATE_SENTINEL", json.dumps(projected))
        self.assertIsNone(projected["ordering"][0]["monotonic_nonincreasing"])
        self.assertIsNone(projected["ordering"][0]["highest_above_lowest"])

    def test_common_success_subset(self):
        def row(score, ready=True):
            return {
                "scores": {k: score if k == "overall" else None for k in AUDIT.SCORES},
                "teacher": {k: 6 if k == "overall" else None for k in AUDIT.SCORES},
                "ready": ready,
            }

        a = {"x": row(7), "y": row(9)}
        b = {"x": row(6.5), "y": row(None, False)}
        result = AUDIT.common_scoring(a, b)["overall"]
        self.assertEqual(result["common_successful_evaluations"], 1)
        self.assertEqual(result["flash"]["mae"], 1)
        self.assertEqual(result["pro"]["mae"], 0.5)

    def test_disallowed_read_refused(self):
        with self.assertRaises(AUDIT.AuditError):
            AUDIT.read_json(Path("/not_used"), "run_data.json")
        with self.assertRaises(AUDIT.AuditError):
            AUDIT.read_json(Path("/not_used"), "compare-dev/blind_key.json")

    def test_duplicate_ledger_entries_detected(self):
        row = {
            "type": "reserve",
            "id": "one",
            "run": "dev-flash",
            "kind": "evaluate",
            "category": "text",
            "model": "deepseek-flash",
            "attempt": 0,
            "cap": 184,
        }
        _, errors, _, _ = AUDIT.index_ledger([row, row])
        self.assertEqual(errors["duplicate_reserve"], 1)

    def test_orphan_done_detected(self):
        _, errors, _, _ = AUDIT.index_ledger([{"type": "done", "id": "missing"}])
        self.assertEqual(errors["done_without_reservation"], 1)

    def test_torn_last_line_counted(self):
        with tempfile.TemporaryDirectory(prefix="iwa-numeric-synthetic-") as td:
            root = Path(td)
            (root / "ledger-main.jsonl").write_text(
                '{"type":"header"}\n{"incomplete"', encoding="utf-8"
            )
            rows, torn, _ = AUDIT.read_ledger(root)
            self.assertEqual((len(rows), torn), (1, 1))

    def test_complete_synthetic_batch_and_private_sentinels(self):
        with tempfile.TemporaryDirectory(prefix="iwa-numeric-synthetic-") as td:
            root = Path(td)
            auth = {
                "authorized_stage": "main",
                "authorized_text_request_cap": 184,
                "authorized_vision_requests": 0,
                "only_kind": "evaluate",
                "thinking": "high",
                "max_output_tokens_per_request": 32000,
                "timeout_seconds": 300,
                "source_head": AUDIT.HEAD,
                "models": list(AUDIT.MODELS.values()),
                "peak_CNY_per_million": {"flash": [2, 0.04, 8], "pro": [9, 0.3, 27]},
                "off_peak_CNY_per_million": {"flash": [1, 0.02, 4], "pro": [4.5, 0.15, 13.5]},
            }
            (root / "authorization.json").write_text(json.dumps(auth))
            (root / "launcher_exit.json").write_text('{"code":0}')
            ledger = [{"type": "header", "code_sha256": "synthetic-fingerprint"}]
            summary = {"groups": {}, "PRIVATE_SENTINEL_TEXT": "never_export"}
            for group, n in AUDIT.GROUPS.items():
                summary["groups"][group] = {"runs": {}}
                for model, requested in AUDIT.MODELS.items():
                    run = f"{group}-{model}"
                    report_dir = root / run
                    report_dir.mkdir()
                    samples = []
                    for index in range(n):
                        sid = f"PRIVATE_SENTINEL_ID_{index}"
                        rid = f"{run}-{index}"
                        samples.append(
                            {
                                "id": sid,
                                "scores": {"overall": 6},
                                "teacher": {"overall": 6, "comment": "PRIVATE_SENTINEL_TEXT"},
                                "statuses": {"evaluate": "ready"},
                            }
                        )
                        ledger.extend(
                            [
                                {
                                    "type": "reserve",
                                    "id": rid,
                                    "run": run,
                                    "sample": sid,
                                    "kind": "evaluate",
                                    "category": "text",
                                    "model": requested,
                                    "attempt": 0,
                                    "cap": 184,
                                    "time": "2026-11-12T10:00:00+08:00",
                                },
                                {
                                    "type": "done",
                                    "id": rid,
                                    "ok": True,
                                    "time": "2026-11-12T10:00:01+08:00",
                                    "tokens": {
                                        "prompt_tokens": 1,
                                        "completion_tokens": 1,
                                        "prompt_cache_hit_tokens": 0,
                                    },
                                },
                            ]
                        )
                    metrics = {
                        "calls": n,
                        "first_attempts": n,
                        "first_attempt_json_ok": 1,
                        "first_attempt_valid": 1,
                        "final_ready": 1,
                        "completion_tokens_max": 1,
                    }
                    report = {
                        "model": requested,
                        "code_sha256": "synthetic-fingerprint",
                        "samples": n,
                        "calls": n,
                        "per_sample": samples,
                        "kinds": {"evaluate": metrics},
                        "usage": {
                            "text": {
                                "known_tokens": {"prompt": n, "completion": n},
                                "cache_hit_tokens": 0,
                            }
                        },
                    }
                    (report_dir / "report.json").write_text(json.dumps(report))
                    # Non-JSON sentinels: opening these would break the analysis.
                    (report_dir / "run_data.json").write_text("PRIVATE_SENTINEL_RAW")
                    (report_dir / "raw_calls.jsonl").write_text("PRIVATE_SENTINEL_RAW")
                    price = auth["peak_CNY_per_million"][model]
                    summary["groups"][group]["runs"][model] = {
                        "attempts": {
                            "requests": n,
                            "estimated_cost": n * (price[0] + price[2]) / 1e6,
                            "cost_is_lower_bound": False,
                        },
                        "final": metrics,
                    }
            (root / "ledger-main.jsonl").write_text(
                "\n".join(json.dumps(row) for row in ledger) + "\n"
            )
            (root / "summary.json").write_text(json.dumps(summary))
            result = AUDIT.audit(root, final_requested=True)
            self.assertFalse(result["provisional"])
            self.assertEqual(result["actual_reserved_requests"], 92)
            self.assertTrue(result["integrity"]["all_reports_reconcile"])
            self.assertIsNone(result["numeric_rule_checks"]["recommend_switch_to_pro"])
            self.assertNotIn("PRIVATE_SENTINEL", json.dumps(result))
            # A stale summary must block final numerical decision checks.
            summary["groups"]["dev"]["runs"]["flash"]["attempts"]["requests"] = 1
            (root / "summary.json").write_text(json.dumps(summary))
            result = AUDIT.audit(root, final_requested=True)
            self.assertTrue(result["provisional"])


if __name__ == "__main__":
    unittest.main()
