"""/parent/stats 路由级测试（安全网）。

需 jwt/flask 等全依赖，用 .venv 跑（不进零依赖的 CI 轻量门禁）。
重点验证重构后的 today / weekly / subjects 聚合在真实请求下行为正确。
"""

import time
import unittest
from datetime import date, timedelta

import jwt
from flask import Flask

from api.miniprogram import mp_bp
from models import ParentStudentLink, StudentProfile, Task, User


class ParentStatsRouteTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            SECRET_KEY="test-secret",
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            TESTING=True,
        )
        db = self._db()
        db.init_app(self.app)
        self.app.register_blueprint(mp_bp)

        self.today_iso = date.today().isoformat()
        with self.app.app_context():
            db.create_all()
            parent = User(username="ps_parent", password_hash="x", role=User.ROLE_PARENT, is_active=True)
            student = User(username="ps_student", password_hash="x", role=User.ROLE_STUDENT, is_active=True)
            teacher = User(username="ps_teacher", password_hash="x", role=User.ROLE_TEACHER, is_active=True)
            db.session.add_all([parent, student, teacher])
            db.session.flush()
            db.session.add_all([
                StudentProfile(user_id=student.id, full_name="统计甲"),
                ParentStudentLink(parent_id=parent.id, student_name="统计甲", is_active=True),
            ])
            # 今日 3 个任务：done / not_started / in_progress；学科 语法x2 + 词汇x1
            db.session.add_all([
                Task(date=self.today_iso, student_name="统计甲", category="语法",
                     detail="语法 done", status="done", created_by=teacher.id),
                Task(date=self.today_iso, student_name="统计甲", category="词汇",
                     detail="词汇 待做", status="", created_by=teacher.id),
                Task(date=self.today_iso, student_name="统计甲", category="语法",
                     detail="语法 进行中", status="in_progress", created_by=teacher.id),
            ])
            db.session.commit()
            self.parent_id = parent.id

        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            self._db().session.remove()
            self._db().drop_all()

    @staticmethod
    def _db():
        from models import db
        return db

    def _headers(self, user_id):
        now = int(time.time())
        payload = {
            "sub": str(user_id),
            "role": User.ROLE_PARENT,
            "iat": now,
            "exp": now + int(timedelta(hours=1).total_seconds()),
        }
        token = jwt.encode(payload, "test-secret", algorithm="HS256")
        return {"Authorization": f"Bearer {token}"}

    def _get_stats(self):
        resp = self.client.get(
            "/api/miniprogram/parent/stats?student_name=统计甲",
            headers=self._headers(self.parent_id),
        )
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        return resp.get_json()

    def test_today_overview(self):
        data = self._get_stats()
        today = data["today"]
        self.assertEqual(today["total"], 3)
        self.assertEqual(today["completed"], 1)
        self.assertEqual(today["not_started"], 1)
        self.assertEqual(today["in_progress"], 1)
        self.assertEqual(today["pending_review"], 0)
        self.assertEqual(today["pending"], 0)  # 别名
        self.assertEqual(today["rate"], 33)    # round(1/3*100)

    def test_subjects_aggregation_sorted(self):
        subjects = self._get_stats()["subjects"]
        self.assertEqual(subjects[0]["subject"], "语法")
        self.assertEqual(subjects[0]["count"], 2)
        self.assertEqual(subjects[0]["percent"], 67)
        by_subject = {s["subject"]: s["count"] for s in subjects}
        self.assertEqual(by_subject["词汇"], 1)

    def test_weekly_has_seven_days_with_today_filled(self):
        weekly = self._get_stats()["weekly"]
        self.assertEqual(len(weekly), 7)
        today_label = date.today().strftime("%m-%d")
        last = weekly[-1]
        self.assertEqual(last["date"], today_label)
        self.assertEqual(last["total"], 3)
        self.assertEqual(last["completed"], 1)
        self.assertEqual(last["rate"], 33)

    def test_unbound_student_rejected(self):
        resp = self.client.get(
            "/api/miniprogram/parent/stats?student_name=查无此人",
            headers=self._headers(self.parent_id),
        )
        self.assertEqual(resp.status_code, 403)


if __name__ == "__main__":
    unittest.main()
