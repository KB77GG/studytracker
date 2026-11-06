"""Regressions from the recheck of 597b212 (docs/design/ielts-writing-ai-prompt8-recheck-
20261105): coordinated hundreds / thousands were still merged into one number ("one
hundred and two hundred" = 10200), and a temporal word in front of a quantity ("rose
from 2000 to 2020 buses") still made 2000 and 2020 count as years."""

import unittest

from tools.ielts_writing_ai import copytext, figures, review
from tools.ielts_writing_ai.essay import count_words


def evaluate(source_sentence, suggestion):
    essay_text = f"Public transport is important.\n{source_sentence}\nIn conclusion, buses matter."
    criterion = {
        "band": 6,
        "summary": "论点清楚但展开不足，例子与观点之间缺少解释。",
        "strengths": [{"quote": "Public transport is important.", "comment": "立场明确"}],
        "issues": [{"quote": source_sentence, "comment": "需要说明。", "suggestion": suggestion}],
    }
    raw = {
        "criteria": {"task": criterion},
        "argument": {
            "paragraphs": [{"role": "body", "main_point": source_sentence, "verdict": "supports"}],
            "problems": [],
        },
        "overall_comment": "整体结构完整，例子需要更好地回扣论点。",
        "priorities": ["补充解释"],
    }
    raw["criteria"].update(
        {k: dict(criterion, issues=[]) for k in ("coherence", "lexical", "grammar")}
    )
    result = review.normalize_evaluation(
        raw,
        {
            "task_type": "task2",
            "essay_text": essay_text,
            "prompt_text": "Do you agree?",
            "word_count": count_words(essay_text),
            "target_band": 7.0,
            "image_status": "none",
        },
    )
    return result, copytext.evaluation_text(result, {})


class CoordinatedHundredsTest(unittest.TestCase):
    cases = [
        ("one hundred and two hundred", ["100", "200"]),
        ("one thousand and two thousand", ["1000", "2000"]),
        ("one hundred two hundred", ["100", "200"]),
        ("one thousand two thousand", ["1000", "2000"]),
        ("forty and fifty", ["40", "50"]),
    ]
    compounds = [
        ("one hundred and twenty-five", "125"),
        ("one thousand two hundred", "1200"),
        ("two thousand and twenty", "2020"),
        ("one hundred and two thousand", "102000"),
        ("three hundred thousand", "300000"),
        ("nineteen hundred", "1900"),
        (
            "one million two hundred and thirty-four thousand five hundred and sixty-seven",
            "1234567",
        ),
    ]

    def test_lists_stay_separate_and_compounds_stay_whole(self):
        for text, values in self.cases:
            with self.subTest(text=text):
                self.assertEqual([v for _s, _e, v in figures.split_en_numbers(text)], values)
        for text, value in self.compounds:
            with self.subTest(text=text):
                self.assertEqual([v for _s, _e, v in figures.split_en_numbers(text)], [value])

    def test_reviewer_table_through_normalize_and_copy(self):
        words = "The two buses carry one hundred and two hundred passengers respectively."
        digits = "The two buses carry 100 and 200 passengers respectively."
        fleets = "The two fleets contain one thousand and two thousand buses respectively."
        cases = [
            (words, "The buses carry 100 and 200 passengers respectively.", False),
            (digits, "The buses carry one hundred and two hundred passengers respectively.", False),
            (words, "One bus carries 10200 passengers.", True),
            (digits, "One bus carries 10200 passengers.", True),
            (fleets, "The two fleets contain 1000 and 2000 buses respectively.", False),
            (fleets, "One fleet contains 3000 buses.", True),
        ]
        for source, advice, removed in cases:
            with self.subTest(source=source, advice=advice):
                result, copied = evaluate(source, advice)
                self.assertEqual(result["suggestions_removed"]["criteria"], 1 if removed else 0)
                self.assertEqual(advice in copied, not removed)


class QuantityNotYearTest(unittest.TestCase):
    quantities = [
        "The number of buses rose from 2000 to 2020 buses.",
        "The sample consisted of 2000 buses and another fleet of 2020 buses.",
        "Between 2000 and 2020 buses were recorded in the two cities.",
        "In numbers of buses, City A and City B recorded 2000 and 2020 respectively.",
        "There are 2000 buses in City A and 2020 buses in City B.",
        "2000辆和2020辆",
    ]
    years = [
        "Public transport was compared in 2000 and 2020.",
        "The study ran from 2000 to 2020.",
        "In 2000 car ownership rose; by 2020 it fell.",
        "2000年和2020年",
        "2000-2020",
    ]

    def test_counts_are_never_years(self):
        for text in self.quantities:
            with self.subTest(text=text):
                self.assertEqual(figures.confirmed_years(text), set())

    def test_dates_are_years(self):
        for text in self.years:
            with self.subTest(text=text):
                self.assertEqual(figures.confirmed_years(text), {2000, 2020})

    def test_twenty_years_later_through_normalize_and_copy(self):
        for source in self.quantities[:3]:
            with self.subTest(source=source):
                result, copied = evaluate(source, "Twenty years later, there were 2020 buses.")
                self.assertEqual(result["suggestions_removed"]["criteria"], 1)
                self.assertNotIn("Twenty years later", copied)
        result, copied = evaluate(
            "The study ran from 2000 to 2020.", "Twenty years later, transport was more reliable."
        )
        self.assertEqual(result["suggestions_removed"]["total"], 0)
        self.assertIn("Twenty years later", copied)
        result, _copied = evaluate(
            "The study ran from 2000 to 2020.", "Thirty years later, transport was more reliable."
        )
        self.assertEqual(result["suggestions_removed"]["criteria"], 1)

    def test_word_count_is_not_a_source_for_a_time_span(self):
        # Found while writing these tests: the second quantity essay is exactly 20 words,
        # and the word count was counted as a source for "twenty years".
        source = self.quantities[1]
        self.assertEqual(
            count_words(f"Public transport is important.\n{source}\nIn conclusion, buses matter."),
            20,
        )
        sources = figures.Sources(source, numbers=(20, 250))
        self.assertEqual(sources.unsourced("Twenty years later"), ["Twenty years"])
        self.assertEqual(sources.unsourced("Expand the essay to 250 words."), [])
        self.assertEqual(sources.unsourced("Only 20 of them are mentioned."), [])


if __name__ == "__main__":
    unittest.main()
