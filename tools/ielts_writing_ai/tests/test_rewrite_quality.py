"""Regression tests built from the real deepseek-flash outputs of the 2026-11-04 run
(docs/design/ielts-writing-ai-realcheck-20261104; synthetic samples, no student data)."""

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


def real(sample_id):
    item = REWRITES[sample_id]
    return parse_strict_json(item["raw_text"]), dict(item["submission"])


def normalized(sample_id):
    raw, submission = real(sample_id)
    return review.normalize_rewrite(raw, submission)


def codes(result):
    return [issue["code"] for issue in result["quality_issues"]]


class RealOutputRegressionTest(unittest.TestCase):
    def test_every_real_rewrite_claimed_to_reach_band_7(self):
        # Old prompt: all seven rationales assert "达到/符合 Band 7"; flagged, not trusted.
        for sample_id in REWRITES:
            with self.subTest(sample=sample_id):
                self.assertIn("band_claim", codes(normalized(sample_id)))

    def test_word_count_floor_is_a_quality_failure_not_just_a_warning(self):
        for sample_id, words in (("t2-mid", 247), ("t2-under-length", 220)):
            with self.subTest(sample=sample_id):
                result = normalized(sample_id)
                self.assertEqual(result["word_count"], words)
                self.assertFalse(result["quality_passed"])
                self.assertIn("below_min", codes(result))
                self.assertIn(f"改写稿只有 {words} 词，低于 250 词要求", result["warnings"])

    def test_false_word_count_claim_is_removed(self):
        result = normalized("t2-under-length")
        self.assertNotIn("270", " ".join(result["key_changes"]) + result["band_rationale"])
        self.assertIn("count_claim", codes(result))
        self.assertEqual(len(result["key_changes"]), 4)

    def test_off_topic_rewrite_only_gets_an_uncertainty_note(self):
        # Keyword overlap is not a relevance verdict (see test_quality_review_20261104).
        result = normalized("t2-off-topic")
        self.assertNotIn("off_prompt", codes(result))
        self.assertTrue(any("只是词面提示" in w for w in result["warnings"]))
        raw, submission = real("t2-off-topic")
        self.assertLess(rq.prompt_coverage(submission["prompt_text"], raw["essay"]), 0.2)

    def test_identical_before_after_changes_are_removed(self):
        result = normalized("t2-strong")
        self.assertIn("noop_change", codes(result))
        self.assertEqual(len(result["key_changes"]), 2)
        for line in result["key_changes"]:
            for old, new in rq.change_pairs(line):
                self.assertNotEqual(old.strip().lower(), new.strip().lower())

    def test_changes_that_were_never_made_are_removed(self):
        # t2-good claims three edits whose new wording is not in the rewrite at all.
        result = normalized("t2-good")
        self.assertIn("claim_absent", codes(result))
        self.assertEqual(len(result["key_changes"]), 2)

    def test_task1_change_notes_must_match_the_essay(self):
        result = normalized("t1-no-image")
        self.assertIn("deletion_mismatch", codes(result))  # "删除总结段" / 'In summary' still there
        self.assertIn("noop_change", codes(result))  # 'had grown' -> 'had grown'
        self.assertIn("data_claim", codes(result))  # "数据引用准确" without a chart
        self.assertTrue(any("没有与题图核对" in w for w in result["warnings"]))
        self.assertEqual(len(result["key_changes"]), 1)

    def test_clean_t2_weak_only_lacks_the_answer_map_and_claims_a_band(self):
        # Old-prompt output: no answers map (new requirement) and a "达到 Band 7" claim.
        self.assertEqual(codes(normalized("t2-weak")), ["answer_map_missing", "band_claim"])


class RuleUnitTest(unittest.TestCase):
    def base(self, **overrides):
        raw, submission = real("t2-weak")
        result = {
            "essay": raw["essay"],
            "word_count": 290,
            "key_changes": ["将“I am agree”改为“I partly agree”，修正语法。"],
            "band_rationale": "为了向 Band 7 目标靠近，补充了例子与解释，并修正了全部语法错误。",
        }
        result.update(overrides)
        return result, submission

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
        result, submission = self.base(
            key_changes=["原稿约 270 词，未达到 250 词下限的问题不存在；改写约 290 词。"]
        )
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

    def test_apostrophes_inside_quotes_do_not_break_pairs(self):
        self.assertEqual(
            rq.change_pairs("将“lion's share”改为“lion's share”"),
            [("lion's share", "lion's share")],
        )

    def test_retry_hint_is_english_and_specific(self):
        result, submission = self.base(word_count=200)
        checked = rq.check(result, submission, visual_available=True)
        self.assertIn("only 200 words", rq.retry_hint(checked.issues))

    def test_model_flag_for_off_topic_original_is_shown(self):
        raw, submission = real("t2-weak")
        raw = dict(raw, original_addresses_question=False)
        result = review.normalize_rewrite(raw, submission)
        self.assertTrue(any("原文没有回应题目" in w for w in result["warnings"]))


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


class SequenceClient(FakeClient):
    """Returns the given rewrite texts in order (other kinds use the demo output)."""

    def __init__(self, rewrite_texts):
        super().__init__()
        self.rewrite_texts = list(rewrite_texts)

    def complete(self, messages, **kwargs):
        if (kwargs.get("context") or {}).get("kind") == "rewrite":
            self.calls.append("rewrite")
            return LLMResult(self.rewrite_texts.pop(0), self.model, 1, {})
        return super().complete(messages, **kwargs)


def honest_rewrite():
    raw, _submission = real("t2-weak")
    raw = dict(raw)
    raw["band_rationale"] = "为了向 Band 7 目标靠近：重组段落，补充例子的解释，修正语法错误。"
    raw["answers"] = [
        {"part": f"要求 {i + 1}", "quote": s.text}
        for i, s in enumerate(essay.split_sentences(raw["essay"])[:2])
    ]
    return json.dumps(raw, ensure_ascii=False)


class GeneratorRetryTest(AppTestCase):
    def run_rewrite(self, texts):
        self.client_llm = SequenceClient(texts)
        self.app = self.make_app()
        self.storage = self.app.extensions["iwa"].storage
        _uid, code = self.add_user()
        client = self.login(code)
        # Same question the fixture rewrites answer (otherwise they are correctly off-prompt).
        public_id = self.submit(
            client, prompt_text=samples.TRANSPORT_PROMPT, essay_text=samples.MID
        ).get_json()["public_id"]
        return client.get(f"/api/submissions/{public_id}").get_json()["submission"]["generations"][
            "rewrite"
        ]

    def test_quality_retry_then_clean_rewrite_is_accepted(self):
        rewrite = self.run_rewrite([REWRITES["t2-mid"]["raw_text"], honest_rewrite()])
        self.assertEqual(rewrite["status"], "ready")
        self.assertTrue(rewrite["result"]["quality_passed"])
        self.assertEqual(self.client_llm.calls.count("rewrite"), 2)

    def test_two_flawed_attempts_keep_the_better_one_and_say_so(self):
        # attempt 1: under-length + no answer map + band claim (3 issues);
        # attempt 2: no answer map + band claim (2 issues) -> the second is kept.
        rewrite = self.run_rewrite(
            [REWRITES["t2-mid"]["raw_text"], REWRITES["t2-weak"]["raw_text"]]
        )
        self.assertEqual(rewrite["status"], "ready")
        result = rewrite["result"]
        self.assertFalse(result["quality_passed"])
        self.assertEqual(
            [i["code"] for i in result["quality_issues"]], ["answer_map_missing", "band_claim"]
        )
        self.assertEqual(result["word_count"], 290)
        self.assertIn(copytext.QUALITY_FAILED, rewrite["copy"]["essay"])
        self.assertEqual(self.client_llm.calls.count("rewrite"), 2)
        self.assertEqual(self.storage.usage_today(self.storage.list_users()[0]["id"]), 3)


if __name__ == "__main__":
    unittest.main()
