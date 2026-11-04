"""Regression tests built from the real deepseek-flash outputs of the 2026-11-04 first
run (docs/design/ielts-writing-ai-realcheck-20261104; synthetic samples, no student
data). Since iwa-2026-11-04.3 change notes are structured {before, after, why}; the
first run's free-text notes are kept as fixtures and every finding they exposed is
re-expressed with structured notes built from the same real texts."""

import json
import unittest
from pathlib import Path

from tools.ielts_writing_ai import copytext, essay, review, samples
from tools.ielts_writing_ai import rewrite_quality as rq
from tools.ielts_writing_ai.llm import FakeClient, LLMResult, parse_strict_json

from .helpers import AppTestCase

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "realcheck_20261104.json").read_text(encoding="utf-8")
)
REWRITES = FIXTURE["rewrites"]
WEAK_CHANGE = {"before": "I am agree", "after": "I partly agree", "why": "修正语法错误。"}


def real(sample_id):
    item = REWRITES[sample_id]
    return parse_strict_json(item["raw_text"]), dict(item["submission"])


def with_answers(raw):
    raw = dict(raw)
    raw["answers"] = [
        {"part": f"要求 {i + 1}", "quote": s.text}
        for i, s in enumerate(essay.split_sentences(raw["essay"])[:2])
    ]
    return raw


def normalized(sample_id, **changes):
    raw, submission = real(sample_id)
    raw.update(changes)
    return review.normalize_rewrite(raw, submission)


def codes(result):
    return [issue["code"] for issue in result["quality_issues"]]


class RealOutputRegressionTest(unittest.TestCase):
    def test_free_text_change_notes_are_not_accepted(self):
        # First-run notes are prose; they cannot be verified and are not kept.
        for sample_id in REWRITES:
            with self.subTest(sample=sample_id):
                result = normalized(sample_id)
                self.assertIn("change_unstructured", codes(result))
                self.assertEqual(result["key_changes"], [])

    def test_every_real_rewrite_claimed_to_reach_band_7(self):
        for sample_id in REWRITES:
            with self.subTest(sample=sample_id):
                self.assertIn("band_claim", codes(normalized(sample_id)))

    def test_word_count_floor_is_a_content_failure(self):
        for sample_id, words in (("t2-mid", 247), ("t2-under-length", 220)):
            with self.subTest(sample=sample_id):
                result = normalized(sample_id)
                self.assertEqual(result["word_count"], words)
                self.assertFalse(result["content_passed"])
                self.assertIn("below_min", codes(result))
                self.assertIn(f"改写稿只有 {words} 词，低于 250 词要求", result["warnings"])

    def test_false_word_count_in_a_change_is_removed(self):
        raw, submission = real("t2-under-length")
        change = {
            "before": "I agree that governments should spend more money on public transport",
            "after": essay.split_sentences(raw["essay"])[0].text,
            "why": "改写后扩展到约270词，论证更充分。",  # the real false claim; actual 220
        }
        result = normalized("t2-under-length", key_changes=[change])
        self.assertIn("count_claim", codes(result))
        self.assertEqual(result["key_changes"], [])

    def test_off_topic_rewrite_low_overlap_is_only_a_note_without_the_model_flag(self):
        result = normalized("t2-off-topic")  # first-run output had no off-topic flag
        self.assertNotIn("still_off_topic", codes(result))
        self.assertTrue(any("只是词面提示" in w for w in result["warnings"]))

    def test_identical_before_after_is_removed(self):
        same = "extend opportunity to people who cannot or prefer not to drive"
        result = normalized("t2-strong", key_changes=[{"before": same, "after": same}])
        self.assertIn("noop_change", codes(result))
        apostrophe = "the lion's share of funding"
        result = normalized("t2-strong", key_changes=[{"before": apostrophe, "after": apostrophe}])
        self.assertIn("noop_change", codes(result))

    def test_claimed_edits_that_are_not_in_the_rewrite_are_removed(self):
        # t2-good's first-run claims: the "new" wording is not in the rewrite at all.
        result = normalized(
            "t2-good",
            key_changes=[
                {
                    "before": "there is considerable evidence that",
                    "after": "evidence suggests that",
                    "why": "更简洁",
                },
                {
                    "before": "thereby widening their access to jobs and services",
                    "after": "thereby widening access to jobs and services",
                    "why": "更紧凑",
                },
            ],
        )
        self.assertEqual(codes(result).count("change_unlocatable"), 1)
        self.assertEqual(result["key_changes"], [])

    def test_task1_notes_that_contradict_the_essay(self):
        raw, _sub = real("t1-no-image")
        result = normalized(
            "t1-no-image",
            key_changes=[
                {"before": "In summary", "after": "In summary"},  # real noop claim
                {
                    "before": "In summary, while every country saw an increase",
                    "after": "",
                },  # still there
            ],
        )
        self.assertIn("noop_change", codes(result))
        self.assertIn("change_not_made", codes(result))
        self.assertIn("data_claim", codes(result))  # "数据引用准确" without a chart
        self.assertTrue(any("没有与题图核对" in w for w in result["warnings"]))


class RuleUnitTest(unittest.TestCase):
    def base(self, **overrides):
        raw, submission = real("t2-weak")
        result = {
            "essay": raw["essay"],
            "word_count": 290,
            "key_changes": [dict(WEAK_CHANGE)],
            "band_rationale": "为了向 Band 7 目标靠近，补充了例子与解释，并修正了全部语法错误。",
        }
        result.update(overrides)
        return result, submission

    def test_verified_structured_change_is_kept(self):
        result, submission = self.base()
        checked = rq.check(result, submission, visual_available=True)
        self.assertEqual(checked.result["key_changes"], [WEAK_CHANGE])
        self.assertNotIn("no_changes", [i.code for i in checked.issues])

    def test_honest_rationale_and_negated_claims_are_not_flagged(self):
        for rationale in (
            "为了向 Band 7 目标靠近，补充了例子与解释。",
            "整体虽未达到Band 8的灵活与精准，但论证更完整。",
            "This version works towards Band 7 by developing each idea.",
        ):
            result, submission = self.base(band_rationale=rationale)
            checked = rq.check(result, submission, visual_available=True)
            self.assertNotIn("band_claim", [i.code for i in checked.issues], rationale)

    def test_word_counts_that_match_original_or_limits_are_allowed(self):
        change = dict(WEAK_CHANGE, why="原稿约 270 词，未低于 250 词下限；改写约 290 词。")
        result, submission = self.base(key_changes=[change])
        submission["word_count"] = 270
        checked = rq.check(result, submission, visual_available=True)
        self.assertEqual(len(checked.result["key_changes"]), 1)
        self.assertNotIn("count_claim", [i.code for i in checked.issues])

    def test_wrong_count_in_rationale_drops_only_that_sentence(self):
        result, submission = self.base(
            band_rationale="补充了例子。改写后约 400 词，更充分。修正了语法。"
        )
        checked = rq.check(result, submission, visual_available=True)
        self.assertEqual(checked.result["band_rationale"], "补充了例子。修正了语法。")
        self.assertIn("count_claim", [i.code for i in checked.issues])

    def test_retry_hint_is_english_and_specific(self):
        result, submission = self.base(word_count=200)
        checked = rq.check(result, submission, visual_available=True)
        self.assertIn("only 200 words", rq.retry_hint(checked.issues))

    def test_off_topic_flag_never_asserts_the_rewrite_answers_the_question(self):
        raw, submission = real("t2-weak")
        result = review.normalize_rewrite(dict(raw, original_addresses_question=False), submission)
        self.assertTrue(any("需要人工确认" in w for w in result["warnings"]))
        self.assertFalse(any("按题目重新作答，没有保留" in w for w in result["warnings"]))


class Task1ConsistencyTest(unittest.TestCase):
    def test_contradiction_is_reported_without_scoring_ta(self):
        item = FIXTURE["evaluations"]["t1-no-image"]
        raw = parse_strict_json(item["raw_text"])
        raw["consistency_issues"] = [
            {
                "quote": "Country A had the highest level of ownership in both years",
                "comment": "又说 2020 年 C 约 80%、A 约 75%，前后矛盾。",
            }
        ]
        result = review.normalize_evaluation(raw, item["submission"])
        self.assertIsNone(result["overall_band"])
        self.assertEqual(result["criteria"][0]["state"], "not_assessable")
        self.assertTrue(result["consistency_issues"][0]["quote_found"])
        self.assertTrue(any("前后矛盾" in w for w in result["warnings"]))
        copied = copytext.evaluation_text(result, {})
        self.assertIn("文内数据自洽检查", copied)
        self.assertIn("不代表与题图一致", copied)

    def test_old_output_without_the_field_is_still_valid(self):
        item = FIXTURE["evaluations"]["t1-no-image"]
        result = review.normalize_evaluation(
            parse_strict_json(item["raw_text"]), item["submission"]
        )
        self.assertEqual(result["consistency_issues"], [])


class CopyTextTest(unittest.TestCase):
    def test_failed_quality_and_unverified_band_are_in_every_copy(self):
        result = normalized("t2-mid")
        copies = copytext.rewrite_texts(result, {"model": "m"})
        for text in copies.values():
            self.assertIn(copytext.QUALITY_FAILED, text)
            self.assertIn("未经评分验证", text)
            self.assertIn("247 词", text)
        self.assertIn("AI 对目标分数段的说明（自述，未经评分验证）", copies["with_notes"])

    def test_structured_and_legacy_changes_are_copyable(self):
        self.assertEqual(
            copytext.change_line(WEAK_CHANGE), "“I am agree” → “I partly agree”（修正语法错误。）"
        )
        self.assertEqual(copytext.change_line({"before": "", "after": "x", "why": ""}), "新增“x”")
        self.assertEqual(copytext.change_line("旧格式说明"), "旧格式说明")


class SequenceClient(FakeClient):
    """Returns the given rewrite texts in order (other kinds use the demo output)."""

    def __init__(self, rewrite_texts):
        super().__init__()
        self.rewrite_texts = list(rewrite_texts)
        self.modes = []

    def complete(self, messages, **kwargs):
        context = kwargs.get("context") or {}
        if context.get("kind") == "rewrite":
            self.calls.append("rewrite")
            self.modes.append(context.get("mode") or "full")
            return LLMResult(self.rewrite_texts.pop(0), self.model, 1, {})
        return super().complete(messages, **kwargs)


def honest_rewrite():
    raw, _submission = real("t2-weak")
    raw = with_answers(raw)
    raw["band_rationale"] = "为了向 Band 7 目标靠近：重组段落，补充例子的解释，修正语法错误。"
    raw["key_changes"] = [dict(WEAK_CHANGE)]
    return json.dumps(raw, ensure_ascii=False)


class GeneratorRetryTest(AppTestCase):
    def run_rewrite(self, texts, essay_text=samples.WEAK):
        self.client_llm = SequenceClient(texts)
        self.app = self.make_app()
        self.storage = self.app.extensions["iwa"].storage
        _uid, code = self.add_user()
        client = self.login(code)
        public_id = self.submit(
            client, prompt_text=samples.TRANSPORT_PROMPT, essay_text=essay_text
        ).get_json()["public_id"]
        return client.get(f"/api/submissions/{public_id}").get_json()["submission"]["generations"][
            "rewrite"
        ]

    def test_content_retry_then_clean_rewrite_is_accepted(self):
        rewrite = self.run_rewrite([REWRITES["t2-mid"]["raw_text"], honest_rewrite()])
        self.assertEqual(rewrite["status"], "ready")
        self.assertTrue(rewrite["result"]["quality_passed"])
        self.assertEqual(self.client_llm.modes, ["full", "full"])

    def test_two_flawed_attempts_keep_the_one_with_fewer_content_problems(self):
        # attempt 1 (t2-mid): too short -> content problem; attempt 2 (t2-weak): notes only.
        rewrite = self.run_rewrite(
            [REWRITES["t2-mid"]["raw_text"], REWRITES["t2-weak"]["raw_text"]]
        )
        result = rewrite["result"]
        self.assertEqual(rewrite["status"], "ready")
        self.assertTrue(result["content_passed"])
        self.assertFalse(result["quality_passed"])
        self.assertEqual(result["word_count"], 290)
        self.assertIn(copytext.QUALITY_FAILED, rewrite["copy"]["essay"])
        self.assertEqual(self.client_llm.calls.count("rewrite"), 2)
        self.assertEqual(self.storage.usage_today(self.storage.list_users()[0]["id"]), 3)


if __name__ == "__main__":
    unittest.main()
