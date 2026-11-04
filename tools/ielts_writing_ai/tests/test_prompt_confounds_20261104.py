"""Prompt confounds raised after the thinking A/B (user analysis, 2026-11-04): the
evaluation asked for 1-4 issues per criterion and told the model most candidates sit at
5.0-6.5, which can push it to find faults and pull strong essays down. Also the next
comparison steps: reasoning_effort max, and comparing two models on identical input."""

import threading
import unittest
from http.server import HTTPServer

from tools.ielts_writing_ai import prompts, realcheck_compare, review
from tools.ielts_writing_ai.config import ConfigError, load_settings
from tools.ielts_writing_ai.llm import ChatClient

from .test_llm import StubHandler, ok
from .test_review import evaluation, submission


def system_prompt(task_type="task2"):
    sub = submission(task_type=task_type, prompt_text="p", image_status="ready")
    return " ".join(prompts.build_evaluate(sub, [])[0][0]["content"].split())


class PromptTest(unittest.TestCase):
    def test_no_assumed_score_range(self):
        for task_type in ("task1", "task2"):
            text = system_prompt(task_type)
            self.assertNotIn("5.0 and 6.5", text)
            self.assertNotIn("Most essays by Chinese candidates", text)
            self.assertIn("do not assume a typical score for the writer", text)
            self.assertIn("do not inflate or deflate", text)

    def test_issues_may_be_empty_and_must_not_be_invented(self):
        text = system_prompt()
        self.assertIn("...0-4; [] when there is no clear error or weakness", text)
        self.assertNotIn("...1-4]", text)
        self.assertIn("never invent one to fill the list", text)
        self.assertGreaterEqual(int(prompts.PROMPT_VERSION.rsplit(".", 1)[1]), 8)

    def test_a_criterion_without_issues_is_accepted_when_strengths_carry_evidence(self):
        raw = evaluation()
        for item in raw["criteria"].values():
            item["issues"] = []
        result = review.normalize_evaluation(raw, submission())
        self.assertTrue(all(c["issues"] == [] for c in result["criteria"]))
        self.assertIsNotNone(result["overall_band"])
        for item in raw["criteria"].values():
            item["strengths"] = []
        with self.assertRaises(review.InvalidOutput):  # still no evidence at all
            review.normalize_evaluation(raw, submission())


class MaxThinkingTest(unittest.TestCase):
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

    def test_max_is_a_level_and_xhigh_is_not(self):
        def settings(mode):
            return load_settings(
                env={
                    "IWA_EVALUATE_THINKING": mode,
                    "IWA_LLM_PROVIDER": "deepseek",
                    "IWA_LLM_API_KEY": "k",
                },
                env_file="/nonexistent",
            )

        settings("max").validate()
        with self.assertRaises(ConfigError):
            settings("xhigh").validate()  # the provider maps it to high

    def test_max_is_sent_as_reasoning_effort(self):
        StubHandler.responses, StubHandler.requests = [ok('{"a": 1}')], []
        client = ChatClient(
            provider="deepseek", base_url=self.url, api_key="k", model="deepseek-flash", timeout=5
        )
        client.complete([], json_mode=True, max_tokens=16000, thinking="max")
        body = StubHandler.requests[0]["body"]
        self.assertEqual((body["thinking"], body["reasoning_effort"]), ({"type": "enabled"}, "max"))


def condition(**overrides):
    value = {
        "dir": "x",
        "provider": "deepseek",
        "model": "deepseek-flash",
        "prompt_version": "iwa-2026-11-04.8",
        "kinds": ["evaluate"],
        "evaluate_thinking": "high",
        "evaluate_max_tokens": [16000],
        "samples": {"s1": "same"},
        "evaluate_inputs": {"s1": "sha"},
        "started_at": "t",
    }
    value.update(overrides)
    return value


class ModelComparisonTest(unittest.TestCase):
    other_model = {"provider": "qwen", "model": "qwen-plus", "evaluate_thinking": "off"}

    def test_a_different_model_is_refused_unless_asked_for(self):
        errors, _ = realcheck_compare.check_same_conditions(condition(), condition(model="other"))
        self.assertEqual(errors, ["模型不同：deepseek-flash vs other"])
        errors, warnings = realcheck_compare.check_same_conditions(
            condition(), condition(model="other"), allow_model_change=True
        )
        self.assertEqual(errors, [])
        self.assertIn("对照的是两个模型", warnings[0])
        self.assertFalse(any("重复性对照" in w for w in warnings))

    def test_model_and_thinking_changing_together_is_flagged(self):
        _errors, warnings = realcheck_compare.check_same_conditions(
            condition(), condition(**self.other_model), allow_model_change=True
        )
        self.assertTrue(any("不能单独归因" in w for w in warnings))

    def test_prompt_and_input_must_still_match(self):
        errors, _ = realcheck_compare.check_same_conditions(
            condition(),
            condition(model="other", prompt_version="iwa-2026-11-04.7"),
            allow_model_change=True,
        )
        self.assertEqual(errors, ["提示词版本不同：iwa-2026-11-04.8 vs iwa-2026-11-04.7"])
        errors, _ = realcheck_compare.check_same_conditions(
            condition(),
            condition(model="other", evaluate_inputs={"s1": "x"}),
            allow_model_change=True,
        )
        self.assertEqual(errors, ["实际发送给评价模型的输入不同：s1"])

    def test_labels_name_the_model_only_when_models_differ(self):
        a, b = condition(), condition(**self.other_model)
        self.assertEqual(realcheck_compare._label(a, b), "deepseek-flash · 思考 high")
        self.assertEqual(
            realcheck_compare._label(a, condition(evaluate_thinking="max")), "思考 high"
        )


if __name__ == "__main__":
    unittest.main()
