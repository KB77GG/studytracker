import time
import unittest
from datetime import datetime, timedelta

import jwt
from flask import Flask
from flask_login import LoginManager

import app as app_module
from api import api_bp
from api.miniprogram import mp_bp
from models import (
    PlanItem,
    PlanItemSession,
    StudentProfile,
    StudyPlan,
    StudySession,
    Task,
    User,
    db,
)
from services.task_date_gate import beijing_today, task_date_end_utc


class TaskTimerDateGateRouteTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            TESTING=True,
            SECRET_KEY="task-timer-date-gate",
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
        )
        db.init_app(self.app)
        self.app.register_blueprint(api_bp)
        self.app.register_blueprint(mp_bp)
        self.app.add_url_rule(
            "/api/session/stop/<int:sid>",
            endpoint="task_timer_legacy_stop",
            view_func=app_module.api_session_stop,
            methods=["POST"],
        )
        login = LoginManager(self.app)

        @login.user_loader
        def load_user(user_id):
            return db.session.get(User, int(user_id))

        self.original_app = app_module.app
        app_module.app = self.app
        with self.app.app_context():
            db.create_all()
            student = User(
                username="task_timer_student",
                password_hash="test",
                role=User.ROLE_STUDENT,
                is_active=True,
            )
            teacher = User(
                username="task_timer_teacher",
                password_hash="test",
                role=User.ROLE_TEACHER,
                is_active=True,
            )
            db.session.add_all([student, teacher])
            db.session.flush()
            profile = StudentProfile(user_id=student.id, full_name="计时学生")
            db.session.add(profile)
            db.session.flush()
            plan = StudyPlan(
                student_id=profile.id,
                plan_date=beijing_today() - timedelta(days=1),
                status=StudyPlan.STATUS_PUBLISHED,
                created_by=teacher.id,
            )
            db.session.add(plan)
            db.session.commit()
            self.student_id = student.id
            self.teacher_id = teacher.id
            self.profile_id = profile.id
            self.plan_id = plan.id
        self.client = self.app.test_client()

    def tearDown(self):
        try:
            with self.app.app_context():
                db.session.remove()
                db.drop_all()
                db.engine.dispose()
        finally:
            app_module.app = self.original_app

    def _headers(self):
        now = int(time.time())
        token = jwt.encode(
            {
                "sub": str(self.student_id),
                "role": User.ROLE_STUDENT,
                "iat": now,
                "exp": now + 3600,
            },
            self.app.config["SECRET_KEY"],
            algorithm="HS256",
        )
        return {"Authorization": f"Bearer {token}"}

    def _expired_plan_item_session(self):
        with self.app.app_context():
            item = PlanItem(
                plan_id=self.plan_id,
                exam_system="IELTS",
                module="听力",
                task_name="跨午夜计时",
                student_status=PlanItem.STUDENT_IN_PROGRESS,
            )
            db.session.add(item)
            db.session.flush()
            cutoff = task_date_end_utc(item)
            session = PlanItemSession(
                plan_item_id=item.id,
                started_at=cutoff - timedelta(seconds=10),
                created_by=self.student_id,
                source="timer",
            )
            db.session.add(session)
            db.session.commit()
            return item.id, session.id

    def test_api_v1_plan_item_timer_closes_at_three_am_and_counts_ten_seconds(self):
        item_id, session_id = self._expired_plan_item_session()

        response = self.client.post(
            f"/api/v1/students/plan-items/{item_id}/timer/{session_id}/stop",
            headers=self._headers(),
        )

        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertEqual(response.get_json()["data"]["session_seconds"], 10)
        with self.app.app_context():
            session = db.session.get(PlanItemSession, session_id)
            self.assertEqual(session.duration_seconds, 10)
            self.assertIsNotNone(session.ended_at)

    def test_miniprogram_plan_item_timer_closes_at_three_am_and_is_idempotent(self):
        item_id, session_id = self._expired_plan_item_session()
        url = f"/api/miniprogram/student/tasks/{item_id}/timer/{session_id}/stop"

        response = self.client.post(url, headers=self._headers())
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertEqual(response.get_json()["duration"], 10)

        repeated = self.client.post(url, headers=self._headers())
        self.assertEqual(repeated.status_code, 200, repeated.get_data(as_text=True))
        self.assertEqual(repeated.get_json()["duration"], 10)

        with self.app.app_context():
            item = db.session.get(PlanItem, item_id)
            self.assertEqual(item.actual_seconds, 10)

    def test_legacy_study_session_timer_closes_at_three_am_and_counts_ten_seconds(self):
        with self.app.app_context():
            task = Task(
                date=(beijing_today() - timedelta(days=1)).isoformat(),
                student_name="计时学生",
                category="学习任务",
                detail="legacy cross midnight",
                status="progress",
                created_by=self.teacher_id,
            )
            db.session.add(task)
            db.session.flush()
            cutoff = task_date_end_utc(task)
            session = StudySession(
                task_id=task.id,
                started_at=cutoff - timedelta(seconds=10),
                created_by=self.student_id,
            )
            db.session.add(session)
            db.session.commit()
            session_id = session.id

        with self.client.session_transaction() as flask_session:
            flask_session["_user_id"] = str(self.student_id)
            flask_session["_fresh"] = True
        response = self.client.post(f"/api/session/stop/{session_id}")

        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertEqual(response.get_json()["seconds"], 10)
        with self.app.app_context():
            session = db.session.get(StudySession, session_id)
            task = db.session.get(Task, session.task_id)
            self.assertEqual(session.seconds, 10)
            self.assertIsNotNone(session.ended_at)
            self.assertEqual(task.actual_seconds, 10)

    def test_same_day_legacy_stop_remains_writable(self):
        with self.app.app_context():
            task = Task(
                date=beijing_today().isoformat(),
                student_name="计时学生",
                category="学习任务",
                detail="same day",
                status="progress",
                created_by=self.teacher_id,
            )
            db.session.add(task)
            db.session.flush()
            session = StudySession(
                task_id=task.id,
                started_at=datetime.utcnow() - timedelta(seconds=3),
                created_by=self.student_id,
            )
            db.session.add(session)
            db.session.commit()
            session_id = session.id

        with self.client.session_transaction() as flask_session:
            flask_session["_user_id"] = str(self.student_id)
            flask_session["_fresh"] = True
        response = self.client.post(f"/api/session/stop/{session_id}")

        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertGreaterEqual(response.get_json()["seconds"], 2)


if __name__ == "__main__":
    unittest.main()
