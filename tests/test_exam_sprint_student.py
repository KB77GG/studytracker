"""Sprint reading tasks on current and older student clients, entirely offline."""

import hashlib
import os
import tempfile
import time
import unittest
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

import jwt
from flask import Flask

from api.miniprogram import (
    _load_student_reading_test,
    _parent_test_question_map,
    _teacher_practice_question_map,
    _usable_reading_image,
    mp_bp,
)
from models import PlanItem, PlanItemSession, StudentProfile, StudyPlan, Task, User, db
from services.exam_sprint import state_directory
from services.exam_sprint_store import content_directory, save_converted_documents
from services.exam_sprint_student import (
    load_student_ninefen_reading,
    ninefen_reading_task_path,
    sprint_reading_image_url,
)
from services.task_date_gate import beijing_today
from services.web_practice_tasks import web_practice_payload
from tests.test_ninefen_content import IMAGE, convert, paper


class SprintStudentTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.env = patch.dict(os.environ, {"EXAM_SPRINT_STATE_DIR": str(self.root / "sprint")})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.image_bytes = b"synthetic diagram bytes"
        self.image_name = hashlib.sha256(self.image_bytes).hexdigest() + ".png"
        self.image_url = "/practice/sprint/assets/" + self.image_name
        self.asset = state_directory(self.root) / "assets" / self.image_name
        self.asset.parent.mkdir(parents=True)
        self.asset.write_bytes(self.image_bytes)
        raw, answers = paper()
        self.converted = convert(raw, answers, media_map={IMAGE: self.image_url})
        self.mapping = save_converted_documents(self.root, self.converted)[0]
        self.test_id = self.mapping["target_id"]
        self.document = self.converted["documents"][0]["payload"]
        self.app = Flask(__name__, root_path=str(self.root))
        self.app.config.update(
            SECRET_KEY="synthetic-secret",
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            TESTING=True,
        )
        db.init_app(self.app)
        self.app.register_blueprint(mp_bp)
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        student = User(username="sprint-student", password_hash="test", role="student")
        other = User(username="other-student", password_hash="test", role="student")
        db.session.add_all([student, other])
        db.session.flush()
        self.profile = StudentProfile(user_id=student.id, full_name="合成热榜学生")
        db.session.add_all(
            [
                self.profile,
                StudentProfile(user_id=other.id, full_name="其他合成学生"),
            ]
        )
        self.task = Task(
            date=beijing_today().isoformat(),
            student_name="合成热榜学生",
            category="雅思-阅读-7天热榜",
            detail="合成热榜阅读",
            status="pending",
            reading_test_id=self.test_id,
            reading_passage_number=1,
            reading_access_token="synthetic token+&?",
            planned_minutes=20,
            actual_seconds=0,
        )
        db.session.add(self.task)
        db.session.commit()
        self.headers = self.headers_for(student)
        self.other_headers = self.headers_for(other)
        self.client = self.app.test_client()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.context.pop()

    def headers_for(self, user):
        token = jwt.encode(
            {"sub": str(user.id), "exp": int(time.time()) + 3600},
            "synthetic-secret",
            algorithm="HS256",
        )
        return {"Authorization": f"Bearer {token}"}

    def native(self, *, headers=None, token=None):
        return self.client.get(
            f"/api/miniprogram/student/reading/cambridge/{self.task.id}",
            headers=self.headers if headers is None else headers,
            query_string={"token": self.task.reading_access_token if token is None else token},
        )

    def test_today_and_detail_have_exact_task_bound_website_guidance(self):
        expected = web_practice_payload(self.task)
        self.assertEqual(expected["kind"], "exam_sprint_reading")
        parsed = urlsplit(expected["url"])
        self.assertEqual(parsed.netloc, "studytracker.xin")
        self.assertEqual(parsed.path, f"/reading/test/{self.test_id}")
        self.assertEqual(
            parse_qs(parsed.query),
            {
                "task_id": [str(self.task.id)],
                "token": [self.task.reading_access_token],
                "passage": ["1"],
            },
        )
        today = self.client.get("/api/miniprogram/student/tasks/today", headers=self.headers)
        self.assertEqual(today.status_code, 200)
        card = next(row for row in today.json["tasks"] if row["id"] == self.task.id)
        self.assertEqual(card["web_practice"], expected)
        detail = self.client.get(
            f"/api/miniprogram/student/tasks/{self.task.id}",
            headers=self.headers,
        )
        self.assertEqual(detail.json["task"]["web_practice"], expected)

    def test_native_compatibility_preserves_diagram_long_ids_and_no_answer_keys(self):
        response = self.native()
        self.assertEqual(response.status_code, 200)
        test = response.json["test"]
        self.assertEqual(test["id"], self.test_id)
        self.assertEqual(test["question_count"], 4)
        groups = test["passages"][0]["groups"]
        self.assertEqual(groups[0]["image_url"], "https://studytracker.xin" + self.image_url)
        qid = self.document["passages"][0]["groups"][0]["questions"][0]["id"]
        self.assertIsInstance(groups[0]["questions"][0]["id"], str)
        self.assertEqual(groups[0]["questions"][0]["id"], qid)
        self.assertIn(f"Q1 ${qid}$", groups[0]["collect"])

        def assert_no_answers(value):
            if isinstance(value, dict):
                self.assertFalse({"answer", "answers", "answer_key", "analysis"} & value.keys())
                for item in value.values():
                    assert_no_answers(item)
            elif isinstance(value, list):
                for item in value:
                    assert_no_answers(item)

        assert_no_answers(test)

    def test_native_requires_student_ownership_and_exact_token(self):
        self.assertEqual(self.native(headers={}).status_code, 401)
        self.assertEqual(self.native(headers=self.other_headers).status_code, 404)
        self.assertEqual(self.native(token="wrong").status_code, 403)
        self.assertEqual(self.native(token="").status_code, 400)
        forbidden = self.client.get(
            f"/api/miniprogram/student/tasks/{self.task.id}",
            headers=self.other_headers,
        )
        self.assertEqual(forbidden.status_code, 403)
        self.assertNotIn("web_practice", forbidden.json)

    def test_date_gate_remains_read_only_for_future_and_expired_native_tasks(self):
        for delta in (-2, 1):
            with self.subTest(delta=delta):
                self.task.date = (beijing_today() + timedelta(days=delta)).isoformat()
                db.session.commit()
                response = self.native()
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.json["task"]["read_only"])
                self.assertFalse(response.json["task"]["can_start"])

    def test_generic_submit_and_timer_cannot_complete_native_reading_assignment(self):
        for suffix in ("submit", "timer/start"):
            response = self.client.post(
                f"/api/miniprogram/student/tasks/{self.task.id}/{suffix}",
                headers=self.headers,
                json={"accuracy": 100, "duration_seconds": 1200},
            )
            self.assertEqual(response.status_code, 409)
            self.assertEqual(response.json["error"], "web_practice_required")
        db.session.refresh(self.task)
        self.assertEqual(self.task.status, "pending")
        self.assertFalse(self.task.student_submitted)
        self.assertEqual(self.task.actual_seconds, 0)
        self.assertEqual(PlanItemSession.query.count(), 0)

    def test_linked_plan_item_uses_task_binding_and_blocks_generic_completion(self):
        plan = StudyPlan(
            student_id=self.profile.id,
            plan_date=beijing_today(),
            created_by=self.profile.user_id,
            status=StudyPlan.STATUS_PUBLISHED,
        )
        db.session.add(plan)
        db.session.flush()
        item = PlanItem(
            id=1001,
            plan_id=plan.id,
            exam_system="IELTS",
            module="阅读",
            task_name="合成热榜任务",
            resource_type="reading",
            resource_id=self.test_id,
        )
        db.session.add(item)
        db.session.flush()
        self.task.plan_item_id = item.id
        db.session.commit()
        self.assertEqual(web_practice_payload(item), web_practice_payload(self.task))
        for suffix in ("submit", "timer/start"):
            response = self.client.post(
                f"/api/miniprogram/student/tasks/{item.id}/{suffix}",
                headers=self.headers,
                json={"accuracy": 100},
            )
            self.assertEqual(response.status_code, 409)
        self.assertEqual(PlanItemSession.query.count(), 0)

    def test_invalid_binding_has_guidance_without_url_and_keeps_generic_guard(self):
        for field, invalid in (
            ("reading_access_token", None),
            ("reading_passage_number", 2),
            ("reading_test_id", "ninefen_invalid"),
        ):
            with self.subTest(field=field):
                original = getattr(self.task, field)
                setattr(self.task, field, invalid)
                db.session.commit()
                self.assertIsNone(web_practice_payload(self.task)["url"])
                response = self.client.post(
                    f"/api/miniprogram/student/tasks/{self.task.id}/submit",
                    headers=self.headers,
                    json={},
                )
                self.assertEqual(response.status_code, 409)
                setattr(self.task, field, original)
                db.session.commit()

    def test_missing_or_corrupt_diagram_disables_exercise_and_guidance_link(self):
        for mode in ("same-length corruption", "missing"):
            with self.subTest(mode=mode):
                if mode == "missing":
                    self.asset.unlink()
                else:
                    self.asset.write_bytes(b"X" * len(self.image_bytes))
                self.assertIsNone(load_student_ninefen_reading(self.root, self.test_id))
                self.assertIsNone(web_practice_payload(self.task)["url"])
                self.assertEqual(self.native().status_code, 404)
                self.assertEqual(_usable_reading_image({"img_url": self.image_url}), "")
                self.asset.write_bytes(self.image_bytes)

    def test_bad_receipt_and_traversal_alias_do_not_load_static_fallback(self):
        path = content_directory(self.root) / self.mapping["relative_path"]
        original = path.read_bytes()
        path.write_bytes(original + b" ")
        self.assertIsNone(_load_student_reading_test(self.test_id)[0])
        self.assertEqual(self.native().status_code, 404)
        path.write_bytes(original)
        self.assertIsNotNone(_load_student_reading_test(self.test_id)[0])
        self.assertIsNone(_load_student_reading_test("../" + self.test_id)[0])
        self.assertIsNone(_load_student_reading_test(self.test_id + "/")[0])

    def test_image_allowlist_rejects_external_traversal_query_and_symlinks(self):
        for value in (
            "https://example.com/" + self.image_name,
            "https://studytracker.xin" + self.image_url,
            self.image_url + "?x=1",
            self.image_url + "#x",
            "/practice/sprint/assets/../" + self.image_name,
            "/practice/sprint/assets/%2e%2e/" + self.image_name,
            self.image_url.replace(".png", ".svg"),
        ):
            with self.subTest(value=value):
                self.assertEqual(sprint_reading_image_url(self.root, value), "")
        self.asset.unlink()
        external = self.root / "external.png"
        external.write_bytes(self.image_bytes)
        self.asset.symlink_to(external)
        self.assertEqual(sprint_reading_image_url(self.root, self.image_url), "")

    def test_review_loaders_keep_fixed_version_without_any_current_snapshot(self):
        self.assertFalse((state_directory(self.root) / "current.json").exists())
        loaded, identifier = _load_student_reading_test(self.test_id)
        self.assertEqual(identifier, self.test_id)
        self.assertEqual(loaded, self.document)
        teacher = _teacher_practice_question_map(self.task, "reading")
        parent = _parent_test_question_map(loaded, "reading_test")
        question = loaded["passages"][0]["groups"][1]["questions"][0]
        self.assertEqual(teacher[question["id"]]["title"], question["title"])
        self.assertEqual(parent[question["id"]], question["title"])
        self.task.reading_passage_number = None
        path = ninefen_reading_task_path(self.root, self.task)
        self.assertNotIn("passage", parse_qs(urlsplit(path).query))


if __name__ == "__main__":
    unittest.main()
