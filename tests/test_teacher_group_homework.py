"""Exercise small-class homework with real routes and isolated synthetic data."""

import copy
import json
import time
import unittest
from datetime import date, datetime
from pathlib import Path
from unittest.mock import patch

import jwt
from flask import Flask
from sqlalchemy import event
from sqlalchemy.exc import IntegrityError

from api.miniprogram import mp_bp
from api.teacher_group_homework import teacher_group_homework_bp
from api.teacher_practice_access import teacher_practice_bp
from models import (
    AuditLogEntry,
    ListeningTestSubmission,
    PracticeSubmissionAttempt,
    ReadingTestSubmission,
    StudentProfile,
    Task,
    User,
    db,
)


class TeacherGroupHomeworkTest(unittest.TestCase):
    def setUp(self):
        self.today = date.today().isoformat()
        self.names = ["合成甲", "合成乙", "合成丙"]
        self.app = Flask(__name__)
        self.app.static_folder = str(Path(__file__).resolve().parents[1] / "static")
        self.app.config.update(
            SECRET_KEY="group-homework-test-secret",
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            WECHAT_TASK_TEMPLATE_ID="synthetic-task-template",
            TESTING=True,
        )
        db.init_app(self.app)
        self.app.register_blueprint(mp_bp)
        self.app.register_blueprint(teacher_group_homework_bp)
        self.app.register_blueprint(teacher_practice_bp)
        with self.app.app_context():
            db.create_all()
            teacher = User(
                username="group-teacher",
                password_hash="test",
                role=User.ROLE_TEACHER,
                scheduler_teacher_id=17,
                is_active=True,
            )
            other_teacher = User(
                username="other-group-teacher",
                password_hash="test",
                role=User.ROLE_TEACHER,
                scheduler_teacher_id=18,
                is_active=True,
            )
            students = [
                User(
                    username=f"synthetic-group-student-{index}",
                    password_hash="test",
                    role=User.ROLE_STUDENT,
                    wechat_openid=f"synthetic-openid-{index}",
                    is_active=True,
                )
                for index in range(3)
            ]
            db.session.add_all([teacher, other_teacher, *students])
            db.session.flush()
            profiles = [
                StudentProfile(full_name=name, user_id=student.id)
                for name, student in zip(self.names, students, strict=True)
            ]
            db.session.add_all(profiles)
            db.session.commit()
            self.teacher_id = teacher.id
            self.other_teacher_id = other_teacher.id
            self.student_ids = [student.id for student in students]
            self.profile_ids = [profile.id for profile in profiles]
        self.schedule = {
            "schedule_id": "group-class-1",
            "schedule_uid": "id:group-class-1",
            "student_id": 201,
            "student_name": "/".join(self.names),
            "teacher_id": 17,
            "course_name": "雅思听力",
            "schedule_date": self.today,
            "start_time": f"{self.today} 10:00",
            "end_time": f"{self.today} 11:00",
        }
        self.scheduler_rows = [
            {
                **self.schedule,
                "scheduler_student_id": 201,
                "scheduler_student_ids": [201],
                "student_profiles": [{"id": 201, "name": "/".join(self.names)}],
            }
        ]
        self.scheduler_patch = patch(
            "services.teacher_homework_recipients.fetch_range_schedules_by_dates",
            side_effect=self._fetch_schedules,
        )
        self.scheduler_fetch = self.scheduler_patch.start()
        self.addCleanup(self.scheduler_patch.stop)
        self.quick_scheduler_patch = patch(
            "api.teacher_practice_access.fetch_range_schedules_by_dates",
            side_effect=self._fetch_schedules,
        )
        self.quick_scheduler_patch.start()
        self.addCleanup(self.quick_scheduler_patch.stop)
        self.push_patch = patch(
            "api.teacher_group_homework.send_subscribe_message_result",
            return_value={"ok": True},
        )
        self.push = self.push_patch.start()
        self.addCleanup(self.push_patch.stop)
        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _headers(self, user_id=None, role=User.ROLE_TEACHER):
        now = int(time.time())
        token = jwt.encode(
            {
                "sub": str(user_id or self.teacher_id),
                "role": role,
                "iat": now,
                "exp": now + 3600,
            },
            self.app.config["SECRET_KEY"],
            algorithm="HS256",
        )
        return {"Authorization": f"Bearer {token}"}

    def _fetch_schedules(self, *args, **kwargs):
        return {"schedules": self.scheduler_rows}, None

    def _preview(self):
        response = self.client.get(
            "/api/miniprogram/teacher/homework/recipients",
            query_string=self.schedule,
            headers=self._headers(),
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        return response.get_json()

    def _item(self, suffix="甲"):
        return {
            "date": self.today,
            "source_type": "custom",
            "category": "课堂练习",
            "detail": f"合成练习{suffix}",
            "planned_minutes": 20,
            "note": "合成要求",
        }

    def _payload(self, *, item_count=1):
        roster = self._preview()
        self.assertTrue(roster["can_assign"], roster)
        return {
            **self.schedule,
            "roster_token": roster["roster_token"],
            "recipient_profile_ids": [member["profile_id"] for member in roster["members"]],
            "idempotency_key": "synthetic-group-request-001",
            "items": [self._item(str(index)) for index in range(item_count)],
        }

    def _post(self, payload):
        return self.client.post(
            "/api/miniprogram/teacher/homework/group",
            json=payload,
            headers=self._headers(),
        )

    def _task_count(self):
        with self.app.app_context():
            return Task.query.count()

    def test_three_members_two_items_create_six_independent_student_tasks(self):
        payload = self._payload(item_count=2)
        response = self._post(payload)
        self.assertEqual(response.status_code, 200, response.get_json())
        body = response.get_json()
        self.assertEqual(body["member_count"], 3)
        self.assertEqual(body["task_count"], 6)
        self.assertEqual(len({task["id"] for task in body["tasks"]}), 6)
        self.assertEqual({task["student_name"] for task in body["tasks"]}, set(self.names))
        self.assertEqual(self._task_count(), 6)
        for student_id, name in zip(self.student_ids, self.names, strict=True):
            student_response = self.client.get(
                "/api/miniprogram/student/tasks/today",
                query_string={"date": self.today},
                headers=self._headers(student_id, User.ROLE_STUDENT),
            )
            self.assertEqual(student_response.status_code, 200)
            tasks = student_response.get_json()["tasks"]
            expected_ids = {task["id"] for task in body["tasks"] if task["student_name"] == name}
            self.assertEqual({task["id"] for task in tasks}, expected_ids)
            self.assertEqual(len(tasks), 2)
        self.assertEqual(self.push.call_count, 6)

    def test_replay_does_not_create_tasks_or_send_more_notifications(self):
        payload = self._payload(item_count=2)
        first = self._post(payload)
        self.assertEqual(first.status_code, 200, first.get_json())
        self.push.reset_mock()
        retry = self._post(payload)
        self.assertEqual(retry.status_code, 200, retry.get_json())
        self.assertTrue(retry.get_json()["replayed"])
        self.assertEqual(
            {task["id"] for task in first.get_json()["tasks"]},
            {task["id"] for task in retry.get_json()["tasks"]},
        )
        self.assertEqual(self._task_count(), 6)
        self.push.assert_not_called()

    def test_same_key_changed_payload_is_conflict(self):
        payload = self._payload()
        self.assertEqual(self._post(payload).status_code, 200)
        payload["items"][0]["detail"] = "不同的作业内容"
        self.assertEqual(self._post(payload).status_code, 409)
        self.assertEqual(self._task_count(), 3)

    def test_partial_existing_batch_is_not_silently_completed(self):
        payload = self._payload()
        self.assertEqual(self._post(payload).status_code, 200)
        with self.app.app_context():
            db.session.delete(Task.query.order_by(Task.id).first())
            db.session.commit()
        self.push.reset_mock()
        response = self._post(payload)
        self.assertEqual(response.status_code, 409, response.get_json())
        self.assertEqual(self._task_count(), 2)
        self.push.assert_not_called()

    def test_invalid_second_item_rolls_back_entire_batch(self):
        payload = self._payload(item_count=2)
        payload["items"][1]["source_type"] = "unknown-resource"
        response = self._post(payload)
        self.assertEqual(response.status_code, 400, response.get_json())
        self.assertEqual(self._task_count(), 0)
        self.push.assert_not_called()

    def test_database_insert_conflict_rolls_back_all_members_and_receipt(self):
        payload = self._payload(item_count=2)
        inserted = []

        def conflict_on_second_task(mapper, connection, target):
            inserted.append(target.student_name)
            if len(inserted) == 2:
                raise IntegrityError("synthetic insert", {}, Exception("synthetic conflict"))

        event.listen(Task, "before_insert", conflict_on_second_task)
        try:
            response = self._post(payload)
        finally:
            event.remove(Task, "before_insert", conflict_on_second_task)
        self.assertEqual(response.status_code, 409, response.get_json())
        self.assertEqual(self._task_count(), 0)
        with self.app.app_context():
            self.assertEqual(AuditLogEntry.query.count(), 0)
        self.push.assert_not_called()

    def test_missing_member_is_shown_and_nobody_receives_tasks(self):
        payload = self._payload()
        with self.app.app_context():
            db.session.get(StudentProfile, self.profile_ids[1]).is_deleted = True
            db.session.commit()
        preview = self._preview()
        self.assertFalse(preview["can_assign"])
        member = next(row for row in preview["members"] if row["student_name"] == self.names[1])
        self.assertEqual(member["status"], "missing")
        response = self._post(payload)
        self.assertGreaterEqual(response.status_code, 400)
        self.assertLess(response.status_code, 500)
        self.assertEqual(self._task_count(), 0)
        self.push.assert_not_called()

    def test_ambiguous_name_blocks_all_members(self):
        payload = self._payload()
        with self.app.app_context():
            db.session.add(StudentProfile(full_name=self.names[1]))
            db.session.commit()
        preview = self._preview()
        self.assertFalse(preview["can_assign"])
        member = next(row for row in preview["members"] if row["student_name"] == self.names[1])
        self.assertEqual(member["status"], "ambiguous")
        response = self._post(payload)
        self.assertGreaterEqual(response.status_code, 400)
        self.assertEqual(self._task_count(), 0)

    def test_cannot_omit_one_recipient_or_add_unlisted_profile(self):
        payload = self._payload()
        for recipient_ids in (self.profile_ids[:2], [*self.profile_ids, 99999]):
            with self.subTest(recipient_ids=recipient_ids):
                response = self._post({**payload, "recipient_profile_ids": recipient_ids})
                self.assertGreaterEqual(response.status_code, 400)
                self.assertLess(response.status_code, 500)
                self.assertEqual(self._task_count(), 0)

    def test_forged_roster_token_is_rejected(self):
        payload = self._payload()
        payload["roster_token"] = "forged-token"
        response = self._post(payload)
        self.assertIn(response.status_code, (400, 403, 409))
        self.assertEqual(self._task_count(), 0)

    def test_expired_roster_token_is_rejected(self):
        payload = self._payload()
        claims = jwt.decode(
            payload["roster_token"], self.app.config["SECRET_KEY"], algorithms=["HS256"]
        )
        claims.update(iat=int(time.time()) - 3600, exp=int(time.time()) - 5)
        payload["roster_token"] = jwt.encode(
            claims, self.app.config["SECRET_KEY"], algorithm="HS256"
        )
        response = self._post(payload)
        self.assertEqual(response.status_code, 409, response.get_json())
        self.assertEqual(self._task_count(), 0)

    def test_server_roster_change_invalidates_confirmation(self):
        payload = self._payload()
        self.scheduler_rows[0]["student_profiles"][0]["name"] = "/".join(self.names[:2])
        self.scheduler_rows[0]["student_name"] = "/".join(self.names[:2])
        response = self._post(payload)
        self.assertEqual(response.status_code, 409, response.get_json())
        self.assertEqual(self._task_count(), 0)

    def test_forged_teacher_does_not_authorize_other_teacher_schedule(self):
        self.scheduler_rows[0]["teacher_id"] = 18
        response = self.client.get(
            "/api/miniprogram/teacher/homework/recipients",
            query_string={**self.schedule, "teacher_id": 17},
            headers=self._headers(),
        )
        self.assertEqual(response.status_code, 403, response.get_json())
        self.assertEqual(self._task_count(), 0)

    def test_roster_token_cannot_be_used_by_another_teacher(self):
        payload = self._payload()
        response = self.client.post(
            "/api/miniprogram/teacher/homework/group",
            json=payload,
            headers=self._headers(self.other_teacher_id),
        )
        self.assertIn(response.status_code, (403, 409))
        self.assertEqual(self._task_count(), 0)

    def test_notification_failure_keeps_all_tasks_and_reports_each_failure(self):
        payload = self._payload()
        self.push.return_value = {"ok": False, "errcode": 43101}
        response = self._post(payload)
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(self._task_count(), 3)
        body = response.get_json()
        self.assertEqual(body["push_sent"], 0)
        self.assertEqual(len(body["recipients"]), 3)
        self.assertTrue(all(row["push_errors"] for row in body["recipients"]))

    def test_notification_exception_cannot_turn_successful_save_into_error(self):
        payload = self._payload()
        self.push.side_effect = RuntimeError("synthetic notification outage")
        with self.assertLogs(self.app.logger.name, level="WARNING"):
            response = self._post(payload)
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(self._task_count(), 3)
        self.assertEqual(response.get_json()["push_sent"], 0)
        self.assertTrue(all(row["push_errors"] for row in response.get_json()["recipients"]))

    def test_list_only_contains_current_teachers_member_tasks(self):
        payload = self._payload()
        created = self._post(payload)
        self.assertEqual(created.status_code, 200, created.get_json())
        with self.app.app_context():
            db.session.add_all(
                [
                    Task(
                        date=self.today,
                        student_name=self.names[0],
                        detail="其他老师作业",
                        category="test",
                        created_by=self.other_teacher_id,
                    ),
                    Task(
                        date=self.today,
                        student_name="其他学生",
                        detail="非成员作业",
                        category="test",
                        created_by=self.teacher_id,
                    ),
                ]
            )
            db.session.commit()
        response = self.client.get(
            "/api/miniprogram/teacher/homework/group",
            query_string={
                **self.schedule,
                "roster_token": payload["roster_token"],
                "date": self.today,
            },
            headers=self._headers(),
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(
            {task["id"] for task in response.get_json()["tasks"]},
            {task["id"] for task in created.get_json()["tasks"]},
        )

    def test_group_edit_updates_one_member_without_changing_siblings(self):
        payload = self._payload()
        response = self._post(payload)
        self.assertEqual(response.status_code, 200, response.get_json())
        task_id = response.get_json()["tasks"][0]["id"]
        updated = self.client.patch(
            f"/api/miniprogram/teacher/homework/group/{task_id}",
            json={**payload, **self._item(), "detail": "仅修改当前学生"},
            headers=self._headers(),
        )
        self.assertEqual(updated.status_code, 200, updated.get_json())
        with self.app.app_context():
            self.assertEqual(db.session.get(Task, task_id).detail, "仅修改当前学生")
            self.assertEqual(Task.query.filter_by(detail="仅修改当前学生").count(), 1)

    def test_group_list_retains_listening_reading_scores_and_attempt_details(self):
        payload = self._payload()
        created = self._post(payload)
        self.assertEqual(created.status_code, 200, created.get_json())
        created_ids = [task["id"] for task in created.get_json()["tasks"]]
        result_rows = [
            {
                "ids": ["1"],
                "numbers": [1],
                "answer": "answer",
                "value": "wrong",
                "marks": 1,
                "awarded": 0,
                "correct": False,
            }
        ]
        with self.app.app_context():
            for index, (kind, submission_model) in enumerate(
                (
                    ("listening", ListeningTestSubmission),
                    ("reading", ReadingTestSubmission),
                )
            ):
                task = db.session.get(Task, created_ids[index])
                task.status = "done"
                if kind == "listening":
                    task.listening_exercise_id = "ielts18_test1"
                    task.listening_resource_type = "cambridge_test"
                else:
                    task.reading_test_id = "ielts18_test1_reading"
                db.session.add_all(
                    [
                        submission_model(
                            task_id=task.id,
                            student_name=task.student_name,
                            test_id="ielts18_test1",
                            correct_count=9,
                            total_count=10,
                            accuracy=90,
                            attempt_count=2,
                            results_json=json.dumps(result_rows),
                            wrong_numbers_json="[1]",
                            submitted_at=datetime(2026, 11, 14, 4, 0),
                        ),
                        PracticeSubmissionAttempt(
                            task_id=task.id,
                            student_name=task.student_name,
                            kind=kind,
                            test_id="ielts18_test1",
                            attempt_number=1,
                            correct_count=6,
                            total_count=10,
                            accuracy=60,
                            results_json=json.dumps(result_rows),
                            wrong_numbers_json="[1,2,3,4]",
                            submitted_at=datetime(2026, 11, 14, 3, 0),
                        ),
                    ]
                )
            db.session.commit()
        response = self.client.get(
            "/api/miniprogram/teacher/homework/group",
            query_string={
                **self.schedule,
                "roster_token": payload["roster_token"],
                "date": self.today,
            },
            headers=self._headers(),
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        listed = {task["id"]: task for task in response.get_json()["tasks"]}
        for index, kind in enumerate(("listening", "reading")):
            task_id = created_ids[index]
            result = listed[task_id]["practice_result"]
            self.assertEqual(result["kind"], kind)
            self.assertEqual(result["accuracy"], 90.0)
            overview = result["attempt_overview"]
            self.assertEqual(overview["attempt_count"], 2)
            self.assertEqual(overview["first_attempt"]["accuracy"], 60.0)
            self.assertEqual(overview["latest_attempt"]["accuracy"], 90.0)
            detail = self.client.get(
                f"/api/miniprogram/teacher/homework/{task_id}/result",
                headers=self._headers(),
            )
            self.assertEqual(detail.status_code, 200, detail.get_json())
            history = detail.get_json()["attempt_history"]["attempts"]
            self.assertEqual([attempt["attempt_number"] for attempt in history], [1, 2])
            self.assertEqual(history[-1]["wrong_details"][0]["question_label"], "Q1")
        self.assertIsNone(listed[created_ids[2]]["practice_result"])

    def test_group_edit_rejects_other_teachers_task(self):
        payload = self._payload()
        with self.app.app_context():
            task = Task(
                date=self.today,
                student_name=self.names[0],
                detail="其他老师的作业",
                category="test",
                created_by=self.other_teacher_id,
            )
            db.session.add(task)
            db.session.commit()
            task_id = task.id
        response = self.client.patch(
            f"/api/miniprogram/teacher/homework/group/{task_id}",
            json={**payload, **self._item()},
            headers=self._headers(),
        )
        self.assertEqual(response.status_code, 403, response.get_json())

    def test_malformed_group_edit_is_validation_error_with_no_mutation(self):
        payload = self._payload()
        created = self._post(payload)
        self.assertEqual(created.status_code, 200, created.get_json())
        task_id = created.get_json()["tasks"][0]["id"]
        response = self.client.patch(
            f"/api/miniprogram/teacher/homework/group/{task_id}",
            json={**payload, **self._item(), "detail": {"unexpected": "object"}},
            headers=self._headers(),
        )
        self.assertEqual(response.status_code, 400, response.get_json())
        with self.app.app_context():
            self.assertEqual(db.session.get(Task, task_id).detail, "合成练习0")

    def test_one_members_completion_does_not_complete_other_members_tasks(self):
        response = self._post(self._payload())
        self.assertEqual(response.status_code, 200, response.get_json())
        first_task = next(
            task for task in response.get_json()["tasks"] if task["student_name"] == self.names[0]
        )
        with self.app.app_context():
            db.session.get(Task, first_task["id"]).status = "done"
            db.session.commit()
        for index, student_id in enumerate(self.student_ids):
            student_response = self.client.get(
                "/api/miniprogram/student/tasks/today",
                query_string={"date": self.today},
                headers=self._headers(student_id, User.ROLE_STUDENT),
            )
            self.assertEqual(student_response.status_code, 200)
            tasks = student_response.get_json()["tasks"]
            self.assertEqual(len(tasks), 1)
            self.assertEqual(tasks[0]["status"], "completed" if index == 0 else "pending")

    def test_student_cannot_use_teacher_group_endpoints(self):
        payload = self._payload()
        response = self.client.post(
            "/api/miniprogram/teacher/homework/group",
            json=payload,
            headers=self._headers(self.student_ids[0], User.ROLE_STUDENT),
        )
        self.assertEqual(response.status_code, 403, response.get_json())
        self.assertEqual(self._task_count(), 0)

    def test_listening_and_reading_tokens_are_unique_for_each_member(self):
        payload = self._payload(item_count=2)
        payload["items"][0].update(
            source_type="cambridge_listening", practice_test_id="ielts18_test1"
        )
        payload["items"][1].update(
            source_type="cambridge_reading", practice_test_id="ielts18_test1_reading"
        )
        with (
            patch(
                "api.miniprogram._load_cambridge_listening_test",
                return_value=({"title": "合成听力", "sections": [{}]}, "ielts18_test1"),
            ),
            patch(
                "api.miniprogram._load_cambridge_reading_test",
                return_value=({"title": "合成阅读", "passages": [{}]}, "ielts18_test1_reading"),
            ),
        ):
            response = self._post(payload)
        self.assertEqual(response.status_code, 200, response.get_json())
        with self.app.app_context():
            listening = Task.query.filter(Task.listening_exercise_id.isnot(None)).all()
            reading = Task.query.filter(Task.reading_test_id.isnot(None)).all()
            self.assertEqual(len(listening), 3)
            self.assertEqual(len(reading), 3)
            self.assertTrue(all(task.listening_access_token for task in listening))
            self.assertTrue(all(task.reading_access_token for task in reading))
            self.assertEqual(len({task.listening_access_token for task in listening}), 3)
            self.assertEqual(len({task.reading_access_token for task in reading}), 3)

    def test_single_student_legacy_route_still_works(self):
        with patch("api.miniprogram.send_subscribe_message_result", return_value={"ok": True}):
            response = self.client.post(
                "/api/miniprogram/teacher/homework",
                json={**self._item(), "student_name": self.names[0], "teacher_id": 17},
                headers=self._headers(),
            )
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(self._task_count(), 1)

    def test_quick_group_edit_preserves_subject_restriction(self):
        response = self.client.get(
            "/api/miniprogram/teacher/practice-students",
            query_string={"month": self.today[:7]},
            headers=self._headers(),
        )
        self.assertEqual(response.status_code, 200, response.get_json())
        subject = response.get_json()["students"][0]["subjects"][0]
        payload = self._payload()
        payload.update(
            quick_practice=1,
            subject_key="listening",
            allowed_source="cambridge_listening",
            practice_context_token=subject["practice_context_token"],
        )
        payload["items"][0].update(
            source_type="cambridge_listening", practice_test_id="ielts18_test1"
        )
        with patch(
            "api.miniprogram._load_cambridge_listening_test",
            return_value=({"title": "合成听力", "sections": [{}]}, "ielts18_test1"),
        ):
            created = self._post(payload)
            self.assertEqual(created.status_code, 200, created.get_json())
            task_id = created.get_json()["tasks"][0]["id"]
            edit_payload = {**payload, **payload["items"][0], "detail": "当前学生听力修改"}
            updated = self.client.patch(
                f"/api/miniprogram/teacher/homework/group/{task_id}",
                json=edit_payload,
                headers=self._headers(),
            )
            self.assertEqual(updated.status_code, 200, updated.get_json())
        forbidden_payload = copy.deepcopy(edit_payload)
        forbidden_payload.update(
            source_type="cambridge_reading", practice_test_id="ielts18_test1_reading"
        )
        forbidden = self.client.patch(
            f"/api/miniprogram/teacher/homework/group/{task_id}",
            json=forbidden_payload,
            headers=self._headers(),
        )
        self.assertEqual(forbidden.status_code, 403, forbidden.get_json())

    def test_other_students_quick_token_cannot_authorize_group_post_or_patch(self):
        self.scheduler_rows[0]["course_name"] = "雅思阅读"
        self.scheduler_rows.append(
            {
                "schedule_id": "different-student-listening",
                "scheduler_student_id": 301,
                "teacher_id": 17,
                "student_name": "其他合成学生",
                "course_name": "雅思听力",
                "schedule_date": self.today,
                "start_time": "14:00",
                "end_time": "15:00",
            }
        )
        subjects_response = self.client.get(
            "/api/miniprogram/teacher/practice-students",
            query_string={"month": self.today[:7]},
            headers=self._headers(),
        )
        self.assertEqual(subjects_response.status_code, 200, subjects_response.get_json())
        other = next(
            student
            for student in subjects_response.get_json()["students"]
            if student["student_id"] == 301
        )
        subject = other["subjects"][0]
        payload = self._payload()
        forged = copy.deepcopy(payload)
        forged.update(
            student_id=301,
            student_name="其他合成学生",
            quick_practice=1,
            subject_key="listening",
            allowed_source="cambridge_listening",
            practice_context_token=subject["practice_context_token"],
        )
        forged["items"][0].update(
            source_type="cambridge_listening", practice_test_id="ielts18_test1"
        )
        posted = self._post(forged)
        self.assertEqual(posted.status_code, 403, posted.get_json())
        self.assertEqual(self._task_count(), 0)
        created = self._post(payload)
        self.assertEqual(created.status_code, 200, created.get_json())
        task_id = created.get_json()["tasks"][0]["id"]
        edited = self.client.patch(
            f"/api/miniprogram/teacher/homework/group/{task_id}",
            json={**forged, **forged["items"][0]},
            headers=self._headers(),
        )
        self.assertEqual(edited.status_code, 403, edited.get_json())
        with self.app.app_context():
            self.assertEqual(db.session.get(Task, task_id).detail, "合成练习0")
            self.assertIsNone(db.session.get(Task, task_id).listening_exercise_id)

    def test_invalid_numeric_items_are_rejected_before_creating_any_member_task(self):
        payload = self._payload()
        for invalid in (float("inf"), {"minutes": 20}, "Infinity", True):
            with self.subTest(invalid=invalid):
                attempt = copy.deepcopy(payload)
                attempt["items"][0]["planned_minutes"] = invalid
                response = self._post(attempt)
                self.assertEqual(response.status_code, 400, response.get_json())
                self.assertEqual(self._task_count(), 0)
        self.push.assert_not_called()

    def test_invalid_numeric_patch_keeps_existing_task_unchanged(self):
        payload = self._payload()
        created = self._post(payload)
        self.assertEqual(created.status_code, 200, created.get_json())
        task_id = created.get_json()["tasks"][0]["id"]
        for invalid in (float("inf"), {"minutes": 20}, "Infinity", True):
            with self.subTest(invalid=invalid):
                response = self.client.patch(
                    f"/api/miniprogram/teacher/homework/group/{task_id}",
                    json={**payload, **self._item(), "planned_minutes": invalid},
                    headers=self._headers(),
                )
                self.assertEqual(response.status_code, 400, response.get_json())
                with self.app.app_context():
                    self.assertEqual(db.session.get(Task, task_id).planned_minutes, 20)

    def test_client_course_object_is_replaced_by_verified_course_for_post_and_patch(self):
        payload = self._payload()
        payload["course_name"] = {"untrusted": "object"}
        payload["items"][0].pop("category")
        created = self._post(payload)
        self.assertEqual(created.status_code, 200, created.get_json())
        self.assertTrue(all(task["category"] == "雅思听力" for task in created.get_json()["tasks"]))
        task_id = created.get_json()["tasks"][0]["id"]
        edit_payload = {**payload, **payload["items"][0], "detail": "可信课程修改"}
        edited = self.client.patch(
            f"/api/miniprogram/teacher/homework/group/{task_id}",
            json=edit_payload,
            headers=self._headers(),
        )
        self.assertEqual(edited.status_code, 200, edited.get_json())
        self.assertEqual(edited.get_json()["task"]["category"], "雅思听力")

    def test_unbound_admin_can_assign_verified_teacher_class(self):
        with self.app.app_context():
            user = db.session.get(User, self.teacher_id)
            user.role = User.ROLE_ADMIN
            user.scheduler_teacher_id = None
            db.session.commit()
        response = self._post(self._payload())
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()["task_count"], 3)
        self.assertEqual(self._task_count(), 3)

    def test_inactive_login_does_not_receive_a_reminder(self):
        with self.app.app_context():
            db.session.get(User, self.student_ids[0]).is_active = False
            db.session.commit()
        response = self._post(self._payload())
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()["task_count"], 3)
        self.assertEqual(response.get_json()["push_sent"], 2)
        self.assertEqual(response.get_json()["recipients"][0]["push_errors"], ["no_student_openid"])
        self.assertEqual(self.push.call_count, 2)

    def test_old_generic_group_request_never_sends_only_to_bound_first_member(self):
        with self.app.app_context():
            db.session.get(StudentProfile, self.profile_ids[0]).scheduler_student_id = 201
            db.session.commit()
        with patch("api.miniprogram.send_subscribe_message_result") as old_push:
            response = self.client.post(
                "/api/miniprogram/teacher/homework",
                json={**self.schedule, **self._item()},
                headers=self._headers(),
            )
        self.assertEqual(response.status_code, 409, response.get_json())
        self.assertEqual(response.get_json()["error"], "group_assignment_required")
        self.assertEqual(self._task_count(), 0)
        old_push.assert_not_called()

    def test_old_quick_single_name_cannot_hide_verified_group_roster(self):
        with self.app.app_context():
            db.session.get(StudentProfile, self.profile_ids[0]).scheduler_student_id = 201
            db.session.commit()
        listed = self.client.get(
            "/api/miniprogram/teacher/practice-students",
            query_string={"month": self.today[:7]},
            headers=self._headers(),
        )
        self.assertEqual(listed.status_code, 200, listed.get_json())
        subject = listed.get_json()["students"][0]["subjects"][0]
        with patch("api.miniprogram.send_subscribe_message_result") as old_push:
            response = self.client.post(
                "/api/miniprogram/teacher/homework/quick-practice",
                json={
                    **self.schedule,
                    **self._item(),
                    "student_name": self.names[0],
                    "source_type": "cambridge_listening",
                    "subject_key": "listening",
                    "allowed_source": "cambridge_listening",
                    "practice_context_token": subject["practice_context_token"],
                },
                headers=self._headers(),
            )
        self.assertEqual(response.status_code, 409, response.get_json())
        self.assertEqual(response.get_json()["error"], "group_assignment_required")
        self.assertEqual(self._task_count(), 0)
        old_push.assert_not_called()


if __name__ == "__main__":
    unittest.main()
