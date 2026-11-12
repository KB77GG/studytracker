"""The evaluation uses its own model (IWA_EVALUATE_MODEL). The first real comparison
(2026-11-12, docs/design/ielts-writing-ai-model-comparison-20261112-results) chose
deepseek-v4-pro for the evaluation; refine and rewrite were not compared and keep
IWA_LLM_MODEL. Pro took up to 255 s per evaluation request, so the evaluation timeout
default is 420 s. No network: the real client talks to a local stub server."""

import shutil
import tempfile
import threading
import unittest
from http.server import HTTPServer
from pathlib import Path

from tools.ielts_writing_ai import batch, realcheck
from tools.ielts_writing_ai.config import load_settings
from tools.ielts_writing_ai.llm import ChatClient, FakeClient

from .helpers import AppTestCase, settings_for
from .test_llm import StubHandler, ok

PRO = "deepseek-v4-pro"


class ModelsClient(FakeClient):
    """Records the model each generation kind asked for."""

    def __init__(self):
        super().__init__(model="deepseek-flash")
        self.asked = []

    def complete(self, messages, **kwargs):
        self.asked.append(((kwargs.get("context") or {}).get("kind"), kwargs.get("model")))
        return super().complete(messages, **kwargs)


class SettingsTest(unittest.TestCase):
    def settings(self, **env):
        return load_settings(env={f"IWA_{k}": v for k, v in env.items()}, env_file="/nonexistent")

    def test_the_evaluation_model_defaults_to_the_main_model(self):
        s = self.settings(LLM_PROVIDER="deepseek", LLM_API_KEY="k")
        self.assertEqual(
            (s.evaluate_model, s.public_summary()["evaluate_model"]), ("", "deepseek-flash")
        )
        self.assertEqual(s.evaluate_thinking_timeout, 420.0)
        s = self.settings(LLM_PROVIDER="deepseek", LLM_API_KEY="k", EVALUATE_MODEL=f" {PRO} ")
        self.assertEqual((s.llm_model, s.evaluate_model), ("deepseek-flash", PRO))
        self.assertEqual(s.public_summary()["evaluate_model"], PRO)
        s.validate()
        self.assertEqual(
            self.settings(EVALUATE_THINKING_TIMEOUT="300").evaluate_thinking_timeout, 300.0
        )


class GeneratorTest(AppTestCase):
    settings_overrides = {"evaluate_thinking": "high", "evaluate_model": PRO}

    def setUp(self):
        super().setUp()
        self.client_llm = ModelsClient()
        self.app = self.make_app()
        self.storage = self.app.extensions["iwa"].storage

    def test_only_the_evaluation_asks_for_the_evaluation_model(self):
        _uid, code = self.add_user()
        client = self.login(code)
        public_id = self.submit(client).get_json()["public_id"]
        asked = dict(self.client_llm.asked)
        self.assertEqual(asked["evaluate"], PRO)
        self.assertIsNone(asked["refine"])  # the client's own model
        self.assertIsNone(asked["rewrite"])
        sub = client.get(f"/api/submissions/{public_id}").get_json()["submission"]
        models = {kind: g["model"] for kind, g in sub["generations"].items()}
        self.assertEqual(
            models, {"evaluate": PRO, "refine": "deepseek-flash", "rewrite": "deepseek-flash"}
        )


class WithoutEvaluationModelTest(AppTestCase):
    def test_nothing_changes_when_it_is_not_set(self):
        self.client_llm = ModelsClient()
        self.app = self.make_app()
        _uid, code = self.add_user()
        self.submit(self.login(code))
        self.assertEqual({model for _kind, model in self.client_llm.asked}, {None})


class ClientTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), StubHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}/v1/chat/completions"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_one_request_can_name_another_model(self):
        StubHandler.requests = []
        client = ChatClient(
            provider="deepseek",
            base_url=self.url,
            api_key="secret",
            model="deepseek-flash",
            timeout=5,
        )
        for model in (PRO, None):
            StubHandler.responses = [ok('{"a": 1}')]
            client.complete([], json_mode=True, max_tokens=50, model=model)
        self.assertEqual(
            [r["body"]["model"] for r in StubHandler.requests], [PRO, "deepseek-flash"]
        )


class RealcheckTest(unittest.TestCase):
    def test_the_run_reports_and_records_the_evaluation_model(self):
        tmp = Path(tempfile.mkdtemp(prefix="iwa-evalmodel-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        settings = settings_for(str(tmp / "d"), evaluate_model=PRO, evaluate_thinking="high")
        items = realcheck.load_samples("builtin")[:1]
        data = realcheck.run(
            settings, items, client=FakeClient(model="deepseek-flash"), kinds=("evaluate",)
        )
        self.assertEqual({c["model"] for c in data["calls"]}, {PRO})
        report = realcheck.build_report(data)
        self.assertEqual((report["model"], report["served_models"]), (PRO, [PRO]))
        both = dict(data, kinds=["evaluate", "refine"])
        self.assertEqual(realcheck.run_model(both), "fake-demo（评价 deepseek-v4-pro）")

    def test_the_comparison_batch_keeps_each_side_on_its_own_model(self):
        # A trial configuration that evaluates with Pro must not turn the batch's
        # Flash side into Pro.
        tmp = Path(tempfile.mkdtemp(prefix="iwa-evalmodel-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        env_file = tmp / "trial.env"
        env_file.write_text(
            f"IWA_LLM_PROVIDER=deepseek\nIWA_LLM_API_KEY=k\nIWA_EVALUATE_MODEL={PRO}\n"
        )
        for key, model in batch.MODELS.items():
            env = batch.child_env(key, dry=False, env_file=env_file, out=tmp)
            settings = load_settings(env=env, env_file=env_file)
            with self.subTest(side=key):
                self.assertEqual((settings.llm_model, settings.evaluate_model), (model, model))
                self.assertEqual(
                    settings.evaluate_thinking_timeout, 300.0
                )  # pinned for comparisons


if __name__ == "__main__":
    unittest.main()
