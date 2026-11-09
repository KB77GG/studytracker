"""Regressions from the .10 / high / 32000 real run (8/14 requests, 6/7 usable;
docs/design/ielts-writing-ai-prompt10-high-20261109): mid left argument unclosed twice
(the sixth real brace error, all of them a brace missing right after a list closed),
and adopted feedback explained a grammar band by the essay being off-topic, called
neutral wording impolite and called brief development "not explained". The fixture
holds the 8 real replies (reasoning text not included)."""

import json
import re
import unittest
from pathlib import Path

from tools.ielts_writing_ai import essay as essay_lib
from tools.ielts_writing_ai import prompts, review
from tools.ielts_writing_ai.llm import parse_strict_json

FX = json.loads(
    (Path(__file__).parent / "fixtures" / "realcheck_20261109_prompt10.json").read_text(
        encoding="utf-8"
    )
)
SUBS = FX["submissions"]


def system(sample_id):
    sub = SUBS[sample_id]
    messages, _ = prompts.build_evaluate(sub, essay_lib.split_sentences(sub["essay_text"]))
    return messages[0]["content"]


def closing_runs(text: str) -> list[int]:
    return [len(m.group()) for m in re.finditer(r"[\]}]+", re.sub(r"\s+", "", text))]


class StructureTest(unittest.TestCase):
    def test_real_mid_failures_stay_rejected_and_are_named(self):
        for attempt in FX["attempts"]["t2-mid"]:
            with self.subTest(text=attempt["text"][:40]):
                self.assertIsNone(parse_strict_json(attempt["text"]))
                self.assertIn(
                    "overall_comment、priorities 被写进了 argument 里面：argument 写完后少了一个 }",
                    review.json_problem("evaluate", attempt["text"], SUBS["t2-mid"]),
                )
                # The brace is missing right after the improvements list closed.
                self.assertIn('"}], "overall_comment"', attempt["text"])

    def test_usable_replies_do_not_depend_on_key_order(self):
        for sample_id in ("t2-weak", "t2-good", "t2-strong", "t2-off-topic", "t2-under-length"):
            with self.subTest(sample=sample_id):
                raw = parse_strict_json(FX["attempts"][sample_id][-1]["text"])
                reordered = json.loads(json.dumps(raw))
                for key, item in list(reordered["criteria"].items()):
                    order = ("band", "strengths", "issues", "summary")
                    reordered["criteria"][key] = {k: item[k] for k in order if k in item} | {
                        k: v for k, v in item.items() if k not in order
                    }
                argument = reordered["argument"]
                reordered["argument"] = {k: v for k, v in argument.items() if k != "position"}
                reordered["argument"]["position"] = argument.get("position")
                self.assertEqual(
                    review.normalize_evaluation(reordered, SUBS[sample_id]),
                    review.normalize_evaluation(raw, SUBS[sample_id]),
                )
        self.assertTrue(
            review.normalize_evaluation(
                parse_strict_json(FX["attempts"]["t1-no-image"][0]["text"]), SUBS["t1-no-image"]
            )["criteria"]
        )

    def test_every_object_in_the_example_ends_with_a_plain_field(self):
        self.assertGreaterEqual(int(prompts.PROMPT_VERSION.rsplit(".", 1)[1]), 11)
        for task_type, visual in (("task2", True), ("task1", False), ("task1", True)):
            with self.subTest(task=task_type, visual=visual):
                example = prompts.evaluate_example(task_type, visual)
                criterion = example["criteria"]["grammar"]
                self.assertEqual(list(criterion), ["band", "strengths", "issues", "summary"])
                if task_type == "task2":
                    self.assertEqual(
                        list(example["argument"]),
                        ["paragraphs", "problems", "improvements", "position"],
                    )
                # At most two brackets close in a row (.10 had ]}} and }]}} runs).
                self.assertLessEqual(max(closing_runs(json.dumps(example))), 2)
        content = system("t2-mid")
        self.assertIn("every object ends with a plain field after its lists", content)
        self.assertIn(
            json.dumps(prompts.evaluate_example("task2", True), ensure_ascii=False), content
        )


class JudgementRulesTest(unittest.TestCase):
    def test_general_rules_are_in_both_prompts(self):
        for sample_id in ("t2-off-topic", "t1-no-image"):
            content = system(sample_id)
            for text in (
                "Explain each band with that criterion's own features only",
                "an off-topic essay can still use varied, accurate grammar",
                "Language feedback has three kinds",
                "Accurate, neutral everyday wording is neither an error nor impolite",
                "check that it does not already use one",
                "Call development brief when a point is explained briefly",
            ):
                with self.subTest(sample=sample_id, text=text):
                    self.assertIn(text, content)

    def test_no_wording_from_this_runs_samples_was_added(self):
        # The built-in samples are the test set: rules stay general, so the next run is
        # not improved by having seen the answers.
        content = system("t2-under-length")
        for phrase in ("old people", "elderly", "carbon emissions", "everybody", "transported by"):
            with self.subTest(phrase=phrase):
                self.assertNotIn(phrase, content)


if __name__ == "__main__":
    unittest.main()
