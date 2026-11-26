"""Real SQLite/domain integration for the desktop task adapter, with no network."""

import io
import json
import unittest
from datetime import datetime, time, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from jinja2 import DictLoader
from sqlalchemy import event
from sqlalchemy.exc import OperationalError

from api.practice_vocabulary import practice_vocabulary_bp
from models import (
    DictationRecord,
    DictationWord,
    StudentProfile,
    StudentVocabularyMastery,
    Task,
    User,
    VocabularyLearningFlow,
    VocabularyLearningQuestion,
    VocabularyReviewAttempt,
    VocabularyReviewItem,
    VocabularyReviewSession,
    VocabularyReviewSettlement,
    VocabularyTaskReview,
    VocabularyTaskSettlement,
    db,
)
from services.task_date_gate import beijing_today
from services.vocabulary_context import build_context_question
from services.vocabulary_mastery import ensure_mastery, ensure_word_sense
from services.vocabulary_synonyms import synonym_sense_key
from tests import test_vocabulary_group_learning_api as fixture


class VocabularyWebRoutesTest(unittest.TestCase):
    tearDown = fixture.VocabularyGroupLearningApiTest.tearDown
    _task = fixture.VocabularyGroupLearningApiTest._task

    def setUp(self):
        fixture.VocabularyGroupLearningApiTest.setUp(self)
        self.app.config["PRACTICE_VOCABULARY_WEB_ENABLED"] = True
        self.app.jinja_loader = DictLoader(
            {"practice/vocabulary_task.html": "{{ boot_data|tojson }}"}
        )
        self.app.register_blueprint(practice_vocabulary_bp)
        with self.client.session_transaction() as session:
            session["practice_student_name"] = "HTTP 小组学生"
        response = self.client.get(f"/practice/vocabulary/tasks/{self.task_id}")
        self.assertEqual(response.status_code, 200)
        self.boot = json.loads(response.data)
        self.web_headers = {
            "X-CSRF-Token": self.boot["csrf_token"],
            "X-Practice-Identity": self.boot["identity_key"],
        }

    def _post(self, action, payload=None, task_id=None, expected=200):
        response = self.client.post(
            f"/api/practice/vocabulary/tasks/{task_id or self.task_id}/{action}",
            json=payload or {},
            headers=self.web_headers,
        )
        self.assertEqual(response.status_code, expected, response.get_json())
        return response.get_json()

    def _state(self, task_id=None):
        response = self.client.get(
            f"/api/practice/vocabulary/tasks/{task_id or self.task_id}/state"
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        return response.get_json()

    def _stream_request(
        self, body, *, length=None, terminated=False, chunk_size=None, chunked=False
    ):
        class ObservedInput:
            def __init__(self):
                self.buffer = io.BytesIO(body)
                self.bytes_read = 0
                self.read_sizes = []

            def read(self, size=-1):
                if not 0 <= size <= 16_385:
                    raise AssertionError(f"unbounded body read: {size}")
                self.read_sizes.append(size)
                chunk = self.buffer.read(min(size, chunk_size) if chunk_size else size)
                self.bytes_read += len(chunk)
                return chunk

        stream = ObservedInput()
        environ = {"wsgi.input": stream, "CONTENT_TYPE": "application/json", "CONTENT_LENGTH": ""}
        if length is not None:
            environ["CONTENT_LENGTH"] = str(length)
        if terminated:
            environ["wsgi.input_terminated"] = True
        if chunked:
            environ["HTTP_TRANSFER_ENCODING"] = "chunked"
        response = self.client.post(
            f"/api/practice/vocabulary/tasks/{self.task_id}/sync",
            headers=self.web_headers,
            environ_overrides=environ,
        )
        return response, stream

    def _question_payload(self, flow, task_id=None, wrong=False, forgot=False):
        question = flow["current_question"]
        with self.app.app_context():
            stored = db.session.get(VocabularyLearningQuestion, question["learning_question_id"])
            expected = json.loads(stored.answer_payload_json)
        answer = expected.get("answer_option_id") or expected.get("answer")
        return {
            **{
                key: question[key]
                for key in (
                    "learning_question_id",
                    "queue_item_id",
                    "question_id",
                    "word_id",
                    "sense_id",
                    "dimension",
                )
            },
            "queue_token": flow["queue_token"],
            "attempt_id": f"vocabulary-group:{task_id or self.task_id}:{'retry' if flow.get('retry') else 'first'}:{question['learning_question_id']}",
            "retry": bool(flow.get("retry")),
            "answer": "" if forgot else "wrong" if wrong else answer,
            "response_kind": "forgot" if forgot else "answer",
        }

    def _view(self, task_id=None):
        flow = self._post("sync", task_id=task_id)["flow"]
        while flow["phase"] == "familiarity":
            word = next(row for row in flow["familiarity"] if not row["viewed"])
            flow = self._post(
                "familiarity",
                {"queue_token": flow["queue_token"], "word_id": word["word_id"]},
                task_id,
            )["flow"]
        return flow

    def _finish(self, task_id=None):
        for _ in range(120):
            flow = self._post("sync", task_id=task_id)["flow"]
            if flow["completed"]:
                return flow
            if flow["phase"] == "familiarity":
                self._view(task_id)
            elif flow["correction_required"]:
                question = flow["current_question"]
                self._post(
                    "corrections",
                    {
                        "queue_token": flow["queue_token"],
                        "learning_question_id": question["learning_question_id"],
                        "answer": question["revealed_answer"],
                        "attempt_id": f"correct:{question['learning_question_id']}:{question.get('correction_count', 0)}",
                    },
                    task_id,
                )
            else:
                self._post("answers", self._question_payload(flow, task_id), task_id)
        self.fail("flow never completed")

    def _seed_due(self):
        with self.app.app_context():
            user = db.session.get(User, self.student_id)
            word = DictationWord.query.order_by(DictationWord.id).first()
            mastery = ensure_mastery(user, word, ensure_word_sense(word))
            mastery.meaning_recall_stage = 1
            mastery.meaning_recall_next_due_at = datetime.utcnow() - timedelta(days=1)
            db.session.commit()

    def test_page_and_get_state_do_not_create_or_modify_learning(self):
        self.assertNotIn("question", self.boot)
        with self.app.app_context():
            writes = []

            def record(conn, cursor, statement, params, context, many):
                if statement.lstrip().split()[0].upper() in {"UPDATE", "INSERT", "DELETE"}:
                    writes.append(statement)

            event.listen(db.engine, "before_cursor_execute", record)
            try:
                self.assertEqual(self._state()["stage"], "not_started")
                self.assertEqual(self._state()["stage"], "not_started")
                self.assertEqual(VocabularyLearningFlow.query.count(), 0)
                self.assertEqual(writes, [])
            finally:
                event.remove(db.engine, "before_cursor_execute", record)

    def test_resume_and_duplicate_answer_share_one_record_with_miniprogram(self):
        flow = self._view()
        payload = self._question_payload(flow)
        response = self._post("answers", payload)
        self.assertTrue(response["feedback"]["is_correct"])
        duplicate = self.client.post(
            "/api/dictation/submit",
            json={**payload, "task_id": self.task_id, "input_mode": "native"},
            headers=self.headers,
        )
        self.assertEqual(duplicate.status_code, 200)
        self.assertTrue(duplicate.get_json()["idempotent"])
        again = self._post("answers", payload)
        self.assertTrue(again["feedback"]["idempotent"])
        resumed = self._post("sync", {"attempt_id": payload["attempt_id"]})["flow"]
        self.assertEqual(resumed["saved_response"]["attempt_id"], payload["attempt_id"])
        self.assertEqual(self._state()["stage"], "in_progress")
        with self.app.app_context():
            self.assertEqual(DictationRecord.query.count(), 1)
            self.assertEqual(DictationRecord.query.one().input_mode, "native")

    def test_all_four_goals_finish_and_settlement_replay_is_read_only(self):
        modes = set()
        for goal in ("reading", "writing", "listening", "comprehensive"):
            with self.subTest(goal=goal):
                task_id = self._task(goal)
                self._view(task_id)
                with self.app.app_context():
                    modes.update(
                        json.loads(q.question_snapshot_json)["mode"]
                        for q in VocabularyLearningQuestion.query.filter_by(task_id=task_id).all()
                    )
                complete = self._finish(task_id)
                result = self._post(
                    "settle",
                    {"queue_token": complete["queue_token"], "duration_seconds": 75},
                    task_id,
                )
                self.assertEqual(result["stage"], "result")
                self.assertEqual(result["settlement"]["accuracy"], 100)
                repeated = self._post(
                    "settle",
                    {"queue_token": complete["queue_token"], "duration_seconds": 999},
                    task_id,
                )
                self.assertTrue(repeated["already_settled"])
                self.assertEqual(self._state(task_id)["stage"], "result")
                with self.app.app_context():
                    self.assertEqual(db.session.get(Task, task_id).actual_seconds, 75)
                    self.assertEqual(
                        VocabularyTaskSettlement.query.filter_by(task_id=task_id).count(), 1
                    )
        self.assertEqual(
            modes,
            {
                "en_to_zh",
                "zh_to_en",
                "audio_to_zh",
                "audio_to_en",
                "context_choice",
                "context_fill",
            },
        )

    def test_forgot_then_retry_keeps_first_score_and_hides_answer(self):
        flow = self._view()
        result = self._post("answers", self._question_payload(flow, forgot=True))
        self.assertEqual(result["feedback"]["response_kind"], "forgot")
        self.assertFalse(result["feedback"]["is_correct"])
        complete = self._finish()
        result = self._post("settle", {"queue_token": complete["queue_token"]})
        self.assertEqual(result["settlement"]["correct_count"], 1)
        self.assertEqual(result["settlement"]["total_count"], 2)
        self.assertEqual(result["settlement"]["scored_forgotten_count"], 1)

    def test_comprehensive_pending_correction_survives_sync_and_is_bounded(self):
        task_id = self._task("comprehensive")
        flow = self._view(task_id)
        result = self._post("answers", self._question_payload(flow, task_id, wrong=True), task_id)
        self.assertTrue(result["feedback"]["correction_required"])
        flow = self._post("sync", task_id=task_id)["flow"]
        self.assertTrue(flow["correction_required"])
        q = flow["current_question"]
        self.assertTrue(q["revealed_answer"])
        for count in (1, 2):
            result = self._post(
                "corrections",
                {
                    "learning_question_id": q["learning_question_id"],
                    "queue_token": flow["queue_token"],
                    "answer": "wrong",
                    "attempt_id": f"correction:{q['learning_question_id']}:{count}",
                },
                task_id,
            )
            self.assertEqual(result["feedback"]["correction_count"], count)
        self.assertTrue(result["feedback"]["correction_exhausted"])
        self.assertFalse(self._post("sync", task_id=task_id)["flow"]["correction_required"])

    def test_old_client_keeps_existing_correction_release(self):
        task_id = self._task("comprehensive")
        flow = self._view(task_id)
        self._post("answers", self._question_payload(flow, task_id, wrong=True), task_id)
        response = self.client.get(
            f"/api/miniprogram/student/tasks/{task_id}/vocabulary-queue", headers=self.headers
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get_json()["correction_required"])

    def test_security_headers_types_size_origin_and_identity_drift(self):
        base = f"/api/practice/vocabulary/tasks/{self.task_id}/sync"
        for headers, expected, code in [
            ({}, 403, "csrf"),
            ({**self.web_headers, "X-Practice-Identity": "old"}, 409, "identity_changed"),
            ({**self.web_headers, "Origin": "https://evil.example"}, 403, "csrf"),
        ]:
            with self.subTest(code=code):
                response = self.client.post(base, json={}, headers=headers)
                self.assertEqual(response.status_code, expected)
                self.assertEqual(response.get_json()["error"], code)
        self.assertEqual(self.client.post(base, json=[], headers=self.web_headers).status_code, 400)
        self.assertEqual(
            self.client.post(base, data="x", headers=self.web_headers).status_code, 415
        )
        self.assertEqual(
            self.client.post(base, json={"a": "x" * 17000}, headers=self.web_headers).status_code,
            413,
        )

    def test_feature_off_missing_identity_foreign_and_unsupported_tasks(self):
        self.app.config["PRACTICE_VOCABULARY_WEB_ENABLED"] = False
        self.assertEqual(
            self.client.get(f"/practice/vocabulary/tasks/{self.task_id}").status_code, 403
        )
        self.app.config["PRACTICE_VOCABULARY_WEB_ENABLED"] = True
        with self.client.session_transaction() as session:
            session.pop("practice_student_name")
        self.assertEqual(
            self.client.get(f"/api/practice/vocabulary/tasks/{self.task_id}/state").status_code, 401
        )
        with self.client.session_transaction() as session:
            session["practice_student_name"] = "HTTP 小组学生"
        with self.app.app_context():
            task = db.session.get(Task, self.task_id)
            task.student_name = "另一位学生"
            db.session.commit()
        self.assertEqual(
            self.client.get(f"/api/practice/vocabulary/tasks/{self.task_id}/state").status_code, 404
        )
        with self.app.app_context():
            task = db.session.get(Task, self.task_id)
            task.student_name, task.vocabulary_goal = "HTTP 小组学生", None
            db.session.commit()
        self.assertEqual(
            self.client.get(f"/api/practice/vocabulary/tasks/{self.task_id}/state").status_code, 409
        )

    def test_feature_off_blocks_all_registered_routes_before_any_sql(self):
        # setUp obtained a real page with a valid, uniquely linked student.
        # Reuse that session and its actual tokens, so auth failure cannot pass
        # this test accidentally; every refusal must be feature_disabled.
        with self.client.session_transaction() as session:
            self.assertEqual(session["practice_student_name"], "HTTP 小组学生")
            self.assertEqual(session["practice_vocabulary_csrf"], self.boot["csrf_token"])
        headers = {**self.web_headers, "Origin": "http://localhost"}
        prefix = practice_vocabulary_bp.name + "."
        rules = [rule for rule in self.app.url_map.iter_rules() if rule.endpoint.startswith(prefix)]
        endpoints = {rule.endpoint.removeprefix(prefix) for rule in rules}
        self.assertTrue(
            {
                "task_page",
                "task_state",
                "sync",
                "familiarity",
                "answers",
                "corrections",
                "settle",
                "review_claim",
                "review_answers",
                "review_corrections",
                "review_settle",
            }.issubset(endpoints),
            endpoints,
        )
        learning_models = (
            DictationRecord,
            StudentVocabularyMastery,
            VocabularyLearningFlow,
            VocabularyLearningQuestion,
            VocabularyTaskReview,
            VocabularyTaskSettlement,
            VocabularyReviewSession,
            VocabularyReviewItem,
            VocabularyReviewAttempt,
            VocabularyReviewSettlement,
        )
        adapter = self.app.url_map.bind("localhost")
        with self.app.app_context():
            self.assertTrue(all(model.query.count() == 0 for model in learning_models))
            self.app.config["PRACTICE_VOCABULARY_WEB_ENABLED"] = False
            statements = []

            def record(conn, cursor, statement, params, context, many):
                statements.append(statement)

            event.listen(db.engine, "before_cursor_execute", record)
            try:
                for rule in rules:
                    self.assertEqual(rule.arguments, {"task_id"})
                    # HEAD/OPTIONS are Flask's automatically supplied methods;
                    # enumerate every registered page/API operation instead.
                    for method in sorted(rule.methods - {"HEAD", "OPTIONS"}):
                        path = adapter.build(
                            rule.endpoint, {"task_id": self.task_id}, method=method
                        )
                        with self.subTest(method=method, path=path):
                            options = {"method": method, "headers": headers}
                            if method != "GET":
                                options["json"] = {}
                            response = self.client.open(path, **options)
                            self.assertEqual(response.status_code, 403)
                            body = (
                                json.loads(response.data)
                                if rule.endpoint == prefix + "task_page"
                                else response.get_json()
                            )
                            self.assertEqual(body["error"], "feature_disabled")
                            self.assertEqual(statements, [], path)
            finally:
                event.remove(db.engine, "before_cursor_execute", record)
            self.assertTrue(all(model.query.count() == 0 for model in learning_models))
            self.assertEqual(db.session.get(Task, self.task_id).status, "pending")
            self.assertFalse(db.session.new or db.session.dirty)

    def test_staff_classroom_ambiguous_and_account_priority(self):
        with self.client.session_transaction() as session:
            session["classroom_unlocked"] = True
        self.assertEqual(
            self.client.get(f"/api/practice/vocabulary/tasks/{self.task_id}/state").status_code, 403
        )
        with self.client.session_transaction() as session:
            session.pop("classroom_unlocked")
        with self.app.app_context():
            db.session.add(StudentProfile(full_name="HTTP 小组学生"))
            db.session.commit()
        self.assertEqual(
            self.client.get(f"/api/practice/vocabulary/tasks/{self.task_id}/state").status_code, 409
        )
        with self.client.session_transaction() as session:
            session["_user_id"] = str(self.student_id)
            session["_fresh"] = True
        self.assertEqual(self._state()["stage"], "not_started")

    def test_future_and_expired_read_only_no_flow_or_write(self):
        for offset in (1, -2):
            with self.subTest(offset=offset):
                task_id = self._task("reading")
                with self.app.app_context():
                    task = db.session.get(Task, task_id)
                    task.date = (beijing_today() + timedelta(days=offset)).isoformat()
                    db.session.commit()
                self.assertEqual(self._state(task_id)["stage"], "read_only")
                self.assertEqual(self._post("sync", task_id=task_id)["stage"], "read_only")
                response = self._post(
                    "familiarity", {"word_id": 1, "queue_token": "x"}, task_id, expected=403
                )
                self.assertIn(
                    response["error"],
                    {"task_not_open", "task_future", "task_expired", "task_not_open_yet"},
                )
                with self.app.app_context():
                    self.assertEqual(
                        VocabularyLearningFlow.query.filter_by(task_id=task_id).count(), 0
                    )

    def test_premature_settlement_and_operational_failure_do_not_finish(self):
        flow = self._view()
        self._post("settle", {"queue_token": flow["queue_token"]}, expected=409)
        with patch(
            "api.practice_vocabulary.settle_vocabulary_group_submission",
            side_effect=OperationalError("synthetic", {}, Exception("locked")),
        ):
            self.assertEqual(
                self._post("settle", {"queue_token": flow["queue_token"]}, expected=409)["error"],
                "state_conflict",
            )
        with self.app.app_context():
            self.assertEqual(VocabularyTaskSettlement.query.count(), 0)
            self.assertNotEqual(db.session.get(Task, self.task_id).status, "done")

    def test_review_gate_claim_answer_settle_then_return_to_original_task(self):
        self._seed_due()
        self.assertEqual(self._state()["stage"], "review_gate")
        self.assertEqual(self._post("sync")["stage"], "review_gate")
        session = self._post("review/claim")["review"]
        same = self._post("review/claim")["review"]
        self.assertEqual(session["session_id"], same["session_id"])
        for item in session["items"]:
            with self.app.app_context():
                expected = json.loads(
                    db.session.get(VocabularyReviewItem, item["review_item_id"]).answer_payload_json
                )
            payload = {
                **{
                    key: item[key]
                    for key in ("review_item_id", "question_id", "word_id", "sense_id", "dimension")
                },
                "session_id": session["session_id"],
                "session_token": session["session_token"],
                "answer": expected.get("answer_option_id") or expected.get("answer"),
                "attempt_id": f"web-review:{item['review_item_id']}",
            }
            self._post("review/answers", dict(payload, session_token="wrong"), expected=404)
            response = self._post("review/answers", payload)
            self.assertTrue(response["feedback"]["is_correct"])
            self.assertTrue(response["feedback"]["answer_feedback"]["word"])
            self.assertIn("core_meaning_zh", response["feedback"]["answer_feedback"])
            self.assertIn("audio_tts_url", response["feedback"]["answer_feedback"])
        settled = self._post(
            "review/settle",
            {
                "session_id": session["session_id"],
                "session_token": session["session_token"],
                "queue_token": session["queue_token"],
            },
        )
        self.assertEqual(settled["stage"], "review_result")
        self.assertEqual(self._post("sync")["stage"], "learning")
        with self.app.app_context():
            self.assertEqual(VocabularyReviewSession.query.count(), 1)
            self.assertEqual(VocabularyLearningFlow.query.count(), 1)

    def test_malformed_origin_and_non_ascii_headers_fail_closed(self):
        path = f"/api/practice/vocabulary/tasks/{self.task_id}/sync"
        for extra in (
            {"Origin": "http://[broken"},
            {"Origin": "https://localhost:444"},
            {"Origin": "ftp://localhost"},
            {"X-CSRF-Token": "无效"},
            {"X-Practice-Identity": "无效"},
        ):
            response = self.client.post(path, json={}, headers={**self.web_headers, **extra})
            self.assertIn(response.status_code, (403, 409), response.get_json())
        response = self.client.post(
            path, json={}, headers={**self.web_headers, "Origin": "http://localhost"}
        )
        self.assertEqual(response.status_code, 200)

    def test_https_origin_is_allowed_behind_http_proxy_without_forwarded_trust(self):
        path = f"/api/practice/vocabulary/tasks/{self.task_id}/sync"
        for origin in ("https://localhost", "http://localhost"):
            response = self.client.post(
                path,
                json={},
                headers={
                    **self.web_headers,
                    "Origin": origin,
                    "Forwarded": "host=evil.example;proto=ftp",
                    "X-Forwarded-Host": "evil.example",
                    "X-Forwarded-Proto": "ftp",
                },
                environ_overrides={"wsgi.url_scheme": "http"},
            )
            self.assertEqual(response.status_code, 200, response.get_json())
        for missing in ("X-CSRF-Token", "X-Practice-Identity"):
            headers = {**self.web_headers, "Origin": "https://localhost"}
            headers.pop(missing)
            response = self.client.post(path, json={}, headers=headers)
            self.assertIn(response.status_code, (403, 409))
        response = self.client.post(path, json={}, headers=self.web_headers)
        self.assertEqual(response.status_code, 200)  # Missing Origin remains compatible.
        response = self.client.post(
            path,
            base_url="http://localhost:5002",
            json={},
            headers={**self.web_headers, "Origin": "https://localhost:5002"},
        )
        self.assertEqual(response.status_code, 200, response.get_json())

    def test_origin_rejects_other_hosts_ports_and_non_origin_url_components(self):
        path = f"/api/practice/vocabulary/tasks/{self.task_id}/sync"
        for origin in (
            "https://evil.example",
            "https://localhost.evil.example",
            "https://localhost:444",
            "https://localhost:invalid",
            "https://localhost:99999",
            "https://user@localhost",
            "https://localhost/",
            "https://localhost?x=1",
            "https://localhost#fragment",
            "https://localhost?",
            "https://localhost#",
            "https://local\thost",
            " https://localhost",
            "https://localhost\\@evil.example",
            "https://[broken",
            "ftp://localhost",
            "//localhost",
            "null",
            "",
        ):
            with self.subTest(origin=origin):
                response = self.client.post(
                    path,
                    json={},
                    headers={
                        **self.web_headers,
                        "Origin": origin,
                        "Forwarded": "host=localhost;proto=https",
                        "X-Forwarded-Host": "localhost",
                        "X-Forwarded-Proto": "https",
                    },
                )
                self.assertEqual(response.status_code, 403)
                self.assertEqual(response.get_json()["error"], "csrf")
        with self.app.app_context():
            self.assertEqual(VocabularyLearningFlow.query.count(), 0)

    def test_declared_oversize_body_is_rejected_without_reading(self):
        response, stream = self._stream_request(b"{}", length=16_385)
        self.assertEqual(response.status_code, 413)
        self.assertEqual(response.get_json()["error"], "request_too_large")
        self.assertEqual(stream.read_sizes, [])
        with self.app.app_context():
            self.assertEqual(VocabularyLearningFlow.query.count(), 0)

    def test_streaming_bodies_stop_after_one_probe_byte_despite_missing_or_false_length(self):
        body = b"{}" + b" " * 200_000
        for length, chunked in ((None, False), (None, True), (2, False), (0, False)):
            with self.subTest(length=length, chunked=chunked):
                response, stream = self._stream_request(
                    body, length=length, terminated=True, chunk_size=113, chunked=chunked
                )
                self.assertEqual(response.status_code, 413)
                self.assertEqual(response.get_json()["error"], "request_too_large")
                self.assertEqual(stream.bytes_read, 16_385)
                self.assertGreater(len(stream.read_sizes), 1)
        with self.app.app_context():
            self.assertEqual(VocabularyLearningFlow.query.count(), 0)

    def test_exact_byte_limit_json_and_small_chunked_json_are_accepted(self):
        body = '{"padding":"词"}'.encode()
        body += b" " * (16_384 - len(body))
        for payload, length, terminated, chunked in (
            (body, len(body), False, False),
            (body, None, True, True),
            (b"{}", None, True, True),
        ):
            with self.subTest(length=length, terminated=terminated):
                response, stream = self._stream_request(
                    payload, length=length, terminated=terminated, chunked=chunked
                )
                self.assertEqual(response.status_code, 200, response.get_json())
                self.assertEqual(stream.bytes_read, len(payload))

    def test_unsafe_unknown_length_and_truncated_json_fail_without_unbounded_reads(self):
        response, stream = self._stream_request(b"{}" + b" " * 200_000)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "invalid_json")
        self.assertEqual(stream.bytes_read, 0)  # Preserve Werkzeug's safe WSGI fallback.
        for body, length in ((b'{"answer":"word"}', 2), (b"{}", 30)):
            response, stream = self._stream_request(body, length=length)
            self.assertEqual(response.status_code, 400)
            self.assertEqual(response.get_json()["error"], "invalid_json")
            self.assertLessEqual(stream.bytes_read, min(len(body), length))
        with self.app.app_context():
            self.assertEqual(VocabularyLearningFlow.query.count(), 0)

    def test_cancelled_identity_mapped_task_is_not_accessible(self):
        with self.app.app_context():
            task = db.session.get(Task, self.task_id)
            task.cancelled_at = datetime.utcnow()
            db.session.commit()
            self.assertIsNotNone(task)
            response = self.client.get(f"/api/practice/vocabulary/tasks/{self.task_id}/state")
            self.assertEqual(response.status_code, 404)

    def test_correction_duplicate_reports_persisted_answer(self):
        task_id = self._task("comprehensive")
        flow = self._view(task_id)
        self._post("answers", self._question_payload(flow, task_id, wrong=True), task_id)
        flow = self._post("sync", task_id=task_id)["flow"]
        payload = {
            "queue_token": flow["queue_token"],
            "learning_question_id": flow["current_question"]["learning_question_id"],
            "answer": "wrong",
            "attempt_id": "correction-persisted",
        }
        self._post("corrections", payload, task_id)
        duplicate = self._post("corrections", dict(payload, answer="another-answer"), task_id)
        self.assertTrue(duplicate["feedback"]["idempotent"])
        self.assertEqual(duplicate["feedback"]["student_answer"], "wrong")

    def test_grace_boundary_expiry_does_not_advance_existing_flow(self):
        self._view()
        tomorrow = beijing_today() + timedelta(days=1)
        grace = datetime.combine(tomorrow, time(2, 59), ZoneInfo("Asia/Shanghai"))
        cutoff = datetime.combine(tomorrow, time(3), ZoneInfo("Asia/Shanghai"))
        with patch("services.task_date_gate._local_now", return_value=grace):
            state = self._state()
            self.assertEqual(state["stage"], "in_progress")
            self.assertTrue(state["access"]["is_grace_period"])
        with self.app.app_context():
            before = VocabularyLearningFlow.query.one().state_version
        with patch("services.task_date_gate._local_now", return_value=cutoff):
            state = self._state()
            self.assertEqual(state["stage"], "read_only")
            self.assertEqual(state["access"]["task_date_state"], "expired")
            self.assertEqual(self._post("sync")["stage"], "read_only")
        with self.app.app_context():
            self.assertEqual(VocabularyLearningFlow.query.one().state_version, before)

    def test_completed_get_has_no_database_writes_and_cannot_answer(self):
        complete = self._finish()
        self._post("settle", {"queue_token": complete["queue_token"]})
        with self.app.app_context():
            writes = []

            def record(conn, cursor, statement, params, context, many):
                if statement.lstrip().split()[0].upper() in {"INSERT", "UPDATE", "DELETE"}:
                    writes.append(statement)

            event.listen(db.engine, "before_cursor_execute", record)
            try:
                self.assertEqual(self._state()["stage"], "result")
                self.assertEqual(writes, [])
            finally:
                event.remove(db.engine, "before_cursor_execute", record)
        self.assertEqual(
            self._post("answers", {}, expected=403)["error"], "task_completed_read_only"
        )

    def test_review_wrong_correction_replay_and_same_student_task_gate(self):
        self._seed_due()
        session = self._post("review/claim")["review"]
        other_task = self._task("reading")
        shared = self._post("review/claim", task_id=other_task)["review"]
        self.assertEqual(session["session_id"], shared["session_id"])
        item = session["items"][0]
        payload = {
            **{
                key: item[key]
                for key in ("review_item_id", "question_id", "word_id", "sense_id", "dimension")
            },
            "session_id": session["session_id"],
            "session_token": session["session_token"],
            "queue_token": session["queue_token"],
            "answer": "wrong",
            "attempt_id": "review-first-wrong",
            "supports_correction": False,
        }
        wrong = self._post("review/answers", payload)
        self.assertTrue(wrong["feedback"]["correction_required"])
        self.assertTrue(wrong["feedback"]["answer_feedback"]["word"])
        restored = self._post("review/claim")["review"]
        self.assertTrue(restored["items"][0]["correction_required"])
        self._post("review/settle", payload, expected=409)
        correction = dict(payload, attempt_id="review-correction-1")
        first = self._post("review/corrections", correction)
        self.assertTrue(first["feedback"]["correction_required"])
        duplicate = self._post("review/corrections", dict(correction, answer="changed"))
        self.assertTrue(duplicate["feedback"]["idempotent"])
        self.assertEqual(duplicate["feedback"]["student_answer"], "wrong")
        second = self._post(
            "review/corrections", dict(correction, attempt_id="review-correction-2")
        )
        self.assertTrue(second["feedback"]["correction_exhausted"])
        self._post("review/settle", payload)
        self.assertEqual(self._post("sync", task_id=other_task)["stage"], "learning")

    def test_foreign_review_session_is_rejected(self):
        self._seed_due()
        session = self._post("review/claim")["review"]
        with self.app.app_context():
            other = User(
                username="foreign-review",
                password_hash="test",
                role=User.ROLE_STUDENT,
                is_active=True,
            )
            db.session.add(other)
            db.session.flush()
            row = db.session.get(VocabularyReviewSession, session["session_id"])
            row.student_id = other.id
            db.session.commit()
        self._post(
            "review/settle",
            {
                "session_id": session["session_id"],
                "session_token": session["session_token"],
                "queue_token": session["queue_token"],
            },
            expected=404,
        )

    def test_numeric_task_preserves_input_punctuation_and_tts_hint(self):
        with self.app.app_context():
            word = DictationWord.query.order_by(DictationWord.id).first()
            word.word, word.translation, word.core_meaning_zh = "£12.50", "", ""
            db.session.commit()
        flow = self._view()
        q = flow["current_question"]
        self.assertEqual(q["mode"], "audio_to_en")
        self.assertEqual(q["question"]["answer_type"], "numeric")
        self.assertIn("numeric=1", q["question"]["prompt"]["audio_tts_url"])
        result = self._post("answers", self._question_payload(flow))
        self.assertTrue(result["feedback"]["is_correct"])
        self.assertIn("numeric=1", result["feedback"]["answer_feedback"]["audio_tts_url"])

    def test_stale_question_error_snapshot_and_retry_never_leak_answer(self):
        flow = self._view()
        payload = self._question_payload(flow, wrong=True)
        self._post("answers", payload)
        stale = self._post("answers", dict(payload, attempt_id="stale-position"), expected=409)
        self.assertEqual(stale["error"], "question_not_current")
        self.assertNotIn("last_saved_response", stale["state"])
        self.assertNotIn("forgot_items", stale["state"])
        self.assertTrue(
            all(set(row) == {"word_id", "viewed"} for row in stale["state"]["familiarity"])
        )
        flow = self._post("sync")["flow"]
        self._post("answers", self._question_payload(flow))
        retry = self._post("sync")["flow"]
        self.assertEqual(retry["phase"], "retry")
        self.assertNotIn("revealed_answer", retry["current_question"])
        self.assertNotIn("first_answer", retry["current_question"])
        recovered = self._post("sync", {"attempt_id": payload["attempt_id"]})["flow"]
        self.assertEqual(recovered["saved_response"]["student_answer"], "wrong")

    def test_malformed_recovery_ids_do_not_initialize_flow(self):
        for key, value in (("attempt_id", []), ("attempt_id", "a" * 97)):
            self._post("sync", {key: value}, expected=400)
        with self.app.app_context():
            self.assertEqual(VocabularyLearningFlow.query.count(), 0)
        response = self.client.get(f"/api/practice/vocabulary/tasks/{self.task_id}/state")
        self.assertEqual(response.headers["Cache-Control"], "no-store, private")

    def test_classroom_synonym_and_missing_examples_keep_real_domain_modes(self):
        with self.app.app_context():
            word = DictationWord.query.order_by(DictationWord.id).first()
            word.word, word.translation, word.core_meaning_zh = "participate", "= take part in", ""
            word.example_en, word.example_zh, word.usage_pattern = "", "", ""
            sense = ensure_word_sense(word)
            sense.lemma, sense.definition_en, sense.part_of_speech = (
                "participate",
                "take part in",
                "synonym",
            )
            sense.canonical_key = synonym_sense_key("participate", "take part in")
            db.session.commit()
        task_id = self._task("reading")
        flow = self._view(task_id)
        question = flow["current_question"]
        self.assertEqual(question["mode"], "context_fill")
        self.assertEqual(question["phase"], "active_recall")
        self.assertEqual(question["question"]["prompt"]["sentence"], "participate = ____")
        self.assertNotIn("take part in", json.dumps(question))
        self.assertTrue(flow["diagnostics"])
        feedback = self._post("answers", self._question_payload(flow, task_id), task_id)["feedback"]
        self.assertTrue(feedback["is_correct"])
        self.assertEqual(feedback["revealed_answer"], "take part in")

    def test_actual_name_switch_rejects_old_page_before_task_lookup(self):
        with self.app.app_context():
            other = User(
                username="switched-student",
                password_hash="test",
                role=User.ROLE_STUDENT,
                is_active=True,
            )
            db.session.add(other)
            db.session.flush()
            db.session.add(StudentProfile(user_id=other.id, full_name="切换后的学生"))
            db.session.commit()
        with self.client.session_transaction() as session:
            session["practice_student_name"] = "切换后的学生"
        response = self._post("sync", expected=409)
        self.assertEqual(response["error"], "identity_changed")
        with self.app.app_context():
            self.assertEqual(VocabularyLearningFlow.query.count(), 0)

    def test_context_choice_correction_accepts_public_label_mapped_to_option_id(self):
        task_id = self._task("comprehensive")
        flow = self._view(task_id)
        for _ in range(20):
            question = flow["current_question"]
            if question["mode"] == "context_choice":
                break
            self._post("answers", self._question_payload(flow, task_id), task_id)
            flow = self._post("sync", task_id=task_id)["flow"]
        else:
            self.fail("comprehensive fixture did not reach context_choice")
        self._post("answers", self._question_payload(flow, task_id, wrong=True), task_id)
        flow = self._post("sync", task_id=task_id)["flow"]
        question = flow["current_question"]
        public_option = next(
            option
            for option in question["question"]["options"]
            if option["label"] == question["revealed_answer"]
        )
        result = self._post(
            "corrections",
            {
                "queue_token": flow["queue_token"],
                "learning_question_id": question["learning_question_id"],
                "answer": public_option["id"],
                "attempt_id": "public-context-correction",
            },
            task_id,
        )
        self.assertTrue(result["feedback"]["correction_completed"])
        self.assertEqual(result["feedback"]["correction_count"], 1)
        with self.app.app_context():
            stored = db.session.get(VocabularyLearningQuestion, question["learning_question_id"])
            self.assertFalse(stored.first_is_correct)

    def test_review_context_choice_correction_uses_same_public_transport_contract(self):
        self._seed_due()
        session = self._post("review/claim")["review"]
        item = session["items"][0]
        with self.app.app_context():
            stored = db.session.get(VocabularyReviewItem, item["review_item_id"])
            word = db.session.get(DictationWord, stored.word_id)
            public, expected = build_context_question(
                word,
                DictationWord.query.filter_by(book_id=word.book_id).all(),
                seed="web-review-correction",
                allowed_kinds={"meaning_choice"},
            )
            stored.dimension = "context_use"
            stored.question_id = public["question_id"]
            stored.question_snapshot_json = json.dumps(public, ensure_ascii=False)
            stored.answer_payload_json = json.dumps(expected, ensure_ascii=False)
            db.session.commit()
        item = self._post("review/claim")["review"]["items"][0]
        payload = {
            **{
                key: item[key]
                for key in ("review_item_id", "question_id", "word_id", "sense_id", "dimension")
            },
            "session_id": session["session_id"],
            "session_token": session["session_token"],
            "answer": "wrong",
            "attempt_id": "review-context-first",
        }
        result = self._post("review/answers", payload)
        self.assertTrue(result["feedback"]["correction_required"])
        revealed = result["feedback"]["revealed_answer"]
        option = next(
            option for option in item["question"]["options"] if option["label"] == revealed
        )
        corrected = self._post(
            "review/corrections",
            dict(payload, answer=option["id"], attempt_id="review-context-correction"),
        )
        self.assertTrue(corrected["feedback"]["correction_completed"])
        self.assertEqual(corrected["feedback"]["correction_count"], 1)
        self.assertTrue(corrected["feedback"]["answer_feedback"]["word"])


if __name__ == "__main__":
    unittest.main()
