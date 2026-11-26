"""Independent multi-client, two-connection and parent-projection checks.

Only synthetic fixtures in a temporary SQLite file are used. A barrier forces
both concurrent HTTP requests past their first-answer lookup before either can
write; no application or grading functions are replaced with fake results.
"""

import json
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

import jwt
from flask import Flask
from flask_login import LoginManager
from jinja2 import DictLoader
from sqlalchemy import event

from api.dictation import dictation_bp
from api.miniprogram import mp_bp
from api.practice_vocabulary import practice_vocabulary_bp
from api.vocab_review import vocab_review_bp
from models import (
    DictationBook,
    DictationRecord,
    DictationWord,
    ParentStudentLink,
    PlanEvidence,
    PlanItem,
    StudentProfile,
    StudentVocabularyMastery,
    StudyPlan,
    Task,
    User,
    VocabularyLearningFlow,
    VocabularyLearningQuestion,
    VocabularyReviewSession,
    VocabularyTaskSettlement,
    db,
)
from services import vocabulary_group_learning as learning
from services.task_date_gate import beijing_today


class VocabularyWebAdversarialTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="web-vocabulary-adversarial-")
        self.app = Flask(__name__)
        self.app.config.update(
            SECRET_KEY="synthetic-adversarial-secret-at-least-32-bytes",
            TESTING=True,
            PRACTICE_VOCABULARY_WEB_ENABLED=True,
            SQLALCHEMY_DATABASE_URI=f"sqlite:///{Path(self.temp.name) / 'fixture.sqlite'}",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            SQLALCHEMY_ENGINE_OPTIONS={"connect_args": {"timeout": 2}},
        )
        self.app.jinja_loader = DictLoader(
            {"practice/vocabulary_task.html": "{{ boot_data|tojson }}"}
        )
        db.init_app(self.app)
        manager = LoginManager(self.app)
        manager.user_loader(lambda uid: db.session.get(User, int(uid)))
        for blueprint in (dictation_bp, mp_bp, vocab_review_bp, practice_vocabulary_bp):
            self.app.register_blueprint(blueprint)
        with self.app.app_context():
            db.create_all()
            teacher, student, parent = [
                User(
                    username=f"adversarial-{role}", password_hash="test", role=role, is_active=True
                )
                for role in ("teacher", "student", "parent")
            ]
            db.session.add_all([teacher, student, parent])
            db.session.flush()
            profile = StudentProfile(user_id=student.id, full_name="独立合成学生")
            db.session.add(profile)
            db.session.flush()
            db.session.add(
                ParentStudentLink(
                    parent_id=parent.id, student_name=profile.full_name, is_active=True
                )
            )
            book = DictationBook(
                title="独立合成词书", word_count=3, created_by=teacher.id, is_active=True
            )
            db.session.add(book)
            db.session.flush()
            for index, (word, meaning, pattern, example) in enumerate(
                [
                    ("depend", "依赖", "depend on", "We depend on clear feedback."),
                    ("focus", "集中", "focus on", "We focus on the main idea."),
                    ("achieve", "实现", "achieve a goal", "We achieve a useful goal."),
                ],
                1,
            ):
                db.session.add(
                    DictationWord(
                        book_id=book.id,
                        sequence=index,
                        word=word,
                        translation=meaning,
                        core_meaning_zh=meaning,
                        phonetic=f"/{word}/",
                        usage_pattern=pattern,
                        example_en=example,
                    )
                )
            plan = StudyPlan(
                student_id=profile.id, plan_date=beijing_today(), created_by=teacher.id
            )
            db.session.add(plan)
            db.session.flush()
            item = PlanItem(
                plan_id=plan.id,
                exam_system="雅思",
                module="词汇",
                task_name="合成词汇任务",
                actual_seconds=15,
            )
            db.session.add(item)
            db.session.flush()
            task = Task(
                student_name=profile.full_name,
                date=beijing_today().isoformat(),
                category="词汇",
                created_by=teacher.id,
                plan_item_id=item.id,
                dictation_book_id=book.id,
                vocabulary_goal="listening",
                dictation_mode="audio_to_en",
                dictation_word_start=1,
                dictation_word_end=3,
            )
            db.session.add(task)
            db.session.commit()
            self.task_id, self.student_id, self.parent_id, self.item_id = (
                task.id,
                student.id,
                parent.id,
                item.id,
            )
        self.client, self.web_headers = self._web_client()
        self.mini_client = self.app.test_client()
        self.mini_headers = self._bearer(self.student_id, "student")
        self.base = f"/api/practice/vocabulary/tasks/{self.task_id}"

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.engine.dispose()
        self.temp.cleanup()

    def _bearer(self, user_id, role):
        token = jwt.encode(
            {"sub": str(user_id), "role": role}, self.app.config["SECRET_KEY"], algorithm="HS256"
        )
        return {"Authorization": f"Bearer {token}"}

    def _web_client(self):
        client = self.app.test_client()
        with client.session_transaction() as session:
            session["practice_student_name"] = "独立合成学生"
        response = client.get(f"/practice/vocabulary/tasks/{self.task_id}")
        self.assertEqual(response.status_code, 200)
        boot = json.loads(response.data)
        return client, {
            "X-CSRF-Token": boot["csrf_token"],
            "X-Practice-Identity": boot["identity_key"],
        }

    def _post(self, action, payload=None, expected=200):
        response = self.client.post(
            f"{self.base}/{action}", json=payload or {}, headers=self.web_headers
        )
        self.assertEqual(response.status_code, expected, response.get_json())
        return response.get_json()

    def _view(self):
        flow = self._post("sync")["flow"]
        while flow["phase"] == "familiarity":
            row = next(row for row in flow["familiarity"] if not row["viewed"])
            flow = self._post(
                "familiarity", {"queue_token": flow["queue_token"], "word_id": row["word_id"]}
            )["flow"]
        return flow

    def _answer_payload(self, flow, *, wrong=False):
        question = flow["current_question"]
        with self.app.app_context():
            row = db.session.get(VocabularyLearningQuestion, question["learning_question_id"])
            answer = json.loads(row.answer_payload_json)
        result = {
            key: question[key]
            for key in (
                "learning_question_id",
                "queue_item_id",
                "question_id",
                "word_id",
                "sense_id",
                "dimension",
            )
        }
        result.update(
            queue_token=flow["queue_token"],
            attempt_id=f"vocabulary-group:{self.task_id}:{'retry' if flow['retry'] else 'first'}:{question['learning_question_id']}",
            retry=bool(flow["retry"]),
            input_mode="native",
            answer="wrong" if wrong else answer.get("answer_option_id") or answer["answer"],
        )
        return result

    def _finish(self):
        for _ in range(60):
            flow = self._post("sync")["flow"]
            if flow["completed"]:
                return flow
            self._post("answers", self._answer_payload(flow))
        self.fail("synthetic learning did not finish")

    def test_two_connections_same_attempt_commit_exactly_one_first_answer(self):
        flow = self._view()
        payload = self._answer_payload(flow)
        other_client, other_headers = self._web_client()
        barrier = threading.Barrier(2)
        connections = set()
        guard = threading.Lock()
        original = learning._current_question

        def rendezvous(current_flow):
            question = original(current_flow)
            raw_connection = db.session.connection().connection.driver_connection
            with guard:
                connections.add(id(raw_connection))
            barrier.wait(timeout=5)
            return question

        def answer(client, headers):
            response = client.post(f"{self.base}/answers", json=payload, headers=headers)
            return response.status_code, response.get_json()

        with patch.object(learning, "_current_question", side_effect=rendezvous):
            with ThreadPoolExecutor(max_workers=2) as executor:
                jobs = [
                    executor.submit(answer, self.client, self.web_headers),
                    executor.submit(answer, other_client, other_headers),
                ]
                responses = [job.result(timeout=10) for job in jobs]
        self.assertEqual(len(connections), 2, "test must use two real SQLite connections")
        self.assertIn(200, [status for status, _ in responses], responses)
        for status, body in responses:
            self.assertIn(status, (200, 409), body)
            if status == 409:
                self.assertEqual(body["error"], "state_conflict")
        recovered = self._post("answers", payload)
        self.assertTrue(recovered["feedback"]["idempotent"])
        with self.app.app_context():
            records = DictationRecord.query.filter_by(attempt_id=payload["attempt_id"]).all()
            self.assertEqual(len(records), 1)
            self.assertTrue(records[0].is_first_attempt)
            question = db.session.get(VocabularyLearningQuestion, payload["learning_question_id"])
            self.assertEqual(question.first_attempt_id, payload["attempt_id"])
            mastery = StudentVocabularyMastery.query.filter_by(
                student_id=self.student_id, sense_id=question.sense_id
            ).one()
            self.assertEqual(getattr(mastery, f"{question.dimension}_stage"), 1)
            self.assertEqual(DictationRecord.query.count(), 1)

    def test_distinct_web_and_bearer_clients_alternate_and_keep_first_scores(self):
        flow = self._view()
        web_payload = self._answer_payload(flow)
        self._post("answers", web_payload)
        replay = self.mini_client.post(
            "/api/dictation/submit",
            json={**web_payload, "task_id": self.task_id, "answer": "late changed input"},
            headers=self.mini_headers,
        )
        self.assertEqual(replay.status_code, 200)
        self.assertTrue(replay.get_json()["idempotent"])
        self.assertEqual(replay.get_json()["student_answer"], web_payload["answer"])
        queue_response = self.mini_client.get(
            f"/api/miniprogram/student/tasks/{self.task_id}/vocabulary-queue",
            headers=self.mini_headers,
        )
        self.assertEqual(queue_response.status_code, 200)
        flow = queue_response.get_json()
        mini_payload = self._answer_payload(flow, wrong=True)
        saved = self.mini_client.post(
            "/api/dictation/submit",
            json={**mini_payload, "task_id": self.task_id},
            headers=self.mini_headers,
        )
        self.assertEqual(saved.status_code, 200)
        self.assertFalse(saved.get_json()["is_correct"])
        replay = self._post("answers", dict(mini_payload, answer="late edited answer"))
        self.assertTrue(replay["feedback"]["idempotent"])
        self.assertEqual(replay["feedback"]["student_answer"], "wrong")
        complete = self._finish()
        result = self._post(
            "settle", {"queue_token": complete["queue_token"], "duration_seconds": 83}
        )["settlement"]
        self.assertEqual(
            (result["correct_count"], result["total_count"], result["accuracy"]), (5, 6, 83.3)
        )
        with self.app.app_context():
            self.assertEqual(VocabularyLearningFlow.query.count(), 1)
            self.assertEqual(DictationRecord.query.filter_by(is_first_attempt=True).count(), 6)
            stored = db.session.get(
                VocabularyLearningQuestion, mini_payload["learning_question_id"]
            )
            self.assertFalse(stored.first_is_correct)
            self.assertTrue(stored.retry_is_correct)

    def test_web_settlement_matches_plan_and_existing_parent_api(self):
        flow = self._view()
        self._post("answers", self._answer_payload(flow, wrong=True))
        complete = self._finish()
        settled = self._post(
            "settle", {"queue_token": complete["queue_token"], "duration_seconds": 65}
        )["settlement"]
        self.assertEqual(
            (settled["correct_count"], settled["total_count"], settled["accuracy"]),
            (5, 6, 83.3),
        )
        response = self.mini_client.get(
            f"/api/miniprogram/parent/tasks/{self.task_id}",
            headers=self._bearer(self.parent_id, "parent"),
        )
        self.assertEqual(response.status_code, 200)
        detail = response.get_json()["detail"]
        self.assertEqual(
            (detail["state"], detail["accuracy"], detail["completion_rate"]),
            ("completed", settled["accuracy"], 100),
        )
        self.assertEqual(
            (detail["summary"]["assigned_total"], detail["summary"]["attempted_total"]), (3, 3)
        )
        with self.app.app_context():
            task, item = db.session.get(Task, self.task_id), db.session.get(PlanItem, self.item_id)
            self.assertEqual((task.actual_seconds, item.actual_seconds), (65, 65))
            self.assertEqual((task.status, item.student_status), ("done", "submitted"))
            self.assertEqual(item.submitted_at, task.submitted_at)
            self.assertEqual(detail["submitted_at"], task.submitted_at.isoformat())
            metadata = json.loads(item.resource_metadata)
            self.assertEqual(
                (
                    metadata["vocabulary_goal"],
                    metadata["dictation_word_start"],
                    metadata["dictation_word_end"],
                ),
                ("listening", 1, 3),
            )
            before = (
                DictationRecord.query.count(),
                StudentVocabularyMastery.query.count(),
                VocabularyReviewSession.query.count(),
                PlanEvidence.query.count(),
            )
        self._post("settle", {"queue_token": complete["queue_token"], "duration_seconds": 900})
        with self.app.app_context():
            self.assertEqual(
                (
                    DictationRecord.query.count(),
                    StudentVocabularyMastery.query.count(),
                    VocabularyReviewSession.query.count(),
                    PlanEvidence.query.count(),
                ),
                before,
            )
            self.assertEqual(
                (
                    db.session.get(Task, self.task_id).actual_seconds,
                    db.session.get(PlanItem, self.item_id).actual_seconds,
                ),
                (65, 65),
            )
            self.assertEqual(VocabularyTaskSettlement.query.count(), 1)

    def test_feature_off_rejects_every_endpoint_without_sql_writes(self):
        flow = self._view()
        self.app.config["PRACTICE_VOCABULARY_WEB_ENABLED"] = False
        writes = []
        with self.app.app_context():

            def record(conn, cursor, statement, params, context, many):
                if statement.lstrip().split()[0].upper() in {"INSERT", "UPDATE", "DELETE"}:
                    writes.append(statement)

            event.listen(db.engine, "before_cursor_execute", record)
            try:
                self.assertEqual(
                    self.client.get(f"/practice/vocabulary/tasks/{self.task_id}").status_code, 403
                )
                self.assertEqual(self.client.get(f"{self.base}/state").status_code, 403)
                for action in (
                    "sync",
                    "familiarity",
                    "answers",
                    "corrections",
                    "settle",
                    "review/claim",
                    "review/answers",
                    "review/corrections",
                    "review/settle",
                ):
                    body = self._post(action, {"queue_token": flow["queue_token"]}, expected=403)
                    self.assertEqual(body["error"], "feature_disabled")
                self.assertEqual(writes, [])
                self.assertEqual(DictationRecord.query.count(), 0)
                self.assertEqual(VocabularyTaskSettlement.query.count(), 0)
                self.assertEqual(VocabularyReviewSession.query.count(), 0)
            finally:
                event.remove(db.engine, "before_cursor_execute", record)

    def test_active_retry_and_nested_conflict_payloads_hide_current_and_future_answers(self):
        with self.app.app_context():
            task = db.session.get(Task, self.task_id)
            task.vocabulary_goal = "writing"
            db.session.commit()
        flow = self._view()
        words = ("depend", "focus", "achieve")
        self.assertEqual(flow["current_question"]["mode"], "zh_to_en")
        self.assertTrue(all(word not in json.dumps(flow) for word in words))
        self.assertNotIn("questions", flow)
        payload = self._answer_payload(flow, wrong=True)
        conflict = self._post("answers", dict(payload, queue_token="wrong-token"), expected=409)
        self.assertEqual(conflict["error"], "queue_changed")
        self.assertTrue(all(word not in json.dumps(conflict) for word in words))
        self.assertEqual(
            conflict["state"]["current_question"]["learning_question_id"],
            payload["learning_question_id"],
        )
        self._post("answers", payload)
        for _ in range(40):
            current = self._post("sync")["flow"]
            if current["retry"]:
                q = current["current_question"]
                self.assertEqual(q["learning_question_id"], payload["learning_question_id"])
                self.assertNotIn("revealed_answer", q)
                self.assertNotIn("first_answer", q)
                self.assertNotIn("answer_feedback", q)
                self.assertTrue(all(word not in json.dumps(q) for word in words))
                break
            self._post("answers", self._answer_payload(current))
        else:
            self.fail("wrong first answer never reached bounded retry")

    def test_get_state_is_read_only_through_unsaved_settlement_and_cutoff(self):
        self._view()
        complete = self._finish()
        with self.app.app_context():
            flow = VocabularyLearningFlow.query.one()
            before = (flow.state_version, flow.phase, flow.current_group_index)
        for stage in ("in_progress", "result"):
            writes = []
            with self.app.app_context():

                def record(conn, cursor, statement, params, context, many, writes=writes):
                    if statement.lstrip().split()[0].upper() in {"INSERT", "UPDATE", "DELETE"}:
                        writes.append(statement)

                event.listen(db.engine, "before_cursor_execute", record)
                try:
                    response = self.client.get(f"{self.base}/state")
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.get_json()["stage"], stage)
                    self.assertEqual(writes, [])
                    self.assertFalse(db.session.dirty or db.session.new)
                finally:
                    event.remove(db.engine, "before_cursor_execute", record)
            if stage == "in_progress":
                self._post("settle", {"queue_token": complete["queue_token"]})
                with self.app.app_context():
                    item = db.session.get(PlanItem, self.item_id)
                    item.plan.plan_date = beijing_today() - timedelta(days=2)
                    db.session.commit()
        with self.app.app_context():
            flow = VocabularyLearningFlow.query.one()
            self.assertEqual((flow.state_version, flow.phase, flow.current_group_index), before)
