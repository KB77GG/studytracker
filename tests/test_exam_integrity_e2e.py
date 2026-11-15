"""Real existing exam routes must remain usable with absent or locked integrity."""

import hashlib
import unittest
from datetime import datetime

from flask import template_rendered

from models import ExamIntegrityState, MockExamSession, db
from services import exam_integrity
from tests.exam_integrity_e2e_support import ROOT, IntegritySandbox

BASELINE_SHA = {
    "exam/process.html": "d403c724ce8fd41d0b094aaae344865a00acc657e9465b7584c57bf52687e0d5",
    "listening/test_practice.html": "058e26cea2c535e8ab84d27a4974b689ff51257c1b42a90bf6a6bd13a26d0fdb",
    "reading/test_practice.html": "b943bf032d269a7595cc2d7b19c97b5b734854dfbebaae65d290c5036d6354e9",
    "exam/writing.html": "2da9eedc76cd1d4cfa024480ff888fbbe45ffe78d113bd4148c344b564edd91d",
}


class ExamIntegrityRealFlowTest(unittest.TestCase):
    def make_sandbox(self, tables=True):
        sandbox = IntegritySandbox(create_integrity=tables)
        self.addCleanup(sandbox.close)
        sandbox.login()
        return sandbox

    def assert_page(self, s, path, guard=False):
        response = s.client.get(path)
        self.assertEqual(response.status_code, 200, response.data[:500])
        self.assertEqual(b"exam_guard.js" in response.data, guard)
        return response

    def objective(self, s, section, locked=False, expired=False):
        self.assert_page(s, s.process_url + "/" + section, guard=locked)
        if section == "listening":
            response = s.client.post(s.api_url + "/start-listening", json={})
            self.assertTrue(response.get_json()["ok"])
        if locked:
            with s.app.app_context():
                row = (
                    db.session.query(ExamIntegrityState)
                    .filter_by(session_ref=str(s.session_id))
                    .one()
                )
                row.is_locked = True
                row.locked_at = datetime.utcnow()
                row.locked_section = section
                db.session.commit()
        response = s.client.put(s.api_url + "/draft/" + section, json={"answers": {"1": "TRUE"}})
        self.assertEqual(response.status_code, 200, response.data)
        self.assertTrue(response.get_json()["ok"])
        if expired:
            s.expire(section)
        response = s.client.post(
            s.api_url + "/submit-" + section,
            json={"answers": {"1": "FALSE" if expired else "TRUE"}},
        )
        self.assertEqual(response.status_code, 200, response.data)
        body = response.get_json()
        self.assertTrue(body["ok"])
        self.assertEqual(body["result"]["correct"], 1)
        self.assertEqual(body["auto_submitted"], expired)

    def writing(self, s, locked=False, expired=False):
        self.assert_page(s, s.process_url + "/writing", guard=locked)
        draft = {
            "essay_task1": "My original first essay.",
            "essay_task2": "My original second essay.",
        }
        response = s.client.post(s.api_url + "/save-writing-draft", json=draft)
        self.assertTrue(response.get_json()["ok"])
        if expired:
            s.expire("writing", seconds=-6)
        response = s.client.post(s.api_url + "/submit-writing", json=draft)
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(response.get_json()["auto_submitted"], expired)
        self.assert_page(s, s.process_url + "/result")
        self.assert_page(s, s.process_url + "/review")
        with s.app.app_context():
            row = db.session.get(MockExamSession, s.session_id)
            self.assertEqual(row.status, "submitted")
            self.assertEqual(row.writing_essay_task1, draft["essay_task1"])

    def test_missing_tables_full_exam_and_review_still_work(self):
        s = self.make_sandbox(tables=False)
        self.assert_page(s, s.process_url)
        self.objective(s, "listening")
        self.objective(s, "reading")
        self.writing(s)
        with s.app.app_context():
            from sqlalchemy import inspect

            self.assertFalse(
                any(
                    name.startswith("exam_integrity_")
                    for name in inspect(db.engine).get_table_names()
                )
            )

    def test_locked_state_drafts_manual_submit_and_review_work(self):
        self.locked_journey(expired=False)

    def test_locked_state_expired_submit_uses_saved_answers_and_returns_score(self):
        self.locked_journey(expired=True)

    def locked_journey(self, expired):
        s = self.make_sandbox()
        with s.app.app_context():
            exam_integrity.set_policy(s.exam_id, "enforce")
            state = exam_integrity.record_event(
                s.exam_id,
                s.session_id,
                {
                    "type": "hello",
                    "section": "process",
                    "page_id": "page-process",
                    "device_id": "synthetic-device",
                },
            )
            self.assertEqual(state["mode"], "enforce")
        self.assert_page(s, s.process_url, guard=True)
        self.objective(s, "listening", locked=True, expired=expired)
        self.objective(s, "reading", locked=True, expired=expired)
        self.writing(s, locked=True, expired=expired)

    def test_drop_tables_during_exam_then_save_and_submit(self):
        s = self.make_sandbox()
        with s.app.app_context():
            exam_integrity.set_policy(s.exam_id, "enforce")
        self.assert_page(s, s.process_url, guard=True)
        with s.app.app_context():
            for name in ("exam_integrity_event", "exam_integrity_state", "exam_integrity_policy"):
                db.metadata.tables[name].drop(db.engine)
        body = s.client.get(s.api_url + "/integrity/state").get_json()
        self.assertEqual(body["mode"], "off")
        self.objective(s, "listening")
        self.objective(s, "reading")
        self.writing(s)

    def test_default_off_four_templates_are_byte_identical_to_plan_baseline(self):
        s = self.make_sandbox()
        cases = [
            ("", "exam/process.html"),
            ("/listening", "listening/test_practice.html"),
            ("/reading", "reading/test_practice.html"),
            ("/writing", "exam/writing.html"),
        ]
        for suffix, template_name in cases:
            if suffix in {"/reading", "/writing"}:
                section = "listening" if suffix == "/reading" else "reading"
                with s.app.app_context():
                    row = db.session.get(MockExamSession, s.session_id)
                    setattr(row, section + "_submitted_at", datetime.utcnow())
                    row.current_section = section
                    db.session.commit()
            captured = []

            def capture(_sender, template, context, captured=captured, **_kwargs):
                captured.append(dict(context))

            with template_rendered.connected_to(capture, s.app):
                response = self.assert_page(s, s.process_url + suffix)
            include = '{% include "exam/_integrity_guard.html" %}'
            if suffix:
                include = "{% if exam_context %}" + include + "{% endif %}"
            source = (ROOT / "templates" / template_name).read_text().replace(include, "")
            # Original ecc06f23 source hashes keep this check usable in shallow CI clones.
            self.assertEqual(
                hashlib.sha256(source.encode()).hexdigest(), BASELINE_SHA[template_name]
            )
            with s.app.test_request_context(s.process_url + suffix):
                baseline = s.app.jinja_env.from_string(source).render(captured[-1])
            self.assertEqual(response.get_data(as_text=True), baseline, template_name)


if __name__ == "__main__":
    unittest.main()
