"""Regressions from the review of .11 (docs/design/ielts-writing-ai-prompt11-review-20261109):
the new rule put all argument quality under Task Response, contradicting the argument
check that explains Coherence & Cohesion (logical progression is a CC feature in the
official criteria); and examples taken from the seven built-in essays were still in the
online prompt. The built-in essays are the development regression set: their wording
stays in the offline fixtures, never in the prompt."""

import unittest

from tools.ielts_writing_ai import essay as essay_lib
from tools.ielts_writing_ai import prompts
from tools.ielts_writing_ai import samples as builtin

# Wording of the development samples or of feedback on them that earlier prompts used
# as examples (.6 - .11), plus phrases flagged by the manual reviews.
DEVELOPMENT_PHRASES = (
    "much less crowded",
    "do not have cars",
    "cannot afford a car",
    "a steady climb",
    "forty passengers",
    "full bus",
    "Country B",
    "Country A",
    "lion's share",
    "public transport",
    "roads where necessary",
    "in both years",
    "only assertions",
    "touched on",
    "old people",
    "elderly",
    "carbon emissions",
    "everybody",
    "transported by",
)


def system_prompts():
    for sample in builtin.SAMPLES:
        sub = {
            "task_type": sample["task_type"],
            "prompt_text": sample["prompt"],
            "essay_text": sample["essay"],
            "word_count": essay_lib.count_words(sample["essay"]),
            "image_status": "none",
            "target_band": 7.0,
        }
        messages, _ = prompts.build_evaluate(sub, essay_lib.split_sentences(sub["essay_text"]))
        yield sample["id"], sub["task_type"], messages[0]["content"]


class CriterionBoundaryTest(unittest.TestCase):
    def test_each_finding_goes_to_the_criterion_it_evidences(self):
        self.assertGreaterEqual(int(prompts.PROMPT_VERSION.rsplit(".", 1)[1]), 12)
        for sample_id, task_type, content in system_prompts():
            with self.subTest(sample=sample_id):
                self.assertIn(prompts.CRITERION_BOUNDARIES[task_type], content)
                self.assertIn(prompts.LANGUAGE_BOUNDARY, content)
                self.assertIn("logical progression", prompts.CRITERION_BOUNDARIES[task_type])
                self.assertNotIn("never a reason for a Coherence", content)  # the .11 conflict
                if task_type == "task2":
                    self.assertIn("whichever each one evidences", content)
                    self.assertIn("in the summary of the criterion it evidences", content)
                    self.assertIn("development and support of ideas under Task Response", content)
                else:
                    self.assertIn("under Task Achievement", content)

    def test_language_bands_rest_on_language_evidence(self):
        for text in ("off-topic content", "missing data", "weak support"):
            self.assertIn(text, prompts.LANGUAGE_BOUNDARY)


class DevelopmentSetTest(unittest.TestCase):
    def test_no_wording_from_the_development_samples_in_the_online_prompt(self):
        prompts_seen = list(system_prompts())
        self.assertEqual(len(prompts_seen), len(builtin.SAMPLES))
        for sample_id, _task, content in prompts_seen:
            for phrase in DEVELOPMENT_PHRASES:
                with self.subTest(sample=sample_id, phrase=phrase):
                    self.assertNotIn(phrase.lower(), content.lower())

    def test_the_general_rules_that_replaced_them(self):
        content = dict((s, c) for s, _t, c in system_prompts())
        task2, task1 = content["t2-mid"], content["t1-no-image"]
        for text in (
            "'mostly X, but Y where necessary'",
            "A conclusion that restates the main side without repeating the exceptions is "
            "consistent",
            "a natural comparative phrase is not an error",
            "do not turn a stated fact into a different cause, or two data points into a "
            "continuous trend",
            "naming the measured figure instead of the thing it belongs to",
            "calling a point unexplained or barely mentioned",
        ):
            with self.subTest(text=text):
                self.assertIn(text, " ".join(task2.split()))
        self.assertIn("it calls one item the highest throughout", task1)


if __name__ == "__main__":
    unittest.main()
