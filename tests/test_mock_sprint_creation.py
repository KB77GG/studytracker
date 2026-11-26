"""Real staff creation endpoint with an isolated database and synthetic source papers."""

import os
import tempfile
import unittest
from unittest.mock import patch

from config import Config

with patch.object(Config, "SQLALCHEMY_DATABASE_URI", "sqlite:///:memory:"):
    from tests import test_task_assignment_routes as routes
from models import MockExam
from services.exam_sprint_papers import load_sprint_paper
from tests.test_exam_sprint_papers import fixture


class MockSprintCreationTest(unittest.TestCase):
    def setUp(self):
        self.harness = routes.LegacyTaskAssignmentRouteTest()
        self.harness.setUp()
        self.addCleanup(self.harness.tearDown)
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.state = temp.name
        p = patch.dict(os.environ, {"EXAM_SPRINT_STATE_DIR": self.state})
        p.start()
        self.addCleanup(p.stop)
        self.app = self.harness.app
        self.app.add_url_rule(
            "/admin/mock-exams/create",
            endpoint="admin_mock_exams_create",
            view_func=routes.app_module.admin_mock_exams_create,
            methods=["GET", "POST"],
        )
        self.app.add_url_rule(
            "/admin/mock-exams", endpoint="admin_mock_exams_index", view_func=lambda: "OK"
        )
        self.app.add_url_rule("/", endpoint="index", view_func=lambda: "OK")
        self.catalogs = {}
        self.payloads = {}
        for subject in ("listening", "reading"):
            catalog, payloads = fixture(subject)
            for group in catalog["groups"]:
                for item in group["items"]:
                    item.update(
                        rank=1,
                        question_count=(
                            10 if subject == "listening" else [13, 13, 14][group["part"] - 1]
                        ),
                    )
                    item["mapping"]["subject"] = subject
            self.catalogs[subject] = {**catalog, "stale": False}
            self.payloads[subject] = payloads
        mocks = [
            patch(
                "api.mock_exam_creation.load_sprint_catalog",
                side_effect=lambda root, s: self.catalogs[s],
            ),
            patch(
                "services.exam_sprint_papers._local_target",
                side_effect=lambda root, m: (
                    self.payloads[m["subject"]][m["target_id"]],
                    "/practice",
                ),
            ),
        ]
        for name in ("listening", "reading", "writing"):
            mocks.append(patch(f"app._mock_exam_{name}_options", return_value=[]))
        for p in mocks:
            p.start()
            self.addCleanup(p.stop)
        self.harness._login()

    def post(self, **extra):
        values = {
            "name": "Synthetic hotlist mock",
            "pincode": "HOT01",
            "listening_source": "sprint",
            "reading_source": "sprint",
            "listening_sprint_part": list(self.payloads["listening"]),
            "reading_sprint_part": list(self.payloads["reading"]),
        }
        values.update(extra)
        return self.harness.client.post("/admin/mock-exams/create", data=values)

    def test_creates_two_immutable_forty_question_papers_and_keeps_existing_loaders(self):
        response = self.post()
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            exam = MockExam.query.one()
            for subject in ("reading", "listening"):
                identifier = getattr(exam, f"{subject}_test_id")
                self.assertEqual(
                    load_sprint_paper(".", subject, identifier)[0]["question_count"], 40
                )
                loader = getattr(routes.app_module, f"_load_{subject}_test_payload")
                self.assertEqual(loader(identifier)[0]["id"], identifier)

    def test_public_practice_cannot_read_or_grade_composed_answers(self):
        self.assertEqual(self.post().status_code, 302)
        from flask import jsonify

        def public_loader(subject, test_id):
            loader = getattr(routes.app_module, f"_load_{subject}_test_payload")
            value = loader(test_id)[0]
            return (jsonify(value), 200) if value else ("not found", 404)

        # Register before the client's first request by using a separate application
        # context for each ordinary route; the loader must reject every method.
        with self.app.app_context():
            exam = MockExam.query.one()
            ids = {
                subject: getattr(exam, f"{subject}_test_id") for subject in ("reading", "listening")
            }
        for subject, identifier in ids.items():
            for method in ("GET", "POST"):
                with self.app.test_request_context(
                    f"/api/{subject}/test/{identifier}", method=method
                ):
                    response, status = public_loader(subject, identifier)
                    self.assertEqual(status, 404)

    def test_bad_selection_does_not_save_exam_or_paper(self):
        response = self.post(reading_sprint_part=["entry-2", "entry-1", "entry-3"])
        self.assertEqual(response.status_code, 200)
        with self.app.app_context():
            self.assertEqual(MockExam.query.count(), 0)
        from pathlib import Path

        self.assertFalse(Path(self.state, "papers").exists())

    def test_unknown_mode_and_writing_fail_closed(self):
        with patch("app._load_writing_test_payload", return_value=(None, None, "")):
            self.assertEqual(self.post(writing_test_id="missing").status_code, 200)
        self.assertEqual(self.post(listening_source="unknown").status_code, 200)
        with self.app.app_context():
            self.assertEqual(MockExam.query.count(), 0)

    def test_old_full_paper_creation_still_works(self):
        with (
            patch(
                "app._load_listening_test_payload", return_value=({"id": "old-l"}, None, "old-l")
            ),
            patch("app._load_reading_test_payload", return_value=({"id": "old-r"}, None, "old-r")),
        ):
            response = self.post(
                listening_source="existing",
                reading_source="existing",
                listening_test_id="old-l",
                reading_test_id="old-r",
            )
        self.assertEqual(response.status_code, 302)
        with self.app.app_context():
            self.assertEqual(MockExam.query.one().listening_test_id, "old-l")

    def test_student_cannot_create_and_get_does_not_write(self):
        self.assertEqual(self.harness.client.get("/admin/mock-exams/create").status_code, 200)
        self.harness._login_as(self.harness.student_user_id)
        self.assertEqual(self.post().status_code, 302)
        with self.app.app_context():
            self.assertEqual(MockExam.query.count(), 0)

    def test_duplicate_pincode_is_validation_error(self):
        self.assertEqual(self.post().status_code, 302)
        self.assertEqual(self.post().status_code, 200)
        with self.app.app_context():
            self.assertEqual(MockExam.query.count(), 1)


if __name__ == "__main__":
    unittest.main()
