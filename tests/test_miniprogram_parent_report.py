import time
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

import jwt
from flask import Flask

from api.miniprogram import mp_bp
from models import (
    db,
    DictationBook,
    DictationRecord,
    DictationWord,
    MaterialBank,
    ParentStudentLink,
    Question,
    QuestionOption,
    StudentAnswer,
    StudentProfile,
    StudentWordMastery,
    Task,
    User,
)


ROOT = Path(__file__).resolve().parents[1]


class ParentReportMarkupTest(unittest.TestCase):
    def test_overview_metrics_open_filtered_task_details(self):
        markup = (ROOT / "miniprogram/pages/parent/home/index.wxml").read_text(encoding="utf-8")
        logic = (ROOT / "miniprogram/pages/parent/home/index.js").read_text(encoding="utf-8")
        api_source = (ROOT / "api/miniprogram.py").read_text(encoding="utf-8")

        self.assertIn("查看全部 {{stats.today.total}} 项", markup)
        self.assertIn('data-filter="not_started"', markup)
        self.assertIn('data-filter="pending_review"', markup)
        self.assertIn('bindtap="showTodayTasks"', markup)
        self.assertIn("showTodayTasks(e)", logic)
        self.assertIn("filteredTodayTasks", logic)
        self.assertIn('"not_started": status_counts["not_started"]', api_source)
        self.assertIn('"pending_review": status_counts["pending_review"]', api_source)
        self.assertIn('"today_tasks": today_task_items', api_source)

    def test_recent_activity_links_to_question_details(self):
        markup = (ROOT / "miniprogram/pages/parent/home/index.wxml").read_text(encoding="utf-8")
        logic = (ROOT / "miniprogram/pages/parent/home/index.js").read_text(encoding="utf-8")
        app_config = (ROOT / "miniprogram/app.json").read_text(encoding="utf-8")
        detail_markup = (ROOT / "miniprogram/pages/parent/task-detail/index.wxml").read_text(encoding="utf-8")

        self.assertIn('bindtap="viewTaskDetail"', markup)
        self.assertIn("查看题目与批改", markup)
        self.assertIn("viewTaskDetail(e)", logic)
        self.assertIn("pages/parent/task-detail/index", app_config)
        self.assertIn("学生答案", detail_markup)
        self.assertIn("正确答案", detail_markup)
        self.assertIn("掌握状态按多次复习结果更新", detail_markup)


class ParentTaskDetailApiTest(unittest.TestCase):
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

        with self.app.app_context():
            db.create_all()
            parent = User(username="parent_report", password_hash="test", role=User.ROLE_PARENT, is_active=True)
            other_parent = User(username="other_parent", password_hash="test", role=User.ROLE_PARENT, is_active=True)
            student = User(username="report_student", password_hash="test", role=User.ROLE_STUDENT, is_active=True)
            teacher = User(username="report_teacher", password_hash="test", role=User.ROLE_TEACHER, is_active=True)
            db.session.add_all([parent, other_parent, student, teacher])
            db.session.flush()
            profile = StudentProfile(user_id=student.id, full_name="学生甲")
            link = ParentStudentLink(parent_id=parent.id, student_name="学生甲", is_active=True)
            db.session.add_all([profile, link])

            book = DictationBook(title="四级核心词", word_count=2, created_by=teacher.id, is_active=True)
            db.session.add(book)
            db.session.flush()
            word_one = DictationWord(book_id=book.id, sequence=1, word="accuracy", translation="准确性")
            word_two = DictationWord(book_id=book.id, sequence=2, word="achieve", translation="实现")
            db.session.add_all([word_one, word_two])
            db.session.flush()
            dictation_task = Task(
                date="2026-06-21",
                student_name="学生甲",
                category="词汇",
                detail="四级单词 Day 1",
                status="done",
                accuracy=50,
                created_by=teacher.id,
                dictation_book_id=book.id,
                dictation_word_start=1,
                dictation_word_end=2,
            )
            db.session.add(dictation_task)
            db.session.flush()
            db.session.add_all([
                DictationRecord(student_id=student.id, task_id=dictation_task.id, book_id=book.id, word_id=word_one.id, student_answer="accurcy", is_correct=False),
                DictationRecord(student_id=student.id, task_id=dictation_task.id, book_id=book.id, word_id=word_one.id, student_answer="accuracy", is_correct=True),
                DictationRecord(student_id=student.id, task_id=dictation_task.id, book_id=book.id, word_id=word_two.id, student_answer="acheive", is_correct=False),
                StudentWordMastery(student_id=student.id, word_id=word_one.id, book_id=book.id, review_level=5, mistake_count=1, correct_streak=0),
                StudentWordMastery(student_id=student.id, word_id=word_two.id, book_id=book.id, review_level=1, mistake_count=2, correct_streak=0),
            ])

            material = MaterialBank(title="语法选择练习", type="grammar", created_by=teacher.id, is_active=True)
            db.session.add(material)
            db.session.flush()
            question_one = Question(material_id=material.id, sequence=1, question_type="choice", content="Choose the correct answer.", reference_answer="B")
            question_two = Question(material_id=material.id, sequence=2, question_type="text", content="Rewrite the sentence.", reference_answer="A model answer.")
            db.session.add_all([question_one, question_two])
            db.session.flush()
            db.session.add_all([
                QuestionOption(question_id=question_one.id, option_key="A", option_text="wrong"),
                QuestionOption(question_id=question_one.id, option_key="B", option_text="right"),
            ])
            material_task = Task(
                date="2026-06-21",
                student_name="学生甲",
                category="语法",
                detail="语法选择练习",
                status="done",
                accuracy=50,
                created_by=teacher.id,
                material_id=material.id,
            )
            db.session.add(material_task)
            db.session.flush()
            db.session.add_all([
                StudentAnswer(task_id=material_task.id, question_id=question_one.id, student_id=student.id, answer_type="choice", text_answer="B", is_correct=True, reviewed=True),
                StudentAnswer(task_id=material_task.id, question_id=question_two.id, student_id=student.id, answer_type="text", text_answer="My rewrite.", is_correct=None, reviewed=False),
            ])
            db.session.commit()
            self.parent_id = parent.id
            self.other_parent_id = other_parent.id
            self.dictation_task_id = dictation_task.id
            self.material_task_id = material_task.id

        self.client = self.app.test_client()
        self.parent_headers = self._headers(self.parent_id)
        self.other_parent_headers = self._headers(self.other_parent_id)

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _headers(self, user_id):
        now = int(time.time())
        payload = {
            "sub": str(user_id),
            "role": User.ROLE_PARENT,
            "iat": now,
            "exp": now + int(timedelta(hours=1).total_seconds()),
        }
        return {"Authorization": f"Bearer {jwt.encode(payload, 'test-secret', algorithm='HS256')}"}

    def test_parent_sees_latest_dictation_result_and_mastery(self):
        response = self.client.get(
            f"/api/miniprogram/parent/tasks/{self.dictation_task_id}",
            headers=self.parent_headers,
        )
        self.assertEqual(response.status_code, 200)
        detail = response.get_json()["detail"]
        self.assertEqual(detail["kind"], "dictation")
        self.assertEqual(detail["summary"]["assigned_total"], 2)
        self.assertEqual(detail["summary"]["correct_total"], 1)
        self.assertEqual(detail["summary"]["wrong_total"], 1)
        self.assertEqual(detail["summary"]["mastered_total"], 1)
        self.assertEqual(detail["items"][0]["student_answer"], "accuracy")
        self.assertEqual(detail["items"][0]["attempt_count"], 2)
        self.assertEqual(detail["items"][1]["mastery_label"], "巩固中")

    def test_parent_sees_question_answer_and_pending_review(self):
        response = self.client.get(
            f"/api/miniprogram/parent/tasks/{self.material_task_id}",
            headers=self.parent_headers,
        )
        self.assertEqual(response.status_code, 200)
        detail = response.get_json()["detail"]
        self.assertEqual(detail["summary"]["pending_total"], 1)
        self.assertEqual(detail["items"][0]["student_answer"], "B. right")
        self.assertEqual(detail["items"][0]["correct_answer"], "B. right")
        self.assertEqual(detail["items"][1]["result_label"], "待批改")

    def test_unlinked_parent_cannot_view_task_detail(self):
        response = self.client.get(
            f"/api/miniprogram/parent/tasks/{self.dictation_task_id}",
            headers=self.other_parent_headers,
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error"], "student_not_bound")


if __name__ == "__main__":
    unittest.main()
