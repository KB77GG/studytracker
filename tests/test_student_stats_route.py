"""/student/stats 路由级测试（安全网）。

需 jwt/flask 等全依赖，用 .venv 跑（不进零依赖 CI）。
验证重构后的 streak / 累计时长 / 平均正确率 / 等级 / 勋章 / 周活跃度在真实请求下正确。
"""

import time
import unittest
from datetime import date, timedelta

import jwt
from flask import Flask

from api.miniprogram import mp_bp
from models import StudentProfile, Task, User


class StudentStatsRouteTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            SECRET_KEY="test-secret",
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            TESTING=True,
        )
        from models import db
        db.init_app(self.app)
        self.app.register_blueprint(mp_bp)

        today = date.today()
        yesterday = today - timedelta(days=1)
        with self.app.app_context():
            db.create_all()
            student = User(username="ss_student", password_hash="x", role=User.ROLE_STUDENT, is_active=True)
            teacher = User(username="ss_teacher", password_hash="x", role=User.ROLE_TEACHER, is_active=True)
            db.session.add_all([student, teacher])
            db.session.flush()
            db.session.add(StudentProfile(user_id=student.id, full_name="统计生"))
            db.session.add_all([
                Task(date=today.isoformat(), student_name="统计生", category="阅读",
                     status="done", actual_seconds=3600, accuracy=90, created_by=teacher.id),
                Task(date=yesterday.isoformat(), student_name="统计生", category="听力",
                     status="done", actual_seconds=1800, accuracy=80, created_by=teacher.id),
            ])
            db.session.commit()
            self.student_id = student.id

        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            from models import db
            db.session.remove()
            db.drop_all()

    def _headers(self):
        now = int(time.time())
        payload = {"sub": str(self.student_id), "role": User.ROLE_STUDENT,
                   "iat": now, "exp": now + 3600}
        token = jwt.encode(payload, "test-secret", algorithm="HS256")
        return {"Authorization": f"Bearer {token}"}

    def _stats(self):
        resp = self.client.get("/api/miniprogram/student/stats", headers=self._headers())
        self.assertEqual(resp.status_code, 200, resp.get_data(as_text=True))
        return resp.get_json()["stats"]

    def test_totals_streak_accuracy_level(self):
        s = self._stats()
        self.assertEqual(s["total_hours"], 1.5)            # (3600+1800)/3600
        self.assertEqual(s["streak"], 2)                   # 今天+昨天连续
        self.assertEqual(s["average_accuracy"], 85.0)      # (90+80)/2
        self.assertEqual(s["weekly_practice_count"], 2)
        self.assertEqual(s["level"], 1)                    # int(1.5//5)+1

    def test_weekly_activity_seven_days(self):
        s = self._stats()
        self.assertEqual(len(s["weekly_activity"]), 7)
        self.assertEqual(s["weekly_activity"][-1]["count"], 1)  # 今日 1 个完成任务
        self.assertEqual(s["weekly_activity"][-1]["minutes"], 60)

    def test_badges_newbie_when_no_thresholds(self):
        badges = {b["id"] for b in self._stats()["badges"]}
        self.assertEqual(badges, {"newbie"})


if __name__ == "__main__":
    unittest.main()
