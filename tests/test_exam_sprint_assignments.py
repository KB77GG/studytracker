"""Synthetic staff assignment -> token-bound practice -> completion regressions."""

import copy
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from jinja2 import FileSystemLoader

from config import Config

# The existing route harness imports app. Force its initial DB into memory too;
# every test then receives the harness's own empty SQLite database.
with patch.object(Config, "SQLALCHEMY_DATABASE_URI", "sqlite:///:memory:"):
    from tests import test_task_assignment_routes as routes

from models import ListeningTestSubmission, ReadingTestSubmission, Task, db
from services.exam_sprint import publish_snapshot
from services.exam_sprint_catalog import sprint_assignment_options
from services.exam_sprint_store import load_ninefen_document
from tests.test_exam_sprint_catalog import SprintCatalogFixture


class SprintAssignmentRouteTests(unittest.TestCase):
    def setUp(self):
        self.harness = routes.LegacyTaskAssignmentRouteTest()
        self.harness.setUp()
        self.addCleanup(self.harness.tearDown)
        env = patch.dict(os.environ, {}, clear=False)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("EXAM_SPRINT_STATE_DIR", None)
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.fixture = SprintCatalogFixture(temporary.name)
        self.app = self.harness.app
        self.app.root_path = str(self.fixture.root)
        self.app.jinja_loader = FileSystemLoader(Path(__file__).resolve().parents[1] / "templates")
        for subject, rule, function in (
            (
                "reading",
                "/api/reading/test/<test_id>/submit",
                routes.app_module.api_reading_test_submit,
            ),
            (
                "listening",
                "/api/listening/jijing/<part_id>/submit",
                routes.app_module.api_listening_jijing_submit,
            ),
        ):
            self.app.add_url_rule(
                rule, endpoint=f"sprint_{subject}_submit", view_func=function, methods=["POST"]
            )
        self.options = sprint_assignment_options(self.fixture.root)

    def test_staff_picker_renders_both_verified_subjects_without_answers(self):
        self.harness._login()
        response = self.harness.client.get("/tasks")
        self.assertEqual(response.status_code, 200)
        markup = response.get_data(as_text=True)
        self.assertIn('data-listening-filter="exam_sprint"', markup)
        self.assertIn('label="7天热榜 · 阅读"', markup)
        for subject in ("reading", "listening"):
            self.assertIn(f'value="{self.options[subject][0]["id"]}"', markup)
        self.assertNotIn('"answer": "drum"', markup)

    def create(self, subject, **extra):
        row = self.options[subject][0]
        values = (
            {"reading_test_id": row["id"], "reading_passage_number": "3"}
            if subject == "reading"
            else {"listening_exercise_id": row["id"], "listening_resource_type": "jijing"}
        )
        return self.harness._post(
            idempotency_key=f"sprint-{subject}", task_source=subject, detail="", **values, **extra
        )

    def test_teacher_assignments_bind_canonical_version_and_server_locked_passage(self):
        for subject in ("reading", "listening"):
            response = self.create(subject)
            self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        with self.app.app_context():
            reading, listening = Task.query.order_by(Task.id).all()
            self.assertEqual(reading.reading_test_id, self.options["reading"][0]["target_id"])
            self.assertEqual(reading.reading_passage_number, 1)
            self.assertEqual(
                listening.listening_exercise_id, self.options["listening"][0]["target_id"]
            )
            self.assertEqual(listening.listening_resource_type, "jijing")
            self.assertEqual(reading.category, "雅思-阅读-7天热榜")
            self.assertEqual(listening.category, "雅思-听力-7天热榜")
            self.assertTrue(reading.reading_access_token)
            self.assertTrue(listening.listening_access_token)

    def test_assignment_revalidates_current_media_before_any_task_write(self):
        item = self.fixture.item("listening")
        audio = next(
            asset for asset in item["mapping"]["assets"] if asset["filename"].endswith(".mp3")
        )
        (self.fixture.state / "assets" / audio["filename"]).unlink()
        response = self.create("listening")
        self.assertNotEqual(response.status_code, 200)
        with self.app.app_context():
            self.assertEqual(Task.query.count(), 0)

    def test_old_assigned_versions_complete_after_the_next_catalog_withdraws_them(self):
        for subject in ("reading", "listening"):
            response = self.create(subject)
            self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        newer = copy.deepcopy(self.fixture.snapshot)
        for groups in newer["subjects"].values():
            for group in groups:
                for row in group["items"]:
                    row["source_available"] = False
        publish_snapshot(self.fixture.state, newer)
        with self.app.app_context():
            tasks = Task.query.order_by(Task.id).all()
            bindings = [
                ("reading", tasks[0].id, tasks[0].reading_test_id, tasks[0].reading_access_token),
                (
                    "listening",
                    tasks[1].id,
                    tasks[1].listening_exercise_id,
                    tasks[1].listening_access_token,
                ),
            ]
        client = self.app.test_client()
        for subject, task_id, target, token in bindings:
            payload = load_ninefen_document(self.fixture.root, subject, target)
            groups = payload["passages"][0]["groups"] if subject == "reading" else payload["groups"]
            key = "questions" if subject == "reading" else "items"
            answers = {
                str(question["id"]): question["answer"]
                for group in groups
                for question in group[key]
            }
            route = (
                f"/api/reading/test/{target}/submit"
                if subject == "reading"
                else f"/api/listening/jijing/{target}/submit"
            )
            wrong = client.post(
                route, json={"task_id": task_id, "token": "wrong-token", "answers": answers}
            )
            self.assertEqual(wrong.status_code, 403)
            response = client.post(
                route, json={"task_id": task_id, "token": token, "answers": answers}
            )
            self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
            self.assertTrue(response.get_json()["synced"])
            self.assertEqual(response.get_json()["result"]["correct"], 4)
        with self.app.app_context():
            self.assertEqual(
                [task.status for task in Task.query.order_by(Task.id)], ["done", "done"]
            )
            self.assertEqual(ReadingTestSubmission.query.count(), 1)
            self.assertEqual(ListeningTestSubmission.query.count(), 1)


if __name__ == "__main__":
    unittest.main()
