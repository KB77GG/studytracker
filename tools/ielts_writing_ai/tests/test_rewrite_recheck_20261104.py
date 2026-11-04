"""Regressions from the second real run (iwa-2026-11-04.2, 24 calls) and its review
(docs/design/ielts-writing-ai-quality-recheck-20261104). All texts below are the real
deepseek-flash outputs for the built-in synthetic samples."""

import json
import unittest
from pathlib import Path

from tools.ielts_writing_ai import essay, prompts, realcheck, review, samples
from tools.ielts_writing_ai import rewrite_quality as rq
from tools.ielts_writing_ai.llm import FakeClient, LLMError, LLMResult, parse_strict_json
from tools.ielts_writing_ai.web import _with_cross_notes

from .helpers import AppTestCase

FX = json.loads(
    (Path(__file__).parent / "fixtures" / "realcheck_20261104b.json").read_text(encoding="utf-8")
)


def attempt(sample_id, n):
    return parse_strict_json(FX["rewrite_attempts"][sample_id][n])


def normalize(sample_id, raw):
    return review.normalize_rewrite(raw, dict(FX["submissions"][sample_id]))


def codes(result):
    return [i["code"] for i in result["quality_issues"]]


T1_FIX = {
    "before": "Country A had the highest level of ownership in both years",
    "after": "Country A had the highest level of ownership in 2000",
    "why": "原句说 A 两年都最高，与后文 2020 年 C 更高的数字矛盾。",
}
T1_THE = {
    "before": "the growth was particularly striking",
    "after": "growth was particularly striking",
    "why": "去掉多余的 the。",
}


class OffTopicTest(unittest.TestCase):
    def test_both_real_off_topic_rewrites_are_still_off_topic(self):
        for n in (0, 1):
            with self.subTest(attempt=n):
                result = normalize("t2-off-topic", attempt("t2-off-topic", n))
                self.assertIn("still_off_topic", codes(result))
                self.assertFalse(result["content_passed"])
                self.assertFalse(result["quality_passed"])

    def test_model_flag_is_not_turned_into_a_claim_that_the_rewrite_answers(self):
        result = normalize("t2-off-topic", attempt("t2-off-topic", 1))
        self.assertTrue(any("需要人工确认" in w for w in result["warnings"]))
        self.assertFalse(any("按题目重新作答，没有保留" in w for w in result["warnings"]))

    def test_a_real_fresh_answer_to_the_question_is_not_flagged(self):
        # The flag says the original is off-topic, but this rewrite answers transport.
        raw = attempt("t2-weak", 0)
        raw["original_addresses_question"] = False
        result = normalize("t2-off-topic", raw)
        self.assertNotIn("still_off_topic", codes(result))

    def test_realcheck_sanity_catches_a_passed_off_topic_rewrite(self):
        sub = dict(FX["submissions"]["t2-off-topic"])
        essay_text = attempt("t2-off-topic", 1)["essay"]
        sample = {
            "id": "t2-off-topic",
            "submission": sub,
            "generations": {
                "rewrite": {
                    "status": "ready",
                    "result": {"essay": essay_text, "quality_passed": True},
                }
            },
        }
        self.assertFalse(realcheck._off_topic_rewrite_check(sample)["ok"])
        sample["generations"]["rewrite"]["result"]["quality_passed"] = False
        self.assertTrue(realcheck._off_topic_rewrite_check(sample)["ok"])


class StructuredChangeTest(unittest.TestCase):
    def test_real_task1_fix_and_removed_the_are_verified(self):
        original = FX["submissions"]["t1-no-image"]["essay_text"]
        rewrite = attempt("t1-no-image", 0)["essay"]
        self.assertIsNone(rq.verify_change(T1_FIX, original, rewrite))
        # Removing "the" is verified by its location, not refuted by other "the"s.
        self.assertIsNone(rq.verify_change(T1_THE, original, rewrite))

    def test_cut_air_pollution_is_not_mistaken_for_a_deletion(self):
        original = FX["submissions"]["t2-under-length"]["essay_text"]
        rewrite = attempt("t2-under-length", 0)["essay"]
        after = next(
            s.text for s in essay.split_sentences(rewrite) if "cut air pollution" in s.text
        )
        change = {
            "before": "buses and trains produce less pollution than private cars",
            "after": after,
            "why": "说明减少污染的具体影响。",
        }
        self.assertIsNone(rq.verify_change(change, original, rewrite))

    def test_real_old_new_objects_are_accepted_and_verified(self):
        raw = attempt("t2-under-length", 1)  # key_changes came back as [{old, new}, ...]
        self.assertTrue(all(isinstance(c, dict) and "old" in c for c in raw["key_changes"]))
        result = normalize("t2-under-length", raw)
        self.assertEqual(len(result["key_changes"]), len(raw["key_changes"]))
        self.assertTrue(result["quality_passed"], codes(result))

    def test_unchanged_essay_cannot_claim_changes_but_may_say_so_honestly(self):
        raw = attempt("t2-good", 0)  # body identical to the student's essay
        original = FX["submissions"]["t2-good"]["essay_text"]
        self.assertTrue(essay.same_text(raw["essay"], original))
        claim = {
            "before": "Public transport also brings wider social and environmental benefits",
            "after": "Public transport also brings wider social and environmental benefits.",
            "why": "强化主题句。",
        }
        result = normalize("t2-good", dict(raw, key_changes=[claim]))
        self.assertIn("change_not_made", codes(result))
        honest = dict(raw, key_changes=[], unchanged_reason="原文已符合目标，无需修改。")
        result = normalize("t2-good", honest)
        self.assertNotIn("no_changes", codes(result))
        self.assertTrue(any("无需修改" in w for w in result["warnings"]))
        result = normalize("t2-good", dict(raw, key_changes=[]))
        self.assertIn("no_changes", codes(result))

    def test_real_noop_in_summary_claim(self):
        raw = attempt("t1-no-image", 1)
        result = normalize(
            "t1-no-image",
            dict(raw, key_changes=[{"before": "In summary", "after": "In summary", "why": "呼应"}]),
        )
        self.assertIn("noop_change", codes(result))


class SequenceClient(FakeClient):
    def __init__(self, rewrite_responses):
        super().__init__()
        self.responses = list(rewrite_responses)
        self.modes = []

    def complete(self, messages, **kwargs):
        context = kwargs.get("context") or {}
        if context.get("kind") != "rewrite":
            return super().complete(messages, **kwargs)
        self.modes.append(context.get("mode") or "full")
        response = self.responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return LLMResult(response, self.model, 1, {})


def t1_notes(**overrides):
    rewrite = attempt("t1-no-image", 0)["essay"]
    notes = {
        "original_addresses_question": True,
        "answers": [
            {"part": "概述", "quote": essay.split_sentences(rewrite)[1].text},
            {"part": "关键对比", "quote": essay.split_sentences(rewrite)[2].text},
        ],
        "key_changes": [T1_FIX, T1_THE],
        "band_rationale": "为了向 Band 7 目标靠近，修正了概述与后文数字的矛盾。",
    }
    notes.update(overrides)
    return json.dumps(notes, ensure_ascii=False)


class Task1SelectionTest(AppTestCase):
    def run_t1(self, responses):
        self.client_llm = SequenceClient(responses)
        self.app = self.make_app()
        self.storage = self.app.extensions["iwa"].storage
        _uid, code = self.add_user()
        client = self.login(code)
        public_id = self.submit(
            client,
            task_type="task1",
            prompt_text=samples.TASK1_PROMPT,
            essay_text=samples.TASK1_NO_IMAGE,
        ).get_json()["public_id"]
        return client.get(f"/api/submissions/{public_id}").get_json()["submission"]["generations"][
            "rewrite"
        ]

    def assert_fixed_essay_kept(self, rewrite):
        text = rewrite["result"]["essay"]
        self.assertIn("Country A had the highest level of ownership in 2000", text)
        self.assertNotIn("Country A had the highest level of ownership in both years", text)

    def test_notes_only_problems_repair_notes_and_keep_the_fixed_essay(self):
        first = FX["rewrite_attempts"]["t1-no-image"][0]  # fixed the contradiction; prose notes
        rewrite = self.run_t1([first, t1_notes()])
        self.assertEqual(self.client_llm.modes, ["full", "notes"])
        self.assert_fixed_essay_kept(rewrite)
        result = rewrite["result"]
        self.assertTrue(result["quality_passed"], codes(result))
        self.assertTrue(result["notes_repaired"])
        self.assertEqual(len(result["key_changes"]), 2)

    def test_failed_notes_repair_still_keeps_the_fixed_essay(self):
        first = FX["rewrite_attempts"]["t1-no-image"][0]
        rewrite = self.run_t1([first, LLMError("timeout", "injected")])
        self.assert_fixed_essay_kept(rewrite)
        self.assertEqual(rewrite["result"]["retry_error"], "timeout")
        self.assertFalse(rewrite["result"]["quality_passed"])

    def test_unimproved_notes_repair_keeps_the_first_version(self):
        first = FX["rewrite_attempts"]["t1-no-image"][0]
        rewrite = self.run_t1([first, t1_notes(key_changes=["仍是自由文字说明"], answers=[])])
        self.assert_fixed_essay_kept(rewrite)
        self.assertEqual(rewrite["result"]["retry_error"], "notes_not_improved")

    def test_the_regressed_second_real_attempt_is_never_requested(self):
        first = FX["rewrite_attempts"]["t1-no-image"][0]
        regressed = FX["rewrite_attempts"]["t1-no-image"][1]  # brought the contradiction back
        rewrite = self.run_t1([first, t1_notes(), regressed])
        self.assertEqual(len(self.client_llm.modes), 2)
        self.assertEqual(self.client_llm.responses, [regressed])
        self.assert_fixed_essay_kept(rewrite)


class RankTest(unittest.TestCase):
    def test_tie_keeps_the_earlier_attempt(self):
        same = {"quality_issues": [{"code": "below_min", "kind": "content"}]}
        self.assertLess(review._rewrite_rank(same, 0), review._rewrite_rank(same, 1))

    def test_content_problems_outrank_notes_problems(self):
        content = {"quality_issues": [{"code": "below_min", "kind": "content"}]}
        notes = {"quality_issues": [{"code": "x", "kind": "notes"}] * 4}
        self.assertLess(review._rewrite_rank(notes, 1), review._rewrite_rank(content, 0))


class CrossNoteTest(unittest.TestCase):
    def evaluation(self, band, state="scored"):
        return {"criteria": [{"key": "task", "short": "TR", "band": band, "state": state}]}

    def test_low_task_band_adds_a_human_check_note_to_the_rewrite(self):
        notes = review.rewrite_cross_notes(self.evaluation(4.0))
        self.assertEqual(len(notes), 1)
        self.assertIn("请人工确认", notes[0])
        self.assertEqual(review.rewrite_cross_notes(self.evaluation(6.0)), [])
        self.assertEqual(review.rewrite_cross_notes(self.evaluation(None, "not_assessable")), [])

    def test_web_view_adds_the_note_without_changing_quality(self):
        generations = {
            "evaluate": {"status": "ready", "result": self.evaluation(4.0)},
            "rewrite": {
                "status": "ready",
                "result": {"warnings": [], "quality_passed": True, "essay": "x"},
            },
        }
        view = _with_cross_notes(generations)
        self.assertTrue(view["rewrite"]["result"]["quality_passed"])
        self.assertEqual(len(view["rewrite"]["result"]["warnings"]), 1)
        self.assertEqual(generations["rewrite"]["result"]["warnings"], [])  # not mutated


class PromptTest(unittest.TestCase):
    def test_task1_consistency_check_names_superlatives_against_own_figures(self):
        sub = dict(FX["submissions"]["t1-no-image"])
        messages, _ = prompts.build_evaluate(sub, essay.split_sentences(sub["essay_text"]))
        self.assertIn("in both years", messages[0]["content"])

    def test_real_t1_evaluation_missed_the_contradiction(self):
        # Documented model limitation (2nd run): the field came back empty.
        raw = parse_strict_json(FX["evaluations"]["t1-no-image"])
        self.assertEqual(raw.get("consistency_issues"), [])


if __name__ == "__main__":
    unittest.main()
