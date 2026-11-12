"""Offline review of evaluation-only model routing. No secrets or private samples."""

import io
import json
import socket
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

ROOT = Path("/private/tmp/studytracker-iwa-holdout-review-20261111")
sys.path.insert(0, str(ROOT))

from tools.ielts_writing_ai import batch, ledger, realcheck, realcheck_compare, review
from tools.ielts_writing_ai.config import load_settings
from tools.ielts_writing_ai.llm import ChatClient, FakeClient, LLMError, LLMResult

PRO = "deepseek-v4-pro"
FLASH = "deepseek-flash"


class Review(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="iwa-model-review-")
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)
        self.guard = patch.object(
            socket.socket, "connect", side_effect=AssertionError("Network prohibited")
        )
        self.guard.start()
        self.addCleanup(self.guard.stop)
        self.settings = load_settings(
            env={},
            env_file="/nonexistent",
            data_dir=self.path,
            llm_provider="deepseek",
            llm_api_key="synthetic-key",
            llm_model=FLASH,
            evaluate_model=PRO,
            evaluate_thinking="high",
        )

    def client(self):
        return ChatClient(
            provider="deepseek",
            base_url="https://invalid.invalid/chat/completions",
            api_key="synthetic-key",
            model=FLASH,
            timeout=120,
        )

    @staticmethod
    def response(text="{}", **extra):
        return io.BytesIO(
            json.dumps(
                {
                    "choices": [
                        {"message": {"content": text}, "finish_reason": "stop"}
                    ],
                    **extra,
                }
            ).encode()
        )

    def test_wire_models_thinking_timeout_and_response_fallback(self):
        client = self.client()
        sent = []

        def fake_open(request, timeout=None):
            sent.append((json.loads(request.data), timeout))
            return self.response()

        client._open = fake_open
        generator = review.Generator(None, self.settings, client)
        models = [
            generator._call([], kind, {"kind": kind}, 0, 100).model
            for kind in ("evaluate", "refine", "rewrite")
        ]
        self.assertEqual(models, [PRO, FLASH, FLASH])
        self.assertEqual([s[0]["model"] for s in sent], models)
        self.assertEqual([s[1] for s in sent], [420.0, None, None])
        self.assertEqual([s[0]["max_tokens"] for s in sent], [32000, 100, 100])
        self.assertEqual(
            [s[0]["thinking"]["type"] for s in sent],
            ["enabled", "disabled", "disabled"],
        )
        self.assertEqual(sent[0][0]["reasoning_effort"], "high")
        self.assertEqual(client.model, FLASH)

    def test_shared_client_concurrent_requests_do_not_mutate_base(self):
        client = self.client()
        barrier = threading.Barrier(2)
        seen = []

        def fake_open(request, timeout=None):
            body = json.loads(request.data)
            seen.append(body["model"])
            barrier.wait(timeout=3)
            return self.response()

        client._open = fake_open
        with ThreadPoolExecutor(max_workers=2) as pool:
            a = pool.submit(
                client.complete, [], json_mode=True, max_tokens=10, model=PRO
            )
            b = pool.submit(client.complete, [], json_mode=True, max_tokens=10)
            self.assertEqual((a.result().model, b.result().model), (PRO, FLASH))
        self.assertCountEqual(seen, [PRO, FLASH])
        self.assertEqual(client.model, FLASH)

    def test_validation_retry_keeps_evaluation_model(self):
        class Retry(FakeClient):
            def __init__(self):
                super().__init__(model=FLASH)
                self.options = []

            def complete(self, messages, **kw):
                self.options.append(kw)
                if len(self.options) == 1:
                    return LLMResult("not JSON", kw["model"], 1)
                return super().complete(messages, **kw)

        client = Retry()
        data = realcheck.run(
            self.settings,
            realcheck.load_samples("builtin")[:1],
            client=client,
            kinds=("evaluate",),
            max_calls=2,
        )
        self.assertEqual(len(client.options), 2)
        self.assertEqual([k["model"] for k in client.options], [PRO, PRO])
        self.assertEqual([k["timeout"] for k in client.options], [420.0, 420.0])
        self.assertEqual(
            data["samples"][0]["generations"]["evaluate"]["status"], "ready"
        )
        self.assertEqual(realcheck.build_report(data)["model"], PRO)

    def test_failure_metadata_and_ledger_reserve_name_pro(self):
        class Failed(FakeClient):
            def complete(self, messages, **kw):
                raise LLMError("http_500", "synthetic failure")

        book = ledger.Ledger(
            self.path / "ledger.jsonl",
            text_cap=2,
            vision_cap=0,
            run="probe",
            code_sha256="synthetic",
            prompt_version="probe",
        )
        original_finish = realcheck.Storage.finish_generation
        saved_models = []

        def capture(storage, gid, **kwargs):
            original_finish(storage, gid, **kwargs)
            saved_models.append(storage.get_generation(gid)["model"])

        with patch.object(realcheck.Storage, "finish_generation", capture):
            data = realcheck.run(
                self.settings,
                realcheck.load_samples("builtin")[:1],
                client=Failed(model=FLASH),
                kinds=("evaluate",),
                ledger=book,
            )
        self.assertEqual(data["calls"][0]["model"], PRO)
        self.assertEqual(saved_models, [PRO])
        entries = ledger.read(book.path)
        self.assertEqual([e["model"] for e in entries if e["type"] == "reserve"], [PRO])

    def test_batch_env_beats_opposite_config_and_shell(self):
        cfg = self.path / "fake.env"
        cfg.write_text(
            "IWA_LLM_PROVIDER=deepseek\nIWA_LLM_API_KEY=synthetic\n"
            "IWA_EVALUATE_MODEL=wrong-model\nIWA_EVALUATE_THINKING_TIMEOUT=420\n"
        )
        with patch.dict(
            "os.environ", {"IWA_EVALUATE_MODEL": "also-wrong", "IWA_LLM_MODEL": "wrong"}
        ):
            for side, model in batch.MODELS.items():
                env = batch.child_env(side, dry=False, env_file=cfg, out=self.path)
                settings = load_settings(env=env, env_file=cfg)
                self.assertEqual(
                    (settings.llm_model, settings.evaluate_model), (model, model)
                )
                self.assertEqual(settings.evaluate_thinking_timeout, 300.0)
                self.assertEqual(settings.evaluate_thinking, "high")

    def test_compare_sees_effective_model_not_base(self):
        items = realcheck.load_samples("builtin")[:1]
        a = realcheck.run(
            self.settings, items, client=FakeClient(model=FLASH), kinds=("evaluate",)
        )
        self.settings.evaluate_model = FLASH
        b = realcheck.run(
            self.settings, items, client=FakeClient(model=FLASH), kinds=("evaluate",)
        )

        def cond(data):
            return realcheck_compare.conditions(
                {
                    "dir": "probe",
                    "run_data": data,
                    "report": realcheck.build_report(data),
                }
            )

        ca, cb = cond(a), cond(b)
        self.assertEqual((ca["model"], cb["model"]), (PRO, FLASH))
        errors, _ = realcheck_compare.check_same_conditions(ca, cb)
        self.assertTrue(any("模型不同" in e for e in errors))
        errors, _ = realcheck_compare.check_same_conditions(
            ca, cb, allow_model_change=True
        )
        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
