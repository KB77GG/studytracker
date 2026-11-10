"""realcheck additions for the model comparison on held-out essays (plan:
docs/design/ielts-writing-ai-model-comparison-plan-20261110): several human raters per
essay, ordering groups, one chart reading shared by repeats and by later runs, run-to-run
spread, and a blind review sheet. Synthetic data only - the held-out essays themselves
never go into the repository."""

import json
import shutil
import tempfile
import unittest
from pathlib import Path

from tools.ielts_writing_ai import realcheck, realcheck_compare, samples
from tools.ielts_writing_ai.llm import FakeClient

from .helpers import PNG_BYTES, settings_for

T2 = next(s for s in samples.SAMPLES if s["id"] == "t2-mid")
T1 = next(s for s in samples.SAMPLES if s["task_type"] == "task1")


def sample(sample_id, overall, bands=(None,) * 4, **extra):
    criteria = [{"key": k, "band": b} for k, b in zip(realcheck.CRITERION_KEYS, bands, strict=True)]
    result = {"overall_band": overall, "criteria": criteria} if overall is not None else None
    status = "ready" if result else "failed"
    return {
        "id": sample_id,
        "generations": {"evaluate": {"status": status, "result": result}},
        **extra,
    }


class LoadingTest(unittest.TestCase):
    def load(self, **fields):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "s.jsonl"
            item = {"id": "x", "task_type": "task2", "prompt": T2["prompt"], "essay": T2["essay"]}
            path.write_text(json.dumps({**item, **fields}), encoding="utf-8")
            return realcheck.load_samples(str(path))[0]

    def test_several_raters_give_the_mean_as_teacher(self):
        raters = [
            {"rater": "A", "overall": 7.5, "task": 8, "coherence": 7},
            {"rater": "B", "overall": 7, "task": 7, "coherence": 7, "lexical": 7},
        ]
        item = self.load(teachers=raters, group="g", nominal_band=7.5)
        self.assertEqual(
            item["teacher"], {"overall": 7.25, "task": 7.5, "coherence": 7.0, "lexical": 7.0}
        )
        explicit = self.load(teachers=raters, teacher={"overall": 7})
        self.assertEqual(explicit["teacher"], {"overall": 7})

    def test_invalid_fields_are_rejected(self):
        for fields in (
            {"teachers": {"overall": 7}},
            {"teachers": [{"overall": 11}]},
            {"teachers": [{"task": "7"}]},
            {"nominal_band": "9"},
            {"group": 3},
            {"image_description": ""},
        ):
            with self.subTest(fields=fields), self.assertRaises(realcheck.RealCheckError):
                self.load(**fields)

    def test_repeats(self):
        items = [{"id": "a"}, {"id": "b"}]
        self.assertIs(realcheck.expand_repeats(items, 1), items)
        expanded = realcheck.expand_repeats(items, 3)
        self.assertEqual([i["id"] for i in expanded], ["a", "a#r2", "a#r3", "b", "b#r2", "b#r3"])
        self.assertEqual({i["repeat_of"] for i in expanded}, {"a", "b"})
        for bad in (0, -1, 1.5, "2"):
            with self.assertRaises(realcheck.RealCheckError):
                realcheck.expand_repeats(items, bad)


class MetricsTest(unittest.TestCase):
    def test_rater_agreement_uses_the_raters_own_gap_as_the_yardstick(self):
        raters = [{"overall": 7.5, "task": 8}, {"overall": 7, "task": 7}]
        data = {
            "samples": [
                sample("in", 7.5, (8, 7, 7, 7), teachers=raters),  # inside the range
                sample("edge", 8.0, (6.5, 7, 7, 7), teachers=raters),  # overall: max + 0.5
                sample("out", 6.0, (5.5, 6, 6, 6), teachers=raters),  # below min - 0.5
                sample("failed", None, teachers=raters),
                sample("one-rater", 7.0, (7, 7, 7, 7), teachers=[{"overall": 7}]),
            ]
        }
        out = realcheck._rater_agreement(data)
        self.assertEqual(sorted(out), ["overall", "task"])
        overall = out["overall"]
        self.assertEqual((overall["essays"], overall["scored"]), (4, 3))
        self.assertEqual(overall["rater_gap"], 0.5)
        self.assertEqual(overall["ai_gap"], round((0.25 + 0.75 + 1.25) / 3, 3))
        self.assertEqual(overall["ai_bias"], round((0.25 + 0.75 - 1.25) / 3, 3))
        self.assertEqual(overall["within_range"], round(2 / 3, 3))
        self.assertEqual(out["task"]["rater_gap"], 1.0)
        self.assertIsNone(realcheck._rater_agreement({"samples": [sample("x", 7.0)]}))

    def test_ordering_counts_inversions_and_spread(self):
        def group(name, pairs):
            return [
                sample(f"{name}-{n}", ai, group=name, nominal_band=nominal)
                for n, (nominal, ai) in enumerate(pairs)
            ]

        data = {
            "samples": group("good", [(9, 8.5), (8.5, 8.0), (8, 8.0), (7.5, 7.0), (7, 6.5)])
            + group("bad", [(9, 7.0), (8, 7.5), (7, 7.5)])
            + group("gap", [(9, 8.0), (7, None)])
        }
        out = realcheck._ordering(data)
        self.assertEqual(
            (out["good"]["pairs"], out["good"]["inversions"], out["good"]["ties"]), (10, 0, 1)
        )
        self.assertEqual(out["good"]["spread"], 2.0)
        self.assertEqual((out["bad"]["inversions"], out["bad"]["ties"]), (2, 1))
        self.assertEqual(out["bad"]["spread"], -0.5)
        self.assertEqual((out["gap"]["missing"], out["gap"]["pairs"]), (1, 0))
        self.assertIsNone(realcheck._ordering({"samples": [sample("x", 7.0)]}))

    def test_repeat_spread(self):
        data = {
            "samples": [
                sample("a", 7.0, (7, 7, 7, 7), repeat_of="a"),
                sample("a#r2", 6.0, (6, 7, 6, 6.5), repeat_of="a"),
                sample("b", 6.5, (6.5,) * 4, repeat_of="b"),
                sample("b#r2", None, repeat_of="b"),
                sample("single", 7.0, repeat_of="single"),
            ]
        }
        out = realcheck._repeat_spread(data)
        rows = {r["id"]: r for r in out["samples"]}
        self.assertEqual(sorted(rows), ["a", "b"])
        self.assertEqual(
            rows["a"]["spread"],
            {"overall": 1.0, "task": 1.0, "coherence": 0.0, "lexical": 1.0, "grammar": 0.5},
        )
        self.assertEqual((rows["b"]["runs"], rows["b"]["ready"], rows["b"]["spread"]), (2, 1, {}))
        self.assertEqual(
            (out["overall_spread_mean"], out["overall_spread_max"], out["any_failed"]),
            (1.0, 1.0, 1),
        )


class RunTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="iwa-holdout-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def item(self, base, **extra):
        return {
            "id": extra.pop("id", base["id"]),
            "task_type": base["task_type"],
            "prompt": base["prompt"],
            "essay": base["essay"],
            **extra,
        }

    def test_report_sections_from_a_demo_run(self):
        raters = [{"overall": 6.5, "task": 7}, {"overall": 6, "task": 6}]
        items = realcheck.expand_repeats(
            [
                self.item(T2, id="hi", teachers=raters, group="g", nominal_band=9),
                self.item(T2, id="lo", group="g", nominal_band=7),
            ],
            2,
        )
        data = realcheck.run(
            settings_for(str(self.tmp / "d")), items, client=FakeClient(), kinds=("evaluate",)
        )
        report = realcheck.build_report(data)
        self.assertEqual(report["rater_agreement"]["overall"]["essays"], 2)  # both repeats
        self.assertEqual(report["ordering"]["g"]["pairs"], 4)
        self.assertEqual(report["repeat_spread"]["overall_spread_max"], 0.0)
        markdown = realcheck.render_markdown(report)
        for heading in ("## 与多位评委对比", "## 排序检查", "## 重复运行波动"):
            self.assertIn(heading, markdown)
        plain = realcheck.build_report(
            realcheck.run(
                settings_for(str(self.tmp / "p")),
                [self.item(T2)],
                client=FakeClient(),
                kinds=("evaluate",),
            )
        )
        self.assertIsNone(plain["rater_agreement"])
        self.assertNotIn("## 排序检查", realcheck.render_markdown(plain))

    def test_one_chart_reading_is_shared_by_repeats_and_later_runs(self):
        image = self.tmp / "chart.png"
        image.write_bytes(PNG_BYTES)
        items = realcheck.expand_repeats([self.item(T1, id="t1", image=str(image))], 2)
        vision = FakeClient(model="vision-double")
        data = realcheck.run(
            settings_for(str(self.tmp / "a")),
            items,
            client=FakeClient(),
            vision_client=vision,
            kinds=("evaluate",),
        )
        self.assertEqual(vision.calls, ["describe_image"])  # once, not once per repeat
        self.assertEqual([s["image_status"] for s in data["samples"]], ["ready", "ready"])
        self.assertEqual([s["image_reused"] for s in data["samples"]], [False, True])
        reading = data["image_descriptions"]["t1"]
        self.assertEqual({s["submission"]["image_description"] for s in data["samples"]}, {reading})
        out = self.tmp / "report-a"
        realcheck.write_report(data, realcheck.build_report(data), out)
        saved = out / "image_descriptions.json"
        self.assertEqual(json.loads(saved.read_text(encoding="utf-8")), {"t1": reading})

        later = realcheck.expand_repeats([self.item(T1, id="t1", image=str(image))], 2)
        self.assertEqual(realcheck.apply_image_descriptions(later, saved), 2)
        second = realcheck.run(  # no vision client at all: the saved reading is used
            settings_for(str(self.tmp / "b")), later, client=FakeClient(), kinds=("evaluate",)
        )
        for s in second["samples"]:
            self.assertEqual((s["image_status"], s["image_reused"]), ("ready", True))
            self.assertEqual(s["submission"]["image_description"], reading)
            scores = realcheck._scores(s)
            self.assertIsNotNone(scores["task"])  # Task Achievement is assessed
        self.assertFalse(any(c["kind"] == "describe_image" for c in second["calls"]))
        # The two runs judged the same reading, so they can be compared.
        realcheck.write_report(second, realcheck.build_report(second), self.tmp / "report-b")
        cmp = realcheck_compare.compare(out, self.tmp / "report-b")
        self.assertEqual(len(cmp["samples"]), 2)

    def test_reading_file_errors(self):
        items = [self.item(T1, id="t1")]
        with self.assertRaises(realcheck.RealCheckError):
            realcheck.apply_image_descriptions(items, self.tmp / "missing.json")
        bad = self.tmp / "bad.json"
        bad.write_text("[1]", encoding="utf-8")
        with self.assertRaises(realcheck.RealCheckError):
            realcheck.apply_image_descriptions(items, bad)
        other = self.tmp / "other.json"
        other.write_text(json.dumps({"someone-else": "reading"}), encoding="utf-8")
        self.assertEqual(realcheck.apply_image_descriptions(items, other), 0)
        self.assertNotIn("image_description", items[0])


class BlindReviewTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="iwa-blind-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)

    def run_dir(self, name, model):
        settings = settings_for(str(self.tmp / f"data-{name}"), llm_model=model)
        items = realcheck.load_samples("builtin")[:3]
        data = realcheck.run(settings, items, client=FakeClient(model=model), kinds=("evaluate",))
        realcheck.write_report(data, realcheck.build_report(data), self.tmp / name)
        return self.tmp / name

    def test_sheet_hides_the_runs_and_the_key_is_separate(self):
        a, b = self.run_dir("a", "model-alpha"), self.run_dir("b", "model-beta")
        cmp = realcheck_compare.compare(a, b, allow_model_change=True)
        sheet, key = realcheck_compare.render_blind_review(cmp, seed=7)
        self.assertNotIn("model-alpha", sheet)
        self.assertNotIn("model-beta", sheet)
        self.assertNotRegex(sheet, r"\bA\b|\bB\b")
        self.assertEqual(sheet.count("### 甲"), 3)
        self.assertEqual(sheet.count("### 乙"), 3)
        self.assertIn("LR 问题", sheet)  # language issues with their suggestions
        self.assertIn("【演示】补充一个具体的解释或例子。", sheet)
        self.assertIn("④ 漏掉评委都指出的明确错误", sheet)
        for sides in key["samples"].values():
            self.assertEqual(sorted(sides.values()), ["a", "b"])
        self.assertEqual(realcheck_compare.render_blind_review(cmp, seed=7), (sheet, key))
        orders = {
            json.dumps(realcheck_compare.render_blind_review(cmp, seed=n)[1]["samples"])
            for n in range(8)
        }
        self.assertGreater(len(orders), 1)  # the order depends on the seed

        out = self.tmp / "cmp"
        realcheck_compare.write(cmp, out)
        self.assertFalse((out / "blind_review.md").exists())
        realcheck_compare.write(cmp, out, blind_seed=7)
        self.assertEqual((out / "blind_review.md").read_text(encoding="utf-8"), sheet)
        stored = json.loads((out / "blind_key.json").read_text(encoding="utf-8"))
        self.assertEqual(stored["samples"], key["samples"])
        self.assertEqual(stored["conditions"]["a"]["model"], "model-alpha")


if __name__ == "__main__":
    unittest.main()
