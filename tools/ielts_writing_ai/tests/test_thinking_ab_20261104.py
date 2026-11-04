"""Regressions from the thinking A/B run (off vs high, 7 + 7 evaluate calls, prompt
iwa-2026-11-04.6; docs/design/ielts-writing-ai-thinking-ab-20261104): English number
words bypassed the figure check ("about forty times as many people"), language advice
changed the writer's meaning, and teacher annotations had no place in realcheck.
The fixture holds the 14 real deepseek-flash outputs (reasoning text redacted)."""

import json
import tempfile
import unittest
from pathlib import Path

from tools.ielts_writing_ai import copytext, figures, prompts, realcheck, realcheck_compare, review
from tools.ielts_writing_ai.llm import parse_strict_json

FX = json.loads(
    (Path(__file__).parent / "fixtures" / "realcheck_20261104e.json").read_text(encoding="utf-8")
)


def evaluate(mode, sample_id, raw=None):
    raw = raw if raw is not None else parse_strict_json(FX["evaluations"][mode][sample_id])
    return review.normalize_evaluation(raw, FX["submissions"][sample_id])


def advice(result) -> list[str]:
    texts = [i["suggestion"] for c in result["criteria"] for i in c["issues"]]
    texts += result["priorities"]
    mapped = result["argument"] or {}
    texts += [p["suggestion"] for p in mapped.get("problems") or []]
    texts += [i["suggestion"] for i in mapped.get("improvements") or []]
    return [t for t in texts if t]


class EnglishNumberTest(unittest.TestCase):
    def test_real_forty_times_advice_is_removed_everywhere(self):
        raw_text = FX["evaluations"]["high"]["t2-mid"]
        self.assertIn("forty times as many people", raw_text)
        self.assertNotRegex(FX["submissions"]["t2-mid"]["essay_text"], r"(?i)\b(40|forty)\b")
        result = evaluate("high", "t2-mid")
        self.assertEqual(result["suggestions_removed"]["criteria"], 1)
        visible = json.dumps(result, ensure_ascii=False) + copytext.evaluation_text(result, {})
        self.assertNotIn("forty times", visible)
        issue = next(i for i in result["criteria"][0]["issues"] if i["suggestion_removed"])
        self.assertEqual(issue["suggestion"], "")

    def test_reviewer_percent_table(self):
        cases = [
            ("Public transport can reduce emissions.", "Reduce emissions by 40 percent.", True),
            ("Public transport can reduce emissions.", "Reduce emissions by forty percent.", True),
            ("Emissions fell by 40 percent.", "Reduce emissions by 40%.", False),
            ("Emissions fell by forty percent.", "Reduce emissions by 40%.", False),
            ("Emissions fell by 41%.", "Reduce emissions by forty percent.", True),
        ]
        for source, suggestion, removed in cases:
            with self.subTest(source=source, suggestion=suggestion):
                self.assertEqual(bool(figures.Sources(source).unsourced(suggestion)), removed)

    def test_word_forms(self):
        self.assertEqual(figures.en_number("forty-two"), "42")
        self.assertEqual(figures.en_number("one hundred and twenty"), "120")
        self.assertEqual(figures.en_number("a hundred"), "100")
        self.assertEqual(figures.en_number("two thousand and twenty"), "2020")
        self.assertEqual(
            figures.figures("1.5 million riders"), [("1500000", figures.PLAIN, "1.5 million")]
        )
        self.assertEqual(figures.figures("the twenty-first century"), [])
        self.assertEqual(figures.figures("one example"), [("1", figures.PLAIN, "one")])

    def test_kinds_and_their_sources(self):
        empty = figures.Sources("Buses help.", numbers=(97, 250))
        self.assertEqual(empty.unsourced("one example, two reasons"), [])  # structural
        self.assertEqual(empty.unsourced("three times as many"), ["three times"])  # a fact
        self.assertEqual(empty.unsourced("扩写到 two hundred and sixty words"), [])  # a target
        self.assertEqual(empty.unsourced("fourteen cities"), ["fourteen"])
        self.assertEqual(empty.unsourced("1.5 million riders"), ["1.5 million"])
        counted = figures.Sources("We counted 40 buses.")
        self.assertEqual(counted.unsourced("forty times as many"), ["forty times"])
        self.assertEqual(figures.Sources("It is 40 times cheaper.").unsourced("forty-fold"), [])
        self.assertEqual(figures.Sources("1,800,000 people").unsourced("1.8 million people"), [])

    def test_spans_between_source_years_are_derived_not_invented(self):
        sources = figures.Sources("Ownership in 2000 and 2020.")
        for text in ("Twenty years later", "20 years later", "over the two decades"):
            with self.subTest(text=text):
                self.assertEqual(sources.unsourced(text), [])
        self.assertEqual(sources.unsourced("thirty years later"), ["thirty years"])
        self.assertEqual(sources.unsourced("in 1990"), ["1990"])

    def test_no_real_output_keeps_an_unsourced_figure_and_only_forty_times_is_removed(self):
        removed = {}
        for mode, outputs in FX["evaluations"].items():
            for sample_id in outputs:
                result = evaluate(mode, sample_id)
                sources = figures.for_submission(FX["submissions"][sample_id])
                with self.subTest(mode=mode, sample=sample_id):
                    self.assertEqual([a for a in advice(result) if sources.unsourced(a)], [])
                if result["suggestions_removed"]["total"]:
                    removed[(mode, sample_id)] = result["suggestions_removed"]["total"]
        # In particular "Twenty years later" (2000 -> 2020) in high Task 1 is kept.
        self.assertEqual(removed, {("high", "t2-mid"): 1})


class PromptTest(unittest.TestCase):
    def test_language_advice_must_keep_meaning_and_check_context(self):
        text = " ".join(
            prompts.build_evaluate(FX["submissions"]["t2-mid"], [])[0][0]["content"].split()
        )
        for phrase in (
            "read the whole sentence before calling a structure wrong",
            "must keep the writer's meaning",
            "never add facts, causes, figures, multipliers or trends",
            "'a steady climb'",
            "complete, usable sentence",
            "check that it really says it",
        ):
            self.assertIn(phrase, text)
        self.assertIn("(0) Question type", prompts.ARGUMENT_CHECKLIST)
        self.assertGreaterEqual(
            int(prompts.PROMPT_VERSION.rsplit(".", 1)[1]), 7
        )  # introduced in .7


ESSAY = (
    "People have different views about free time. In my opinion, both are important.\n"
    "Organised activities help children learn. One case in point is learning Maths at school.\n"
    "Free time also matters. Langlang chose to play the piano and became famous."
)


def jsonl(tmp, **item):
    base = {"id": "s1", "task_type": "task2", "prompt": "Discuss both views.", "essay": ESSAY}
    path = Path(tmp) / "samples.jsonl"
    path.write_text(json.dumps({**base, **item}, ensure_ascii=False) + "\n", encoding="utf-8")
    return str(path)


def sample_with(result, findings):
    return {
        "id": "s1",
        "task_type": "task2",
        "teacher_findings": findings,
        "generations": {"evaluate": {"status": "ready", "result": result}},
    }


FINDINGS = [
    {"quote": "One case in point is learning Maths at school.", "note": "走题"},
    {"quote": "Langlang chose to play the piano and became famous.", "note": "例子不贴题"},
]
RESULT = {
    "criteria": [{"key": "task", "issues": [{"quote": "learning Maths at school"}]}],
    "argument": {
        "problems": [
            {
                "type": "unclear_position",
                "quote": "In my opinion, both are important.",
                "conflicts_with": None,
            }
        ],
        "improvements": [],
    },
    "consistency_issues": [],
}


class TeacherFindingsTest(unittest.TestCase):
    def test_samples_file_validates_teacher_quotes(self):
        with tempfile.TemporaryDirectory() as tmp:
            items = realcheck.load_samples(jsonl(tmp, teacher_findings=FINDINGS))
            self.assertEqual(items[0]["teacher_findings"], FINDINGS)
            for bad in ("x", [{"note": "走题"}], [{"quote": "Not in the essay at all."}]):
                with self.subTest(bad=bad), self.assertRaises(realcheck.RealCheckError):
                    realcheck.load_samples(jsonl(tmp, teacher_findings=bad))

    def test_overlap_is_location_only(self):
        self.assertTrue(realcheck.spans_overlap("learning Maths at school", FINDINGS[0]["quote"]))
        self.assertTrue(
            realcheck.spans_overlap("Langlang chose to play the piano", FINDINGS[1]["quote"])
        )
        self.assertFalse(realcheck.spans_overlap("Free time also matters.", FINDINGS[1]["quote"]))
        self.assertFalse(realcheck.spans_overlap("", FINDINGS[1]["quote"]))

    def test_coverage_report_and_review_sheet(self):
        coverage = realcheck.teacher_coverage(sample_with(RESULT, FINDINGS))
        self.assertEqual((coverage["covered"], coverage["total"]), (1, 2))
        self.assertEqual(coverage["ai_spans_not_marked_by_teacher"], 1)
        self.assertEqual([f["covered"] for f in coverage["findings"]], [True, False])
        metrics = realcheck._teacher_findings_metrics({"samples": [sample_with(RESULT, FINDINGS)]})
        self.assertEqual((metrics["covered"], metrics["total"], metrics["rate"]), (1, 2, 0.5))
        self.assertIsNone(
            realcheck._teacher_findings_metrics({"samples": [sample_with(RESULT, [])]})
        )
        view = realcheck_compare.sample_view({"calls": []}, sample_with(RESULT, FINDINGS))
        cmp = {
            "conditions": {"a": {"evaluate_thinking": "off"}, "b": {"evaluate_thinking": "high"}},
            "samples": [{"a": view, "b": view}],
        }
        sheet = realcheck_compare.render_manual_review(cmp)
        self.assertIn("| 老师批注 | A 覆盖：否 / B 覆盖：否 | — | Langlang chose", sheet)
        self.assertIn("例子不贴题", sheet)


if __name__ == "__main__":
    unittest.main()
