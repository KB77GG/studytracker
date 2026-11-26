"""Regression coverage for the extracted legacy PlanItem projection."""

import json
import unittest
from datetime import datetime
from types import SimpleNamespace

from flask import Flask, request

from api.miniprogram import _sync_plan_item_from_legacy_task
from models import PlanEvidence, PlanItem, StudentProfile, StudyPlan, Task, User, db
from services.task_plan_item_sync import sync_plan_item_from_task_submission


class TaskPlanItemSyncTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:", SQLALCHEMY_TRACK_MODIFICATIONS=False
        )
        db.init_app(self.app)
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        self.user = User(username="sync-student", password_hash="test", role="student")
        db.session.add(self.user)
        db.session.flush()
        self.profile = StudentProfile(user_id=self.user.id, full_name="合成同步学生")
        db.session.add(self.profile)
        db.session.flush()
        plan = StudyPlan(
            student_id=self.profile.id,
            plan_date=datetime(2026, 11, 26).date(),
            created_by=self.user.id,
        )
        db.session.add(plan)
        db.session.flush()
        self.item = PlanItem(
            plan_id=plan.id,
            exam_system="材料练习",
            module="未分模块",
            task_name="材料练习",
            actual_seconds=40,
        )
        db.session.add(self.item)
        db.session.flush()
        self.task = Task(
            student_name=self.profile.full_name,
            category="词汇",
            created_by=self.user.id,
            plan_item_id=self.item.id,
            dictation_book_id=7,
            vocabulary_goal="writing",
            dictation_mode="zh_to_en",
            dictation_order="random",
            dictation_word_start=8,
            dictation_word_end=16,
            actual_seconds=30,
            submitted_at=datetime(2026, 11, 26, 12),
        )
        db.session.add(self.task)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.context.pop()

    def test_shared_projection_preserves_metadata_duration_and_evidence(self):
        synced = sync_plan_item_from_task_submission(
            self.task,
            note="练习完成",
            evidence_files=["/uploads/a.mp3", "/uploads/b.docx", "/uploads/c.png"],
            duration=50,
            uploader_id=self.user.id,
        )
        db.session.flush()
        self.assertIs(synced, self.item)
        self.assertEqual(
            (self.item.exam_system, self.item.module, self.item.task_name),
            ("词汇", "词汇", "单词默写"),
        )
        self.assertEqual(self.item.resource_type, PlanItem.RESOURCE_DICTATION)
        self.assertEqual(self.item.resource_id, "dictation_book:7")
        self.assertEqual(
            json.loads(self.item.resource_metadata),
            {
                "vocabulary_goal": "writing",
                "learning_goal": "writing",
                "dictation_mode": "zh_to_en",
                "dictation_order": "random",
                "dictation_word_start": 8,
                "dictation_word_end": 16,
            },
        )
        self.assertEqual(self.item.student_status, PlanItem.STUDENT_SUBMITTED)
        self.assertEqual(self.item.submitted_at, self.task.submitted_at)
        self.assertEqual(self.item.actual_seconds, 50)
        self.assertEqual(self.item.student_comment, "练习完成")
        evidence = PlanEvidence.query.order_by(PlanEvidence.id).all()
        self.assertEqual([row.file_type for row in evidence], ["audio", "doc", "image"])
        self.assertEqual([row.original_filename for row in evidence], ["a.mp3", "b.docx", "c.png"])
        self.assertEqual({row.uploader_id for row in evidence}, {self.user.id})
        # The caller still owns the transaction, including all evidence writes.
        db.session.rollback()
        self.assertEqual(PlanEvidence.query.count(), 0)
        self.assertEqual(self.item.student_status, PlanItem.STUDENT_PENDING)

    def test_legacy_wrapper_uses_request_uploader_and_preserves_higher_time(self):
        with self.app.test_request_context("/"):
            request.current_api_user = self.user
            _sync_plan_item_from_legacy_task(
                self.task, evidence_files=["/uploads/old.wav"], duration=10
            )
        db.session.flush()
        self.assertEqual(self.item.actual_seconds, 40)
        self.assertEqual(PlanEvidence.query.one().uploader_id, self.user.id)

    def test_missing_item_returns_none_without_request_context(self):
        self.assertIsNone(_sync_plan_item_from_legacy_task(SimpleNamespace(plan_item=None)))

    def test_non_vocabulary_metadata_and_comment_are_preserved(self):
        self.task.dictation_book_id = None
        self.item.resource_metadata = '{"keep":true}'
        self.item.exam_system = "雅思"
        self.item.student_comment = "已有评语"
        self.task.actual_seconds = 70
        sync_plan_item_from_task_submission(self.task)
        self.assertEqual(self.item.resource_metadata, '{"keep":true}')
        self.assertEqual(self.item.exam_system, "雅思")
        self.assertEqual(self.item.student_comment, "已有评语")
        self.assertEqual(self.item.actual_seconds, 70)

    def test_course_label_and_legacy_defaults_preserved(self):
        self.item.exam_system = "托福"
        self.task.dictation_order = "unknown"
        self.task.dictation_mode = None
        self.task.dictation_word_start = None
        sync_plan_item_from_task_submission(self.task, note="文" * 300)
        metadata = json.loads(self.item.resource_metadata)
        self.assertEqual(self.item.exam_system, "托福")
        self.assertEqual(metadata["dictation_order"], "sequence")
        self.assertEqual(metadata["dictation_mode"], "audio_to_en")
        self.assertEqual(metadata["dictation_word_start"], 1)
        self.assertEqual(len(self.item.student_comment), 255)
