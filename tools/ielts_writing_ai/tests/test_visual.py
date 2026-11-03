"""A Task 1 image only supports Task Achievement when the vision reading is sufficient."""

import io
import json
import unittest

from tools.ielts_writing_ai import visual
from tools.ielts_writing_ai.llm import FakeClient, LLMResult

from .helpers import PNG_BYTES, AppTestCase

# The two vision outputs from the 2026-11-03 review that were wrongly accepted as "ready".
REVIEW_CANNOT_READ = (
    "I cannot read this image. All figures, units, categories and trends are unclear."
)
REVIEW_BLANK = "The uploaded picture is blank; it contains no readable chart or diagram."


def disclaimer_wrapped(json_text: str) -> list[str]:
    return [
        "无法读图，下面只是示例：\n```json\n" + json_text + "\n```",
        "I can't read this image; here is an example only:\n" + json_text,
        json_text + "\nNote: the values above are illustrative, the image was illegible.",
        "```json\n" + json_text + "\n```\n以上为示例数据。",
    ]


def reading(**overrides):
    value = {
        "readability": "sufficient",
        "visual_type": "bar_chart",
        "title": "Visitors to four museums in 2020",
        "units": "thousand visitors",
        "categories": ["A", "B", "C", "D"],
        "periods": ["2020"],
        "data_points": [
            {"label": "Museum A", "value": "140"},
            {"label": "Museum B", "value": "90"},
            {"label": "Museum C", "value": "200"},
            {"label": "Museum D", "value": "60"},
        ],
        "main_features": ["C was the most visited", "D was the least visited"],
        "unclear": [],
        "summary": "A bar chart comparing visitor numbers to four museums in 2020.",
    }
    value.update(overrides)
    return json.dumps(value)


class AssessTest(unittest.TestCase):
    def test_sufficient_chart_is_accepted_and_rendered(self):
        result = visual.assess(reading())
        self.assertTrue(result.sufficient)
        self.assertIn("Museum C = 200", result.description)
        self.assertIn("Units: thousand visitors", result.description)

    def test_fenced_json_is_accepted(self):
        self.assertTrue(visual.assess("```json\n" + reading() + "\n```").sufficient)

    def test_disclaimer_outside_valid_json_is_rejected(self):
        # Third review: "can't read it, below is only an example" + a sufficient-looking JSON.
        for text in disclaimer_wrapped(reading()):
            with self.subTest(text=text[:40]):
                result = visual.assess(text)
                self.assertFalse(result.sufficient)
                self.assertEqual(result.code, "unstructured")

    def test_review_plain_text_outputs_are_rejected(self):
        for text in (REVIEW_CANNOT_READ, REVIEW_BLANK, "", "Sure! Here is the chart."):
            with self.subTest(text=text):
                result = visual.assess(text)
                self.assertFalse(result.sufficient)
                self.assertEqual(result.code, "unstructured")

    def test_model_judgement_partial_or_unreadable_is_respected(self):
        for value in ("partial", "unreadable", "", "good"):
            with self.subTest(readability=value):
                self.assertFalse(visual.assess(reading(readability=value)).sufficient)

    def test_claimed_sufficient_but_describes_blank_or_illegible(self):
        for summary in (
            REVIEW_BLANK,
            REVIEW_CANNOT_READ,
            "The chart is too blurry to read.",
            "图片是空白的",
            "Values are illegible.",
        ):
            with self.subTest(summary=summary):
                result = visual.assess(reading(summary=summary))
                self.assertFalse(result.sufficient)
                self.assertEqual(result.code, "insufficient")

    def test_ordinary_chart_wording_is_not_mistaken_for_unreadable(self):
        summary = "There is no data for Museum E in 2015; the other values are clearly labelled."
        self.assertTrue(visual.assess(reading(summary=summary)).sufficient)

    def test_missing_key_data_is_rejected(self):
        two_points = [{"label": "A", "value": "1"}, {"label": "B", "value": "2"}]
        unclear_values = [
            {"label": "A", "value": "unclear"},
            {"label": "B", "value": "?"},
            {"label": "C", "value": "about"},
            {"label": "D", "value": "12"},
        ]
        cases = {
            "no data": reading(data_points=[]),
            "two points": reading(data_points=two_points),
            "unreadable values": reading(data_points=unclear_values),
            "more unclear than clear": reading(unclear=["a", "b", "c", "d", "e"]),
            "no main features": reading(main_features=[]),
            "no type": reading(visual_type="none"),
            "other type": reading(visual_type="other"),
            "not an object": "[1, 2, 3]",
        }
        for name, text in cases.items():
            with self.subTest(case=name):
                self.assertFalse(visual.assess(text).sufficient)

    def test_maps_and_processes_need_described_changes_or_stages(self):
        map_ok = reading(visual_type="map", data_points=[], main_features=["x", "y"])
        self.assertTrue(visual.assess(map_ok).sufficient)
        map_thin = reading(visual_type="map", data_points=[], main_features=["x"])
        self.assertFalse(visual.assess(map_thin).sufficient)
        process_ok = reading(visual_type="process", data_points=[], main_features=["a", "b", "c"])
        self.assertTrue(visual.assess(process_ok).sufficient)
        process_thin = reading(visual_type="process", data_points=[], main_features=["a", "b"])
        self.assertFalse(visual.assess(process_thin).sufficient)


class StaticVision(FakeClient):
    """Vision double that answers every image with a fixed text."""

    def __init__(self, text):
        super().__init__(model="vision-double")
        self.text = text

    def complete(
        self, messages, *, json_mode, max_tokens, temperature=0.2, context=None, retries=1
    ):
        self.calls.append("describe_image")
        return LLMResult(self.text, self.model, 1, {})


class VisionGateEndToEndTest(AppTestCase):
    """Upload -> vision -> generation -> API -> copy -> history, with model doubles."""

    def run_with_vision(self, text):
        self.app = self.make_app(vision_client=StaticVision(text))
        self.storage = self.app.extensions["iwa"].storage
        _uid, code = self.add_user()
        client = self.login(code)
        public_id = self.submit(
            client,
            task_type="task1",
            prompt_text="The chart below shows visitors to four museums in 2020.",
            image=(io.BytesIO(PNG_BYTES), "chart.png"),
        ).get_json()["public_id"]
        sub = client.get(f"/api/submissions/{public_id}").get_json()["submission"]
        history = client.get("/api/submissions").get_json()["items"][0]
        return sub, history

    def test_review_outputs_never_produce_ta_or_overall(self):
        for text in (
            REVIEW_CANNOT_READ,
            REVIEW_BLANK,
            reading(readability="partial"),
            reading(summary=REVIEW_BLANK),
            reading(data_points=[]),
            *disclaimer_wrapped(reading()),
        ):
            with self.subTest(vision=text[:50]):
                sub, history = self.run_with_vision(text)
                self.assertEqual(sub["image"]["status"], "failed")
                self.assertTrue(sub["image"]["unusable_reason"].startswith("题图信息不足"))
                evaluation = sub["generations"]["evaluate"]
                result = evaluation["result"]
                self.assertEqual(result["criteria"][0]["state"], "not_assessable")
                self.assertIsNone(result["criteria"][0]["band"])
                self.assertIsNone(result["overall_band"])
                self.assertTrue(any("题图信息不足" in w for w in result["warnings"]))
                copied = evaluation["copy"]["evaluation"]
                self.assertIn("总分：不可评", copied)
                self.assertIn("题图信息不足", copied)
                self.assertNotIn("预估总分", copied)
                self.assertIn("没有与题图核对", sub["generations"]["rewrite"]["copy"]["essay"])
                self.assertIsNone(history["overall_band"])
                self.assertEqual(history["overall_state"], "not_assessable")

    def test_sufficient_reading_scores_ta_and_feeds_the_prompt(self):
        sub, history = self.run_with_vision(reading())
        self.assertEqual(sub["image"]["status"], "ready")
        self.assertEqual(sub["image"]["unusable_reason"], "")
        self.assertIn("Museum C = 200", sub["image"]["description"])
        result = sub["generations"]["evaluate"]["result"]
        self.assertEqual(result["criteria"][0]["state"], "scored")
        self.assertIsNotNone(result["overall_band"])
        self.assertEqual(history["overall_state"], "scored")


if __name__ == "__main__":
    unittest.main()
