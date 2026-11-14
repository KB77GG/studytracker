"""Language advice that keeps a figure Task Achievement corrected (official Task 1 run of
2026-11-14: six suggestions under CC / LR / GRA kept a value or trend the same answer's
TA part had corrected). Figures only; trend words are not checked. Synthetic texts."""

import unittest

from tools.ielts_writing_ai import conflicts, copytext, essay, figures, review

from .helpers import confirmed_image

READING = (
    "Type: line_graph\nTitle: Share of people watching TV\nUnits: %\n"
    "Data: TV 16:00 = 22%; TV 21:00 = 47%; TV 22:00 = 40%; Radio 08:00 = 30%"
)
ESSAY = (
    "The graph shows the share of people who watched television and listened to the radio.\n"
    "In the evening, television viewing climbed to 45% at 22:00, which was its peak.\n"
    "Radio was most popular in the morning, when 30% of people listened at 08:00.\n"
    "At 16:00 the figure for television was about 22%, and it then rose steadily.\n"
    "Overall, television dominated the evening while radio led in the morning hours."
)
PEAK = "television viewing climbed to 45% at 22:00, which was its peak."
REASON = "数据描述大体完整，但个别数值与题图不符，需要核对。"


def submission(reading=READING, check=True):
    return {
        "task_type": "task1",
        "prompt_text": "The graph shows the share of people watching TV and listening to radio.",
        "essay_text": ESSAY,
        "word_count": essay.count_words(ESSAY),
        "target_band": 7.0,
        "image_status": "ready",
        "image_description": reading,
        "image_check": confirmed_image(reading) if check else None,
    }


def criterion(issues, strength="Radio was most popular in the morning"):
    return {
        "band": 6,
        "summary": REASON,
        "strengths": [{"quote": strength, "comment": "对比清楚"}],
        "issues": issues,
    }


TA_FIX = {
    "quote": "climbed to 45% at 22:00",
    "comment": "题图显示 22:00 约为 40%，原文数值有误。",
    "suggestion": "fell to about 40% at 22:00",
}


def raw(ta_issues=(TA_FIX,), lexical=(), coherence=(), grammar=()):
    return {
        "criteria": {
            "task": criterion(list(ta_issues)),
            "coherence": criterion(list(coherence)),
            "lexical": criterion(list(lexical)),
            "grammar": criterion(list(grammar)),
        },
        "comparisons": [],
        "overall_comment": "整体信息基本完整，但部分数据需要按题图改正。",
        "priorities": ["核对晚间峰值的数值", "注意时间顺序的衔接"],
    }


def lexical_issue(suggestion, quote=PEAK):
    return {"quote": quote, "comment": "climb 用词可以更准确。", "suggestion": suggestion}


def issues_of(result, key):
    return next(c for c in result["criteria"] if c["key"] == key)["issues"]


class TaskConflictTest(unittest.TestCase):
    def evaluate(self, data, **sub):
        return review.normalize_evaluation(data, submission(**sub))

    def test_a_suggestion_keeping_the_corrected_value_is_dropped(self):
        result = self.evaluate(
            raw(lexical=[lexical_issue("television viewing surged to 45% at 22:00")])
        )
        issue = issues_of(result, "lexical")[0]
        self.assertEqual(issue["suggestion"], "")
        self.assertTrue(issue["suggestion_removed"])
        self.assertEqual(issue["removed_reason"], "task_conflict")
        self.assertEqual(issue["comment"], "climb 用词可以更准确。")  # the comment stays
        self.assertEqual(result["task_conflicts"], 1)
        self.assertEqual(result["suggestions_removed"]["total"], 0)  # not an unsourced figure
        self.assertTrue(any("TA 部分已指出有误的数据" in w for w in result["warnings"]))
        self.assertEqual(issues_of(result, "task")[0]["suggestion"], TA_FIX["suggestion"])
        copied = copytext.copies_for("evaluate", result, {}, submission())["evaluation"]
        self.assertIn(copytext.CONFLICT_NOTE, copied)
        self.assertNotIn("surged to 45%", copied)

    def test_suggestions_that_agree_or_concern_other_sentences_stay(self):
        cases = {
            "follows the correction": lexical_issue(
                "television viewing fell to about 40% at 22:00"
            ),
            "no figure": lexical_issue("television viewing increased sharply"),
            "other sentence, same value": lexical_issue(
                "As much as 30% of people tuned in at 08:00.",
                quote="when 30% of people listened at 08:00",
            ),
        }
        for name, issue in cases.items():
            with self.subTest(case=name):
                result = self.evaluate(raw(lexical=[issue]))
                kept = issues_of(result, "lexical")[0]
                self.assertEqual(kept["suggestion"], issue["suggestion"])
                self.assertFalse(kept["suggestion_removed"])
                self.assertEqual(result["task_conflicts"], 0)

    def test_every_language_criterion_and_part_quotes_are_covered(self):
        keep_peak = "television viewing climbed to 45% at 22:00, its highest point"
        result = self.evaluate(
            raw(
                coherence=[lexical_issue(keep_peak, quote="In the evening, television viewing")],
                grammar=[lexical_issue(keep_peak, quote="which was its peak")],
                lexical=[lexical_issue(keep_peak)],
            )
        )
        self.assertEqual(result["task_conflicts"], 3)
        for key in ("coherence", "lexical", "grammar"):
            self.assertEqual(issues_of(result, key)[0]["removed_reason"], "task_conflict")

    def test_only_replacements_of_real_figures_count_as_corrections(self):
        lexical = [lexical_issue("television viewing surged to 45% at 22:00")]
        for name, ta in {
            "detail dropped, nothing new": dict(
                TA_FIX, suggestion="climbed sharply in the evening"
            ),
            "figure added, none replaced": dict(
                TA_FIX, suggestion="climbed to 45% (from 22%) at 22:00"
            ),
            "quote not in the essay": dict(TA_FIX, quote="climbed to 46% at 23:00"),
            "no suggestion": dict(TA_FIX, suggestion=""),
        }.items():
            with self.subTest(case=name):
                result = self.evaluate(raw(ta_issues=[ta], lexical=lexical))
                self.assertEqual(result["task_conflicts"], 0)
                self.assertTrue(issues_of(result, "lexical")[0]["suggestion"])

    def test_a_corrected_time_counts_but_the_minutes_do_not(self):
        ta = dict(TA_FIX, quote="45% at 22:00", suggestion="45% at 21:00")
        keeps_22 = lexical_issue("television viewing reached 45% at 22:00")
        result = self.evaluate(raw(ta_issues=[ta], lexical=[keeps_22]))
        self.assertEqual(result["task_conflicts"], 1)  # "22" was replaced by "21"
        other_time = lexical_issue(
            "Radio peaked at 08:00 with 30% of listeners.",
            quote="when 30% of people listened at 08:00",
        )
        result = self.evaluate(raw(ta_issues=[ta], lexical=[other_time]))
        self.assertEqual(result["task_conflicts"], 0)  # the shared "00" is not a figure

    def test_nothing_is_checked_without_a_scored_task_criterion(self):
        lexical = [lexical_issue("television viewing surged to 45% at 22:00")]
        result = self.evaluate(raw(lexical=lexical), check=False)  # reading not confirmed
        self.assertEqual(result["criteria"][0]["state"], "not_assessable")
        self.assertEqual(result["task_conflicts"], 0)
        self.assertTrue(issues_of(result, "lexical")[0]["suggestion"])

    def test_small_plain_numbers_are_not_corrections(self):
        self.assertEqual(
            conflicts.corrected_values(
                {"quote": "two lines", "quote_found": True, "suggestion": "three lines"}
            ),
            set(),
        )
        self.assertEqual(
            conflicts.corrected_values(
                {"quote": "at 5% and 22:00", "quote_found": True, "suggestion": "at 8% and 22:00"}
            ),
            {"5"},  # a small percentage still counts
        )


class UncheckedChartSourceTest(unittest.TestCase):
    def test_an_unchecked_reading_is_no_source_of_figures(self):
        sub = submission(check=False)
        self.assertEqual(figures.for_submission(sub).unsourced("about 47%"), [])  # old rule
        self.assertEqual(
            figures.for_submission(sub, chart_checked=False).unsourced("about 47%"), ["47%"]
        )
        self.assertEqual(figures.for_submission(sub, chart_checked=True).unsourced("about 47%"), [])
        # In the evaluation: the reading was not sent, so its 47% backs no suggestion.
        lexical = [lexical_issue("television viewing reached 47% in the evening")]
        result = review.normalize_evaluation(raw(lexical=lexical), sub)
        self.assertEqual(issues_of(result, "lexical")[0]["suggestion"], "")
        self.assertEqual(result["suggestions_removed"]["criteria"], 1)
        confirmed = review.normalize_evaluation(raw(lexical=lexical), submission())
        self.assertTrue(issues_of(confirmed, "lexical")[0]["suggestion"])


if __name__ == "__main__":
    unittest.main()
