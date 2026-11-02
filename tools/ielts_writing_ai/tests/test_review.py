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


def criterion(band, quote="i dont agree"):
    return {
        "band": band,
        "summary": "说明",
        "strengths": ["a", "b"],
        "issues": [{"quote": quote, "comment": "c", "suggestion": "s"}],
    }


class EvaluationTest(unittest.TestCase):
    def raw(self, **bands):
        values = {"task": 6, "coherence": 6, "lexical": 6.5, "grammar": 6.5}
        values.update(bands)
        return {
            "criteria": {key: criterion(value) for key, value in values.items()},
            "overall_comment": "总评",
            "priorities": ["p1", "p2", {"bad": 1}],
            "overall_band": 9,  # must be ignored
        }

    def test_overall_is_computed_not_trusted(self):
        result = review.normalize_evaluation(self.raw(), submission())
        self.assertEqual(result["overall_band"], 6.5)
        self.assertEqual([c["short"] for c in result["criteria"]], ["TR", "CC", "LR", "GRA"])
        self.assertEqual(result["priorities"], ["p1", "p2"])

    def test_task1_labels(self):
        result = review.normalize_evaluation(self.raw(), submission(task_type="task1"))
        self.assertEqual(result["criteria"][0]["short"], "TA")
        self.assertEqual(result["criteria"][0]["label"], "Task Achievement")

    def test_quote_verification(self):
        raw = self.raw()
        raw["criteria"]["lexical"] = criterion(6, quote="this sentence is invented")
        result = review.normalize_evaluation(raw, submission())
        self.assertTrue(result["criteria"][0]["issues"][0]["quote_found"])
        self.assertFalse(result["criteria"][2]["issues"][0]["quote_found"])

    def test_missing_or_invalid_criterion_is_rejected(self):
        raw = self.raw()
        del raw["criteria"]["grammar"]
        with self.assertRaises(review.InvalidOutput):
            review.normalize_evaluation(raw, submission())
        with self.assertRaises(review.InvalidOutput):
            review.normalize_evaluation(self.raw(task="nine"), submission())
        with self.assertRaises(review.InvalidOutput):
            review.normalize_evaluation({"criteria": []}, submission())

    def test_word_count_and_unread_image_warnings(self):
        result = review.normalize_evaluation(
            self.raw(), submission(task_type="task1", image_status="skipped")
        )
        self.assertEqual(len(result["warnings"]), 2)
        self.assertIn("150", result["warnings"][0])


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
    def test_fenced_and_wrapped_json(self):
        self.assertEqual(extract_json_object('```json\n{"a": 1}\n```'), {"a": 1})
        self.assertEqual(extract_json_object('Here: {"a": {"b": 2}} done'), {"a": {"b": 2}})

    def test_invalid_json(self):
        for value in ("no json", "[1, 2]", "{broken"):
            with self.assertRaises(LLMError):
                extract_json_object(value)


if __name__ == "__main__":
    unittest.main()
