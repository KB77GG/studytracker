import json
import unittest
from urllib.parse import parse_qs, urlsplit

from flask import Flask
from flask_login import LoginManager

from api.question_type_practice import question_type_practice_bp
from models import (
    PlanItem,
    QuestionTypePracticeAttempt,
    StudentProfile,
    Task,
    User,
    db,
)
from services.question_type_practice import TASK_TYPE, snapshot_from_task


class QuestionTypePracticeRouteTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__, template_folder="../templates", static_folder="../static")
        self.app.config.update(
            TESTING=True,
            SECRET_KEY="question-type-route-test",
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
        )
        db.init_app(self.app)
        login = LoginManager(self.app)

        @login.user_loader
        def load_user(user_id):
            return db.session.get(User, int(user_id))

        @self.app.get("/practice")
        def practice_library():
            return "practice"

        @self.app.get("/")
        def index():
            return "index"

        @self.app.get("/login", endpoint="login")
        def login_page():
            return "login"

        @self.app.get("/logout")
        def logout():
            return "logout"

        @self.app.get("/student/today")
        def student_today():
            return "today"

        self.app.register_blueprint(question_type_practice_bp)
        with self.app.app_context():
            db.create_all()
            staff = User(username="assistant", password_hash="test", role=User.ROLE_ASSISTANT)
            student_user = User(username="student", password_hash="test", role=User.ROLE_STUDENT)
            db.session.add_all([staff, student_user])
            db.session.flush()
            profile = StudentProfile(full_name="测试学生", user_id=student_user.id)
            db.session.add(profile)
            db.session.commit()
            self.staff_id = staff.id
        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _login_staff(self):
        with self.client.session_transaction() as flask_session:
            flask_session["_user_id"] = str(self.staff_id)
            flask_session["_fresh"] = True

    def _create_reading_task(self):
        self._login_staff()
        selection = {
            "student_names": ["测试学生"],
            "subject": "reading",
            "standard_type": "judgment",
            "scope": "all",
            "count": 1,
            "pace": "training",
            "planned_minutes": 12,
            "due_date": "2026-08-29",
        }
        preview = self.client.post("/api/question-type-practice/preview", json=selection)
        self.assertEqual(preview.status_code, 200, preview.get_data(as_text=True))
        selection["group_ids"] = [row["question_group_id"] for row in preview.get_json()["groups"]]
        response = self.client.post("/api/question-type-practice/assign", json=selection)
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        return response.get_json()["tasks"][0]

    def test_batch_assignment_uses_existing_task_and_plan_item_with_frozen_snapshot(self):
        row = self._create_reading_task()
        with self.app.app_context():
            task = db.session.get(Task, row["id"])
            snapshot = snapshot_from_task(task)
            self.assertEqual(task.grading_mode, TASK_TYPE)
            self.assertIsNotNone(task.plan_item_id)
            self.assertEqual(task.plan_item.resource_type, PlanItem.RESOURCE_QUESTION_TYPE_PRACTICE)
            self.assertEqual(task.plan_item.resource_id, snapshot["snapshot_hash"])
            self.assertEqual(
                snapshot["group_ids"], json.loads(task.plan_item.resource_metadata)["group_ids"]
            )

    def test_verified_public_student_can_see_specialty_builder(self):
        with self.client.session_transaction() as flask_session:
            flask_session["practice_student_name"] = "测试学生"
        response = self.client.get("/practice/question-types")
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        body = response.get_data(as_text=True)
        self.assertIn("按题型练完整题组", body)
        self.assertIn("开始练习（已选", body)
        self.assertIn("当前学生：测试学生", body)

        inventory = self.client.get("/api/question-type-practice/inventory?subject=reading")
        self.assertEqual(inventory.status_code, 200)
        types = inventory.get_json()["types"]
        self.assertEqual(
            [row["label"] for row in types],
            ["全部", "填空题", "单选题", "多选题", "匹配题", "判断题"],
        )
        self.assertTrue(all(row["unit_count"] > 0 for row in types))

        preview = self.client.post(
            "/api/question-type-practice/preview",
            json={
                "subject": "listening",
                "standard_type": "completion",
                "scope": "ielts10_test1",
                "unit_count": 1,
                "pace": "training",
            },
        )
        self.assertEqual(preview.status_code, 200, preview.get_data(as_text=True))
        groups = preview.get_json()["groups"]
        self.assertTrue(groups)
        self.assertEqual(
            len({(row["test_id"], row["unit_number"]) for row in groups}),
            1,
        )

        catalog = self.client.post(
            "/api/question-type-practice/catalog",
            json={
                "subject": "reading",
                "standard_type": "all",
                "scope": "cambridge:all",
            },
        )
        self.assertEqual(catalog.status_code, 200, catalog.get_data(as_text=True))
        payload = catalog.get_json()
        self.assertGreater(payload["summary"]["volume_count"], 10)
        self.assertGreater(payload["summary"]["unit_count"], 20)
        self.assertTrue(all(row["group_ids"] for row in payload["units"]))
        self.assertEqual(payload["units"][0]["volume"], 21)

    def test_token_draft_submit_result_and_wrong_group_repush(self):
        row = self._create_reading_task()
        task_id = row["id"]
        token = row["url"].split("token=", 1)[1]
        draft_url = f"/api/question-type-practice/task/{task_id}/draft?token={token}"
        submit_url = (
            f"/api/question-type-practice/task/{task_id}/submit?token={token}"
            "&practice_return=%2Fstudent%2Ftoday"
            "&practice_exit=%2Fstudent%2Ftoday"
            "&practice_source=student_today"
            "&practice_identity=student_account"
        )
        self.assertEqual(
            self.client.put(draft_url, json={"answers": {"9000000001": "WRONG"}}).status_code, 200
        )
        loaded = self.client.get(draft_url).get_json()
        self.assertEqual(loaded["answers"], {"9000000001": "WRONG"})
        for forbidden in ("result", "results", "answer", "correct", "score"):
            self.assertNotIn(forbidden, loaded)

        submitted = self.client.post(
            submit_url,
            json={"answers": {"9000000001": "WRONG"}, "duration_seconds": 42},
        )
        self.assertEqual(submitted.status_code, 200, submitted.get_data(as_text=True))
        submitted_payload = submitted.get_json()
        self.assertTrue(submitted_payload["synced"])
        next_query = parse_qs(urlsplit(submitted_payload["next_url"]).query)
        self.assertEqual(next_query["practice_return"], ["/student/today"])
        self.assertEqual(next_query["practice_source"], ["student_today"])
        with self.app.app_context():
            task = db.session.get(Task, task_id)
            attempt = QuestionTypePracticeAttempt.query.filter_by(task_id=task_id).one()
            self.assertEqual(task.status, "done")
            self.assertTrue(task.student_submitted)
            self.assertEqual(attempt.duration_seconds, 42)
            self.assertTrue(json.loads(attempt.wrong_group_ids_json))
            self.assertEqual(task.plan_item.student_status, PlanItem.STUDENT_SUBMITTED)

        self._login_staff()
        repush = self.client.post(
            f"/api/question-type-practice/task/{task_id}/repush",
            json={"mode": "wrong", "due_date": "2026-08-30", "planned_minutes": 10},
        )
        self.assertEqual(repush.status_code, 200, repush.get_data(as_text=True))
        self.assertEqual(len(repush.get_json()["tasks"]), 1)

    def test_wrong_token_cannot_read_or_submit(self):
        row = self._create_reading_task()
        task_id = row["id"]
        self.assertEqual(
            self.client.get(
                f"/api/question-type-practice/task/{task_id}/draft?token=wrong"
            ).status_code,
            404,
        )
        self.assertEqual(
            self.client.post(
                f"/api/question-type-practice/task/{task_id}/submit?token=wrong",
                json={"answers": {}},
            ).status_code,
            404,
        )


if __name__ == "__main__":
    unittest.main()
