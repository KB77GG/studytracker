"""Synthetic planner regression tests; no production app or database imports."""

import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from unittest.mock import patch

from flask import Flask, g
from flask_login import LoginManager

from api.task_planner import task_planner_bp
from models import (
    DictationBook,
    DictationWord,
    PlanItem,
    StudentProfile,
    StudyPlan,
    Task,
    User,
    VocabularyTaskSettlement,
    db,
)
from models_task_planner import TaskPlannerEntry, TaskPlannerEvent, TaskPlannerStudent
from services import task_planner as planner
from services.task_date_gate import SHANGHAI
from services.task_deletion import delete_unstarted_task

NOW = datetime(2026, 10, 29, 3, 5, tzinfo=SHANGHAI)


class PlannerFixture(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.app = Flask(__name__)
        self.app.config.update(
            TESTING=True,
            SECRET_KEY="synthetic-planner-test",
            SQLALCHEMY_DATABASE_URI=f"sqlite:///{self.directory.name}/test.db",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            TASK_PLANNER_ROOT=self.directory.name,
        )
        db.init_app(self.app)
        login = LoginManager(self.app)

        @login.user_loader
        def load_user(user_id):
            return db.session.get(User, int(user_id))

        self.app.register_blueprint(task_planner_bp)
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        roles = ("assistant", "teacher", "student", "student", "parent", "admin")
        users = [
            User(username=f"synthetic-{i}", password_hash="test", role=role)
            for i, role in enumerate(roles)
        ]
        db.session.add_all(users)
        db.session.flush()
        (
            self.staff_id,
            self.teacher_id,
            self.user_id,
            self.other_user_id,
            self.parent_id,
            self.admin_id,
        ) = [user.id for user in users]
        student = StudentProfile(full_name="合成学生甲", user_id=self.user_id)
        other = StudentProfile(full_name="合成学生乙", user_id=self.other_user_id)
        book = DictationBook(
            title="合成测试词书", created_by=self.staff_id, word_count=8, is_active=True
        )
        db.session.add_all([student, other, book])
        db.session.flush()
        self.student_id, self.other_id, self.book_id = student.id, other.id, book.id
        db.session.add_all(
            [
                DictationWord(
                    book_id=book.id,
                    sequence=i,
                    word=f"word{i}",
                    translation=f"释义{i}",
                    core_meaning_zh=f"释义{i}",
                )
                for i in range(1, 9)
            ]
        )
        db.session.commit()
        self.network = patch(
            "requests.sessions.Session.request",
            side_effect=AssertionError("External network forbidden"),
        )
        self.network_mock = self.network.start()
        self.client = self.app.test_client()

    def tearDown(self):
        self.network.stop()
        db.session.remove()
        db.engine.dispose()
        self.context.pop()
        self.directory.cleanup()

    def data(self, **changes):
        payload = {
            "student_id": self.student_id,
            "target_date": NOW.date().isoformat(),
            "kind": "dictation",
            "selection": {
                "book_id": self.book_id,
                "word_start": 1,
                "word_end": 2,
                "vocabulary_goal": "reading",
                "dictation_mode": "audio_to_en",
                "dictation_order": "sequence",
            },
            "planned_minutes": 15,
            "note": "合成安排说明",
        }
        payload.update(changes)
        return payload

    def draft(self, **changes):
        return planner.save_entry(self.data(**changes), self.staff_id, now=NOW)

    def ready(self, **changes):
        row = self.draft(**changes)
        return planner.confirm_entry(row.id, row.version, self.staff_id, now=NOW)

    def publish(self, row, **kwargs):
        return planner.publish_entry(
            row.id, actor_id=self.staff_id, expected_version=row.version, now=NOW, **kwargs
        )

    def prerequisite(self, *, student_id=None, user_status="pending", review="pending", **fields):
        student_id = student_id or self.student_id
        profile = db.session.get(StudentProfile, student_id)
        day = (NOW - timedelta(days=1)).date()
        plan = StudyPlan(student_id=student_id, plan_date=day, created_by=self.staff_id)
        db.session.add(plan)
        db.session.flush()
        item = PlanItem(
            plan_id=plan.id,
            exam_system="雅思",
            module="写作",
            task_name="前置合成任务",
            student_status=user_status,
            review_status=review,
        )
        db.session.add(item)
        db.session.flush()
        task = Task(
            student_name=profile.full_name,
            date=day.isoformat(),
            category="雅思-写作",
            detail="前置合成任务",
            status="pending",
            created_by=self.staff_id,
            plan_item_id=item.id,
            **fields,
        )
        db.session.add(task)
        db.session.commit()
        return task

    def login(self, user_id=None):
        with self.client.session_transaction() as session:
            session["_user_id"] = str(user_id or self.staff_id)
            session["_fresh"] = True
        g.pop("_login_user", None)

    def csrf_headers(self):
        response = self.client.get("/api/task-planner/bootstrap")
        self.assertEqual(response.status_code, 200)
        return {"X-CSRF-Token": response.get_json()["csrf_token"]}


class TaskPlannerServiceTest(PlannerFixture):
    def test_draft_and_confirmation_do_not_create_formal_tasks_or_enable_student(self):
        row = self.draft()
        self.assertEqual(row.status, "draft")
        row = planner.confirm_entry(row.id, row.version, self.staff_id, now=NOW)
        self.assertEqual(row.status, "ready")
        self.assertEqual(row.confirmed_by, self.staff_id)
        self.assertEqual(Task.query.count(), 0)
        self.assertEqual(PlanItem.query.count(), 0)
        self.assertEqual(TaskPlannerStudent.query.count(), 0)
        payload = planner.entry_payload(row)
        self.assertFalse(payload["student_enabled"])
        self.assertNotIn("prepared_json", payload)
        self.assertFalse(self.network_mock.called)

    def test_edit_revokes_confirmation_and_stale_version_is_rejected(self):
        row = self.ready()
        old_version = row.version
        row = planner.save_entry(
            self.data(note="改后的说明"),
            self.staff_id,
            entry_id=row.id,
            expected_version=old_version,
            now=NOW,
        )
        self.assertEqual(row.status, "draft")
        self.assertIsNone(row.confirmed_by)
        self.assertIsNone(row.confirmed_at)
        with self.assertRaises(planner.TaskPlannerError) as raised:
            planner.confirm_entry(row.id, old_version, self.staff_id, now=NOW)
        self.assertEqual(raised.exception.code, "version_conflict")
        self.assertEqual(Task.query.count(), 0)

    def test_unconfirmed_cannot_publish_and_formal_entry_is_immutable(self):
        row = self.draft()
        with self.assertRaises(planner.TaskPlannerError):
            self.publish(row)
        row = planner.confirm_entry(row.id, row.version, self.staff_id, now=NOW)
        row = self.publish(row)
        self.assertEqual(row.status, "published")
        with self.assertRaises(planner.TaskPlannerError):
            planner.cancel_entry(row.id, row.version, self.staff_id)
        with self.assertRaises(planner.TaskPlannerError):
            planner.save_entry(
                self.data(), self.staff_id, entry_id=row.id, expected_version=row.version, now=NOW
            )
        self.assertEqual(Task.query.count(), 1)

    def test_publish_creates_linked_task_once_and_old_version_replay_returns_it(self):
        row = self.ready()
        entry_id, old_version = row.id, row.version
        row = self.publish(row)
        task_id = row.published_task_id
        task = db.session.get(Task, task_id)
        self.assertEqual((task.dictation_word_start, task.dictation_word_end), (1, 2))
        self.assertEqual(task.date, NOW.date().isoformat())
        self.assertEqual(task.plan_item.plan.student_id, self.student_id)
        self.assertEqual(task.plan_item.plan.plan_date, NOW.date())
        self.assertEqual(task.assignment_idempotency_key, f"planner:{entry_id}:{self.student_id}")
        result = planner.publish_entry(
            entry_id, self.staff_id, expected_version=old_version, now=NOW
        )
        self.assertEqual(result.published_task_id, task_id)
        self.assertEqual(Task.query.count(), 1)
        self.assertEqual(PlanItem.query.count(), 1)
        self.assertEqual(TaskPlannerEvent.query.filter_by(action="publish").count(), 1)
        self.assertFalse(self.network_mock.called)

    def test_cancelled_entry_never_publishes(self):
        row = self.ready()
        row = planner.cancel_entry(row.id, row.version, self.staff_id)
        with self.assertRaises(planner.TaskPlannerError):
            self.publish(row)
        planner.set_student_enabled(self.student_id, True, self.staff_id)
        self.assertEqual(planner.run_due(now=NOW)["eligible"], 0)
        self.assertEqual(Task.query.count(), 0)

    def test_automatic_dispatch_is_opt_in_and_dry_run_does_not_write(self):
        row = self.ready()
        self.assertEqual(planner.run_due(now=NOW)["eligible"], 0)
        planner.set_student_enabled(self.student_id, True, self.staff_id)
        count = TaskPlannerEvent.query.count()
        report = planner.run_due(now=NOW, dry_run=True)
        self.assertEqual((report["eligible"], report["published"]), (1, 0))
        self.assertEqual(Task.query.count(), 0)
        self.assertEqual(TaskPlannerEvent.query.count(), count)
        self.assertEqual(db.session.get(TaskPlannerEntry, row.id).status, "ready")
        planner.set_student_enabled(self.student_id, False, self.staff_id)
        self.assertEqual(planner.run_due(now=NOW)["eligible"], 0)
        planner.set_student_enabled(self.student_id, True, self.staff_id)
        self.assertEqual(planner.run_due(now=NOW)["published"], 1)
        self.assertEqual(planner.run_due(now=NOW)["eligible"], 0)

    def test_window_includes_0305_to_085959_and_excludes_other_times(self):
        self.ready()
        planner.set_student_enabled(self.student_id, True, self.staff_id)
        for clock in ((2, 59, 59), (3, 0, 0), (3, 4, 59), (9, 0, 0), (23, 0, 0)):
            with self.subTest(clock=clock):
                now = NOW.replace(hour=clock[0], minute=clock[1], second=clock[2])
                self.assertTrue(planner.run_due(now=now)["outside_window"])
                self.assertEqual(Task.query.count(), 0)
        now = NOW.replace(hour=8, minute=59, second=59)
        self.assertEqual(planner.run_due(now=now)["published"], 1)

    def test_runner_never_backfills_or_publishes_future_dates(self):
        row = self.ready()
        planner.set_student_enabled(self.student_id, True, self.staff_id)
        for days in (-1, 1):
            self.assertEqual(planner.run_due(now=NOW + timedelta(days=days))["eligible"], 0)
        with self.assertRaises(planner.TaskPlannerError) as raised:
            planner.publish_entry(row.id, self.staff_id, row.version, now=NOW + timedelta(days=1))
        self.assertEqual(raised.exception.code, "wrong_date")
        self.assertEqual(db.session.get(TaskPlannerEntry, row.id).target_date, NOW.date())
        self.assertEqual(Task.query.count(), 0)

    def test_same_name_profiles_are_rejected_before_saving(self):
        db.session.add(StudentProfile(full_name="合成学生甲"))
        db.session.commit()
        with self.assertRaises(planner.TaskPlannerError) as raised:
            self.draft()
        self.assertEqual(raised.exception.code, "ambiguous_student")
        self.assertEqual(TaskPlannerEntry.query.count(), 0)

    def test_wrong_student_and_later_prerequisites_are_rejected(self):
        other = self.prerequisite(student_id=self.other_id)
        with self.assertRaises(planner.TaskPlannerError):
            self.draft(prerequisite_task_id=other.id)
        own = self.prerequisite()
        own.date = (NOW + timedelta(days=1)).date().isoformat()
        db.session.commit()
        with self.assertRaises(planner.TaskPlannerError):
            self.draft(prerequisite_task_id=own.id)
        self.assertEqual(TaskPlannerEntry.query.count(), 0)

    def test_incomplete_dependency_blocks_only_its_arrangement(self):
        before = self.prerequisite()
        blocked = self.ready(prerequisite_task_id=before.id)
        other = self.ready(student_id=self.other_id)
        for student_id in (self.student_id, self.other_id):
            planner.set_student_enabled(student_id, True, self.staff_id)
        report = planner.run_due(now=NOW)
        self.assertEqual((report["blocked"], report["published"]), (1, 1))
        self.assertEqual(db.session.get(TaskPlannerEntry, blocked.id).status, "blocked")
        self.assertEqual(db.session.get(TaskPlannerEntry, other.id).status, "published")
        self.assertEqual(db.session.get(TaskPlannerEntry, blocked.id).target_date, NOW.date())

    def test_submitted_pending_review_allows_progress_but_rejected_blocks(self):
        before = self.prerequisite(user_status="submitted", submitted_at=NOW.replace(tzinfo=None))
        row = self.ready(prerequisite_task_id=before.id)
        before.plan_item.review_status = "rejected"
        db.session.commit()
        result = self.publish(row)
        self.assertEqual(result.status, "blocked")
        self.assertEqual(Task.query.count(), 1)
        before = db.session.get(Task, before.id)
        before.plan_item.review_status = "pending"
        db.session.commit()
        row = planner.confirm_entry(row.id, result.version, self.staff_id, now=NOW)
        self.assertEqual(self.publish(row).status, "published")
        self.assertEqual(db.session.get(Task, before.id).plan_item.review_status, "pending")

    def test_word_dependency_needs_own_student_settlement(self):
        before = self.prerequisite(vocabulary_goal="reading", student_submitted=True)
        row = self.ready(prerequisite_task_id=before.id)
        self.assertEqual(self.publish(row).status, "blocked")
        for student_user_id, expected in (
            (self.other_user_id, "blocked"),
            (self.user_id, "published"),
        ):
            db.session.add(
                VocabularyTaskSettlement(
                    student_id=student_user_id,
                    task_id=before.id,
                    queue_token=f"synthetic-{student_user_id}",
                    result_json="{}",
                    settled_at=NOW.replace(tzinfo=None),
                )
            )
            db.session.commit()
            row = planner.confirm_entry(row.id, row.version, self.staff_id, now=NOW)
            self.assertEqual(self.publish(row).status, expected)

    def test_confirming_actor_is_rechecked_at_execution(self):
        row = self.ready()
        planner.set_student_enabled(self.student_id, True, self.staff_id)
        db.session.get(User, self.staff_id).is_active = False
        db.session.commit()
        self.assertEqual(planner.run_due(now=NOW)["blocked"], 1)
        self.assertEqual(Task.query.count(), 0)
        self.assertIn("账号", db.session.get(TaskPlannerEntry, row.id).last_error)

    def test_resource_disabled_after_confirmation_blocks_without_substitution(self):
        row = self.ready()
        db.session.get(DictationBook, self.book_id).is_active = False
        db.session.commit()
        self.assertEqual(self.publish(row).status, "blocked")
        self.assertEqual(Task.query.count(), 0)
        self.assertEqual(PlanItem.query.count(), 0)

    def test_duplicate_ready_plan_and_formal_task_are_blocked(self):
        first = self.ready()
        second = self.draft()
        with self.assertRaises(planner.TaskPlannerError) as raised:
            planner.confirm_entry(second.id, second.version, self.staff_id, now=NOW)
        self.assertEqual(raised.exception.code, "duplicate_plan")
        self.publish(first)
        with self.assertRaises(planner.TaskPlannerError) as raised:
            planner.confirm_entry(second.id, second.version, self.staff_id, now=NOW)
        self.assertEqual(raised.exception.code, "duplicate_assignment")
        self.assertEqual(Task.query.count(), 1)

    def test_flush_failure_rolls_back_both_tables_and_retry_succeeds(self):
        row = self.ready()
        original = planner.resources.create_resource_task

        def fail_after_flush(*args, **kwargs):
            original(*args, **kwargs)
            db.session.flush()
            raise RuntimeError("synthetic failure after both rows")

        with patch.object(planner.resources, "create_resource_task", side_effect=fail_after_flush):
            result = self.publish(row)
        self.assertEqual(result.status, "failed")
        self.assertEqual(
            (Task.query.count(), PlanItem.query.count(), StudyPlan.query.count()), (0, 0, 0)
        )
        self.assertIsNone(result.published_task_id)
        result = self.publish(result)
        self.assertEqual(result.status, "published")
        self.assertEqual((Task.query.count(), PlanItem.query.count()), (1, 1))
        self.assertEqual(TaskPlannerEvent.query.filter_by(action="failed").count(), 1)

    def test_concurrent_dispatchers_create_only_one_task(self):
        row = self.ready()
        entry_id, version = row.id, row.version
        db.session.remove()
        barrier = threading.Barrier(2)

        def dispatch():
            with self.app.app_context():
                barrier.wait(timeout=10)
                result = planner.publish_entry(
                    entry_id, self.staff_id, expected_version=version, now=NOW
                )
                task_id = result.published_task_id
                db.session.remove()
                return task_id

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(dispatch) for _ in range(2)]
            ids = [future.result(timeout=20) for future in futures]
        self.assertEqual(ids[0], ids[1])
        self.assertIsNotNone(ids[0])
        self.assertEqual((Task.query.count(), PlanItem.query.count()), (1, 1))

    def test_non_staff_cannot_save_or_enable_and_enable_requires_boolean(self):
        for user_id in (self.user_id, self.parent_id):
            with self.assertRaises(planner.TaskPlannerError) as raised:
                planner.save_entry(self.data(), user_id, now=NOW)
            self.assertEqual(raised.exception.status, 403)
            with self.assertRaises(planner.TaskPlannerError):
                planner.set_student_enabled(self.student_id, True, user_id)
        for invalid in ("false", "true", 0, 1, None):
            with self.subTest(value=invalid):
                with self.assertRaises(planner.TaskPlannerError):
                    planner.set_student_enabled(self.student_id, invalid, self.staff_id)
        self.assertEqual(TaskPlannerStudent.query.count(), 0)

    def test_generated_unstarted_task_can_be_cancelled_without_republishing(self):
        row = self.publish(self.ready())
        task_id = row.published_task_id
        delete_unstarted_task(task_id, actor_id=self.staff_id, is_allowed=lambda task: True)
        db.session.commit()
        self.assertEqual(Task.query.count(), 0)
        self.assertEqual(db.session.get(TaskPlannerEntry, row.id).status, "published")
        self.assertEqual(self.publish(row).published_task_id, task_id)
        self.assertEqual(Task.query.count(), 0)

    def test_cancelled_prerequisite_blocks_linked_arrangement(self):
        before = self.prerequisite()
        row = self.ready(prerequisite_task_id=before.id)
        delete_unstarted_task(before.id, actor_id=self.staff_id, is_allowed=lambda task: True)
        db.session.commit()
        self.assertEqual(self.publish(row).status, "blocked")
        self.assertEqual(Task.query.count(), 0)


class TaskPlannerAPITest(PlannerFixture):
    def test_anonymous_and_non_staff_cannot_read_or_write(self):
        self.assertEqual(self.client.get("/api/task-planner/bootstrap").status_code, 401)
        self.assertEqual(self.client.get("/task-planner").status_code, 302)
        for user_id in (self.user_id, self.parent_id):
            self.login(user_id)
            self.assertEqual(self.client.get("/api/task-planner/bootstrap").status_code, 403)
            self.assertEqual(
                self.client.post("/api/task-planner/entries", json=self.data()).status_code, 403
            )

    def test_staff_bootstrap_has_minimal_profile_and_stable_csrf(self):
        for user_id in (self.staff_id, self.teacher_id, self.admin_id):
            self.login(user_id)
            first = self.client.get("/api/task-planner/bootstrap")
            self.assertEqual(first.status_code, 200)
            body = first.get_json()
            self.assertTrue(all(set(row) == {"id", "name", "enabled"} for row in body["students"]))
            self.assertTrue(all(not row["enabled"] for row in body["students"]))
            self.assertEqual(
                body["csrf_token"],
                self.client.get("/api/task-planner/bootstrap").get_json()["csrf_token"],
            )

    def test_csrf_origin_and_json_are_required(self):
        self.login()
        self.assertEqual(
            self.client.post("/api/task-planner/entries", json=self.data()).status_code, 403
        )
        headers = self.csrf_headers()
        bad_origin = dict(headers, Origin="https://untrusted.example")
        self.assertEqual(
            self.client.post(
                "/api/task-planner/entries", json=self.data(), headers=bad_origin
            ).status_code,
            403,
        )
        self.assertEqual(
            self.client.post("/api/task-planner/entries", data="x", headers=headers).status_code,
            400,
        )
        self.assertEqual(
            self.client.post("/api/task-planner/entries", json=[], headers=headers).status_code, 400
        )
        self.assertEqual(TaskPlannerEntry.query.count(), 0)

    def test_api_save_confirm_edit_and_stale_version_contract(self):
        self.login()
        headers = self.csrf_headers()
        today = datetime.now(SHANGHAI).date().isoformat()
        payload = self.data(target_date=today)
        created = self.client.post("/api/task-planner/entries", json=payload, headers=headers)
        self.assertEqual(created.status_code, 201, created.get_data(as_text=True))
        entry = created.get_json()["entry"]
        base = f"/api/task-planner/entries/{entry['id']}"
        confirmed = self.client.post(
            base + "/confirm", json={"version": entry["version"]}, headers=headers
        )
        self.assertEqual(confirmed.status_code, 200, confirmed.get_data(as_text=True))
        new_entry = confirmed.get_json()["entry"]
        self.assertEqual(new_entry["status"], "ready")
        stale = self.client.patch(
            base, json=dict(payload, version=entry["version"]), headers=headers
        )
        self.assertEqual(stale.status_code, 409)
        edited = self.client.patch(
            base, json=dict(payload, version=new_entry["version"], note="编辑"), headers=headers
        )
        self.assertEqual(edited.status_code, 200)
        self.assertEqual(edited.get_json()["entry"]["status"], "draft")
        self.assertEqual(Task.query.count(), 0)
        self.assertEqual(PlanItem.query.count(), 0)

    def test_attention_finds_old_unpublished_entries_without_rescheduling(self):
        row = self.ready()
        row.target_date = (datetime.now(SHANGHAI) - timedelta(days=5)).date()
        db.session.commit()
        self.login()
        normal = self.client.get("/api/task-planner/entries").get_json()
        self.assertEqual(normal["entries"], [])
        attention = self.client.get("/api/task-planner/entries?status=attention").get_json()
        self.assertEqual([entry["id"] for entry in attention["entries"]], [row.id])
        self.assertIn("目标日期已过", attention["entries"][0]["error"])
        self.assertEqual(Task.query.count(), 0)

    def test_invalid_query_and_non_boolean_enrollment_are_rejected(self):
        self.login()
        headers = self.csrf_headers()
        for query in (
            "from=bad",
            "from=2026-01-01&to=2026-12-31",
            "status=unknown",
            "student_id=true",
        ):
            self.assertEqual(self.client.get("/api/task-planner/entries?" + query).status_code, 400)
        path = f"/api/task-planner/students/{self.student_id}/enable"
        self.assertEqual(
            self.client.post(path, json={"enabled": "false"}, headers=headers).status_code, 400
        )
        response = self.client.post(path, json={"enabled": True}, headers=headers)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["enabled"])


if __name__ == "__main__":
    unittest.main()
