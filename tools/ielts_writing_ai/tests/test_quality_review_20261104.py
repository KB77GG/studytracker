"""Formal regressions for the 8 findings of the 2026-11-04 offline quality review
(docs/design/ielts-writing-ai-quality-review-20261104). The review's probes assert the
old defective behaviour; these tests assert the corrected behaviour for the same cases."""

import json
import tempfile
import unittest
from pathlib import Path

from tools.ielts_writing_ai import essay, realcheck, review
from tools.ielts_writing_ai import rewrite_quality as rq
from tools.ielts_writing_ai.llm import FakeClient, LLMError, LLMResult, parse_strict_json

from .helpers import settings_for

FIXTURE = json.loads(
    (Path(__file__).parent / "fixtures" / "realcheck_20261104.json").read_text(encoding="utf-8")
)

GAP_YEAR_PROMPT = (
    "In many countries, young people are encouraged to work or travel for a year between "
    "finishing high school and starting university studies. Discuss the advantages and "
    "disadvantages for young people who decide to do this."
)
GAP_YEAR_ANSWER = """Taking a gap year after graduation can be a valuable opportunity, but it also carries risks. In my view, the benefits depend on whether the break has a clear purpose and a realistic budget.

One advantage is greater maturity. A teenager who spends several months earning a salary must arrive on time, cooperate with colleagues and deal politely with customers. These responsibilities develop independence and help someone who has always relied on parents understand the demands of adult life. Visiting another country can have a similar effect: arranging accommodation, communicating in an unfamiliar language and adapting to different customs encourage confidence. Such experiences can also clarify career ambitions before an applicant commits to an expensive degree.

However, postponing higher education can bring financial difficulties. Air fares and accommodation are costly, especially for families with limited savings. Even a temporary job may offer little security, leaving the graduate with neither useful qualifications nor enough money for tuition. Another concern is the loss of academic habits. After months away from books, returning to lectures and examinations may feel difficult. Friends will already be further ahead in their courses, which can create pressure to abandon a degree altogether.

These drawbacks do not make every gap year a mistake. A structured plan can reduce them: the participant could save a fixed amount, undertake a short placement related to a future profession and reserve regular time for reading. Parents should discuss practical expectations without treating an overseas adventure as compulsory.

Overall, a planned break can broaden a teenager's perspective and strengthen independence, while an unstructured one can waste money and delay qualifications. The best choice therefore depends on personal circumstances rather than a universal rule."""


def answers_for(text, n=2):
    return [
        {"part": f"题目要求 {i + 1}", "quote": s.text}
        for i, s in enumerate(essay.split_sentences(text)[:n])
    ]


def weak_case(**changes):
    item = FIXTURE["rewrites"]["t2-weak"]
    raw = parse_strict_json(item["raw_text"])
    raw["band_rationale"] = "为了向目标分数段靠近，重组论证并修正语言。"
    raw["answers"] = answers_for(raw["essay"])
    raw.update(changes)
    return raw, dict(item["submission"])


def check(raw, submission):
    result = review.normalize_rewrite(raw, submission)
    return result, [i["code"] for i in result["quality_issues"]]


class Finding1TopicRelevanceTest(unittest.TestCase):
    def gap_year(self, prompt=GAP_YEAR_PROMPT):
        _raw, sub = weak_case()
        sub.update(
            prompt_text=prompt,
            essay_text=GAP_YEAR_ANSWER,
            word_count=essay.count_words(GAP_YEAR_ANSWER),
        )
        raw = {
            "essay": GAP_YEAR_ANSWER,
            "answers": [
                {"part": "优点", "quote": "One advantage is greater maturity."},
                {
                    "part": "缺点",
                    "quote": "However, postponing higher education can bring "
                    "financial difficulties.",
                },
            ],
            "key_changes": ["明确两方面后果，并以规划是否充分作为判断依据。"],
            "band_rationale": "组织正反论证，补充具体解释；没有对改写稿另行评分。",
        }
        return check(raw, sub)

    def test_on_topic_paraphrase_is_not_failed_by_low_keyword_overlap(self):
        result, codes = self.gap_year()
        self.assertEqual(codes, [])
        self.assertTrue(result["quality_passed"])
        self.assertEqual(len(result["answers"]), 2)

    def test_exam_instructions_do_not_change_the_topic_overlap(self):
        plain = rq.prompt_coverage(GAP_YEAR_PROMPT, GAP_YEAR_ANSWER)
        with_instructions = rq.prompt_coverage(
            GAP_YEAR_PROMPT + " You should spend about 40 minutes on this task. "
            "Write at least 250 words.",
            GAP_YEAR_ANSWER,
        )
        self.assertEqual(plain, with_instructions)
        _result, codes = self.gap_year(
            GAP_YEAR_PROMPT + " You should spend about 40 minutes on this task. "
            "Write at least 250 words."
        )
        self.assertEqual(codes, [])

    def test_keyword_stuffed_off_topic_essay_no_longer_passes(self):
        item = FIXTURE["rewrites"]["t2-off-topic"]
        raw = parse_strict_json(item["raw_text"])
        raw["essay"] = (
            "Government spending on public transport and building roads is a familiar "
            "question. However, this response considers online learning.\n\n" + raw["essay"]
        )
        raw["key_changes"] = ["整理在线学习和课堂教学的优缺点。"]
        raw["band_rationale"] = "按两种教学形式组织论证，没有独立评定改写分数。"
        result, codes = check(raw, item["submission"])
        self.assertFalse(result["quality_passed"])
        self.assertIn("answer_map_missing", codes)
        self.assertNotIn("off_prompt", codes)  # overlap no longer decides anything

    def test_answer_quotes_must_exist_in_the_rewrite(self):
        raw, sub = weak_case(
            answers=[
                {"part": "立场", "quote": "I strongly believe roads are useless."},
                {"part": "让步", "quote": "Public transport is never crowded."},
            ]
        )
        result, codes = check(raw, sub)
        self.assertIn("answer_unverified", codes)
        self.assertIn("answer_map_missing", codes)
        self.assertEqual(result["answers"], [])

    def test_very_low_overlap_is_only_an_uncertainty_note(self):
        item = FIXTURE["rewrites"]["t2-off-topic"]
        raw = parse_strict_json(item["raw_text"])
        raw["answers"] = answers_for(raw["essay"])
        result, codes = check(raw, item["submission"])
        self.assertTrue(any("只是词面提示" in w for w in result["warnings"]))
        self.assertNotIn("off_prompt", codes)


class Finding2NegatedDataClaimTest(unittest.TestCase):
    def t1(self, rationale):
        item = FIXTURE["rewrites"]["t1-no-image"]
        raw = parse_strict_json(item["raw_text"])
        raw["key_changes"] = ["根据学生原稿整理段落，保留现有数字。"]
        raw["answers"] = answers_for(raw["essay"])
        raw["band_rationale"] = rationale
        return check(raw, item["submission"])

    def test_honest_limitations_are_not_data_claims(self):
        for rationale in (
            "题图缺失，无法确认数据准确。",
            "题图缺失，不能保证数据正确。",
            "数据准确性无法核实。",
            "The figures are taken from the draft; we cannot confirm the data are accurate.",
        ):
            with self.subTest(rationale=rationale):
                _result, codes = self.t1(rationale)
                self.assertNotIn("data_claim", codes)

    def test_positive_accuracy_claims_are_still_flagged(self):
        for rationale in ("数据引用准确。", "所有数据正确无误。", "The data are accurate."):
            with self.subTest(rationale=rationale):
                _result, codes = self.t1(rationale)
                self.assertIn("data_claim", codes)


class Finding3CaseChangeTest(unittest.TestCase):
    def test_capitalisation_fix_is_a_real_change(self):
        raw, sub = weak_case(key_changes=["将“i partly agree”改为“I partly agree”，修正句首大写。"])
        self.assertTrue(essay.contains_exact(raw["essay"], "I partly agree"))
        result, codes = check(raw, sub)
        self.assertEqual(codes, [])
        self.assertEqual(len(result["key_changes"]), 1)

    def test_punctuation_change_is_a_real_change(self):
        self.assertFalse(essay.same_text("However the", "However, the"))

    def test_claimed_new_wording_lookup_is_case_sensitive(self):
        raw, sub = weak_case(key_changes=["将“I partly agree”改为“i partly agree”。"])
        _result, codes = check(raw, sub)
        self.assertIn("claim_absent", codes)  # "i partly agree" is not in the rewrite


class Finding4WordCountTest(unittest.TestCase):
    def test_limit_valued_number_about_the_rewrite_is_still_checked(self):
        raw, sub = weak_case(key_changes=["改写稿共330词，扩展了原稿的论据。"])
        result, codes = check(raw, sub)
        self.assertEqual(result["word_count"], 290)
        self.assertIn("count_claim", codes)

    def test_roles_of_numbers(self):
        text = "原稿只有约97词，远低于250词下限；改写后扩展到约270词；应至少写250词"
        roles = [rq.count_role(text, m.start(), m.end()) for m in rq.COUNT_RE.finditer(text)]
        self.assertEqual(roles, ["original", "target", "current", "target"])
        self.assertEqual(rq.false_count(text, actual=220, original=97), 270)
        self.assertIsNone(rq.false_count(text, actual=270, original=97))

    def test_wrong_claim_about_the_original_is_also_caught(self):
        self.assertEqual(rq.false_count("原稿约180词", actual=290, original=97), 180)


class Finding5ChineseScoreClaimTest(unittest.TestCase):
    def test_chinese_score_claims_are_flagged(self):
        for rationale in (
            "本篇已达到雅思写作7分标准。",
            "这是一篇7分作文。",
            "可以拿到6.5分。",
            "整体符合7.0分水平。",
            "将语言提升到7分水平。",
            "我认为这是7分作文。",
        ):
            with self.subTest(rationale=rationale):
                _result, codes = check(*weak_case(band_rationale=rationale))
                self.assertIn("band_claim", codes)

    def test_negation_intent_and_original_are_not_claims(self):
        for rationale in (
            "为了达到7分目标，补充了论证。",
            "整体虽未达到Band 8的灵活与精准。",
            "向 Band 7 目标靠近：重组段落。",
            "原稿大约只能拿到5分，改写重点修正了语法。",
            "为了提升到7分水平，补充论证。",
        ):
            with self.subTest(rationale=rationale):
                _result, codes = check(*weak_case(band_rationale=rationale))
                self.assertNotIn("band_claim", codes)


class Finding6ConsistencyEvidenceTest(unittest.TestCase):
    def evaluate(self, issues):
        item = FIXTURE["evaluations"]["t1-no-image"]
        raw = parse_strict_json(item["raw_text"])
        raw["consistency_issues"] = issues
        return review.normalize_evaluation(raw, item["submission"])

    def test_unverifiable_quote_never_becomes_a_finding(self):
        result = self.evaluate(
            [{"quote": "Invented country Z has 999 percent ownership.", "comment": "严重矛盾。"}]
        )
        self.assertEqual(result["consistency_issues"], [])
        self.assertFalse(any("引文已在原文中核实" in w for w in result["warnings"]))
        self.assertTrue(any("无法在原文中找到" in w for w in result["warnings"]))

    def test_verified_quote_is_reported_as_model_finding_not_numeric_proof(self):
        result = self.evaluate(
            [
                {
                    "quote": "Country A had the highest level of ownership in both years",
                    "comment": "与 2020 年 C 约 80% 矛盾。",
                }
            ]
        )
        self.assertEqual(len(result["consistency_issues"]), 1)
        self.assertTrue(any("不是逐个数字的程序化校验" in w for w in result["warnings"]))


class SecondAttemptFailure(FakeClient):
    def __init__(self, first_text, error):
        super().__init__()
        self.first_text, self.error, self.count = first_text, error, 0

    def complete(self, messages, **kwargs):
        self.count += 1
        if self.count == 1:
            return LLMResult(self.first_text, self.model, 1, {})
        raise LLMError(self.error, "injected retry failure")


class Finding7RetryFailureKeepsDraftTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="iwa-q7-")
        self.settings = settings_for(self.tmp)
        self.item = next(s for s in realcheck.load_samples("builtin") if s["id"] == "t2-mid")
        self.first = FIXTURE["rewrites"]["t2-mid"]["raw_text"]  # 247 words: quality retry

    def test_transport_failures_on_the_retry_keep_the_first_draft(self):
        for error in ("timeout", "truncated", "http_503"):
            with self.subTest(error=error):
                client = SecondAttemptFailure(self.first, error)
                data = realcheck.run(
                    self.settings, [self.item], client=client, kinds=("rewrite",), max_calls=42
                )
                generation = data["samples"][0]["generations"]["rewrite"]
                self.assertEqual(client.count, 2)
                self.assertEqual(generation["status"], "ready")
                result = generation["result"]
                self.assertEqual(result["word_count"], 247)
                self.assertFalse(result["quality_passed"])
                self.assertEqual(result["retry_error"], error)
                self.assertTrue(any("质量重试没有完成" in w for w in result["warnings"]))

    def test_call_budget_on_the_retry_keeps_the_draft_without_a_third_call(self):
        client = SecondAttemptFailure(self.first, "must_not_be_called")
        data = realcheck.run(
            self.settings, [self.item], client=client, kinds=("rewrite",), max_calls=1
        )
        generation = data["samples"][0]["generations"]["rewrite"]
        self.assertEqual(client.count, 1)
        self.assertEqual(len(data["calls"]), 1)
        self.assertEqual(generation["status"], "ready")
        self.assertEqual(generation["result"]["retry_error"], "call_budget")

    def test_without_any_draft_a_failure_is_still_a_failure(self):
        class AlwaysFails(FakeClient):
            def complete(self, messages, **kwargs):
                raise LLMError("http_503", "down")

        data = realcheck.run(
            self.settings, [self.item], client=AlwaysFails(), kinds=("rewrite",), max_calls=42
        )
        generation = data["samples"][0]["generations"]["rewrite"]
        self.assertEqual(generation["status"], "failed")
        self.assertIsNone(generation["result"])


class OneGoodSixFailures(FakeClient):
    def __init__(self, good_text):
        super().__init__()
        self.good_text, self.count = good_text, 0

    def complete(self, messages, **kwargs):
        self.count += 1
        if self.count == 1:
            return LLMResult(self.good_text, self.model, 1, {})
        raise LLMError("truncated", "injected truncation")


class Finding8DenominatorTest(unittest.TestCase):
    def test_failed_generations_stay_in_the_acceptance_denominator(self):
        raw, _sub = weak_case(band_rationale="为了向 Band 7 目标靠近：重组段落，补充解释。")
        with tempfile.TemporaryDirectory(prefix="iwa-q8-") as tmp:
            data = realcheck.run(
                settings_for(tmp),
                realcheck.load_samples("builtin"),
                client=OneGoodSixFailures(json.dumps(raw, ensure_ascii=False)),
                kinds=("rewrite",),
                max_calls=42,
            )
        report = realcheck.build_report(data)
        rr = report["refine_rewrite"]
        self.assertEqual(
            (rr["rewrite_requested"], rr["rewrite_generated"], rr["rewrite_quality_passed_count"]),
            (7, 1, 1),
        )
        self.assertEqual(rr["rewrite_quality_passed_of_requested"], round(1 / 7, 3))
        self.assertEqual(rr["rewrite_quality_passed_of_generated"], 1.0)
        self.assertEqual(report["kinds"]["rewrite"]["final_ready"], round(1 / 7, 3))
        markdown = realcheck.render_markdown(report)
        self.assertIn("占全部请求 14%", markdown)
        self.assertIn("生成失败计为未通过", markdown)


if __name__ == "__main__":
    unittest.main()
