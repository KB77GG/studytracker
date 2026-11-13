"""A well-formed chart reading is not a checked one. The first real reading
(2026-11-13, docs/design/ielts-writing-ai-official-t1-pro-20261113-results) passed every
automatic gate but had two clearly wrong values. Now Task Achievement is scored only
from a reading a person confirmed (optionally correcting it): on the page the
generations wait for that check, in realcheck the frozen reading must carry a check
bound to the image. The misreading is reproduced here with a synthetic chart; the
official chart's values stay out of the repository and out of the prompts."""

import io
import json
import shutil
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

from tools.ielts_writing_ai import __main__ as cli
from tools.ielts_writing_ai import essay, imagecheck, prompts, realcheck, storage, visual
from tools.ielts_writing_ai.llm import FakeClient

from .helpers import CONFIRMED_IMAGE, PNG_BYTES, AppTestCase, settings_for
from .test_visual import StaticVision, reading

PROMPT = "The graph below shows the share of commuters using trains and buses at two times of day."
WRONG = reading(
    visual_type="line_graph",
    title="Share of commuters by mode",
    units="%",
    categories=["Trains", "Buses"],
    periods=["16:00", "22:00"],
    data_points=[
        {"label": "Trains 16:00", "value": "14%"},  # the image shows about 22%
        {"label": "Trains 22:00", "value": "45%"},  # the image shows about 40%
        {"label": "Buses 16:00", "value": "30%"},
        {"label": "Buses 22:00", "value": "10%"},
    ],
    main_features=["Trains peak in the evening", "Buses fall late at night"],
    summary="A line graph of the share of commuters by mode at two times.",
)
ESSAY_T1 = (
    "The graph compares how many commuters used trains and buses at two times of day.\n"
    "Overall, trains became more popular later in the day, while buses lost users.\n"
    "At 16:00, about a fifth of commuters took the train, compared with 30% for buses. "
    "By 22:00, the figure for trains had roughly doubled, whereas buses fell to only 10%.\n"
    "In short, the two modes moved in opposite directions over the evening, and trains "
    "ended the period well ahead of buses in terms of their share of commuters."
)


def corrected(text):
    return text.replace("Trains 16:00 = 14%", "Trains 16:00 = 22%").replace(
        "Trains 22:00 = 45%", "Trains 22:00 = 40%"
    )


class Recording(FakeClient):
    def __init__(self):
        super().__init__()
        self.sent = {}

    def complete(self, messages, **kwargs):
        kind = (kwargs.get("context") or {}).get("kind")
        self.sent.setdefault(kind, []).append(json.dumps(messages, ensure_ascii=False))
        return super().complete(messages, **kwargs)


class GateTest(unittest.TestCase):
    def sub(self, **extra):
        return {
            "task_type": "task1",
            "prompt_text": PROMPT,
            "essay_text": ESSAY_T1,
            "word_count": essay.count_words(ESSAY_T1),
            "target_band": 7.0,
            "image_status": "ready",
            "image_description": "Data: Trains 16:00 = 22%",
            **extra,
        }

    def test_only_a_confirmed_reading_reaches_the_model(self):
        for check, available in (
            (None, False),
            ('{"status": "skipped", "edited": false}', False),
            ("not json", False),
            (CONFIRMED_IMAGE, True),
        ):
            sub = self.sub(image_check=check)
            with self.subTest(check=check):
                self.assertEqual(prompts.visual_available(sub), available)
                messages, _ = prompts.build_evaluate(sub, essay.split_sentences(ESSAY_T1))
                self.assertEqual("visual_summary" in messages[1]["content"], available)
                if available:
                    self.assertIn("checked against the image by a person", messages[1]["content"])
                else:
                    self.assertIn("NOT available", messages[1]["content"])
        self.assertTrue(prompts.awaiting_image_check(self.sub()))
        self.assertFalse(prompts.awaiting_image_check(self.sub(image_check=CONFIRMED_IMAGE)))
        self.assertFalse(prompts.awaiting_image_check(self.sub(image_status="failed")))

    def test_the_check_form_lists_one_value_per_line(self):
        text = visual.assess(WRONG).description
        form = visual.check_text(text)
        self.assertIn("Data:\n- Trains 16:00 = 14%\n- Trains 22:00 = 45%", form)
        self.assertTrue(visual.same_reading(form, text))
        self.assertTrue(visual.same_reading(form + "\n\n", text))
        self.assertFalse(visual.same_reading(corrected(form), text))


class WebCheckTest(AppTestCase):
    def setUp(self):
        super().setUp()
        self.client_llm = Recording()
        self.app = self.make_app(vision_client=StaticVision(WRONG))
        self.storage = self.app.extensions["iwa"].storage
        _uid, code = self.add_user()
        self.client = self.login(code)

    def submit_t1(self):
        return self.submit(
            self.client,
            task_type="task1",
            prompt_text=PROMPT,
            essay_text=ESSAY_T1,
            image=(io.BytesIO(PNG_BYTES), "chart.png"),
        ).get_json()["public_id"]

    def view(self, public_id):
        return self.client.get(f"/api/submissions/{public_id}").get_json()["submission"]

    def test_a_wrong_reading_waits_and_the_corrected_one_is_used(self):
        public_id = self.submit_t1()
        sub = self.view(public_id)
        self.assertEqual(sub["image"]["status"], "ready")
        self.assertTrue(sub["image"]["awaiting_check"])
        self.assertIn("- Trains 16:00 = 14%", sub["image"]["check_text"])
        self.assertEqual(sub["image"]["unusable_reason"], "题图读数尚未核对")
        self.assertEqual({g["status"] for g in sub["generations"].values()}, {"queued"})
        self.assertEqual(self.client_llm.sent, {})  # nothing sent before the check

        response = self.check_image(
            self.client, public_id, description=corrected(sub["image"]["check_text"])
        )
        self.assertEqual(response.status_code, 202)
        self.assertEqual(response.get_json()["check"], {"status": "confirmed", "edited": True})
        sub = self.view(public_id)
        self.assertFalse(sub["image"]["awaiting_check"])
        self.assertEqual(sub["image"]["check"], {"status": "confirmed", "edited": True})
        self.assertIn("Trains 16:00 = 22%", sub["image"]["description"])
        evaluation = sub["generations"]["evaluate"]["result"]
        self.assertEqual(evaluation["criteria"][0]["state"], "scored")
        self.assertIsNotNone(evaluation["overall_band"])
        for kind in ("evaluate", "refine", "rewrite"):
            sent = self.client_llm.sent[kind][0]
            with self.subTest(kind=kind):
                self.assertIn("Trains 16:00 = 22%", sent)
                self.assertNotIn("14%", sent)
                self.assertNotIn("45%", sent)
        stored = prompts.image_check(self.storage.get_owned_submission(public_id, 1))
        self.assertIn("Trains 16:00 = 14%", stored["model_description"])  # kept for audit

    def test_an_unchanged_confirmation_keeps_the_model_text(self):
        public_id = self.submit_t1()
        before = self.view(public_id)["image"]["description"]
        self.assertEqual(self.check_image(self.client, public_id).status_code, 202)
        sub = self.view(public_id)
        self.assertEqual(sub["image"]["check"], {"status": "confirmed", "edited": False})
        self.assertEqual(sub["image"]["description"], before)
        self.assertNotIn("model_description", prompts.image_check(self.storage.get_submission(1)))

    def test_skipping_gives_language_feedback_only(self):
        public_id = self.submit_t1()
        self.assertEqual(self.check_image(self.client, public_id, "skip").status_code, 202)
        sub = self.view(public_id)
        self.assertEqual(sub["image"]["check"], {"status": "skipped", "edited": False})
        self.assertEqual(sub["image"]["unusable_reason"], "未核对题图读数")
        evaluation = sub["generations"]["evaluate"]["result"]
        self.assertEqual(evaluation["criteria"][0]["state"], "not_assessable")
        self.assertIsNone(evaluation["overall_band"])
        self.assertTrue(any("未核对题图读数" in w for w in evaluation["warnings"]))
        sent = self.client_llm.sent["evaluate"][0]
        self.assertNotIn("visual_summary", sent)
        self.assertNotIn("14%", sent)

    def test_bad_requests_change_nothing(self):
        public_id = self.submit_t1()
        url = f"/api/submissions/{public_id}/image-check"
        csrf = {"X-IWA-CSRF": self.client.csrf}
        for payload, status in (
            ({"action": "confirm", "description": "  "}, 422),
            ({"action": "confirm", "description": "x" * 2501}, 422),
            ({"action": "approve"}, 422),
            ({}, 422),
        ):
            with self.subTest(payload=str(payload)[:40]):
                self.assertEqual(
                    self.client.post(url, json=payload, headers=csrf).status_code, status
                )
        self.assertEqual(self.client.post(url, json={"action": "skip"}).status_code, 403)  # no CSRF
        _uid, other_code = self.add_user(name="B")
        other = self.login(other_code, client=self.app.test_client())
        self.assertEqual(self.check_image(other, public_id, "skip").status_code, 404)
        regen = self.client.post(f"/api/submissions/{public_id}/generations/evaluate", headers=csrf)
        self.assertEqual(regen.status_code, 409)  # still waiting: nothing to regenerate
        self.assertTrue(self.view(public_id)["image"]["awaiting_check"])
        self.assertEqual(self.client_llm.sent, {})
        # One decision only.
        self.assertEqual(self.check_image(self.client, public_id, "skip").status_code, 202)
        self.assertEqual(self.check_image(self.client, public_id).status_code, 409)
        task2 = self.submit(self.client).get_json()["public_id"]
        self.assertEqual(self.check_image(self.client, task2, "skip").status_code, 409)

    def test_the_wait_survives_a_restart(self):
        public_id = self.submit_t1()
        self.app = self.make_app(vision_client=StaticVision(WRONG))  # stop + start
        self.storage = self.app.extensions["iwa"].storage
        client = self.app.test_client()
        client.csrf = self.client.csrf
        with self.client.session_transaction() as old, client.session_transaction() as new:
            new.update(old)
        sub = client.get(f"/api/submissions/{public_id}").get_json()["submission"]
        self.assertTrue(sub["image"]["awaiting_check"])
        self.assertEqual({g["status"] for g in sub["generations"].values()}, {"queued"})
        self.assertEqual(self.check_image(client, public_id).status_code, 202)
        sub = client.get(f"/api/submissions/{public_id}").get_json()["submission"]
        self.assertEqual({g["status"] for g in sub["generations"].values()}, {"ready"})


class RealcheckCheckTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="iwa-imgcheck-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.image = self.tmp / "chart.png"
        self.image.write_bytes(PNG_BYTES)
        row = {
            "id": "t1",
            "task_type": "task1",
            "prompt": PROMPT,
            "essay": ESSAY_T1,
            "image": "chart.png",
        }
        self.samples = self.tmp / "s.jsonl"
        self.samples.write_text(json.dumps(row) + "\n", encoding="utf-8")

    def items(self):
        return realcheck.load_samples(str(self.samples))

    def read_images(self):
        data = realcheck.run(
            settings_for(str(self.tmp / "img")),
            self.items(),
            client=FakeClient(),
            vision_client=StaticVision(WRONG),
            kinds=(),
        )
        realcheck.write_report(data, realcheck.build_report(data), self.tmp / "images")
        return self.tmp / "images" / "image_descriptions.json", data

    def evaluate(self, readings, **apply):
        items = self.items()
        realcheck.apply_image_descriptions(items, readings, **apply)
        client = Recording()
        data = realcheck.run(
            settings_for(str(self.tmp / f"ev{len(list(self.tmp.iterdir()))}")),
            items,
            client=client,
            kinds=("evaluate",),
        )
        return data["samples"][0], client.sent["evaluate"][0]

    def confirmed_file(self, corrections=None):
        readings, data = self.read_images()
        text = data["image_outcomes"]["t1"]["description"]
        fixes = {"t1": corrected(visual.check_text(text))} if corrections else {}
        out = self.tmp / "checked.json"
        out.write_text(
            json.dumps(
                imagecheck.confirm(
                    json.loads(readings.read_text(encoding="utf-8")),
                    self.items(),
                    ["t1"],
                    by="老师",
                    corrections=fixes,
                )
            ),
            encoding="utf-8",
        )
        return out

    def test_the_sheet_lists_each_value_with_the_image(self):
        _readings, data = self.read_images()
        sheet = imagecheck.sheet(self.items(), data["image_outcomes"])
        self.assertIn("## t1", sheet)
        self.assertIn(imagecheck.image_sha256(self.image), sheet)
        self.assertIn("- Trains 16:00 = 14%", sheet)
        self.assertIn("ready（未核对）", sheet)

    def test_an_unchecked_reading_scores_no_ta_and_is_not_sent(self):
        readings, _ = self.read_images()
        sample, sent = self.evaluate(readings)
        self.assertIsNone(realcheck._scores(sample)["task"])
        self.assertNotIn("visual_summary", sent)
        with self.assertRaises(realcheck.RealCheckError) as caught:
            self.evaluate(readings, require_checked=True)
        self.assertIn("还没有人工核对", str(caught.exception))

    def test_the_corrected_reading_is_scored_and_bound_to_the_image(self):
        checked = self.confirmed_file(corrections=True)
        record = realcheck.load_image_outcomes(checked)["t1"]
        self.assertTrue(record["check"]["edited"])
        self.assertIn("Trains 16:00 = 14%", record["check"]["model_description"])
        sample, sent = self.evaluate(checked, require_checked=True)
        self.assertIsNotNone(realcheck._scores(sample)["task"])
        self.assertIn("Trains 16:00 = 22%", sent)
        self.assertNotIn("14%", sent)
        self.assertEqual(json.loads(sample["submission"]["image_check"])["by"], "老师")
        self.image.write_bytes(PNG_BYTES + b"\0")  # a different image file
        with self.assertRaises(realcheck.RealCheckError) as caught:
            self.evaluate(checked, require_checked=True)
        self.assertIn("题图与核对读数时的题图不同", str(caught.exception))

    def test_confirmation_refuses_what_it_cannot_bind(self):
        readings, _ = self.read_images()
        stored = json.loads(readings.read_text(encoding="utf-8"))
        items = self.items()
        failed = dict(
            stored, images={"t1": {"status": "failed", "description": None, "error": "x"}}
        )
        for args, kwargs in (
            ((stored, items, ["nope"]), {"by": "老师"}),
            ((stored, items, ["t1"]), {"by": " "}),
            ((stored, items, ["t1", "t1"]), {"by": "老师"}),
            ((stored, items, ["t1"]), {"by": "老师", "corrections": {"t2": "x"}}),
            ((stored, items, ["t1"]), {"by": "老师", "corrections": {"t1": " "}}),
            ((failed, items, ["t1"]), {"by": "老师"}),
            ((imagecheck.confirm(stored, items, ["t1"], by="老师"), items, ["t1"]), {"by": "老师"}),
        ):
            with self.subTest(kwargs=kwargs), self.assertRaises(imagecheck.ImageCheckError):
                imagecheck.confirm(*args, **kwargs)
        bad = imagecheck.confirm(stored, items, ["t1"], by="老师")
        bad["images"]["t1"]["check"]["image_sha256"] = "abc"
        path = self.tmp / "bad.json"
        path.write_text(json.dumps(bad), encoding="utf-8")
        with self.assertRaises(realcheck.RealCheckError):
            realcheck.load_image_outcomes(path)


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="iwa-imgcheck-cli-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        (self.tmp / "chart.png").write_bytes(PNG_BYTES)
        row = {"id": "t1", "task_type": "task1", "prompt": PROMPT, "essay": ESSAY_T1}
        (self.tmp / "s.jsonl").write_text(json.dumps(dict(row, image="chart.png")) + "\n")
        self.env = self.tmp / "demo.env"
        self.env.write_text(f"IWA_DATA_DIR={self.tmp / 'data'}\nIWA_VISION_PROVIDER=fake\n")

    def cli(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            code = cli.main(["--env-file", str(self.env), *argv])
        return code, out.getvalue(), err.getvalue()

    def test_read_check_confirm_and_evaluate(self):
        samples = str(self.tmp / "s.jsonl")
        code, out, _ = self.cli(
            "realcheck", "--samples", samples, "--images-only", "--with-vision",
            "--out", str(self.tmp / "img"),
        )  # fmt: skip
        self.assertEqual(code, 0)
        self.assertIn("读数核对表", out)
        self.assertIn("## t1", (self.tmp / "img" / "image_check.md").read_text(encoding="utf-8"))
        readings = str(self.tmp / "img" / "image_descriptions.json")
        code, _, err = self.cli(
            "realcheck", "--samples", samples, "--kinds", "evaluate",
            "--image-descriptions", readings, "--require-checked-images",
            "--out", str(self.tmp / "refused"),
        )  # fmt: skip
        self.assertEqual(code, 2)
        self.assertIn("还没有人工核对", err)
        checked = str(self.tmp / "checked.json")
        confirm = ("realcheck-check-images", "--samples", samples, "--descriptions", readings)
        code, out, _ = self.cli(*confirm, "--confirm", "t1", "--by", "老师", "--out", checked)
        self.assertEqual(code, 0)
        self.assertIn("已确认 1 个读数", out)
        code, _, err = self.cli(*confirm, "--confirm", "t1", "--by", "另一位", "--out", checked)
        self.assertEqual(code, 2)  # never overwrites a different confirmed file
        self.assertIn("不覆盖", err)
        code, out, _ = self.cli(
            "realcheck", "--samples", samples, "--kinds", "evaluate",
            "--image-descriptions", checked, "--require-checked-images",
            "--out", str(self.tmp / "ev"),
        )  # fmt: skip
        self.assertEqual(code, 0)
        self.assertIn("读数经人工核对的 1 个", out)
        run_data = json.loads((self.tmp / "ev" / "run_data.json").read_text(encoding="utf-8"))
        self.assertIsNotNone(realcheck._scores(run_data["samples"][0])["task"])


class MigrationTest(unittest.TestCase):
    def test_an_old_database_gets_both_new_columns(self):
        tmp = Path(tempfile.mkdtemp(prefix="iwa-migrate2-"))
        self.addCleanup(shutil.rmtree, tmp, ignore_errors=True)
        old_schema = storage.SCHEMA.replace("    image_check TEXT,\n", "").replace(
            "    copied_spans TEXT,\n", ""
        )
        db = tmp / "iwa.sqlite3"
        conn = sqlite3.connect(db)
        conn.executescript(old_schema)
        conn.close()
        store = storage.Storage(db)
        store.init_schema()
        with store.connect() as conn:
            columns = [row["name"] for row in conn.execute("PRAGMA table_info(submission)")]
        self.assertEqual(columns[-2:], ["copied_spans", "image_check"])


if __name__ == "__main__":
    unittest.main()
