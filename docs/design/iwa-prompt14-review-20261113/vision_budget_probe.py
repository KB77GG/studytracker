"""Offline .14 audit: timeout gates, CLI copied fields, staged 16-text/4-image cap.

Only synthetic in-memory credentials/data; no .env, student files, or network.
Temporary reports contain synthetic text and are deleted. Public output is numeric.
"""

from __future__ import annotations

import argparse
import contextlib
import copy
import io
import json
import logging
import socket
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()
    source = args.source.resolve()
    sys.path.insert(0, str(source))
    from tools.ielts_writing_ai import __main__ as cli
    from tools.ielts_writing_ai import essay, ledger, realcheck
    from tools.ielts_writing_ai.config import load_settings
    from tools.ielts_writing_ai.llm import FakeClient, LLMError, LLMResult
    from tools.ielts_writing_ai.tests.helpers import PNG_BYTES

    logging.disable(logging.CRITICAL)
    checks, observations = [], {}
    transport_attempts = []

    def check(name, passed, detail=None):
        checks.append({"check": name, "passed": bool(passed), "detail": detail})

    def network_denied(*_args, **_kwargs):
        transport_attempts.append(True)
        raise AssertionError("network forbidden by offline probe")

    class TrackedFake(FakeClient):
        def __init__(self, *, fail_image=None, retry_text=False):
            super().__init__()
            self.fail_image, self.retry_text = fail_image, retry_text
            self.received = []

        def complete(self, messages, **kwargs):
            self.received.append((copy.deepcopy(messages), copy.deepcopy(kwargs)))
            context = kwargs.get("context") or {}
            if context.get("kind") == "describe_image" and self.fail_image:
                if self.fail_image in {"timeout", "http_503", "network"}:
                    raise LLMError(self.fail_image, "synthetic failure")
                return LLMResult("{}", self.model, 1, {})
            if (
                context.get("kind") == "evaluate"
                and self.retry_text
                and context.get("attempt") == 0
            ):
                return LLMResult("{}", self.model, 1, {})
            return super().complete(messages, **kwargs)

    with tempfile.TemporaryDirectory(prefix="iwa14-budget-offline-") as temporary:
        root = Path(temporary)

        def settings(**env):
            values = {
                "IWA_LLM_PROVIDER": "fake",
                "IWA_VISION_PROVIDER": "fake",
                "IWA_DATA_DIR": str(root / "unused-data"),
                "IWA_EVALUATE_THINKING": "high",
                "IWA_EVALUATE_MODEL": "synthetic-pro",
            }
            values.update(env)
            return load_settings(env=values, env_file=root / "absent-config")

        def invoke(argv, *, config=None, fake=None):
            fake = fake or TrackedFake()
            config = config or settings()

            def build(s, *, vision=False):
                return None if vision and not s.vision_enabled else fake

            with (
                patch.object(cli, "load_settings", return_value=config),
                patch.object(realcheck, "build_client", side_effect=build),
                contextlib.redirect_stdout(io.StringIO()),
                contextlib.redirect_stderr(io.StringIO()),
            ):
                result = cli.main(argv)
            return result, fake

        with (
            patch.object(socket.socket, "connect", network_denied),
            patch.object(socket, "create_connection", network_denied),
        ):
            # Real CLI entry validates each timeout before client/ledger creation.
            for field in ("LLM_TIMEOUT", "EVALUATE_THINKING_TIMEOUT", "VISION_TIMEOUT"):
                for value in ("inf", "-inf", "nan", "0", "-1", "3601", "1e10"):
                    cfg = settings(**{f"IWA_{field}": value})
                    invalid_ledger = root / "never-created-ledger.jsonl"
                    codes = []
                    for command in (
                        ["check"],
                        ["serve"],
                        ["realcheck", "--ledger", str(invalid_ledger), "--ledger-text-cap", "16"],
                    ):
                        code, fake = invoke(command, config=cfg)
                        codes.append(code)
                        check(
                            f"{field}_{value}_{command[0]}_preflight",
                            code == 2 and not fake.received,
                        )
                    check(f"{field}_{value}_no_ledger", not invalid_ledger.exists())
                for value in ("0.5", "240", "3600"):
                    cfg = settings(**{f"IWA_{field}": value})
                    cfg.validate()
                    check(f"{field}_{value}_accepted", getattr(cfg, field.lower()) == float(value))
                cfg = settings(**{f"IWA_{field}": "not-a-number"})
                cfg.validate()
                check(
                    f"{field}_nonnumeric_legacy_default",
                    getattr(cfg, field.lower()) in (120, 180, 420),
                )

            image = root / "synthetic.png"
            image.write_bytes(PNG_BYTES)
            rows = [
                {
                    "id": f"synthetic-{n}",
                    "task_type": "task1",
                    "prompt": "The chart shows the number of visitors to four museums in 2020.",
                    "essay": "Museum C had the most visitors while Museum D had the fewest visitors.",
                    "image": image.name,
                }
                for n in range(4)
            ]
            all_path, remainder_path = root / "all.jsonl", root / "remaining.jsonl"

            def write_rows(path, items):
                path.write_text("".join(json.dumps(row) + "\n" for row in items), encoding="utf-8")

            write_rows(all_path, rows)
            write_rows(remainder_path, rows[1:])
            book = root / "ledger-t1.jsonl"

            def image_args(samples, out, *, limit=None, ledger_path=book, max_calls=4):
                command = [
                    "realcheck",
                    "--samples",
                    str(samples),
                    "--images-only",
                    "--with-vision",
                    "--max-calls",
                    str(max_calls),
                    "--ledger",
                    str(ledger_path),
                    "--ledger-text-cap",
                    "16",
                    "--ledger-vision-cap",
                    "4",
                    "--ledger-run",
                    out,
                    "--out",
                    str(root / out),
                ]
                return command + (["--limit", str(limit)] if limit is not None else [])

            first_code, first_fake = invoke(image_args(all_path, "first", limit=1, max_calls=1))
            first = realcheck.load_image_outcomes(root / "first/image_descriptions.json")
            check(
                "first_limit1_one_image_no_text", first_code == 0 and len(first_fake.received) == 1
            )
            check("first_exact_id", set(first) == {rows[0]["id"]})
            first_usage = ledger.summarize(ledger.read(book))
            check(
                "first_counts_in_shared4",
                first_usage["vision"]["reserved"] == 1 and first_usage["text"]["reserved"] == 0,
            )

            # This boundary represents the mandatory human check. No second image is
            # requested by the first command; the remainder is a separate command.
            remain_code, remain_fake = invoke(image_args(remainder_path, "remaining", max_calls=3))
            remaining = realcheck.load_image_outcomes(root / "remaining/image_descriptions.json")
            check(
                "remaining3_only",
                remain_code == 0
                and len(remain_fake.received) == 3
                and not set(first) & set(remaining),
            )
            combined = {**first, **remaining}
            check(
                "merge_exact4_ready",
                set(combined) == {r["id"] for r in rows}
                and all(v["status"] == "ready" for v in combined.values()),
            )
            frozen_path = root / "frozen.json"
            frozen_path.write_text(json.dumps(realcheck.image_file(combined)), encoding="utf-8")
            check(
                "same_image_four_essay_ids_each_once",
                ledger.summarize(ledger.read(book))["vision"]["reserved"] == 4,
            )

            evaluation = [
                "realcheck",
                "--samples",
                str(all_path),
                "--kinds",
                "evaluate",
                "--repeat",
                "2",
                "--image-descriptions",
                str(frozen_path),
                "--require-ready-images",
                "--max-calls",
                "16",
                "--ledger",
                str(book),
                "--ledger-text-cap",
                "16",
                "--ledger-vision-cap",
                "4",
                "--ledger-run",
                "text",
                "--out",
                str(root / "text"),
            ]
            text_code, text_fake = invoke(evaluation, fake=TrackedFake(retry_text=True))
            text_run = json.loads((root / "text/run_data.json").read_text())
            check(
                "eight_evaluations_all_ready",
                text_code == 0
                and len(text_run["samples"]) == 8
                and all(
                    s["generations"]["evaluate"]["status"] == "ready" for s in text_run["samples"]
                ),
            )
            check(
                "worst_case16_text_zero_vision",
                len(text_fake.received) == 16
                and all(k[1]["context"]["kind"] == "evaluate" for k in text_fake.received),
            )
            check("all8_inputs_frozen", all(s["image_reused"] for s in text_run["samples"]))
            usage = ledger.summarize(ledger.read(book))
            check(
                "total16plus4",
                usage["text"]["reserved"] == 16
                and usage["vision"]["reserved"] == 4
                and usage["text"]["unknown"] == usage["vision"]["unknown"] == 0,
            )
            check(
                "zero_transport_retries",
                all(
                    k[1]["retries"] == 0
                    for k in first_fake.received + remain_fake.received + text_fake.received
                ),
            )
            check(
                "pro_high32000_420_preserved",
                all(
                    (k[1]["thinking"], k[1]["max_tokens"], k[1]["timeout"], k[1]["model"])
                    == ("high", 32000, 420, "synthetic-pro")
                    for k in text_fake.received
                ),
            )
            image_redo_code, image_redo_fake = invoke(
                image_args(all_path, "image-redo", limit=1, max_calls=1)
            )
            text_redo_code, text_redo_fake = invoke(evaluation)
            check(
                "full_ledger_blocks_fifth_image",
                image_redo_code == 3 and not image_redo_fake.received,
            )
            check(
                "full_ledger_blocks_seventeenth_text",
                text_redo_code == 3 and not text_redo_fake.received,
            )
            observations["synthetic_worst_case"] = {
                "text_reserved": usage["text"]["reserved"],
                "vision_reserved": usage["vision"]["reserved"],
                "evaluations": 8,
                "distinct_essays": 4,
                "image_commands": [1, 3],
                "text_retries": 8,
            }

            # CLI cannot combine images-only with frozen input to skip completed IDs.
            incompatible, incompatible_fake = invoke(
                image_args(all_path, "bad-combination") + ["--image-descriptions", str(frozen_path)]
            )
            check(
                "images_only_plus_frozen_rejected_without_call",
                incompatible == 2 and not incompatible_fake.received,
            )

            # Document why a whole-file restart after --limit 1 is unsafe: it re-reads
            # the first id and hits the cap before reading the final id.
            naive_book = root / "naive-ledger.jsonl"
            invoke(
                image_args(all_path, "naive-first", limit=1, max_calls=1, ledger_path=naive_book)
            )
            naive_code, naive_fake = invoke(
                image_args(all_path, "naive-rest", ledger_path=naive_book)
            )
            naive_reserves = [e for e in ledger.read(naive_book) if e.get("type") == "reserve"]
            check(
                "whole4_restart_duplicates_first_and_misses_last",
                naive_code == 3
                and len(naive_fake.received) == 3
                and sum(e["sample"] == rows[0]["id"] for e in naive_reserves) == 2
                and rows[-1]["id"] not in {e["sample"] for e in naive_reserves},
            )

            for mode in ("timeout", "http_503", "network", "invalid_json"):
                failed_book = root / f"failed-{mode}.jsonl"
                fail_out = f"failed-{mode}"
                failure_code, failed_fake = invoke(
                    image_args(all_path, fail_out, limit=1, max_calls=1, ledger_path=failed_book),
                    fake=TrackedFake(fail_image=mode),
                )
                failed_path = root / fail_out / "image_descriptions.json"
                failed_outcomes = realcheck.load_image_outcomes(failed_path)
                check(
                    f"{mode}_one_image_consumed_no_retry",
                    failure_code in (3, 5)
                    and len(failed_fake.received) == 1
                    and ledger.summarize(ledger.read(failed_book))["vision"]["reserved"] == 1,
                )
                check(
                    f"{mode}_failure_exported", failed_outcomes[rows[0]["id"]]["status"] == "failed"
                )
                before = failed_book.read_bytes()
                stopped_code, stopped_fake = invoke(
                    [
                        "realcheck",
                        "--samples",
                        str(all_path),
                        "--limit",
                        "1",
                        "--repeat",
                        "2",
                        "--kinds",
                        "evaluate",
                        "--image-descriptions",
                        str(failed_path),
                        "--require-ready-images",
                        "--ledger",
                        str(failed_book),
                        "--ledger-text-cap",
                        "16",
                        "--ledger-vision-cap",
                        "4",
                        "--out",
                        str(root / f"blocked-{mode}"),
                    ]
                )
                check(
                    f"{mode}_ready_gate_no_call_or_ledger_write",
                    stopped_code == 2
                    and not stopped_fake.received
                    and before == failed_book.read_bytes(),
                )
                # Without the ready gate, frozen failures are still never re-read.
                repeated = realcheck.expand_repeats(copy.deepcopy(rows[:1]), 2)
                repeated[0]["image"] = repeated[1]["image"] = str(image)
                check(
                    f"{mode}_frozen_failure_applied_to_both",
                    realcheck.apply_image_descriptions(repeated, failed_path) == 2,
                )
                freeze_fake = TrackedFake()
                frozen_run = realcheck.run(
                    settings(),
                    repeated,
                    client=freeze_fake,
                    vision_client=freeze_fake,
                    kinds=(),
                    max_calls=2,
                )
                check(
                    f"{mode}_frozen_failure_repeat_zero_calls",
                    not freeze_fake.received
                    and all(
                        s["image_status"] == "failed" and s["image_reused"]
                        for s in frozen_run["samples"]
                    ),
                )

            # New confirmation fields flow through the real CLI, not just helper calls.
            copied_source = "Synthetic local confirmation marker"
            copied_row = {
                "id": "synthetic-copy",
                "task_type": "task2",
                "prompt": "Discuss museum admission fees.",
                "essay": "Museum admission fees should be discussed.\nMy own conclusion favours free admission for children.",
                "copied_from_question": [{"paragraph": 1}],
                "copied_source": copied_source,
            }
            copied_path = root / "copied.jsonl"
            write_rows(copied_path, [copied_row])
            copied_code, copied_fake = invoke(
                [
                    "realcheck",
                    "--samples",
                    str(copied_path),
                    "--kinds",
                    "evaluate",
                    "--max-calls",
                    "2",
                    "--out",
                    str(root / "copied"),
                ]
            )
            copied_run = json.loads((root / "copied/run_data.json").read_text())
            sub = copied_run["samples"][0]["submission"]
            spans = json.loads(sub["copied_spans"])
            sent = json.dumps(copied_fake.received, ensure_ascii=False)
            check(
                "copied_cli_export_preserves_confirmation",
                copied_code == 0 and spans["source"] == copied_source and len(spans["spans"]) == 1,
            )
            check(
                "copied_cli_payload_counts_exclusion_without_source",
                "word_count_without_copied" in sent and copied_source not in sent,
            )
            observations["synthetic_copied_words"] = {
                "all": essay.count_words(copied_row["essay"]),
                "confirmed": essay.count_words(spans["spans"][0]["text"]),
            }
            for change in (
                {"copied_source": None},
                {"copied_from_question": None},
                {"copied_from_question": [{"paragraph": 3}]},
                {"copied_source": "x" * 201},
            ):
                bad = dict(copied_row, **change)
                write_rows(copied_path, [bad])
                bad_book = root / "bad-copy-ledger.jsonl"
                bad_code, bad_fake = invoke(
                    [
                        "realcheck",
                        "--samples",
                        str(copied_path),
                        "--ledger",
                        str(bad_book),
                        "--ledger-text-cap",
                        "16",
                    ]
                )
                check(
                    f"invalid_copied_cli_{len(checks)}_before_ledger",
                    bad_code == 2 and not bad_fake.received and not bad_book.exists(),
                )

    check("network_attempts_zero", not transport_attempts)
    output = {
        "source": str(source),
        "head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=source, text=True
        ).strip(),
        "checks": checks,
        "passed": sum(c["passed"] for c in checks),
        "total": len(checks),
        "real_calls": 0,
        "network_attempts": len(transport_attempts),
        "observations": observations,
        "limitations": [
            "Synthetic data only; no real chart reading or model quality claim.",
            "Ledger caps are caller-supplied, not immutable ledger headers; operator must retain 16/4.",
            "Ledger does not deduplicate sample ids or provide resume; use explicit remaining-file split.",
            "Image outcomes map ids only; bind original input/image hashes externally before paid execution.",
        ],
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                k: output[k]
                for k in ("passed", "total", "real_calls", "network_attempts", "observations")
            },
            ensure_ascii=False,
        )
    )
    return 0 if output["passed"] == output["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
