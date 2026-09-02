import json
import os
import tempfile
import unittest
from datetime import datetime
from urllib.parse import parse_qs, urlsplit

from flask import Flask
from flask_login import LoginManager

from api import question_type_practice as question_type_practice_module
from api.question_type_practice import question_type_practice_bp
from api.task_assignments import task_assignments_bp
from models import (
    AuditLogEntry,
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
        self._audio_tmp = tempfile.TemporaryDirectory()
        self._audio_env_before = os.environ.get("STUDYTRACKER_AUDIO_ROOT")
        os.environ["STUDYTRACKER_AUDIO_ROOT"] = self._audio_tmp.name
        for section in range(1, 5):
            open(os.path.join(self._audio_tmp.name, f"ielts10_test1_s{section}.mp3"), "wb").close()
        question_type_practice_module._library_rows.cache_clear()
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

        @self.app.get("/reading/tests", endpoint="reading_test_index")
        def reading_tests():
            return "reading tests"

        @self.app.get("/reading/jijing", endpoint="reading_jijing_index")
        def reading_jijing():
            return "reading jijing"

        @self.app.get("/listening/tests", endpoint="listening_test_index")
        def listening_tests():
            return "listening tests"

        @self.app.get("/listening", endpoint="listening_index")
        def listening_home():
            return "listening"

        @self.app.get("/listening/jijing", endpoint="listening_jijing_index")
        def listening_jijing():
            return "listening jijing"

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
        self.app.register_blueprint(task_assignments_bp)
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
        question_type_practice_module._library_rows.cache_clear()
        if self._audio_env_before is None:
            os.environ.pop("STUDYTRACKER_AUDIO_ROOT", None)
        else:
            os.environ["STUDYTRACKER_AUDIO_ROOT"] = self._audio_env_before
        self._audio_tmp.cleanup()

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

    def _create_listening_task(self):
        self._login_staff()
        selection = {
            "student_names": ["测试学生"],
            "subject": "listening",
            "standard_type": "completion",
            "scope": "ielts10_test1",
            "count": 1,
            "pace": "training",
            "planned_minutes": 12,
            "due_date": "2026-08-29",
        }
        preview = self.client.post("/api/question-type-practice/preview", json=selection)
        self.assertEqual(preview.status_code, 200, preview.get_data(as_text=True))
        selection["group_ids"] = [preview.get_json()["groups"][0]["question_group_id"]]
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
        with self.app.app_context():
            token = db.session.get(Task, task_id).reading_access_token
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
        review = self.client.get(submitted_payload["next_url"])
        self.assertEqual(review.status_code, 200, review.get_data(as_text=True))
        review_body = review.get_data(as_text=True)
        self.assertIn('data-hl-root="reading-passage"', review_body)
        self.assertIn('data-hl-root="reading-questions"', review_body)
        self.assertIn('js/selection-highlight.js', review_body)
        self.assertIn('"initial_review"', review_body)
        self.assertIn('"highlight_path": "/practice/question-types/task/', review_body)
        self.assertIn('"draft_url": null', review_body)
        self.assertIn('"read_only": true', review_body)
        self.assertNotIn('class="qtr"', review_body)
        with self.app.app_context():
            task = db.session.get(Task, task_id)
            attempt = QuestionTypePracticeAttempt.query.filter_by(task_id=task_id).one()
            self.assertEqual(task.status, "done")
            self.assertTrue(task.student_submitted)
            self.assertEqual(attempt.duration_seconds, 42)
            self.assertTrue(json.loads(attempt.wrong_group_ids_json))
            self.assertEqual(task.plan_item.student_status, PlanItem.STUDENT_SUBMITTED)
            token = task.reading_access_token

        self._login_staff()
        repush = self.client.post(
            f"/api/question-type-practice/task/{task_id}/repush",
            json={"mode": "wrong", "due_date": "2026-08-30", "planned_minutes": 10},
        )
        self.assertEqual(repush.status_code, 200, repush.get_data(as_text=True))
        self.assertEqual(len(repush.get_json()["tasks"]), 1)
        self.assertNotIn(token, repush.get_data(as_text=True))

    def test_listening_result_restores_full_paper_highlight_workspace(self):
        row = self._create_listening_task()
        task_id = row["id"]
        with self.app.app_context():
            token = db.session.get(Task, task_id).listening_access_token
        submitted = self.client.post(
            f"/api/question-type-practice/task/{task_id}/submit?token={token}",
            json={"answers": {}, "duration_seconds": 5},
        )
        self.assertEqual(submitted.status_code, 200, submitted.get_data(as_text=True))
        review = self.client.get(submitted.get_json()["next_url"])
        self.assertEqual(review.status_code, 200, review.get_data(as_text=True))
        body = review.get_data(as_text=True)
        self.assertIn('data-hl-root="listening-transcript"', body)
        self.assertIn('data-hl-root="listening-questions"', body)
        self.assertIn('js/selection-highlight.js', body)
        self.assertIn('"initial_review"', body)
        self.assertIn('"highlight_path": "/practice/question-types/task/', body)
        self.assertIn('"draft_url": null', body)
        self.assertIn('"read_only": true', body)

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
        self.assertEqual(
            self.client.get(
                f"/practice/question-types/task/{task_id}/result?token=wrong"
            ).status_code,
            404,
        )

    def test_duplicate_publish_returns_409_with_per_student_group_details(self):
        first = self._create_reading_task()
        with self.app.app_context():
            task = db.session.get(Task, first["id"])
            token = task.reading_access_token
            group_id = snapshot_from_task(task)["group_ids"][0]
        duplicate = {
            "student_names": ["测试学生"],
            "subject": "reading",
            "standard_type": "judgment",
            "group_ids": [group_id],
            "pace": "training",
            "due_date": "2026-08-29",
            "idempotency_key": "second-publish",
        }
        response = self.client.post("/api/question-type-practice/assign", json=duplicate)
        self.assertEqual(response.status_code, 409, response.get_data(as_text=True))
        payload = response.get_json()
        self.assertEqual(payload["error"], "duplicate_assignment_conflict")
        self.assertEqual(payload["students"][0]["matches"][0]["task_id"], first["id"])
        self.assertEqual(payload["students"][0]["matches"][0]["overlap_type"], "exact")
        self.assertNotIn(token, response.get_data(as_text=True))

    def test_duplicate_preview_and_409_return_complete_student_group_matrix(self):
        with self.app.app_context():
            student_user = User(username="student-two", password_hash="test", role=User.ROLE_STUDENT)
            db.session.add(student_user)
            db.session.flush()
            db.session.add(StudentProfile(full_name="测试学生乙", user_id=student_user.id))
            db.session.commit()

        self._login_staff()
        selection = {
            "student_names": ["测试学生", "测试学生乙"],
            "subject": "reading",
            "standard_type": "judgment",
            "scope": "all",
            "count": 2,
            "pace": "training",
            "planned_minutes": 12,
            "due_date": "2026-08-29",
        }
        preview = self.client.post("/api/question-type-practice/preview", json=selection)
        self.assertEqual(preview.status_code, 200, preview.get_data(as_text=True))
        group_ids = [row["question_group_id"] for row in preview.get_json()["groups"][:2]]
        self.assertEqual(len(group_ids), 2)

        first = self.client.post(
            "/api/question-type-practice/assign",
            json={**selection, "student_names": ["测试学生"], "group_ids": [group_ids[0]], "idempotency_key": "matrix-history"},
        )
        self.assertEqual(first.status_code, 200, first.get_data(as_text=True))
        with self.app.app_context():
            token = db.session.get(Task, first.get_json()["tasks"][0]["id"]).reading_access_token

        history = self.client.post(
            "/api/task-assignments/duplicates",
            json={
                "student_names": ["测试学生", "测试学生乙"],
                "source": "question_type",
                "subject": "reading",
                "standard_type": "judgment",
                "group_ids": group_ids,
            },
        )
        self.assertEqual(history.status_code, 200, history.get_data(as_text=True))
        history_payload = history.get_json()
        self.assertEqual(len(history_payload["matrix_rows"]), 4)
        self.assertEqual(
            {(row["student_name"], row["unit_id"]) for row in history_payload["matrix_rows"]},
            {(student, group) for student in ("测试学生", "测试学生乙") for group in group_ids},
        )
        matrix = {(row["student_name"], row["unit_id"]): row for row in history_payload["matrix_rows"]}
        self.assertEqual(matrix[("测试学生", group_ids[0])]["match"]["task_id"], first.get_json()["tasks"][0]["id"])
        self.assertEqual(matrix[("测试学生", group_ids[1])]["status_label"], "未布置")
        self.assertEqual(matrix[("测试学生乙", group_ids[0])]["status_label"], "未布置")
        self.assertEqual(matrix[("测试学生乙", group_ids[1])]["status_label"], "未布置")
        self.assertNotIn(token, history.get_data(as_text=True))

        conflict = self.client.post(
            "/api/question-type-practice/assign",
            json={**selection, "group_ids": group_ids, "idempotency_key": "matrix-conflict"},
        )
        self.assertEqual(conflict.status_code, 409, conflict.get_data(as_text=True))
        conflict_payload = conflict.get_json()
        self.assertEqual(conflict_payload["error"], "duplicate_assignment_conflict")
        self.assertEqual(len(conflict_payload["matrix_rows"]), 4)
        conflict_matrix = {
            (row["student_name"], row["unit_id"]): row for row in conflict_payload["matrix_rows"]
        }
        self.assertEqual(conflict_matrix[("测试学生", group_ids[0])]["match"]["task_id"], first.get_json()["tasks"][0]["id"])
        self.assertEqual(conflict_matrix[("测试学生", group_ids[1])]["status_label"], "未布置")
        self.assertNotIn(token, conflict.get_data(as_text=True))

    def test_client_retraining_mode_cannot_bypass_unfinished_duplicate(self):
        first = self._create_reading_task()
        with self.app.app_context():
            group_id = snapshot_from_task(db.session.get(Task, first["id"]))["group_ids"][0]
        response = self.client.post(
            "/api/question-type-practice/assign",
            json={
                "student_names": ["测试学生"],
                "subject": "reading",
                "standard_type": "judgment",
                "group_ids": [group_id],
                "retraining_mode": "wrong",
                "idempotency_key": "malicious-bypass",
            },
        )
        self.assertEqual(response.status_code, 409, response.get_data(as_text=True))
        self.assertEqual(response.get_json()["error"], "duplicate_assignment_conflict")

    def test_forced_repeat_derives_source_and_records_actor_reason(self):
        first = self._create_reading_task()
        with self.app.app_context():
            task = db.session.get(Task, first["id"])
            task.status = "done"
            group_id = snapshot_from_task(task)["group_ids"][0]
            db.session.commit()
        response = self.client.post(
            "/api/question-type-practice/assign",
            json={
                "student_names": ["测试学生"],
                "subject": "reading",
                "standard_type": "judgment",
                "group_ids": [group_id],
                "force_repeat": True,
                "confirm_repeat": True,
                "force_reason": "复训来源测试",
                "source_task_id": 999999,
                "idempotency_key": "forced-source-derived",
            },
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertNotIn("token=", response.get_data(as_text=True))
        with self.app.app_context():
            audit = AuditLogEntry.query.filter_by(field="assignment_repeat").order_by(AuditLogEntry.id.desc()).first()
            self.assertEqual(audit.actor_id, self.staff_id)
            self.assertEqual(audit.metadata_payload["reason"], "复训来源测试")
            self.assertEqual(audit.metadata_payload["source_task_ids"], [first["id"]])
            self.assertNotEqual(audit.metadata_payload["source_task_id"], 999999)

    def test_staff_duplicate_history_endpoint_is_token_free(self):
        first = self._create_reading_task()
        with self.app.app_context():
            task = db.session.get(Task, first["id"])
            token = task.reading_access_token
            group_id = snapshot_from_task(task)["group_ids"][0]
        response = self.client.post(
            "/api/task-assignments/duplicates",
            json={
                "student_names": ["测试学生"],
                "source": "question_type",
                "subject": "reading",
                "standard_type": "judgment",
                "group_ids": [group_id],
            },
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        body = response.get_data(as_text=True)
        self.assertNotIn(token, body)
        self.assertEqual(response.get_json()["students"][0]["status_label"], "已布置")

    def test_same_idempotency_key_returns_one_batch(self):
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
            "idempotency_key": "stable-publish-key",
        }
        preview = self.client.post("/api/question-type-practice/preview", json=selection)
        self.assertEqual(preview.status_code, 200, preview.get_data(as_text=True))
        selection["group_ids"] = [preview.get_json()["groups"][0]["question_group_id"]]
        first = self.client.post("/api/question-type-practice/assign", json=selection)
        second = self.client.post("/api/question-type-practice/assign", json=selection)
        self.assertEqual(first.status_code, 200, first.get_data(as_text=True))
        self.assertEqual(second.status_code, 200, second.get_data(as_text=True))
        self.assertTrue(second.get_json()["idempotent"])
        self.assertNotIn("token=", first.get_data(as_text=True))
        self.assertNotIn("token=", second.get_data(as_text=True))
        with self.app.app_context():
            self.assertEqual(Task.query.count(), 1)

    def test_wrong_repush_rejects_empty_groups_and_unknown_students(self):
        row = self._create_reading_task()
        with self.app.app_context():
            task = db.session.get(Task, row["id"])
            attempt = question_type_practice_module._attempt(task, snapshot_from_task(task))
            attempt.submitted_at = datetime.utcnow()
            attempt.wrong_group_ids_json = "[]"
            db.session.commit()
        empty = self.client.post(
            f"/api/question-type-practice/task/{row['id']}/repush",
            json={"mode": "wrong"},
        )
        self.assertEqual(empty.status_code, 400)
        self.assertEqual(empty.get_json()["error"], "wrong_groups_empty")
        with self.app.app_context():
            attempt = QuestionTypePracticeAttempt.query.filter_by(task_id=row["id"]).one()
            attempt.wrong_group_ids_json = json.dumps([snapshot_from_task(db.session.get(Task, row["id"]))["group_ids"][0]])
            db.session.commit()
        unknown = self.client.post(
            f"/api/question-type-practice/task/{row['id']}/repush",
            json={"mode": "wrong", "student_names": ["不存在学生"]},
        )
        self.assertEqual(unknown.status_code, 400)
        self.assertEqual(unknown.get_json()["error"], "student_not_found")

    def test_legacy_teacher_entry_redirects_to_unified_task_drawer(self):
        self._login_staff()
        response = self.client.get("/tasks/question-types")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.location, "/tasks?source=question_type#taskForm")


if __name__ == "__main__":
    unittest.main()
