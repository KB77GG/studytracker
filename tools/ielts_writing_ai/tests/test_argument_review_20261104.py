"""Regressions from the argument-structure review of 49b4c4e
(docs/design/ielts-writing-ai-argument-review-20261104): enum fields with the wrong
JSON type, the strong-essay check ignoring paragraph verdicts, and malformed entries
missing from the drop rate. Also: full quotes are verified before truncation, and a
structural surprise in model output is an invalid output, never an internal error."""

import json
import shutil
import tempfile
import unittest
from unittest import mock

from tools.ielts_writing_ai import argument, realcheck, review, samples
from tools.ielts_writing_ai.llm import FakeClient

from .helpers import TASK2_ESSAY, AppTestCase, settings_for
from .test_argument import FORBID_CHECK, OFF, STRONG, good_map, sample
from .test_review import evaluation, submission
from .test_rewrite_recheck_20261104 import FX, SequenceClient, t1_notes

BAD_VALUES = ([], {}, ["body"], {"role": "body"}, "unknown_enum", None, 3)
ENUM_FIELDS = (("paragraphs", "role"), ("paragraphs", "verdict"), ("problems", "type"))


class EnumTypeTest(unittest.TestCase):
    def test_list_object_or_unknown_enum_is_dropped_not_a_crash(self):
        for section, field in ENUM_FIELDS:
            for value in BAD_VALUES:
                with self.subTest(section=section, field=field, value=value):
                    raw = evaluation()
                    raw["argument"][section][0][field] = value
                    result = review.normalize_evaluation(raw, submission())
                    self.assertEqual(result["argument"]["dropped"], 1)
                    self.assertTrue(any("论证结构分析中有 1 条" in w for w in result["warnings"]))
                    self.assertIsNotNone(result["overall_band"])  # rest of evaluation kept

    def test_remaining_valid_paragraph_keeps_the_evaluation(self):
        raw = evaluation()
        raw["argument"]["paragraphs"][0]["role"] = ["introduction"]
        mapped = review.normalize_evaluation(raw, submission())["argument"]
        self.assertEqual([p["role"] for p in mapped["paragraphs"]], ["body"])
        self.assertEqual(len(mapped["problems"]), 1)

    def test_no_valid_paragraph_left_is_an_incomplete_evaluation(self):
        raw = evaluation()
        for paragraph in raw["argument"]["paragraphs"]:
            paragraph["verdict"] = {"value": "supports"}
        with self.assertRaisesRegex(review.InvalidOutput, "论证结构"):
            review.normalize_evaluation(raw, submission())

    def test_wrong_container_and_position_types(self):
        raw = good_map(position=["I partly agree"], problems={"type": "circular"})
        mapped = argument.normalize(raw, TASK2_ESSAY)
        self.assertIsNone(mapped["position"])
        self.assertEqual(mapped["problems"], [])
        self.assertEqual(mapped["dropped"], 2)  # the position and the bare problem object
        with self.assertRaises(argument.ArgumentInvalid):
            argument.normalize(good_map(paragraphs={"role": "body"}), TASK2_ESSAY)
        for raw in (good_map(position=None, problems=None), good_map(position=None, problems=[])):
            self.assertEqual(argument.normalize(raw, TASK2_ESSAY)["dropped"], 0)


def mutate_first_evaluation(change):
    """A FakeClient whose first evaluation is altered by change(raw_json)."""

    class Client(FakeClient):
        def __init__(self):
            super().__init__()
            self.evaluations = 0

        def complete(self, messages, **kwargs):
            result = super().complete(messages, **kwargs)
            if (kwargs.get("context") or {}).get("kind") == "evaluate":
                self.evaluations += 1
                if self.evaluations == 1:
                    raw = json.loads(result.text)
                    change(raw)
                    result.text = json.dumps(raw, ensure_ascii=False)
            return result

    return Client()


class PipelineTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="iwa-arg-review-")
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def run_one(self, client, limit=1):
        items = realcheck.load_samples("builtin")[:limit]
        data = realcheck.run(
            settings_for(self.tmp), items, client=client, kinds=("evaluate",), max_calls=2 * limit
        )
        return data, realcheck.build_report(data)

    def test_reviewer_case_one_bad_role_is_dropped_on_the_first_call(self):
        def bad_role(raw):
            raw["argument"]["paragraphs"][0]["role"] = ["introduction"]

        client = mutate_first_evaluation(bad_role)
        data, report = self.run_one(client)
        generation = data["samples"][0]["generations"]["evaluate"]
        self.assertEqual(generation["status"], "ready")
        self.assertEqual(client.evaluations, 1)
        self.assertEqual(generation["result"]["argument"]["dropped"], 1)
        self.assertEqual(report["kinds"]["evaluate"]["first_attempt_valid"], 1.0)
        self.assertEqual(report["argument"]["dropped"], 1)

    def test_no_valid_paragraph_is_retried_once_and_the_report_counts_it(self):
        def all_bad(raw):
            for paragraph in raw["argument"]["paragraphs"]:
                paragraph["role"] = ["body"]

        client = mutate_first_evaluation(all_bad)
        data, report = self.run_one(client)
        self.assertEqual(data["samples"][0]["generations"]["evaluate"]["status"], "ready")
        self.assertEqual(client.evaluations, 2)
        self.assertEqual(
            report["kinds"]["evaluate"]["first_attempt_rejections"],
            {"论证结构分析没有给出可核实的段落中心句": 1},
        )
        self.assertEqual(report["argument"]["evaluate_attempts"], 2)
        self.assertEqual(report["argument"]["attempts_rejected_for_argument"], 1)
        self.assertIn("其中 1 次因缺少论证结构", realcheck.render_markdown(report))

    def test_structural_exception_is_an_invalid_output_retried_once(self):
        real = argument.normalize
        seen = []

        def flaky(raw, essay, *rest):
            seen.append(1)
            if len(seen) == 1:
                raise TypeError("unhashable type: 'list'")
            return real(raw, essay, *rest)

        with (
            mock.patch.object(review.argument_lib, "normalize", side_effect=flaky),
            self.assertLogs("iwa.review", "WARNING") as logs,
        ):
            data, _report = self.run_one(FakeClient())
        self.assertIn("TypeError: unhashable type: 'list'", "\n".join(logs.output))
        self.assertEqual(data["samples"][0]["generations"]["evaluate"]["status"], "ready")
        self.assertEqual(len(data["calls"]), 2)

    def test_persistent_structural_exception_fails_as_invalid_output_and_report_completes(self):
        with (
            mock.patch.object(
                review.argument_lib, "normalize", side_effect=TypeError("unhashable type: 'dict'")
            ),
            self.assertLogs("iwa.review", "WARNING"),
        ):
            data, report = self.run_one(FakeClient())
        generation = data["samples"][0]["generations"]["evaluate"]
        self.assertEqual(
            (generation["status"], generation["error_code"]), ("failed", "invalid_output")
        )
        self.assertEqual(
            report["kinds"]["evaluate"]["first_attempt_rejections"],
            {"模型输出结构异常（TypeError）": 1},
        )

    def test_report_is_written_even_if_replaying_an_output_raises(self):
        data, _ = self.run_one(FakeClient())
        with mock.patch.object(review, "normalize_evaluation", side_effect=RuntimeError("boom")):
            report = realcheck.build_report(data)
        self.assertEqual(
            report["kinds"]["evaluate"]["first_attempt_rejections"],
            {"复核时出错（RuntimeError）": 1},
        )
        self.assertIn("## 论证结构", realcheck.render_markdown(report))


class NotesRepairGuardTest(AppTestCase):
    def test_structural_exception_in_notes_repair_keeps_the_fixed_first_essay(self):
        self.client_llm = SequenceClient([FX["rewrite_attempts"]["t1-no-image"][0], t1_notes()])
        self.app = self.make_app()
        self.storage = self.app.extensions["iwa"].storage
        _uid, code = self.add_user()
        client = self.login(code)
        real = review.normalize_rewrite
        seen = []

        def flaky(raw, sub):
            seen.append(1)
            if len(seen) == 2:  # the notes repair
                raise TypeError("unhashable type: 'list'")
            return real(raw, sub)

        with (
            mock.patch.object(review, "normalize_rewrite", side_effect=flaky),
            self.assertLogs("iwa.review", "WARNING"),
        ):
            public_id = self.submit(
                client,
                task_type="task1",
                prompt_text=samples.TASK1_PROMPT,
                essay_text=samples.TASK1_NO_IMAGE,
            ).get_json()["public_id"]
        rewrite = client.get(f"/api/submissions/{public_id}").get_json()["submission"][
            "generations"
        ]["rewrite"]
        self.assertEqual(rewrite["status"], "ready")
        self.assertEqual(rewrite["result"]["retry_error"], "invalid_output")
        self.assertIn(
            "Country A had the highest level of ownership in 2000", rewrite["result"]["essay"]
        )


def outcomes(item):
    return {c["check"].split("（")[0]: c for c in realcheck._argument_checks(item, item["expect"])}


class StrongCheckTest(unittest.TestCase):
    def strong_map(self, **overrides):
        value = good_map(problems=[])
        value.update(overrides)
        return value

    def test_reviewer_case_all_paragraphs_off_position_fails_the_strong_check(self):
        mapped = self.strong_map()
        for paragraph in mapped["paragraphs"]:
            paragraph["verdict"] = "off_position"
        checks = outcomes(sample("t2-strong", mapped, STRONG))
        forbid = checks[FORBID_CHECK]
        self.assertFalse(forbid["ok"])
        self.assertEqual(forbid["detail"]["hits"], ["off_position"])
        self.assertEqual(len(forbid["detail"]["off_position_paragraphs"]), 4)
        # The problem count is a separate measure and is not inflated by verdicts.
        self.assertTrue(checks["论证问题 ≤ 1 条"]["ok"])

    def test_normal_strong_map_passes(self):
        checks = outcomes(sample("t2-strong", self.strong_map(), STRONG))
        self.assertTrue(all(c["ok"] for c in checks.values()), checks)

    def test_inconsistent_position_needs_a_verified_pair_to_count(self):
        mapped = self.strong_map()
        mapped["position"]["consistent"] = False
        forbid = outcomes(sample("t2-strong", mapped, STRONG))[FORBID_CHECK]
        # No conflicting passages were given, so the claim itself is not adopted.
        self.assertTrue(forbid["ok"])
        self.assertIsNone(forbid["detail"]["position_consistent"])
        mapped["problems"] = [
            {
                "type": "inconsistent_position",
                "quote": "i think this idea has advantages and disadvantages",
                "conflicts_with": "I partly agree that university should be free",
                "comment": "开头说有利有弊，结尾才表态。",
            }
        ]
        forbid = outcomes(sample("t2-strong", mapped, STRONG))[FORBID_CHECK]
        self.assertFalse(forbid["ok"])
        self.assertEqual(forbid["detail"]["hits"], ["inconsistent_position"])

    def test_strong_essay_must_have_a_verified_position(self):
        expect = dict(STRONG, argument_position=True)
        with_position = outcomes(sample("t2-strong", self.strong_map(), expect))
        self.assertTrue(with_position["找到可核实的立场句"]["ok"])
        without = outcomes(sample("t2-strong", self.strong_map(position=None), expect))
        self.assertFalse(without["找到可核实的立场句"]["ok"])
        self.assertTrue(samples.SAMPLES[3]["expect"]["argument_position"])
        self.assertEqual(samples.SAMPLES[3]["id"], "t2-strong")

    def test_any_of_only_counts_paragraph_verdicts_when_off_position_is_listed(self):
        mapped = self.strong_map()
        mapped["paragraphs"][1]["verdict"] = "off_position"
        self.assertTrue(
            all(c["ok"] for c in outcomes(sample("t2-off-topic", mapped, OFF)).values())
        )
        irrelevant_only = {"argument_any_of": ["irrelevant"]}
        self.assertFalse(
            any(c["ok"] for c in outcomes(sample("t2-off-topic", mapped, irrelevant_only)).values())
        )


class AccountingTest(unittest.TestCase):
    def test_reviewer_case_eight_string_problems_are_eight_of_thirteen_dropped(self):
        raw = good_map(problems=["not an object"] * 8)
        mapped = argument.normalize(raw, TASK2_ESSAY)
        self.assertEqual(
            {k: mapped[k] for k in ("returned", "kept", "dropped", "duplicates", "over_limit")},
            {"returned": 13, "kept": 5, "dropped": 8, "duplicates": 0, "over_limit": 0},
        )
        metrics = realcheck._argument_metrics({"samples": [sample("malformed", raw, {})]})
        self.assertEqual((metrics["returned"], metrics["dropped"]), (13, 8))
        self.assertAlmostEqual(metrics["dropped_rate"], round(8 / 13, 3))
        markdown = "\n".join(realcheck._argument_markdown(metrics))
        self.assertIn(
            "模型给出 13 条 = 采用 5 + 格式不对或无法核实而丢弃 8 + 重复 0 + 超出上限 0",
            markdown,
        )
        self.assertIn(f"**丢弃率 {realcheck._pct(metrics['dropped_rate'])}**", markdown)

    def test_every_returned_entry_lands_in_exactly_one_bucket(self):
        valid = [
            {"type": t, "quote": "free education", "comment": "c"} for t in argument.PROBLEM_TYPES
        ]
        raw = good_map(
            problems=[
                valid[0],
                dict(valid[0]),
                "x",
                {"type": "circular", "quote": "nope", "comment": "c"},
            ]
            + valid[1:],
            improvements=[{"quote": "free education", "suggestion": "可以再具体一点"}] * 5
            + [{"quote": "free education", "suggestion": "写上超过 80% 的学生受益"}],
        )
        raw["paragraphs"] = raw["paragraphs"] * 3 + [{"role": "body"}]
        mapped = argument.normalize(raw, TASK2_ESSAY)
        self.assertEqual(mapped["returned"], 1 + 13 + 14 + 6)
        self.assertEqual(mapped["kept"], 1 + 4 + argument.MAX_PROBLEMS + argument.MAX_IMPROVEMENTS)
        # paragraph without verdict, "x", unverifiable quote, two unpaired contradictions,
        # the improvement whose only content was an unsourced figure
        self.assertEqual(mapped["dropped"], 1 + 2 + len(argument.PAIRED_TYPES) + 1)
        self.assertEqual(mapped["duplicates"], 8 + 1)  # same real paragraph ×8, repeat ×1
        self.assertEqual(mapped["over_limit"], (9 - argument.MAX_PROBLEMS) + (5 - 3))
        self.assertEqual(
            mapped["returned"],
            mapped["kept"] + mapped["dropped"] + mapped["duplicates"] + mapped["over_limit"],
        )
        self.assertEqual(mapped["suggestions_removed"], 1)

    def test_results_stored_before_the_accounting_fields_still_report(self):
        item = sample("old", good_map(), {})
        stored = item["generations"]["evaluate"]["result"]["argument"]
        for key in ("returned", "kept", "duplicates", "over_limit"):
            stored.pop(key)
        metrics = realcheck._argument_metrics({"samples": [item]})
        self.assertEqual((metrics["returned"], metrics["dropped_rate"]), (7, 0.0))


LONG_PREFIX = "Public transport helps people travel safely. " * 12
LONG_ESSAY = LONG_PREFIX + "This is the original ending.\nIn conclusion, buses matter."


class QuoteTruncationTest(unittest.TestCase):
    def test_invented_ending_after_a_real_prefix_is_not_verified(self):
        raw = {
            "paragraphs": [
                {"role": "body", "verdict": "supports", "main_point": LONG_PREFIX + "Invented."},
                {"role": "conclusion", "verdict": "supports", "main_point": "buses matter"},
            ]
        }
        mapped = argument.normalize(raw, LONG_ESSAY)
        self.assertEqual([p["role"] for p in mapped["paragraphs"]], ["conclusion"])
        self.assertEqual(mapped["dropped"], 1)

    def test_long_real_quote_is_verified_in_full_then_shortened(self):
        quote = LONG_PREFIX + "This is the original ending."
        self.assertGreater(len(quote), argument.QUOTE_LIMIT)
        raw = {"paragraphs": [{"role": "body", "verdict": "supports", "main_point": quote}]}
        shown = argument.normalize(raw, LONG_ESSAY)["paragraphs"][0]["main_point"]
        self.assertEqual(len(shown), argument.QUOTE_LIMIT)
        self.assertIn(shown, LONG_ESSAY)

    def test_criterion_evidence_uses_the_same_rule(self):
        invented = review._evidence_items(
            [{"quote": LONG_PREFIX + "Invented.", "comment": "c"}],
            LONG_ESSAY,
            limit=4,
            with_suggestion=False,
        )[0]
        self.assertFalse(invented["quote_found"])
        real = review._evidence_items(
            [{"quote": LONG_PREFIX + "This is the original ending.", "comment": "c"}],
            LONG_ESSAY,
            limit=4,
            with_suggestion=False,
        )[0]
        self.assertTrue(real["quote_found"])
        self.assertEqual(len(real["quote"]), 300)


if __name__ == "__main__":
    unittest.main()
