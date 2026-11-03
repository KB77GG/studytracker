import unittest

from tools.ielts_writing_ai import essay, review
from tools.ielts_writing_ai.llm import LLMError, extract_json_object

ESSAY = "Many peoples think that. i dont agree with it.\nGovernments should invest more money."


def submission(**overrides):
    value = {
        "task_type": "task2",
        "essay_text": ESSAY,
        "word_count": essay.count_words(ESSAY),
        "target_band": 7.0,
        "image_status": "none",
    }
    value.update(overrides)
    return value


REASON = "论点清楚但展开不足，例子与观点之间缺少解释。"


def criterion(band, quote="i dont agree", strength_quote="Governments should invest"):
    return {
        "band": band,
        "summary": REASON,
        "strengths": [{"quote": strength_quote, "comment": "立场明确"}],
        "issues": [{"quote": quote, "comment": "缺少撇号", "suggestion": "I don't agree"}],
    }


def evaluation(**bands):
    values = {"task": 6, "coherence": 6, "lexical": 6.5, "grammar": 6.5}
    values.update(bands)
    return {
        "criteria": {key: criterion(value) for key, value in values.items()},
        "overall_comment": "整体结构完整，但语言错误较多，影响清晰度。",
        "priorities": ["p1", "p2", {"bad": 1}],
        "overall_band": 9,  # must be ignored
    }


class EvaluationTest(unittest.TestCase):
    def raw(self, **bands):
        return evaluation(**bands)

    def test_overall_is_computed_not_trusted(self):
        result = review.normalize_evaluation(self.raw(), submission())
        self.assertEqual(result["overall_band"], 6.5)
        self.assertEqual(result["overall_state"], "scored")
        self.assertEqual([c["short"] for c in result["criteria"]], ["TR", "CC", "LR", "GRA"])
        self.assertEqual(result["priorities"], ["p1", "p2"])
        self.assertTrue(result["criteria"][0]["strengths"][0]["quote_found"])

    def test_task1_labels_with_a_readable_chart(self):
        result = review.normalize_evaluation(
            self.raw(), submission(task_type="task1", image_status="ready")
        )
        self.assertEqual(result["criteria"][0]["short"], "TA")
        self.assertEqual(result["criteria"][0]["label"], "Task Achievement")
        self.assertEqual(result["criteria"][0]["state"], "scored")
        self.assertIsNotNone(result["overall_band"])

    def test_unverifiable_quote_is_flagged_but_does_not_count(self):
        raw = self.raw()
        raw["criteria"]["lexical"]["issues"].append(
            {"quote": "this sentence is invented", "comment": "虚构"}
        )
        result = review.normalize_evaluation(raw, submission())
        issues = result["criteria"][2]["issues"]
        self.assertTrue(issues[0]["quote_found"])
        self.assertFalse(issues[1]["quote_found"])
        self.assertTrue(any("1 条引文" in w for w in result["warnings"]))

    def test_missing_or_invalid_criterion_is_rejected(self):
        raw = self.raw()
        del raw["criteria"]["grammar"]
        with self.assertRaises(review.InvalidOutput):
            review.normalize_evaluation(raw, submission())
        with self.assertRaises(review.InvalidOutput):
            review.normalize_evaluation(self.raw(task="nine"), submission())
        with self.assertRaises(review.InvalidOutput):
            review.normalize_evaluation({"criteria": []}, submission())

    # -- reviewer repro: completeness and evidence ------------------------------------

    def test_four_nines_without_any_reason_are_rejected(self):
        raw = {
            "criteria": {key: {"band": 9} for key in essay.CRITERIA},
            "overall_comment": "",
            "priorities": [],
        }
        with self.assertRaises(review.InvalidOutput):
            review.normalize_evaluation(raw, submission())

    def test_reason_without_verifiable_evidence_is_rejected(self):
        raw = self.raw()
        raw["criteria"]["grammar"] = {
            "band": 9,
            "summary": REASON,
            "strengths": [{"quote": "flawless complex structures", "comment": "完美"}],
            "issues": [{"quote": "a sentence that is not in the essay", "comment": "x"}],
        }
        with self.assertRaisesRegex(review.InvalidOutput, "GRA"):
            review.normalize_evaluation(raw, submission())

    def test_bare_strength_claims_are_not_evidence(self):
        raw = self.raw()
        raw["criteria"]["coherence"] = {
            "band": 9,
            "summary": REASON,
            "strengths": ["衔接非常自然", "段落完美"],
            "issues": [],
        }
        with self.assertRaisesRegex(review.InvalidOutput, "CC"):
            review.normalize_evaluation(raw, submission())

    def test_too_short_reason_is_rejected(self):
        raw = self.raw()
        raw["criteria"]["lexical"]["summary"] = "很好"
        with self.assertRaisesRegex(review.InvalidOutput, "LR"):
            review.normalize_evaluation(raw, submission())

    def test_overall_comment_and_priorities_are_required(self):
        raw = self.raw()
        raw["overall_comment"] = " "
        with self.assertRaises(review.InvalidOutput):
            review.normalize_evaluation(raw, submission())
        raw = self.raw()
        raw["priorities"] = []
        with self.assertRaises(review.InvalidOutput):
            review.normalize_evaluation(raw, submission())

    # -- reviewer repro: Task 1 without a readable chart ------------------------------

    def test_task1_without_readable_chart_has_no_ta_and_no_overall(self):
        for status in ("none", "skipped", "failed", "pending"):
            with self.subTest(status=status):
                raw = self.raw(task=9)  # the model scores TA anyway, with invented data
                raw["criteria"]["task"]["summary"] = "数据完全准确，覆盖所有关键特征。"
                result = review.normalize_evaluation(
                    raw, submission(task_type="task1", image_status=status)
                )
                ta = result["criteria"][0]
                self.assertEqual(ta["state"], "not_assessable")
                self.assertIsNone(ta["band"])
                self.assertEqual((ta["summary"], ta["strengths"], ta["issues"]), ("", [], []))
                self.assertIn(review.TA_UNASSESSABLE_REASONS[status], ta["reason"])
                self.assertIsNone(result["overall_band"])
                self.assertEqual(result["overall_state"], "not_assessable")
                self.assertEqual([c["state"] for c in result["criteria"][1:]], ["scored"] * 3)
                self.assertTrue(any("不给总分" in w for w in result["warnings"]))

    def test_task1_model_may_return_null_task(self):
        raw = self.raw()
        raw["criteria"]["task"] = None
        result = review.normalize_evaluation(raw, submission(task_type="task1"))
        self.assertIsNone(result["overall_band"])

    def test_task1_rewrite_warns_that_data_is_unverified(self):
        body = " ".join(["word"] * 160)
        result = review.normalize_rewrite(
            {"essay": body}, submission(task_type="task1", image_status="skipped")
        )
        self.assertTrue(any("没有与题图核对" in w for w in result["warnings"]))
        ready = review.normalize_rewrite(
            {"essay": body}, submission(task_type="task1", image_status="ready")
        )
        self.assertFalse(any("题图" in w for w in ready["warnings"]))


class RefinementTest(unittest.TestCase):
    def setUp(self):
        self.sentences = essay.split_sentences(ESSAY)

    def test_original_comes_from_our_split_not_the_model(self):
        raw = {
            "sentences": [
                {
                    "i": 0,
                    "original": "HACKED",
                    "revised": "Many people think so.",
                    "tags": ["grammar", "bogus"],
                    "explanation": "复数",
                },
                {
                    "i": 1,
                    "revised": "I don't agree with it.",
                    "tags": ["spelling", "grammar", "spelling"],
                },
                {
                    "i": 2,
                    "revised": "Governments should invest more money.",
                    "tags": ["grammar"],
                    "explanation": "x",
                },
            ],
            "summary": "总结",
        }
        result = review.normalize_refinement(raw, self.sentences)
        first, second, third = result["sentences"]
        self.assertEqual(first["original"], "Many peoples think that.")
        self.assertTrue(first["changed"])
        self.assertEqual(first["tags"], ["grammar"])
        self.assertEqual(second["tags"], ["spelling", "grammar"])
        self.assertFalse(third["changed"])
        self.assertEqual(third["tags"], [])
        self.assertEqual(third["explanation"], "")
        self.assertEqual(result["changed_count"], 2)
        self.assertEqual(
            result["refined_essay"],
            "Many people think so. I don't agree with it.\n\nGovernments should invest more money.",
        )

    def test_capitalisation_fix_counts_but_quote_style_does_not(self):
        raw = {
            "sentences": [
                {"i": 0, "revised": "Many peoples think  that.", "tags": ["grammar"]},
                {"i": 1, "revised": "I dont agree with it.", "tags": ["grammar"]},
            ]
        }
        result = review.normalize_refinement(raw, self.sentences)
        self.assertFalse(result["sentences"][0]["changed"])  # whitespace only
        self.assertTrue(result["sentences"][1]["changed"])  # i -> I
        self.assertTrue(essay.same_text("don’t — x", "don't - x"))

    def test_missing_sentences_fall_back_to_original(self):
        raw = {"sentences": [{"i": 1, "revised": "I don't agree with it."}]}
        result = review.normalize_refinement(raw, self.sentences)
        self.assertEqual(result["missing_count"], 2)
        self.assertEqual(result["sentences"][0]["revised"], self.sentences[0].text)

    def test_overlong_revision_is_dropped(self):
        raw = {"sentences": [{"i": 0, "revised": "word " * 200}]}
        result = review.normalize_refinement(raw, self.sentences)
        self.assertFalse(result["sentences"][0]["changed"])

    def test_unmatched_output_is_rejected(self):
        with self.assertRaises(review.InvalidOutput):
            review.normalize_refinement({"sentences": [{"i": 99, "revised": "x"}]}, self.sentences)
        with self.assertRaises(review.InvalidOutput):
            review.normalize_refinement({"items": []}, self.sentences)


class RewriteTest(unittest.TestCase):
    def test_paragraphs_normalised_and_short_warning(self):
        body = " ".join(["word"] * 120)
        result = review.normalize_rewrite(
            {"essay": f"{body}\r\n\r\n\r\n{body}", "key_changes": ["k1"], "band_rationale": "r"},
            submission(),
        )
        self.assertEqual(result["essay"].count("\n\n"), 1)
        self.assertEqual(result["word_count"], 240)
        self.assertEqual(len(result["warnings"]), 1)

    def test_too_short_is_rejected(self):
        with self.assertRaises(review.InvalidOutput):
            review.normalize_rewrite({"essay": "Too short."}, submission())


class JsonExtractionTest(unittest.TestCase):
    def test_whole_reply_json_or_single_fence_is_accepted(self):
        self.assertEqual(extract_json_object('{"a": 1}'), {"a": 1})
        self.assertEqual(extract_json_object('  \n{"a": {"b": 2}}\n '), {"a": {"b": 2}})
        self.assertEqual(extract_json_object('```json\n{"a": 1}\n```'), {"a": 1})
        self.assertEqual(extract_json_object('```\n{"a": 1}\n```'), {"a": 1})

    def test_any_text_outside_the_json_is_rejected(self):
        # Third review: a disclaimer before/after valid JSON must not be silently dropped.
        for value in (
            'Here: {"a": {"b": 2}} done',
            '我无法完整评估，下面只是示例：\n{"a": 1}',
            '我无法完整评估，下面只是示例：\n```json\n{"a": 1}\n```',
            '{"a": 1}\n以上仅为示例，并非真实评分。',
            '```json\n{"a": 1}\n```\nNote: this is an example.',
            '```json\n{"a": 1}\n```\n```json\n{"b": 2}\n```',
        ):
            with self.subTest(value=value[:30]), self.assertRaises(LLMError) as ctx:
                extract_json_object(value)
            self.assertEqual(ctx.exception.code, "invalid_json")

    def test_invalid_json(self):
        for value in ("no json", "[1, 2]", "{broken", ""):
            with self.assertRaises(LLMError):
                extract_json_object(value)


if __name__ == "__main__":
    unittest.main()
