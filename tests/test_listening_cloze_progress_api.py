"""Regression coverage for legacy/new listening-cloze coordinate bases."""

import json
import unittest
from pathlib import Path

from flask import Flask

import app as app_module
from api.listening_training import listening_training_bp
from models import ListeningSegmentResult, Task, db

ROOT = Path(__file__).resolve().parents[1]


class ListeningClozeProgressApiTest(unittest.TestCase):
    def setUp(self):
        self.original_app = app_module.app
        self.app = Flask(__name__, static_folder=str(ROOT / "static"))
        self.app.config.update(
            SECRET_KEY="listening-cloze-test",
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            TESTING=True,
        )
        db.init_app(self.app)
        self.app.register_blueprint(listening_training_bp)
        app_module.app = self.app
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()
            task = Task(
                student_name="听写测试",
                category="雅思-听力-精听",
                detail="coordinate regression",
                status="progress",
                listening_exercise_id="ielts20_test1_s1",
                listening_access_token="coordinate-token",
            )
            db.session.add(task)
            db.session.flush()
            db.session.add_all(
                [
                    # Older browser strips the speaker label before indexing.
                    ListeningSegmentResult(
                        task_id=task.id,
                        student_name=task.student_name,
                        segment_index=0,
                        segment_text="I need a table.",
                        hidden_word_indices=json.dumps([1, 3]),
                        answers_json=json.dumps(["need", "table"]),
                        correct_words=2,
                        total_words=2,
                        accuracy=100,
                        is_completed=True,
                        attempt_count=1,
                    ),
                    # Older mini-program and new canonical browser both retain
                    # original segment.text coordinates including WOMAN:.
                    ListeningSegmentResult(
                        task_id=task.id,
                        student_name=task.student_name,
                        segment_index=1,
                        segment_text="WOMAN: I need a table.",
                        hidden_word_indices=json.dumps([2, 4]),
                        answers_json=json.dumps(["need", "table"]),
                        correct_words=2,
                        total_words=2,
                        accuracy=100,
                        is_completed=True,
                        attempt_count=1,
                    ),
                ]
            )
            db.session.commit()
            self.task_id = task.id

    def tearDown(self):
        try:
            with self.app.app_context():
                db.session.remove()
                db.drop_all()
                db.engine.dispose()
        finally:
            app_module.app = self.original_app

    def test_progress_returns_saved_text_for_each_coordinate_basis_without_rewriting_indices(self):
        with self.app.test_request_context(
            f"/api/student/listening/task/{self.task_id}?token=coordinate-token"
        ):
            response = app_module.api_student_listening_task(self.task_id)

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        progress = payload["progress"]

        self.assertEqual(progress["0"]["segment_text"], "I need a table.")
        self.assertEqual(progress["0"]["hidden_word_indices"], [1, 3])
        self.assertEqual(progress["0"]["answers_json"], ["need", "table"])

        self.assertEqual(progress["1"]["segment_text"], "WOMAN: I need a table.")
        self.assertEqual(progress["1"]["hidden_word_indices"], [2, 4])
        self.assertEqual(progress["1"]["answers_json"], ["need", "table"])

    def test_submit_recomputes_score_from_canonical_segment_instead_of_trusting_client(self):
        canonical = "MAN: The Junction? Yeah, I’d definitely recommend that for a special occasion. We had a great time there. Everyone really enjoyed it."
        with self.app.test_request_context(
            f"/api/student/listening/task/{self.task_id}/segment/2?token=coordinate-token",
            method="POST",
            json={
                "segment_text": canonical,
                "hidden_word_indices": [1, 2],
                "answers": ["The", "wrong"],
                "correct_words": 2,
                "total_words": 2,
            },
        ):
            response = app_module.api_student_listening_submit_segment(self.task_id, 2)

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["segment"]["correct_words"], 1)
        self.assertEqual(payload["segment"]["total_words"], 2)
        self.assertEqual(payload["segment"]["accuracy"], 50.0)
        self.assertEqual(
            [row["isCorrect"] for row in payload["segment"]["results"]],
            [True, False],
        )
        self.assertEqual(payload["segment"]["results"][1]["answer"], "Junction")
        with self.app.app_context():
            saved = ListeningSegmentResult.query.filter_by(task_id=self.task_id, segment_index=2).one()
            self.assertEqual(saved.correct_words, 1)
            self.assertEqual(saved.accuracy, 50.0)

    def test_duplicate_submit_returns_immutable_first_attempt(self):
        with self.app.test_request_context(
            f"/api/student/listening/task/{self.task_id}/segment/0?token=coordinate-token",
            method="POST",
            json={
                "segment_text": "forged",
                "hidden_word_indices": [0],
                "answers": ["wrong"],
                "correct_words": 0,
                "total_words": 1,
            },
        ):
            response = app_module.api_student_listening_submit_segment(self.task_id, 0)

        payload = response.get_json()
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["already_saved"])
        self.assertEqual(payload["segment"]["accuracy"], 100)
        with self.app.app_context():
            saved = ListeningSegmentResult.query.filter_by(task_id=self.task_id, segment_index=0).one()
            self.assertEqual(saved.attempt_count, 1)
            self.assertEqual(saved.answers_json, json.dumps(["need", "table"]))

    def test_submit_rejects_noncanonical_text_and_speaker_label_targets(self):
        cases = [
            {
                "segment_text": "not the source sentence",
                "hidden_word_indices": [1],
                "answers": ["The"],
                "expected_error": "segment_text_mismatch",
            },
            {
                "segment_text": "MAN: It’s on Greyson Street, only about a two minute walk from the station.",
                "hidden_word_indices": [0],
                "answers": ["WOMAN"],
                "expected_error": "hidden_word_index_out_of_range",
            },
            {
                "segment_text": "WOMAN: Oh, that’s good. I’d prefer not to have to drive anywhere. But I don’t want to have to walk too far either.",
                "hidden_word_indices": [1],
                "answers": ["   "],
                "expected_error": "empty_answers",
            },
        ]
        for offset, case in enumerate(cases, start=3):
            with self.subTest(case=case["expected_error"]), self.app.test_request_context(
                f"/api/student/listening/task/{self.task_id}/segment/{offset}?token=coordinate-token",
                method="POST",
                json=case,
            ):
                response = self.app.make_response(
                    app_module.api_student_listening_submit_segment(self.task_id, offset)
                )
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.get_json()["error"], case["expected_error"])

    def test_assigned_mode_is_returned_and_enforced_for_first_attempt(self):
        with self.app.app_context():
            task = Task(
                student_name="正式训练",
                category="雅思-听力-精听",
                detail="locked standard",
                status="pending",
                listening_exercise_id="ielts20_test1_s1",
                listening_access_token="locked-token",
                listening_training_mode="standard",
            )
            db.session.add(task)
            db.session.commit()
            task_id = task.id

        with self.app.test_request_context(
            f"/api/student/listening/task/{task_id}?token=locked-token"
        ):
            response = self.app.make_response(
                app_module.api_student_listening_task(task_id)
            )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertTrue(payload["task"]["listening_training_policy"]["locked"])
        segment = payload["exercise"]["parts"][0]["segments"][2]
        self.assertEqual(segment["assigned_training_level"], "standard")

        canonical = segment["text"]
        with self.app.test_request_context(
            f"/api/student/listening/task/{task_id}/segment/2?token=locked-token",
            method="POST",
            json={
                "segment_text": canonical,
                "hidden_word_indices": [1],
                "answers": ["The"],
                "training_level": "basic",
            },
        ):
            mismatch = self.app.make_response(
                app_module.api_student_listening_submit_segment(task_id, 2)
            )
        self.assertEqual(mismatch.status_code, 409)
        self.assertEqual(mismatch.get_json()["error"], "training_level_mismatch")

        with self.app.test_request_context(
            f"/api/student/listening/task/{task_id}/segment/2?token=locked-token",
            method="POST",
            json={
                "segment_text": canonical,
                "hidden_word_indices": [1, 2],
                "answers": ["The", "Junction"],
                "training_level": "standard",
            },
        ):
            saved = self.app.make_response(
                app_module.api_student_listening_submit_segment(task_id, 2)
            )
        self.assertEqual(saved.status_code, 200)
        self.assertEqual(saved.get_json()["segment"]["training_level"], "standard")
        with self.app.app_context():
            row = ListeningSegmentResult.query.filter_by(task_id=task_id).one()
            self.assertEqual(row.training_level, "standard")

    def test_review_task_requires_listen_and_reveal_then_saves_idempotently(self):
        with self.app.app_context():
            task = Task(
                student_name="听辨核对",
                category="雅思-听力-精听",
                detail="review only",
                status="pending",
                listening_exercise_id="ielts20_test1_s1",
                listening_access_token="review-token",
                listening_training_mode="review",
                question_ids=json.dumps([0]),
            )
            db.session.add(task)
            db.session.commit()
            task_id = task.id

        rejected = self.client.post(
            f"/api/student/listening/task/{task_id}/segment/0/review?token=review-token",
            json={"listened": True, "revealed_original": False},
        )
        self.assertEqual(rejected.status_code, 400)
        self.assertEqual(rejected.get_json()["error"], "review_requirements_not_met")

        completed = self.client.post(
            f"/api/student/listening/task/{task_id}/segment/0/review?token=review-token",
            json={"listened": True, "revealed_original": True},
        )
        self.assertEqual(completed.status_code, 200)
        self.assertFalse(completed.get_json()["already_saved"])
        self.assertEqual(completed.get_json()["task"]["completion_rate"], 100.0)
        self.assertIsNone(completed.get_json()["task"]["accuracy"])
        self.assertEqual(completed.get_json()["task"]["status"], "done")

        duplicate = self.client.post(
            f"/api/student/listening/task/{task_id}/segment/0/review?token=review-token",
            json={"listened": True, "revealed_original": True},
        )
        self.assertEqual(duplicate.status_code, 403)
        self.assertEqual(duplicate.get_json()["error"], "task_completed_read_only")
        with self.app.app_context():
            row = ListeningSegmentResult.query.filter_by(task_id=task_id).one()
            self.assertEqual(row.training_level, "review")
            self.assertEqual(row.total_words, 0)


if __name__ == "__main__":
    unittest.main()
