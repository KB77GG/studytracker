"""Read-only task-list helpers include only valid, owned vocabulary flows."""

import unittest
from datetime import datetime
from types import SimpleNamespace

from flask import Flask
from sqlalchemy import event

from models import DictationBook, Task, VocabularyLearningFlow, db
from services.practice_vocabulary_tasks import (
    vocabulary_flow_states,
    vocabulary_practice_fields,
    vocabulary_task_clause,
)


class PracticeVocabularyTasksTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:", SQLALCHEMY_TRACK_MODIFICATIONS=False
        )
        db.init_app(self.app)
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        self.book = DictationBook(title="合成词书", word_count=30, created_by=1)
        db.session.add(self.book)
        db.session.flush()
        self.tasks = []
        for goal in (
            " reading ",
            "writing",
            "listening",
            "comprehensive",
            None,
            "spelling_drill",
            "invalid",
        ):
            task = Task(
                student_name="合成列表学生",
                category="词汇",
                created_by=1,
                dictation_book_id=self.book.id,
                vocabulary_goal=goal,
                dictation_word_start=8,
                dictation_word_end=16,
            )
            db.session.add(task)
            self.tasks.append(task)
        no_book = Task(
            student_name="合成列表学生", category="词汇", created_by=1, vocabulary_goal="reading"
        )
        db.session.add(no_book)
        self.tasks.append(no_book)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        db.engine.dispose()
        self.context.pop()

    def _flow(self, task, student, state):
        flow = VocabularyLearningFlow(
            student_id=student,
            task_id=task.id,
            book_id=self.book.id,
            vocabulary_goal="reading",
            group_size=10,
            total_word_count=9,
            total_group_count=1,
            groups_json="[]",
            queue_token=f"flow-{task.id}-{student}",
            status=state,
            started_at=datetime(2026, 11, 26),
        )
        db.session.add(flow)

    def test_clause_and_payload_reject_legacy_missing_book_and_invalid_goal(self):
        actual = Task.query.filter(vocabulary_task_clause()).order_by(Task.id).all()
        self.assertEqual([task.id for task in actual], [task.id for task in self.tasks[:4]])
        for task in self.tasks[4:]:
            self.assertIsNone(vocabulary_practice_fields(task))

    def test_title_goal_url_and_flow_status_are_read_only(self):
        task = self.tasks[0]
        fields = vocabulary_practice_fields(task, "active")
        self.assertEqual(
            fields,
            {
                "category": "词汇",
                "source_label": "阅读词汇",
                "title": "合成词书 · 第8–16词",
                "url": f"/practice/vocabulary/tasks/{task.id}",
                "in_progress": True,
            },
        )
        self.assertFalse(db.session.dirty or db.session.new)
        task.dictation_word_end = None
        self.assertEqual(vocabulary_practice_fields(task)["title"], "合成词书 · 第8词起")
        task.detail = "老师指定标题"
        self.assertEqual(vocabulary_practice_fields(task, "completed")["title"], task.detail)
        self.assertFalse(vocabulary_practice_fields(task, "completed")["in_progress"])

    def test_states_are_batched_and_never_borrow_another_students_flow(self):
        self._flow(self.tasks[0], 10, "active")
        self._flow(self.tasks[1], 10, "completed")
        self._flow(self.tasks[2], 20, "active")
        db.session.commit()
        task_ids = [task.id for task in self.tasks]
        selects = []

        def track(conn, cursor, statement, parameters, context, executemany):
            if statement.lstrip().upper().startswith("SELECT"):
                selects.append(statement)

        event.listen(db.engine, "before_cursor_execute", track)
        try:
            states = vocabulary_flow_states(SimpleNamespace(user_id=10), self.tasks)
        finally:
            event.remove(db.engine, "before_cursor_execute", track)
        self.assertEqual(states, {task_ids[0]: "active", task_ids[1]: "completed"})
        self.assertEqual(len(selects), 1)
        self.assertFalse(db.session.dirty or db.session.new)
        self.assertEqual(vocabulary_flow_states(SimpleNamespace(user_id=None), self.tasks), {})
        self.assertEqual(VocabularyLearningFlow.query.count(), 3)
