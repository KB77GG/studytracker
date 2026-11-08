"""Regressions from the .9 / high real run (13/14 requests, 4/7 usable;
docs/design/ielts-writing-ai-prompt9-high-20261107/continuation): with the criteria at
the top level two answers wrote them as bare numbers ("task": 7.0) and brace errors did
not go away; a Task 1 suggestion to delete the 23-word conclusion would leave 149 words
(minimum 150). The fixture holds the 8 real replies of the continuation (reasoning text
not included)."""

import json
import unittest
from pathlib import Path
from types import SimpleNamespace

from tools.ielts_writing_ai import copytext, prompts, review
from tools.ielts_writing_ai import essay as essay_lib
from tools.ielts_writing_ai.llm import LLMResult, parse_strict_json

FX = json.loads(
    (Path(__file__).parent / "fixtures" / "realcheck_20261107_prompt9.json").read_text(
        encoding="utf-8"
    )
)
SUBS = FX["submissions"]


def text(sample_id, attempt=-1):
    return FX["attempts"][sample_id][attempt]["text"]


def normalize(sample_id, attempt=-1):
    return review.normalize_evaluation(parse_strict_json(text(sample_id, attempt)), SUBS[sample_id])


def system(sample_id):
    sub = SUBS[sample_id]
    messages, _ = prompts.build_evaluate(sub, essay_lib.split_sentences(sub["essay_text"]))
    return messages[0]["content"]


class ScriptedClient:
    provider, model = "scripted", "scripted"

    def __init__(self, texts):
        self.texts, self.messages = list(texts), []

    def complete(self, messages, **_kwargs):
        self.messages.append(messages)
        return LLMResult(self.texts.pop(0), self.model, 1, {})


class BareNumberTest(unittest.TestCase):
    def test_real_bare_number_criteria_are_rejected_with_the_reason(self):
        raw = parse_strict_json(text("t2-mid"))
        self.assertEqual(raw["task"], 7.0)
        with self.assertRaisesRegex(review.InvalidOutput, "评分项 TR 写成了数字 7.0"):
            review.normalize_evaluation(raw, SUBS["t2-mid"])
        strong = text("t2-strong")
        self.assertIsNone(parse_strict_json(strong))  # still rejected, never repaired
        self.assertIn(
            "overall_comment、priorities 被写进了 argument 里面",
            review.json_problem("evaluate", strong, SUBS["t2-strong"]),
        )
        nested = {"criteria": {k: raw[k] for k in essay_lib.CRITERIA}}
        nested.update({k: v for k, v in raw.items() if k not in essay_lib.CRITERIA})
        with self.assertRaisesRegex(review.InvalidOutput, "写成了数字"):
            review.normalize_evaluation(nested, SUBS["t2-mid"])

    def test_the_retry_is_told_what_was_wrong(self):
        client = ScriptedClient([text("t2-mid"), text("t2-good")])
        generator = review.Generator(
            None, SimpleNamespace(evaluate_thinking="off", llm_temperature=0.2), client
        )
        sub = SUBS["t2-good"]
        generator._generate_valid("evaluate", sub, essay_lib.split_sentences(sub["essay_text"]))
        self.assertIn("写成了数字 7.0", client.messages[1][-1]["content"])

    def test_real_under_length_brace_errors_are_named_with_either_shape(self):
        first = text("t2-under-length", 0)
        self.assertIsNone(parse_strict_json(first))
        problem = review.json_problem("evaluate", first, SUBS["t2-under-length"])
        for part in (
            "lexical 被写进了 coherence 里面",
            "grammar 被写进了 lexical 里面",
            "argument、overall_comment、priorities 被写进了 grammar 里面",
        ):
            self.assertIn(part, problem)
        self.assertEqual(normalize("t2-under-length")["overall_band"], 5.5)  # the retry

    def test_usable_real_answers_still_normalize(self):
        for sample_id in ("t2-good", "t2-off-topic", "t2-under-length", "t1-no-image"):
            with self.subTest(sample=sample_id):
                self.assertTrue(normalize(sample_id)["criteria"])
        weak = FX["attempts"]["t2-weak"][0]
        self.assertEqual((weak["error"], weak["text"]), ("truncated", ""))


class PromptTenTest(unittest.TestCase):
    def test_version_and_nested_example(self):
        self.assertGreaterEqual(int(prompts.PROMPT_VERSION.rsplit(".", 1)[1]), 10)
        for sample_id, task_type, visual in (
            ("t2-weak", "task2", True),
            ("t1-no-image", "task1", False),
        ):
            with self.subTest(sample=sample_id):
                content = system(sample_id)
                example = prompts.evaluate_example(task_type, visual)
                shown = json.dumps(example, ensure_ascii=False)
                self.assertIn(shown, content)
                self.assertEqual(json.loads(shown), example)  # parseable as shown
                self.assertIn("never a bare number", content)
                self.assertIn("priorities = [str (Chinese), ...3-5", content)
                self.assertIn("sit next to criteria, never inside it", content)
                self.assertEqual(list(example["criteria"]), list(essay_lib.CRITERIA))
                if visual:
                    self.assertEqual(example["criteria"]["task"]["band"], -1)
                else:
                    self.assertIsNone(example["criteria"]["task"])

    def test_a_copied_example_can_never_be_scored(self):
        for sample_id, task_type, visual in (
            ("t2-weak", "task2", True),
            ("t1-no-image", "task1", False),
        ):
            with self.subTest(sample=sample_id):
                example = prompts.evaluate_example(task_type, visual)
                with self.assertRaises(review.InvalidOutput):
                    review.normalize_evaluation(example, SUBS[sample_id])
                for key in essay_lib.CRITERIA:
                    criterion = example["criteria"][key]
                    if criterion:  # even with a valid band the placeholder quotes fail
                        criterion["band"] = 6.0
                with self.assertRaises(review.InvalidOutput):
                    review.normalize_evaluation(example, SUBS[sample_id])


class DeletionLengthTest(unittest.TestCase):
    def test_real_task1_deletion_advice_gets_a_length_note(self):
        sub = SUBS["t1-no-image"]
        paragraphs = essay_lib.split_paragraphs(sub["essay_text"])
        self.assertEqual(
            (essay_lib.count_words(sub["essay_text"]), essay_lib.count_words(paragraphs[-1])),
            (172, 23),
        )
        result = normalize("t1-no-image")
        self.assertEqual(result["length_notes"], 2)
        coherence = next(c for c in result["criteria"] if c["key"] == "coherence")
        advice = coherence["issues"][0]["suggestion"]
        self.assertTrue(advice.startswith("删去这一结尾段"))  # the advice is kept
        self.assertIn("约剩 149 词，低于 150 词下限", advice)
        self.assertIn("约剩 149 词", result["priorities"][0])
        self.assertTrue(any("低于 150 词下限" in w for w in result["warnings"]))
        copied = copytext.evaluation_text(result, {})
        self.assertEqual(copied.count("约剩 149 词"), 2)

    def notes(self, essay, advice, quote=None, minimum=250):
        criteria = [{"issues": [{"quote": quote, "suggestion": advice}]}]
        added = review._deletion_notes(criteria, None, [], essay, minimum)
        return added, criteria[0]["issues"][0]["suggestion"]

    def test_cases(self):
        long_paragraph = " ".join(["word"] * 240) + "."
        short = "This last paragraph only repeats the overview."
        essay = f"{long_paragraph}\n{short}\nAnother sentence here. A final sentence ends it."
        total = essay_lib.count_words(essay)
        self.assertEqual(total, 255)
        cases = [
            ("删去这一段。", short, 1),  # 255 - 7 = 248 < 250
            ("Delete this paragraph.", short, 1),
            ("删去“This last paragraph”这一段", None, 1),  # the advice quotes the passage
            ("删去这一句", "Another sentence here.", 0),  # 255 - 3 = 252
            ("把这一段改写得更具体。", short, 0),  # not a deletion
            ("删去 only。", short, 0),  # a word-level edit
            ("删去这一段。", "not in the essay", 0),
        ]
        for advice, quote, expected in cases:
            with self.subTest(advice=advice):
                added, shown = self.notes(essay, advice, quote)
                self.assertEqual(added, expected)
                self.assertEqual("约剩" in shown, bool(expected))
                self.assertTrue(shown.startswith(advice))
        added, shown = self.notes(essay, "删去这一段。", short, minimum=240)
        self.assertEqual(added, 0)


if __name__ == "__main__":
    unittest.main()
