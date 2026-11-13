"""Adapted copy (2026-11-13, after review f46756f): the reviewer's original recorded
that invalid IWA_VISION_TIMEOUT values passed validate(); this copy checks that they are
now refused before any client, request or ledger reservation exists. Everything else is
unchanged.

Synthetic, offline audit of prompt .13 vision routing and realcheck accounting.

Run with the main checkout's .venv; pass the isolated review source explicitly.
No configuration file, real credential, external network, or student data is used.
The urllib opener is replaced below the request builder, so payload construction,
timeout selection, response parsing, Generator, realcheck and ledger remain real.
"""

from __future__ import annotations

import argparse
import io
import json
import logging
import socket
import subprocess
import sys
import tempfile
import urllib.error
from pathlib import Path
from unittest.mock import patch


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(args.source.resolve()))
    from tools.ielts_writing_ai import ledger, prompts, realcheck, review
    from tools.ielts_writing_ai.config import ConfigError, load_settings
    from tools.ielts_writing_ai.llm import FakeClient, build_client
    from tools.ielts_writing_ai.tests.helpers import PNG_BYTES
    from tools.ielts_writing_ai.tests.test_visual import reading

    logging.disable(logging.CRITICAL)
    checks = []
    observations = {}

    def check(name, value, detail=None):
        checks.append({"check": name, "passed": bool(value), "detail": detail})

    class Reply(io.BytesIO):
        status = 200

    class WireStub:
        def __init__(self, mode="ok"):
            self.mode = mode
            self.requests = []

        def open(self, request, timeout):
            body = json.loads(request.data)
            self.requests.append({"body": body, "timeout": timeout})
            # This is the same stdlib check urllib/socket perform before connecting.
            with socket.socket() as sock:
                sock.settimeout(timeout)
            if self.mode == "timeout":
                raise TimeoutError()
            if self.mode == "http_503":
                raise urllib.error.HTTPError(request.full_url, 503, "stub", {}, None)
            if self.mode == "network":
                raise urllib.error.URLError("synthetic offline failure")
            text = {
                "empty": "",
                "unstructured": "Synthetic chart could not be read.",
                "invalid_json": "{}",
            }.get(self.mode, reading())
            raw = {
                "model": body["model"],
                "choices": [
                    {
                        "message": {"content": text},
                        "finish_reason": "length" if self.mode == "truncated" else "stop",
                    }
                ],
                "usage": {"prompt_tokens": 90, "completion_tokens": 17},
            }
            encoded = b"not json" if self.mode == "invalid_response" else json.dumps(raw).encode()
            return Reply(encoded)

    with tempfile.TemporaryDirectory(prefix="iwa-vision-offline-") as tmp:
        root = Path(tmp)

        def settings(**env):
            config = {
                "IWA_DATA_DIR": str(root / "data"),
                "IWA_LLM_PROVIDER": "deepseek",
                "IWA_LLM_API_KEY": "synthetic-offline-only",
                "IWA_LLM_BASE_URL": "http://127.0.0.1:1/not-contacted",
                "IWA_VISION_PROVIDER": "deepseek",
                "IWA_VISION_BASE_URL": "http://127.0.0.1:1/not-contacted",
                "IWA_EVALUATE_MODEL": "deepseek-v4-pro",
                "IWA_EVALUATE_THINKING": "high",
            }
            config.update({f"IWA_{key}": value for key, value in env.items()})
            result = load_settings(env=config, env_file=root / "absent-config")
            result.validate()
            return result

        def client(s, mode="ok", *, vision=True):
            result = build_client(s, vision=vision)
            result._opener = WireStub(mode)
            return result

        def new_ledger(name, vision_cap=1):
            return ledger.Ledger(
                root / f"{name}.jsonl",
                text_cap=0,
                vision_cap=vision_cap,
                run=name,
                code_sha256="synthetic-code",
                prompt_version=prompts.PROMPT_VERSION,
            )

        image = root / "synthetic.png"
        image.write_bytes(PNG_BYTES)
        sample = {
            "id": "synthetic-chart",
            "task_type": "task1",
            "prompt": "The chart shows visits to four synthetic museums in 2020.",
            "essay": "Museum C had the most visits, while D had the fewest visits.",
            "image": str(image),
        }

        def run(s, vision_client, book, repeats=1):
            return realcheck.run(
                s,
                realcheck.expand_repeats([sample], repeats),
                client=FakeClient(),
                vision_client=vision_client,
                kinds=(),
                max_calls=8,
                ledger=book,
            )

        s = settings()
        check(
            "preset_flash_and_key_reuse",
            s.vision_model == "deepseek-flash" and s.vision_api_key == s.llm_api_key,
        )
        check("defaults_2000_180", (s.vision_max_tokens, s.vision_timeout) == (2000, 180.0))
        c = client(s)
        book = new_ledger("success")
        data = run(s, c, book, repeats=2)
        req = c._opener.requests[0]
        body = req["body"]
        check(
            "request_flash_disabled_2000_180",
            (body["model"], body.get("thinking"), body["max_tokens"], req["timeout"])
            == ("deepseek-flash", {"type": "disabled"}, 2000, 180.0),
        )
        check(
            "vision_no_reasoning_effort_and_no_json_response_format",
            "reasoning_effort" not in body and "response_format" not in body,
        )
        blocks = body["messages"][0]["content"]
        check(
            "inline_image_user_message",
            body["messages"][0]["role"] == "user"
            and any(
                b.get("image_url", {}).get("url", "").startswith("data:image/png;base64,")
                for b in blocks
            ),
        )
        check(
            "successful_reading_frozen_across_repeats",
            len(c._opener.requests) == 1
            and [x["image_status"] for x in data["samples"]] == ["ready", "ready"],
        )
        report = realcheck.build_report(data)
        realcheck.write_report(data, report, root / "export")
        exported = json.loads((root / "export/run_data.json").read_text())
        check(
            "export_records_new_vision_budget_timeout",
            (
                exported["settings"]["vision_max_tokens"],
                exported["settings"]["vision_timeout"],
                exported["calls"][0]["max_tokens"],
                exported["calls"][0]["thinking"],
            )
            == (2000, 180.0, 2000, "off"),
        )
        check(
            "ledger_success_category_and_tokens",
            book.check()["vision"]
            == {
                "reserved": 1,
                "ok": 1,
                "failed": 0,
                "unknown": 0,
            }
            and book.check()["text"]["reserved"] == 0,
        )
        observations["export_locations"] = {
            "vision_max_tokens": "run_data.json.settings and raw_calls.jsonl.max_tokens",
            "vision_timeout": "run_data.json.settings (not duplicated in raw calls/ledger)",
            "ledger": "category/model/outcome/token counts; request limits are persistent",
        }

        overrides = settings(VISION_MAX_TOKENS="3000", VISION_TIMEOUT="240")
        c2 = client(overrides)
        run(overrides, c2, new_ledger("overrides"))
        check(
            "override_3000_240_reaches_transport",
            (c2._opener.requests[0]["body"]["max_tokens"], c2._opener.requests[0]["timeout"])
            == (3000, 240.0),
        )

        text = client(s, vision=False)
        generator = review.Generator(None, s, text)
        routing = {}
        for kind in ("evaluate", "refine", "rewrite"):
            generator._call(
                [{"role": "user", "content": "synthetic request"}],
                kind,
                {"kind": kind},
                0,
                prompts.MAX_TOKENS[kind],
            )
            r = text._opener.requests[-1]
            routing[kind] = {
                k: r["body"].get(k) for k in ("model", "thinking", "reasoning_effort", "max_tokens")
            } | {"timeout": r["timeout"]}
        check(
            "evaluate_pro_high_32000_420_unchanged",
            routing["evaluate"]
            == {
                "model": "deepseek-v4-pro",
                "thinking": {"type": "enabled"},
                "reasoning_effort": "high",
                "max_tokens": 32000,
                "timeout": 420.0,
            },
        )
        check(
            "refine_rewrite_flash_off_base_timeout",
            all(
                routing[k]["model"] == "deepseek-flash"
                and routing[k]["thinking"] == {"type": "disabled"}
                and routing[k]["timeout"] == 120.0
                and routing[k]["max_tokens"] == prompts.MAX_TOKENS[k]
                for k in ("refine", "rewrite")
            ),
        )
        observations["routing"] = routing

        failures = {}
        for mode in (
            "timeout",
            "http_503",
            "network",
            "truncated",
            "empty",
            "invalid_response",
            "unstructured",
            "invalid_json",
        ):
            c = client(s, mode)
            book = new_ledger(mode)
            data = run(s, c, book, repeats=2)
            before = len(c._opener.requests)
            resumed = run(s, c, book)
            after = len(c._opener.requests)
            counts = book.check()["vision"]
            call = data["calls"][0]
            failures[mode] = {
                "transport_attempts": before,
                "resume_added_attempts": after - before,
                "recorded_error": call["error"],
                "image_status": data["samples"][0]["image_status"],
                "image_error": data["samples"][0]["image_error"],
                "ledger": counts,
                "resume_abort": resumed["aborted"]["code"],
                "usage_preserved": call["usage"],
            }
            check(
                f"{mode}_one_attempt_failed_image_budget_retained",
                before == after == 1
                and len(data["calls"]) == 1
                and counts["reserved"] == 1
                and data["samples"][0]["image_status"] == "failed"
                and resumed["aborted"]["code"] == "ledger_cap",
            )
            if mode in ("truncated", "empty"):
                check(
                    f"{mode}_usage_preserved",
                    call["usage"]
                    == {
                        "prompt_tokens": 90,
                        "completion_tokens": 17,
                    }
                    and counts["failed"] == 1,
                )
        observations["failures"] = failures

        try:
            settings(VISION_PROVIDER="unsupported-provider")
        except ConfigError:
            check("invalid_provider_rejected", True)
        else:
            check("invalid_provider_rejected", False)
        fallbacks = settings(VISION_MAX_TOKENS="nonnumeric", VISION_TIMEOUT="nonnumeric")
        check(
            "nonnumeric_values_fallback",
            (fallbacks.vision_max_tokens, fallbacks.vision_timeout) == (2000, 180.0),
        )
        clamped = settings(VISION_MAX_TOKENS="-1")
        check("nonpositive_tokens_clamped", clamped.vision_max_tokens == 1)
        illegal = {}
        for value in ("0", "-1", "nan", "inf", "-inf", "1e10"):
            try:
                settings(VISION_TIMEOUT=value)
            except ConfigError as exc:
                illegal[value] = {"rejected_by_validate": True, "message": str(exc)}
            else:
                illegal[value] = {"rejected_by_validate": False}
            check(f"invalid_timeout_{value}_rejected", illegal[value]["rejected_by_validate"])
        for value, expected in (("240", 240.0), ("3600", 3600.0)):
            check(
                f"valid_timeout_{value}_accepted",
                settings(VISION_TIMEOUT=value).vision_timeout == expected,
            )
        observations["invalid_timeout_values"] = illegal

    result = {
        "source": str(args.source.resolve()),
        "head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=args.source, text=True
        ).strip(),
        "scope": "synthetic opener stub; sockets never connect; no .env or real key read",
        "paid_model_calls": 0,
        "checks_passed": sum(c["passed"] for c in checks),
        "checks_total": len(checks),
        "checks": checks,
        "observations": observations,
        "official_docs_checked": [
            "https://api-docs.deepseek.com/guides/vision/",
            "https://api-docs.deepseek.com/guides/thinking_mode/",
            "https://api-docs.deepseek.com/quick_start/pricing/",
        ],
    }
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps({k: result[k] for k in ("checks_passed", "checks_total", "paid_model_calls")}))
    return 0 if all(c["passed"] for c in checks) else 1


if __name__ == "__main__":
    with (
        patch.object(socket.socket, "connect", side_effect=AssertionError("network forbidden")),
        patch.object(socket.socket, "connect_ex", side_effect=AssertionError("network forbidden")),
        patch("socket.create_connection", side_effect=AssertionError("network forbidden")),
    ):
        raise SystemExit(main())
