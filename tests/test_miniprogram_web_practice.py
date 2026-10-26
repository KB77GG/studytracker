"""Website assignments must remain visible without allowing generic completion."""

import json
import time
import unittest
from datetime import datetime, timedelta

import jwt
from flask import Flask

from api.miniprogram import mp_bp
from models import PlanItem, PlanItemSession, StudentProfile, StudyPlan, Task, User, db
from services.task_date_gate import beijing_today


class WebPracticeTasksTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            SECRET_KEY="test-secret",
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            TESTING=True,
        )
        db.init_app(self.app)
        self.app.register_blueprint(mp_bp)
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        student = User(username="web_student", password_hash="test", role="student")
        other = User(username="other_student", password_hash="test", role="student")
        db.session.add_all([student, other])
        db.session.flush()
        db.session.add_all([
            StudentProfile(user_id=student.id, full_name="网页练习合成学生"),
            StudentProfile(user_id=other.id, full_name="其他合成学生"),
        ])
        self.headers = self._headers(student)
        self.other_headers = self._headers(other)
        self.client = self.app.test_client()
        self.tasks = []
        for mode, snapshot, token in [
            ("writing_practice", {"writing_resource_type": "exercise", "writing_resource_id": "t1-001"}, None),
            ("writing_practice", {"writing_resource_type": "mother_topic", "writing_resource_id": "education"}, None),
            ("question_type_practice", {"subject": "listening"}, "synthetic-listening-token"),
            ("question_type_practice", {"subject": "reading"}, "synthetic-reading-token"),
        ]:
            task = Task(
                date=beijing_today().isoformat(), student_name="网页练习合成学生",
                category="网页练习", detail="合成任务", status="pending", grading_mode=mode,
                question_ids=json.dumps(snapshot), planned_minutes=20, actual_seconds=0,
                listening_access_token=token if snapshot.get("subject") == "listening" else None,
                reading_access_token=token if snapshot.get("subject") == "reading" else None,
            )
            db.session.add(task)
            self.tasks.append(task)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def _headers(self, user):
        token = jwt.encode({"sub": str(user.id), "exp": int(time.time()) + 3600}, "test-secret", algorithm="HS256")
        return {"Authorization": f"Bearer {token}"}

    def test_today_and_detail_preserve_bound_website_links(self):
        response = self.client.get("/api/miniprogram/student/tasks/today", headers=self.headers)
        self.assertEqual(response.status_code, 200)
        cards = {row["id"]: row for row in response.json["tasks"]}
        for task in self.tasks:
            with self.subTest(mode=task.grading_mode, task_id=task.id):
                practice = cards[task.id]["web_practice"]
                self.assertEqual(practice["kind"], task.grading_mode)
                self.assertIn("刷题网页", practice["instruction"])
                self.assertTrue(practice["url"].startswith("https://studytracker.xin/"))
                if task.grading_mode == "writing_practice":
                    self.assertIn(f"task_id={task.id}", practice["url"])
                else:
                    self.assertIn(f"/task/{task.id}?token=", practice["url"])
                detail = self.client.get(f"/api/miniprogram/student/tasks/{task.id}", headers=self.headers)
                self.assertEqual(detail.status_code, 200)
                self.assertEqual(detail.json["task"]["web_practice"], practice)

    def test_generic_submission_and_timer_cannot_mark_website_work_complete(self):
        for task in self.tasks:
            for suffix in ("submit", "timer/start"):
                with self.subTest(mode=task.grading_mode, suffix=suffix):
                    response = self.client.post(
                        f"/api/miniprogram/student/tasks/{task.id}/{suffix}",
                        headers=self.headers,
                        json={"accuracy": 100, "duration_seconds": 1200, "note": "fake completion"},
                    )
                    self.assertEqual(response.status_code, 409)
                    self.assertEqual(response.json["error"], "web_practice_required")
                    db.session.refresh(task)
                    self.assertEqual(task.status, "pending")
                    self.assertFalse(task.student_submitted)
                    self.assertEqual(task.accuracy, 0.0)
                    self.assertEqual(task.actual_seconds, 0)
        self.assertEqual(PlanItemSession.query.count(), 0)

    def test_other_student_cannot_read_links_or_submit(self):
        for task in self.tasks:
            response = self.client.get(f"/api/miniprogram/student/tasks/{task.id}", headers=self.other_headers)
            self.assertEqual(response.status_code, 403)
            response = self.client.post(f"/api/miniprogram/student/tasks/{task.id}/submit", headers=self.other_headers, json={})
            self.assertEqual(response.status_code, 403)
            self.assertNotIn("web_practice", response.json)

    def test_invalid_binding_still_blocks_generic_submit(self):
        self.tasks[0].question_ids = "{}"
        self.tasks[2].listening_access_token = None
        db.session.commit()
        for task in (self.tasks[0], self.tasks[2]):
            response = self.client.get(f"/api/miniprogram/student/tasks/{task.id}", headers=self.headers)
            self.assertIsNone(response.json["task"]["web_practice"]["url"])
            response = self.client.post(f"/api/miniprogram/student/tasks/{task.id}/submit", headers=self.headers, json={"accuracy": 100})
            self.assertEqual(response.status_code, 409)

    def test_website_guidance_does_not_unlock_future_or_expired_tasks(self):
        for delta in (-2, 1):
            task = self.tasks[0]
            task.date = (beijing_today() + timedelta(days=delta)).isoformat()
            db.session.commit()
            response = self.client.get(f"/api/miniprogram/student/tasks/{task.id}", headers=self.headers)
            self.assertEqual(response.status_code, 200)
            self.assertTrue(response.json["task"]["read_only"])
            self.assertFalse(response.json["task"]["can_start"])
            self.assertIsNotNone(response.json["task"]["web_practice"])

    def test_generic_tasks_keep_existing_submission_behavior(self):
        task = self.tasks[0]
        task.grading_mode = None
        db.session.commit()
        response = self.client.get(f"/api/miniprogram/student/tasks/{task.id}", headers=self.headers)
        self.assertIsNone(response.json["task"]["web_practice"])
        response = self.client.post(f"/api/miniprogram/student/tasks/{task.id}/submit", headers=self.headers, json={"note": "已完成"})
        self.assertEqual(response.status_code, 200)
        db.session.refresh(task)
        self.assertEqual(task.status, "submitted")

    def test_plan_item_alias_cannot_bypass_website_only_submission_or_timers(self):
        profile = StudentProfile.query.filter_by(full_name="网页练习合成学生").one()
        plan = StudyPlan(
            student_id=profile.id, plan_date=beijing_today(),
            created_by=profile.user_id, status=StudyPlan.STATUS_PUBLISHED,
        )
        db.session.add(plan)
        db.session.flush()
        for index, resource_type in enumerate((
            "writing_exercise", "writing_mother_topic", "question_type_practice",
        )):
            task = self.tasks[index]
            item = PlanItem(
                id=1001 + index, plan_id=plan.id, exam_system="IELTS", module="网页练习",
                task_name="合成网页任务", resource_type=resource_type, resource_id="synthetic",
            )
            db.session.add(item)
            db.session.flush()
            task.plan_item_id = item.id
            # An old client may already have opened a generic timer before this fix.
            session = PlanItemSession(
                plan_item=item, started_at=datetime.utcnow() - timedelta(seconds=60),
                created_by=profile.user_id, source="timer",
            )
            db.session.add(session)
            db.session.commit()
            before_task = (task.status, task.actual_seconds, task.student_submitted, task.accuracy)
            before_item = (item.student_status, item.actual_seconds, item.submitted_at, item.student_comment)
            before_session = (session.ended_at, session.duration_seconds)
            before_count = PlanItemSession.query.count()
            for suffix in ("timer/start", "submit", f"timer/{session.id}/stop"):
                with self.subTest(resource_type=resource_type, suffix=suffix):
                    response = self.client.post(
                        f"/api/miniprogram/student/tasks/{item.id}/{suffix}",
                        headers=self.headers,
                        json={"note": "fake completion", "duration_seconds": 999, "accuracy": 100},
                    )
                    self.assertEqual(response.status_code, 409)
                    self.assertEqual(response.json["error"], "web_practice_required")
                    db.session.refresh(task)
                    db.session.refresh(item)
                    db.session.refresh(session)
                    self.assertEqual((task.status, task.actual_seconds, task.student_submitted, task.accuracy), before_task)
                    self.assertEqual((item.student_status, item.actual_seconds, item.submitted_at, item.student_comment), before_item)
                    self.assertEqual((session.ended_at, session.duration_seconds), before_session)
                    self.assertEqual(PlanItemSession.query.count(), before_count)
                    forbidden = self.client.post(
                        f"/api/miniprogram/student/tasks/{item.id}/{suffix}",
                        headers=self.other_headers, json={},
                    )
                    self.assertEqual(forbidden.status_code, 403)
                    self.assertNotIn("web_practice", forbidden.json)
