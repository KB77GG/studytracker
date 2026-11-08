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
        counts = deletion.annotate(criteria, None, [], essay, minimum)
        return counts["sure"], criteria[0]["issues"][0]["suggestion"]

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


class DeletionCase:
    """Shared helpers: the real 172-word Task 1, checked through normalize and copy."""

    sub = SUBS["t1-no-image"]
    essay = sub["essay_text"]
    paragraphs = essay_lib.split_paragraphs(essay)
    first, last = paragraphs[0], paragraphs[-1]

    def check(self, advice, quote, remaining, channel="issue"):
        """remaining: the number the note must show, None for no note."""
        raw = parse_strict_json(text("t1-no-image"))
        raw["coherence"]["issues"] = [
            {"quote": quote or self.first, "comment": "说明。", "suggestion": advice}
        ]
        raw["priorities"] = [advice if channel == "priority" else "保持段落清晰。"]
        if channel == "priority":
            raw["coherence"]["issues"] = []
        result = review.normalize_evaluation(raw, self.sub)
        coherence = next(c for c in result["criteria"] if c["key"] == "coherence")
        shown = (
            result["priorities"][0]
            if channel == "priority"
            else coherence["issues"][0]["suggestion"]
        )
        copied = copytext.evaluation_text(result, {})
        self.assertTrue(shown.startswith(advice))
        if remaining is None:
            self.assertNotIn("约剩", shown)
            self.assertNotIn("约剩", copied)
            self.assertFalse(any("条建议提到删去" in w for w in result["warnings"]))
        else:
            self.assertIn(f"约剩 {remaining} 词", shown)
            self.assertEqual(copied.count(f"约剩 {remaining} 词"), 1)
            self.assertEqual(result["length_notes"], 1)

    def unsure(self, advice, quote):
        updated, kind = deletion.note(advice, quote, self.essay, 150)
        self.assertEqual(kind, "unsure")
        self.assertNotIn("约剩", updated)
        raw = parse_strict_json(text("t1-no-image"))
        raw["coherence"]["issues"] = [{"quote": quote, "comment": "说明。", "suggestion": advice}]
        raw["priorities"] = ["保持段落清晰。"]
        result = review.normalize_evaluation(raw, self.sub)
        coherence = next(c for c in result["criteria"] if c["key"] == "coherence")
        self.assertIn("无法确定要删的是哪一部分", coherence["issues"][0]["suggestion"])
        self.assertNotIn("约剩", copytext.evaluation_text(result, {}))


# Review of db148ca (docs/design/ielts-writing-ai-prompt10-review-20261108): negated and
# word-only deletions were counted as whole-unit deletions, and the issue's quote was
# used even when the advice named another paragraph. Real 172-word Task 1: the first
# paragraph has 18 words, the last 23 (minimum 150).
class DeletionIntentTargetTest(DeletionCase, unittest.TestCase):
    def test_layout(self):
        counts = [essay_lib.count_words(p) for p in self.paragraphs]
        self.assertEqual((sum(counts), counts[0], counts[-1]), (172, 18, 23))

    def test_negated_or_quoted_deletions_delete_nothing(self):
        for advice in (
            "不要删去这一段，应保留其比较信息。",
            "Do not delete this paragraph; retain the comparison.",
            "不要采用“删除这一段”的意见，应保留其中的比较信息。",
            "无需删除这一段，改写即可。",
            "Rewrite this paragraph rather than delete it.",
        ):
            with self.subTest(advice=advice):
                self.check(advice, self.last, None)

    def test_word_only_deletions_count_the_words(self):
        for advice in (
            "删去这一句中的“In summary”两个词，保留其余内容。",
            'Remove only "In summary" from this sentence, keeping the rest.',
            "删去“In summary”两个词。",
            "删去句子开头的“In summary”。",
        ):
            with self.subTest(advice=advice):
                self.check(advice, self.last, None)  # 172 - 2 = 170

    def test_the_named_target_wins_over_the_issue_quote(self):
        cases = [
            ("删去结尾的“In summary”这一段。", self.first, 149),
            ('Delete the final paragraph beginning "In summary".', self.first, 149),
            ("删去“The bar chart compares”这一引言段。", self.last, None),  # 172 - 18 = 154
            ("删除最后这一段。", "Country A", 149),  # the quote occurs several times
            ("Delete the conclusion.", self.first, 149),
            ("删去第一段。", self.last, None),
        ]
        for advice, quote, remaining in cases:
            with self.subTest(advice=advice):
                self.check(advice, quote, remaining)
        self.check(
            "保留“In summary”这一段，删去“The bar chart compares”这一引言段。",
            None,
            None,
            channel="priority",
        )
        self.check("删去结尾的“In summary”这一段。", None, 149, channel="priority")

    def test_whole_units_still_counted_from_the_issue_quote(self):
        for advice in (
            "删去这一结尾段。",
            "Delete this paragraph.",
            "删除这一整句。",
            "Remove this sentence.",
        ):
            with self.subTest(advice=advice):
                self.check(advice, self.last, 149)
        self.check("删除这一段。", self.first, None)  # 154
        self.check("最后，删除这一段。", self.first, None)  # "最后" as "finally"

    def test_targets_that_cannot_be_pinned_down_get_no_number(self):
        for advice, quote in (
            ("删去“Country A”所在的这一段。", None),  # several paragraphs
            ("删去首段和结尾段。", self.first),  # two positions in one clause
            ("删去第二段的最后一句。", self.first),  # a sentence of which paragraph?
        ):
            with self.subTest(advice=advice):
                found = deletion.analyse(advice, quote, self.essay)
                self.assertIsNotNone(found)
                self.assertTrue(found.unsure)
                updated, kind = deletion.note(advice, quote, self.essay, 150)
                self.assertEqual(kind, "unsure")
                self.assertIn("无法确定要删的是哪一部分", updated)
                self.assertNotIn("约剩", updated)
        updated, kind = deletion.note("删去首段和结尾段。", self.first, self.essay, 100)
        self.assertEqual((updated, kind), (None, ""))  # cannot matter: no note


# Recheck of 7639dd5 (docs/design/ielts-writing-ai-prompt10-recheck-20261108): 别删 /
# Don’t / shouldn't were not read as negation, single quotes were not quotation marks,
# one passage reached by two descriptions was counted twice, and a paragraph that does
# not exist (第九段) fell back to the issue's quote.
class DeletionRecheckTest(DeletionCase, unittest.TestCase):
    def test_common_negations(self):
        for advice in (
            "别删去这一段，应保留比较信息。",
            "千万别删这一段。",
            "切勿删除这一段。",
            "Don’t delete this paragraph.",
            "You shouldn't delete this paragraph.",
            "You shouldn’t delete this paragraph.",
            "You cannot simply delete this paragraph.",
        ):
            with self.subTest(advice=advice):
                self.check(advice, self.last, None)
        self.check("删这一段。", self.last, 149)  # the bare verb is a deletion too

    def test_single_quotes_and_apostrophes(self):
        for advice in (
            "Remove only 'In summary' from this sentence.",
            "Remove only ‘In summary’ from this sentence.",
            "Ignore the advice 'delete this paragraph' and keep it.",
            "Ignore the advice ‘delete this paragraph’ and keep it.",
        ):
            with self.subTest(advice=advice):
                self.check(advice, self.last, None)
        for advice in (
            "Delete this paragraph; it's only a summary.",
            "Delete the writer's final paragraph.",
        ):
            with self.subTest(advice=advice):
                self.check(advice, self.first if "final" in advice else self.last, 149)

    def test_the_same_words_are_deleted_once(self):
        self.assertEqual(len(essay_lib.split_sentences(self.last)), 1)
        for advice in (
            "删去最后一段；删去最后一句。",
            "删去最后一段；删去“In summary”两个词。",
            "Delete the final paragraph; also delete the last sentence.",
        ):
            with self.subTest(advice=advice):
                self.check(advice, self.last, 149)
        self.check("删去首段；删去结尾段。", self.last, 131)  # 172 - 18 - 23

    def test_a_stated_target_that_does_not_exist_is_not_replaced(self):
        self.unsure("删去第九段。", self.last)
        self.unsure("Delete paragraph 9.", self.last)
        self.unsure("删去“a sentence the essay never had”这一段。", self.last)
        self.check("删去第五段。", self.first, 149)  # the last of five paragraphs


# Final check of 9576333 (docs/design/ielts-writing-ai-prompt10-finalcheck-20261108): a
# partial deletion lost its paragraph and was merged into an already deleted one, a
# negation in another sentence or of another word cancelled a deletion, and "第 2 段" /
# "the ninth paragraph" fell back to the issue's quote. The reading was rebuilt around
# "exact or no number": each action is located on its own, then positions are merged.
class DeletionActionTest(DeletionCase, unittest.TestCase):
    def test_partial_deletions_keep_their_paragraph(self):
        cases = [
            ("删去最后一段；删去第二段中的“Country A”两个词。", 147),
            ('Delete the last paragraph; remove only "Country A" from the second paragraph.', 147),
            ("删去第二段；删去最后一段中的“Country A”两个词。", 134),
            ("删去第二段中的“Country A”两个词；删去最后一段。", 147),
            ("删去最后一段；删去最后一段中的“Country A”两个词。", 149),  # really overlapping
            ("删去第二段；删去第二段中的“Country A”两个词。", 136),
        ]
        for advice, remaining in cases:
            with self.subTest(advice=advice):
                self.check(advice, self.last, remaining)

    def test_the_threshold_case_keeps_its_reminder(self):
        essay = "Clearly, " + self.essay
        self.assertEqual(essay_lib.count_words(essay), 173)
        advice = "删去最后一段；删去第二段中的“Country A”两个词。"
        updated, kind = deletion.note(advice, self.last, essay, 150)
        self.assertEqual(kind, "sure")
        self.assertIn("约剩 148 词", updated)

    def test_negation_belongs_to_its_own_verb(self):
        for advice in (
            "Do not remove the introduction. Delete the conclusion.",
            "Delete the conclusion. Do not remove the introduction.",
            "This paragraph is not necessary and you should delete the conclusion.",
            "You do not need the conclusion so remove the conclusion.",
            "Ignore 'do not delete this paragraph' and delete the conclusion.",
            "不要重复概述而应删去结尾段。",
            "不要保留这一段并删去结尾段。",
            "把这一段删去。",
        ):
            with self.subTest(advice=advice):
                self.check(advice, self.last, 149)
        for advice in ("避免把这一段删去。", "Do not remove the words 'In summary'."):
            with self.subTest(advice=advice):
                self.check(advice, self.last, None)

    def test_ordinals_in_any_common_format(self):
        for advice in ("删去第 2 段。", "Delete the 2nd paragraph.", "Delete paragraph two."):
            with self.subTest(advice=advice):
                self.check(advice, self.last, 136)
        for advice in ("删去第 9 段。", "Delete the ninth paragraph.", "Delete the 9th paragraph."):
            with self.subTest(advice=advice):
                self.unsure(advice, self.last)

    def test_anything_not_read_exactly_gets_no_number(self):
        for advice in (
            "删去关于汽车的那一段。",  # an unknown description of the target
            "Delete the paragraph about cars.",
            "删去“Country A”两个词。",  # found in several places
        ):
            with self.subTest(advice=advice):
                self.unsure(advice, self.last)
        self.check("删去后结构更紧凑。", self.last, None)  # names nothing to delete


if __name__ == "__main__":
    unittest.main()
