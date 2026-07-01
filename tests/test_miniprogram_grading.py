import json
import time
import unittest
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import jwt
from flask import Flask

from api.miniprogram import (
    _sync_plan_item_from_legacy_task,
    _task_evidence_files,
    _task_evidence_type,
    _teacher_grading_percentage,
    mp_bp,
)
from models import Task, User, db


class MiniprogramGradingTest(unittest.TestCase):
    def test_sync_plan_item_labels_dictation_tasks(self):
        submitted_at = datetime(2026, 6, 30, 13, 45)
        item = SimpleNamespace(
            exam_system="材料练习",
            module="未分模块",
            task_name="材料练习",
            resource_type=None,
            resource_id=None,
            resource_metadata="",
            student_status="pending",
            submitted_at=None,
            student_comment="",
            actual_seconds=0,
        )
        task = SimpleNamespace(
            plan_item=item,
            dictation_book_id=7,
            dictation_mode="zh_to_en",
            dictation_word_start=37,
            dictation_word_end=80,
            submitted_at=submitted_at,
            actual_seconds=0,
        )

        synced = _sync_plan_item_from_legacy_task(task)
        metadata = json.loads(item.resource_metadata)

        self.assertIs(synced, item)
        self.assertEqual(item.exam_system, "词汇")
        self.assertEqual(item.module, "词汇")
        self.assertEqual(item.task_name, "单词默写")
        self.assertEqual(item.resource_type, "dictation")
        self.assertEqual(item.resource_id, "dictation_book:7")
        self.assertEqual(metadata["dictation_word_start"], 37)

    def test_task_evidence_type_recognizes_miniprogram_audio_formats(self):
        self.assertEqual(_task_evidence_type("/uploads/answer.mp3"), "audio")
        self.assertEqual(_task_evidence_type("/uploads/answer.m4a?token=abc"), "audio")
        self.assertEqual(_task_evidence_type("/uploads/answer.webm#preview"), "audio")
        self.assertEqual(_task_evidence_type("/uploads/homework.jpg"), "image")

    def test_task_evidence_files_separates_audio_and_images(self):
        task = SimpleNamespace(
            evidence_photos='["/uploads/a.mp3", "/uploads/a.png", "/uploads/notes.pdf"]'
        )

        grouped = _task_evidence_files(task)

        self.assertEqual(grouped["audio"], ["/uploads/a.mp3"])
        self.assertEqual(grouped["image"], ["/uploads/a.png"])
        self.assertEqual(grouped["doc"], ["/uploads/notes.pdf"])

    def test_teacher_grading_percentage_validates_range(self):
        self.assertEqual(
            _teacher_grading_percentage("88.25", "accuracy"),
            (88.2, None),
        )
        self.assertEqual(_teacher_grading_percentage("", "accuracy"), (None, None))
        self.assertEqual(
            _teacher_grading_percentage(101, "accuracy"),
            (None, "invalid_accuracy"),
        )
        self.assertEqual(
            _teacher_grading_percentage("bad", "completion_rate"),
            (None, "invalid_completion_rate"),
        )


class TeacherGradingApiTest(unittest.TestCase):
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
            teacher = User(
                username="speaking_teacher",
                password_hash="test",
                role=User.ROLE_TEACHER,
                is_active=True,
            )
            db.session.add(teacher)
            db.session.flush()
            self.teacher_id = teacher.id
            task = Task(
                date="2026-06-13",
                student_name="Student A",
                category="雅思-口语",
                detail="Part 2 recording",
                status="submitted",
                created_by=teacher.id,
                student_submitted=True,
                submitted_at=datetime.now(UTC).replace(tzinfo=None),
                evidence_photos=json.dumps(
                    ["/uploads/answer.mp3", "/uploads/homework.jpg"]
                ),
            )
            db.session.add(task)
            db.session.commit()
            self.task_id = task.id

        now = int(time.time())
        payload = {
            "sub": str(self.teacher_id),
            "role": User.ROLE_TEACHER,
            "iat": now,
            "exp": now + int(timedelta(hours=1).total_seconds()),
        }
        self.headers = {
            "Authorization": f"Bearer {jwt.encode(payload, 'test-secret', algorithm='HS256')}"
        }
        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_teacher_can_list_audio_and_complete_grading(self):
        response = self.client.get(
            "/api/miniprogram/teacher/grading",
            headers=self.headers,
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["pending_count"], 1)
        self.assertEqual(payload["tasks"][0]["audio_files"], ["/uploads/answer.mp3"])
        self.assertEqual(payload["tasks"][0]["image_files"], ["/uploads/homework.jpg"])

        response = self.client.post(
            f"/api/miniprogram/teacher/grading/{self.task_id}",
            headers=self.headers,
            json={
                "accuracy": 87.5,
                "completion_rate": 100,
                "feedback_text": "发音清晰，注意句尾语调。",
            },
        )
        self.assertEqual(response.status_code, 200)

        with self.app.app_context():
            task = db.session.get(Task, self.task_id)
            self.assertEqual(task.status, "done")
            self.assertEqual(task.accuracy, 87.5)
            self.assertEqual(task.feedback_text, "发音清晰，注意句尾语调。")


if __name__ == "__main__":
    unittest.main()
