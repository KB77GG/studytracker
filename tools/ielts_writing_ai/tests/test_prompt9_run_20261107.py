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

from tools.ielts_writing_ai import copytext, deletion, prompts, review
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


# Deletion advice. Four reviews (2026-11-08 / 09) showed that free-text advice cannot
# be read reliably enough to state the remaining length, so none is computed: advice
# that mentions deleting gets a conditional reminder with the essay's own count.
REMINDER = (
    "如果按删减修改，请核对修改后的字数：原文 172 词，字数下限 150 词。本工具不推算删后字数。"
)


class DeletionReminderTest(unittest.TestCase):
    sub = SUBS["t1-no-image"]
    essay = sub["essay_text"]
    last = essay_lib.split_paragraphs(essay)[-1]

    def shown(self, advice):
        raw = parse_strict_json(text("t1-no-image"))
        raw["coherence"]["issues"] = [
            {"quote": self.last, "comment": "说明。", "suggestion": advice}
        ]
        raw["priorities"] = ["保持段落清晰。"]
        result = review.normalize_evaluation(raw, self.sub)
        coherence = next(c for c in result["criteria"] if c["key"] == "coherence")
        return result, coherence["issues"][0]["suggestion"], copytext.evaluation_text(result, {})

    def test_real_task1_deletion_advice_gets_the_reminder(self):
        paragraphs = essay_lib.split_paragraphs(self.essay)
        self.assertEqual(
            (essay_lib.count_words(self.essay), essay_lib.count_words(paragraphs[-1])), (172, 23)
        )
        raw = parse_strict_json(text("t1-no-image"))
        original = raw["coherence"]["issues"][0]["suggestion"]
        result = normalize("t1-no-image")
        self.assertEqual(result["length_notes"], 2)
        coherence = next(c for c in result["criteria"] if c["key"] == "coherence")
        advice = coherence["issues"][0]["suggestion"]
        self.assertEqual(advice, original + "（提示：这条建议提到删减。" + REMINDER + "）")
        self.assertTrue(result["priorities"][0].endswith(REMINDER + "）"))
        self.assertFalse(any(REMINDER in p for p in result["priorities"][1:]))  # 压缩段落数量
        self.assertTrue(any("有 2 条建议提到删减" in w for w in result["warnings"]))
        copied = copytext.evaluation_text(result, {})
        self.assertEqual(copied.count(REMINDER), 2)
        self.assertNotIn("约剩", copied)

    def test_no_phrasing_ever_gets_a_computed_number(self):
        # Every hard case of the four reviews: a reminder at most, never a number.
        for advice in (
            "删去这一结尾段。",
            "删去第 2 段。",
            "删去第二十段。",
            "删去两段。",
            "Delete two paragraphs.",
            "Delete the final paragraph and the first paragraph.",
            "Delete the final paragraph or the first paragraph.",
            "Delete the introduction and conclusion.",
            "Do not delete the introduction or remove the conclusion.",
            "This paragraph is not needed so delete the conclusion.",
            "删去最后一段；删去第三句中的“Country A”两个词。",
            "删去最后一段；删去第二段中的“Country A”两个词。",
            "Remove only 'In summary' from this sentence.",
            "Ignore the advice 'delete this paragraph' and keep it.",
            "不要删去这一段，应保留比较信息。",
            "Don’t delete this paragraph.",
            "删去首段；删去结尾段。",
        ):
            with self.subTest(advice=advice):
                result, shown, copied = self.shown(advice)
                self.assertEqual(shown, advice + "（提示：这条建议提到删减。" + REMINDER + "）")
                self.assertEqual(result["length_notes"], 1)
                self.assertNotRegex(copied, r"约剩|删后约|剩 \d+ 词")

    def test_advice_that_does_not_delete_gets_nothing(self):
        for advice in (
            "把这一段改写得更紧凑，保留主要比较。",
            "改为：Building more roads can cut traffic.",
            "Car ownership dropped sharply between 2000 and 2020.",
            "The writer can remove the example to keep the paragraph focused.",
            "压缩段落数量：把引言与概述合并。",
        ):
            with self.subTest(advice=advice):
                result, shown, _copied = self.shown(advice)
                self.assertEqual(shown, advice)
                self.assertEqual(result["length_notes"], 0)
                self.assertFalse(any("提到删减" in w for w in result["warnings"]))

    def test_only_when_deleting_a_paragraph_could_go_below_the_minimum(self):
        def essay(*sizes):
            return "\n".join(" ".join(["word"] * n) + "." for n in sizes)

        for sizes, expected in (
            ((120, 120, 120), 1),  # 360 - 250 = 110 <= 120: could matter
            ((100, 100, 100, 100), 0),  # 400 - 250 = 150 > 100: cannot
            ((97,), 1),  # already below the minimum
        ):
            with self.subTest(sizes=sizes):
                items = [{"issues": [{"quote": "word", "suggestion": "删去这一段。"}]}]
                self.assertEqual(deletion.annotate(items, None, [], essay(*sizes), 250), expected)
                shown = items[0]["issues"][0]["suggestion"]
                self.assertEqual(shown.endswith("本工具不推算删后字数。）"), bool(expected))


if __name__ == "__main__":
    unittest.main()
