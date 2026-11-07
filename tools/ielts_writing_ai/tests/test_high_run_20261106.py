"""Regressions from the .8 / high real run (9 deepseek-flash evaluate calls, 6/7 ready;
docs/design/ielts-writing-ai-prompt8-high-20261106): three replies were not valid JSON
(one closing brace too many or too few where a long block ends) and the retry was told
only "text outside the JSON"; Task 1 showed the first three of eight listed figures (all
from the wrong year); improvements written under 'comment' were dropped; a hypothetical
example invented a figure. The fixture holds the 9 real outputs (reasoning not included)."""

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from tools.ielts_writing_ai import copytext, jsonshape, prompts, realcheck, review
from tools.ielts_writing_ai import essay as essay_lib
from tools.ielts_writing_ai.llm import FakeClient, LLMResult, parse_strict_json

from .helpers import settings_for

FX = json.loads(
    (Path(__file__).parent / "fixtures" / "realcheck_20261106_high.json").read_text(
        encoding="utf-8"
    )
)
SUBS = FX["submissions"]


def raw(sample_id, attempt=-1):
    return parse_strict_json(FX["attempts"][sample_id][attempt])


def flat(nested):
    out = dict(nested["criteria"])
    out.update({k: v for k, v in nested.items() if k != "criteria"})
    return out


class ScriptedClient:
    provider, model = "scripted", "scripted"

    def __init__(self, texts):
        self.texts = list(texts)
        self.messages = []

    def complete(self, messages, **_kwargs):
        self.messages.append(messages)
        return LLMResult(self.texts.pop(0), self.model, 1, {})


def generate(sample_id, texts):
    client = ScriptedClient(texts)
    generator = review.Generator(
        None, SimpleNamespace(evaluate_thinking="off", llm_temperature=0.2), client
    )
    sub = SUBS[sample_id]
    try:
        result = generator._generate_valid(
            "evaluate", sub, essay_lib.split_sentences(sub["essay_text"])
        )
    except review.InvalidOutput as exc:
        return client, exc
    return client, result


class JsonStructureTest(unittest.TestCase):
    def test_real_failures_stay_rejected_and_are_named(self):
        off_topic = FX["attempts"]["t2-off-topic"][0]
        self.assertIsNone(parse_strict_json(off_topic))
        problem = review.json_problem("evaluate", off_topic, SUBS["t2-off-topic"])
        self.assertIn("在 overall_comment 之后就结束了", problem)
        self.assertIn("priorities 落在了 JSON 之外", problem)
        self.assertIn("improvements 出现在最外层，但它属于 argument", problem)
        for text in FX["attempts"]["t2-under-length"]:
            with self.subTest(attempt=FX["attempts"]["t2-under-length"].index(text)):
                self.assertIsNone(parse_strict_json(text))
                self.assertIn(
                    "argument、overall_comment、priorities 被写进了 criteria 里面：criteria "
                    "写完后少了一个 }",
                    review.json_problem("evaluate", text, SUBS["t2-under-length"]),
                )

    def test_retry_note_carries_the_diagnosis_and_the_retry_must_be_valid_alone(self):
        good = FX["attempts"]["t2-off-topic"][1]
        client, result = generate("t2-off-topic", [FX["attempts"]["t2-off-topic"][0], good])
        evaluation, _model_result = result
        self.assertEqual(evaluation["criteria"][0]["band"], 2.0)
        retry = client.messages[1][-1]["content"]
        self.assertIn("JSON 结构错误", retry)
        self.assertIn("priorities 落在了 JSON 之外", retry)
        self.assertNotIn("JSON 之外不能有其他文字", retry)

        bad = FX["attempts"]["t2-under-length"]
        client, error = generate("t2-under-length", bad)
        self.assertIsInstance(error, review.InvalidOutput)  # no repair, no score
        self.assertIn("被写进了 criteria 里面", str(error))
        self.assertIn("被写进了 criteria 里面", client.messages[1][-1]["content"])

    def test_generic_shapes(self):
        cases = {
            'Here it is: {"a": 1}': "JSON 前面有其他文字",
            '{"a": [1, 2}': "括号不配对（应为 ]，实际是 }）",
            '{"a": "x': "字符串没有结束",
            '{"a": {"b": 1}': "到结尾还有 1 层括号没有闭合（最外层）",
            '{"a": {"b": [1': "到结尾还有 3 层括号没有闭合（b、a、最外层）",
            '{"a": 1} thanks': "JSON 后面还有其他文字",
            '{"a": 1,}': "JSON 语法错误",
        }
        for text, expected in cases.items():
            with self.subTest(text=text):
                self.assertIn(expected, jsonshape.diagnose(text))
        # Inside a flat criterion, with the older nested form still accepted.
        root, homes = prompts.evaluate_shape(SUBS["t2-weak"])
        text = '{"task": {"band": 6, "argument": {}}, "coherence": {}'
        self.assertIn("argument 被写进了 task 里面", jsonshape.diagnose(text, root, homes))
        text = '{"criteria": {"task": {"band": 6}, "coherence": {}}'
        self.assertNotIn("被写进了", jsonshape.diagnose(text, root, homes))

    def test_realcheck_names_the_problem_per_attempt(self):
        calls = [
            {
                "kind": "evaluate",
                "sample": sample_id,
                "attempt": n,
                "ok": True,
                "error": None,
                "text": text,
                "json_mode": True,
                "json_ok": parse_strict_json(text) is not None,
                "latency_ms": 1,
                "usage": {},
                "thinking": "high",
                "max_tokens": 16000,
                "reasoning_tokens": 1,
            }
            for sample_id, texts in FX["attempts"].items()
            for n, text in enumerate(texts)
        ]
        run_data = {
            "samples": [
                {"id": sample_id, "submission": sub, "generations": {}}
                for sample_id, sub in SUBS.items()
            ],
            "calls": calls,
        }
        metrics = realcheck._kind_metrics("evaluate", run_data)
        self.assertEqual(metrics["first_attempt_rejections"], {"JSON 括号或结构错误": 2})
        problems = {(p["sample"], p["attempt"]): p["problem"] for p in metrics["json_problems"]}
        self.assertEqual(
            sorted(problems),
            [("t2-off-topic", 0), ("t2-under-length", 0), ("t2-under-length", 1)],
        )
        self.assertIn("被写进了 criteria 里面", problems[("t2-under-length", 1)])


class UnclosedFirstClient(FakeClient):
    """Answers in the .9 top-level shape; the first evaluation reply of every sample
    loses the brace that closes 'grammar'."""

    def complete(self, messages, **kwargs):
        result = super().complete(messages, **kwargs)
        context = kwargs.get("context") or {}
        if context.get("kind") == "evaluate":
            value = flat(json.loads(result.text))
            text = json.dumps(value, ensure_ascii=False)
            result.text = text
        if context.get("kind") == "evaluate" and context.get("attempt") == 0:
            block = json.dumps(value["grammar"], ensure_ascii=False)
            result.text = text.replace(block, block[:-1], 1)
        return result


class RealcheckReportTest(unittest.TestCase):
    def test_report_lists_the_diagnosis_for_each_rejected_reply(self):
        with tempfile.TemporaryDirectory(prefix="iwa-rc-") as tmp:
            items = [s for s in realcheck.load_samples("builtin") if s["id"] == "t2-weak"]
            data = realcheck.run(
                settings_for(tmp), items, client=UnclosedFirstClient(), kinds=["evaluate"]
            )
            report = realcheck.build_report(data)
        metrics = report["kinds"]["evaluate"]
        self.assertEqual(metrics["first_attempt_rejections"], {"JSON 括号或结构错误": 1})
        self.assertEqual(metrics["final_ready"], 1.0)
        markdown = realcheck.render_markdown(report)
        self.assertIn(
            "原稿评价 · t2-weak 第 1 次：JSON 结构错误：argument、overall_comment、priorities "
            "被写进了 grammar 里面",
            markdown,
        )


class FlatCriteriaTest(unittest.TestCase):
    def test_prompt_asks_for_the_criteria_at_the_top_level(self):
        for sample_id, shape in (
            ("t2-weak", '{"task": C, "coherence": C, "lexical": C, "grammar": C, "argument": A,'),
            (
                "t1-no-image",
                '{"task": null, "coherence": C, "lexical": C, "grammar": C, '
                '"comparisons": [K, ...],',
            ),
        ):
            with self.subTest(sample=sample_id):
                sub = SUBS[sample_id]
                messages, _ = prompts.build_evaluate(
                    sub, essay_lib.split_sentences(sub["essay_text"])
                )
                self.assertIn(shape, messages[0]["content"])
                self.assertNotIn('"criteria":', messages[0]["content"])

    def test_flat_and_nested_give_the_same_evaluation(self):
        for sample_id in ("t2-good", "t1-no-image"):
            with self.subTest(sample=sample_id):
                nested = raw(sample_id)
                self.assertEqual(
                    review.normalize_evaluation(flat(nested), SUBS[sample_id]),
                    review.normalize_evaluation(nested, SUBS[sample_id]),
                )

    def test_both_forms_or_a_nested_root_key_are_rejected(self):
        nested = raw("t2-good")
        both = dict(flat(nested), criteria=nested["criteria"])
        with self.assertRaisesRegex(review.InvalidOutput, "评分项只能出现一次"):
            review.normalize_evaluation(both, SUBS["t2-good"])
        misplaced = flat(nested)
        misplaced["grammar"] = dict(misplaced["grammar"], priorities=misplaced.pop("priorities"))
        with self.assertRaisesRegex(review.InvalidOutput, "priorities 放错了位置"):
            review.normalize_evaluation(misplaced, SUBS["t2-good"])
        with self.assertRaisesRegex(review.InvalidOutput, "缺少评分项"):
            review.normalize_evaluation({"overall_comment": "x"}, SUBS["t2-good"])


REAL_FIGURES = [
    "around 70%",
    "roughly 55%",
    "about 40%",
    "only 15%",
    "about 75%",
    "approximately 65%",
    "nearly 80%",
    "around 35%",
]
# The review of f21da5f (docs/design/ielts-writing-ai-prompt9-review-20261107) only
# spelled out the model's correct comment: with six figures named, "the first four
# mentioned ones" kept 70 / 55 / 40 / 15 and cut the decisive 2020 figures 75 / 80.
EXPANDED = (
    "2000年A的70%高于B的55%、C的40%和D的15%；但2020年C的80%高于A的75%，所以both years不成立。"
)


class Task1FiguresTest(unittest.TestCase):
    def contradiction(self, **changes):
        nested = raw("t1-no-image")
        item = next(c for c in nested["comparisons"] if c["holds"] is False)
        item.update(changes)
        result = review.normalize_evaluation(nested, SUBS["t1-no-image"])
        return result["consistency_issues"][0], copytext.evaluation_text(result, {})

    def test_every_verified_figure_is_kept_in_the_model_order(self):
        cases = {
            "real comment": {},
            "expanded comment": {"comment": EXPANDED},
            "decisive figures first": {"figures": REAL_FIGURES[4:] + REAL_FIGURES[:4]},
            "four figures": {"figures": ["around 70%", "about 75%", "nearly 80%", "only 15%"]},
        }
        for name, changes in cases.items():
            with self.subTest(name):
                issue, text = self.contradiction(**changes)
                expected = changes.get("figures", REAL_FIGURES)
                self.assertEqual(issue["figures"], expected)
                self.assertNotIn("figures_omitted", issue)
                self.assertIn("对照：" + "；".join(f"“{f}”" for f in expected), text)
                self.assertIn("“about 75%”", text)
                self.assertIn("“nearly 80%”", text)
                self.assertNotIn("未列出", text)

    def test_duplicates_claim_parts_and_unverified_spans_are_left_out(self):
        issue, _text = self.contradiction(
            figures=["nearly 80%", " nearly 80% ", "invented 99%", 75, "", "about 75%"]
        )
        self.assertEqual(issue["figures"], ["nearly 80%", "about 75%"])

    def test_over_the_safety_bound_is_said_not_hidden(self):
        values = [f"{n}.5%" for n in range(1, 36)]
        essay = "Values were " + ", ".join(values) + ". Country A was the highest."
        raw_value = {
            "comparisons": [
                {
                    "claim": "Country A was the highest",
                    "figures": values,
                    "holds": False,
                    "comment": "其他国家更高。",
                }
            ]
        }
        issues, _checked, _dropped = review._consistency(raw_value, essay)
        self.assertEqual(issues[0]["figures"], values[: review.MAX_FIGURES])
        self.assertEqual(issues[0]["figures_omitted"], 35 - review.MAX_FIGURES)
        text = copytext.evaluation_text({"criteria": [], "consistency_issues": issues}, {})
        self.assertIn(f"（另有 {35 - review.MAX_FIGURES} 个数字未列出）", text)

    # Recheck of b8a7c1e (docs/design/ielts-writing-ai-prompt9-recheck-20261107): figures
    # were shortened to 300 characters BEFORE being verified, so a real prefix with an
    # invented ending was accepted and counted towards "另有 N 个数字未列出".
    def test_a_long_figure_is_verified_in_full_then_shortened(self):
        paragraph = SUBS["t1-no-image"]["essay_text"].split("\n")[6]
        self.assertGreater(len(paragraph), 300)
        issue, _text = self.contradiction(figures=[paragraph])
        self.assertEqual(issue["figures"], [paragraph[:300]])

        forged = paragraph[:300] + " and Country E reached 99% in 2020."
        nested = raw("t1-no-image")
        item = next(c for c in nested["comparisons"] if c["holds"] is False)
        item["figures"] = [forged]
        result = review.normalize_evaluation(nested, SUBS["t1-no-image"])
        self.assertEqual(result["consistency_issues"], [])  # its only evidence is invalid
        self.assertNotIn("对照：", copytext.evaluation_text(result, {}))

        issue, text = self.contradiction(figures=REAL_FIGURES + [forged, "invented 99%"])
        self.assertEqual(issue["figures"], REAL_FIGURES)
        self.assertNotIn("Country E", text)

    def test_an_invalid_long_figure_is_not_counted_as_omitted(self):
        filler = "The chart shows a steady pattern across many categories over time, " * 6
        values = [f"{n}.5%" for n in range(1, 32)]
        essay = f"Values were {', '.join(values)}. {filler.strip()} Country A was the highest."
        forged = filler[:300] + "with an ending the essay never had."
        self.assertNotIn(forged, essay)
        for count, omitted in ((30, 0), (31, 1)):
            with self.subTest(real=count):
                raw_value = {
                    "comparisons": [
                        {
                            "claim": "Country A was the highest",
                            "figures": values[:count] + [forged],
                            "holds": False,
                            "comment": "其他国家更高。",
                        }
                    ]
                }
                issues, _checked, _dropped = review._consistency(raw_value, essay)
                self.assertEqual(issues[0]["figures"], values[: review.MAX_FIGURES])
                self.assertEqual(issues[0].get("figures_omitted", 0), omitted)


class ImprovementFieldTest(unittest.TestCase):
    def test_real_good_improvements_written_as_comment_are_kept(self):
        nested = raw("t2-good")
        written = nested["argument"]["improvements"]
        self.assertTrue(all("comment" in i and "suggestion" not in i for i in written))
        mapped = review.normalize_evaluation(nested, SUBS["t2-good"])["argument"]
        self.assertEqual(
            [(i["quote"], i["suggestion"]) for i in mapped["improvements"]],
            [(i["quote"], i["comment"]) for i in written],
        )
        self.assertEqual(mapped["dropped"], 0)

    def test_the_same_checks_apply_to_a_comment_field(self):
        nested = raw("t2-strong")
        first = nested["argument"]["improvements"][0]
        self.assertIn("forty passengers", first["suggestion"])
        for field in ("suggestion", "comment"):
            with self.subTest(field=field):
                changed = json.loads(json.dumps(nested))
                changed["argument"]["improvements"][0] = {
                    "quote": first["quote"],
                    field: first["suggestion"],
                }
                result = review.normalize_evaluation(changed, SUBS["t2-strong"])
                self.assertEqual(result["suggestions_removed"]["argument"], 1)
                self.assertNotIn("forty passengers", copytext.evaluation_text(result, {}))
        both = json.loads(json.dumps(nested))
        both["argument"]["improvements"][1]["comment"] = "解释"
        mapped = review.normalize_evaluation(both, SUBS["t2-strong"])["argument"]
        self.assertEqual(
            mapped["improvements"][0]["suggestion"],
            nested["argument"]["improvements"][1]["suggestion"],
        )


class PromptNineTest(unittest.TestCase):
    def system(self, sample_id):
        sub = SUBS[sample_id]
        messages, _ = prompts.build_evaluate(sub, essay_lib.split_sentences(sub["essay_text"]))
        return messages[0]["content"]

    def test_rules(self):
        self.assertGreaterEqual(int(prompts.PROMPT_VERSION.rsplit(".", 1)[1]), 9)
        task2, task1 = self.system("t2-strong"), self.system("t1-no-image")
        for text in (
            "hypothetical example described in words only",
            "not 'a bus carrying forty passengers'",
            "the key is 'suggestion', not 'comment'",
        ):
            self.assertIn(text, task2)
        for system in (task1, task2):
            for text in (
                "put back instead of the quote it must leave a correct sentence",
                "clauses joined by and/but may have different subjects",
                "is a precision point",
                "overall_comment and priorities summarise your own findings",
            ):
                with self.subTest(text=text):
                    self.assertIn(text, system)
        self.assertIn("that decide the claim", task1)
        self.assertIn("at most 4, not every figure", task1)


if __name__ == "__main__":
    unittest.main()
