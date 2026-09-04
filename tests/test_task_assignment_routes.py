"""Route-level regression coverage for the unified legacy assignment form."""

import json
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path

from flask import Flask
from flask_login import LoginManager
from sqlalchemy import inspect, select, text

import app as app_module
from api.task_assignments import listening_segments_api, writing_catalog_api
from models import (
    AuditLogEntry,
    DictationBook,
    DictationWord,
    MaterialBank,
    PlanItem,
    Question,
    StudentProfile,
    StudySession,
    Task,
    User,
    VocabularySense,
    VocabularyTaskReview,
    db,
)
from services.task_deletion import task_reference_columns


class LegacyTaskAssignmentRouteTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__, template_folder="../templates", static_folder="../static")
        self.app.config.update(
            TESTING=True,
            SECRET_KEY="legacy-task-route-test",
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
        )
        self.listening_root = tempfile.TemporaryDirectory()
        self.app.config["LISTENING_ASSIGNMENT_ROOT"] = self.listening_root.name
        Path(self.listening_root.name, "lazy_sample.json").write_text(
            json.dumps(
                {
                    "title": "Lazy sample",
                    "parts": [
                        {
                            "name": "Part 1",
                            "segments": [{"text": "LAZY_SEGMENT_SENTINEL"}],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        db.init_app(self.app)
        login = LoginManager(self.app)

        @login.user_loader
        def load_user(user_id):
            return db.session.get(User, int(user_id))

        self.app.add_url_rule("/tasks", endpoint="tasks_page", view_func=app_module.tasks_page, methods=["GET", "POST"])
        self.app.add_url_rule(
            "/api/tasks/<int:tid>/delete",
            endpoint="api_task_delete",
            view_func=app_module.api_task_delete,
            methods=["POST"],
        )
        self.app.add_url_rule(
            "/api/task-assignments/writing-catalog",
            endpoint="writing_catalog_api",
            view_func=writing_catalog_api,
            methods=["GET"],
        )
        self.app.add_url_rule(
            "/api/task-assignments/listening-segments",
            endpoint="listening_segments_api",
            view_func=listening_segments_api,
            methods=["GET"],
        )
        self.app.jinja_env.globals["url_for"] = lambda endpoint, **values: (
            f"/static/{values.get('filename', '')}"
            if endpoint == "static"
            else f"/{endpoint}"
        )
        self.original_app = app_module.app
        app_module.app = self.app
        with self.app.app_context():
            db.create_all()
            staff = User(username="legacy-route-staff", password_hash="test", role=User.ROLE_ASSISTANT)
            teacher = User(username="legacy-route-teacher", password_hash="test", role=User.ROLE_TEACHER)
            other_teacher = User(username="legacy-route-other-teacher", password_hash="test", role=User.ROLE_TEACHER)
            student_user = User(username="legacy-route-student", password_hash="test", role=User.ROLE_STUDENT)
            db.session.add_all([staff, teacher, other_teacher, student_user])
            db.session.flush()
            self.student_name = "路由学生A"
            db.session.add(StudentProfile(full_name=self.student_name, user_id=student_user.id))
            material = MaterialBank(title="路由材料", type="translation", created_by=staff.id)
            db.session.add(material)
            db.session.flush()
            question = Question(material_id=material.id, sequence=1, question_type="text", content="Translate", reference_answer="answer")
            db.session.add(question)
            db.session.commit()
            self.staff_id = staff.id
            self.teacher_id = teacher.id
            self.other_teacher_id = other_teacher.id
            self.student_user_id = student_user.id
            self.material_id = material.id
            self.question_id = question.id
        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        self.listening_root.cleanup()
        app_module.app = self.original_app

    def _login_as(self, user_id):
        with self.client.session_transaction() as session:
            session["_user_id"] = str(user_id)
            session["_fresh"] = True

    def _login(self):
        self._login_as(self.staff_id)

    def _post(self, **values):
        self._login()
        idempotency_key = values.pop("idempotency_key", "route-key-1")
        payload = {
            "date": date.today().isoformat(),
            "student_name": self.student_name,
            "category": "基础-翻译句子练习",
            "detail": "路由回归任务",
            "status": "pending",
            "planned_minutes": "15",
            "task_source": "custom",
        }
        if idempotency_key is not None:
            payload["idempotency_key"] = idempotency_key
        payload.update(values)
        return self.client.post("/tasks", data=payload, headers={"Accept": "application/json"})

    def test_ordinary_publish_is_idempotent_and_returns_staff_safe_payload(self):
        first = self._post()
        self.assertEqual(first.status_code, 200, first.get_data(as_text=True))
        second = self._post()
        self.assertEqual(second.status_code, 200, second.get_data(as_text=True))
        self.assertTrue(second.get_json()["idempotent"])
        body = second.get_json()["task"]
        self.assertEqual(set(body), {"id", "student_name", "status", "review_url"})
        self.assertNotIn("token=", second.get_data(as_text=True))
        with self.app.app_context():
            self.assertEqual(Task.query.count(), 1)

    def test_staff_writing_catalog_exposes_both_assignable_layers(self):
        self._login()
        response = self.client.get("/api/task-assignments/writing-catalog")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["summary"], {"exercises": 40, "mother_topics": 27})
        self.assertEqual(len(payload["resources"]), 67)
        self.assertEqual(
            {row["resource_type"] for row in payload["resources"]},
            {"exercise", "mother_topic"},
        )

        self._login_as(self.student_user_id)
        forbidden = self.client.get("/api/task-assignments/writing-catalog")
        self.assertEqual(forbidden.status_code, 403)

    def test_intensive_listening_segments_are_staff_only_and_loaded_on_demand(self):
        self._login()
        missing = self.client.get("/api/task-assignments/listening-segments")
        self.assertEqual(missing.status_code, 400)
        response = self.client.get(
            "/api/task-assignments/listening-segments?exercise_id=lazy_sample"
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json()["segments"],
            [
                {
                    "id": 0,
                    "sequence": 1,
                    "content": "Part 1 · 第1句 · LAZY_SEGMENT_SENTINEL",
                }
            ],
        )
        traversal = self.client.get(
            "/api/task-assignments/listening-segments?exercise_id=../lazy_sample"
        )
        self.assertEqual(traversal.status_code, 404)

        self._login_as(self.student_user_id)
        forbidden = self.client.get(
            "/api/task-assignments/listening-segments?exercise_id=lazy_sample"
        )
        self.assertEqual(forbidden.status_code, 403)

    def test_task_workspace_renders_only_one_server_page_and_preserves_filters(self):
        with self.app.app_context():
            tasks = [
                Task(
                    date=date.today().isoformat(),
                    student_name=self.student_name,
                    category="雅思-写作-母题" if index == 12 else "材料练习",
                    detail="唯一筛选任务" if index == 12 else f"分页任务 {index:02d}",
                    status="done" if index % 3 == 0 else "pending",
                    created_by=self.staff_id,
                    planned_minutes=20,
                )
                for index in range(27)
            ]
            db.session.add_all(tasks)
            db.session.commit()

        self._login()
        first = self.client.get("/tasks")
        self.assertEqual(first.status_code, 200, first.get_data(as_text=True))
        first_html = first.get_data(as_text=True)
        self.assertEqual(first_html.count('<tr data-id="'), 10)
        self.assertIn("显示 1–10 / 共 27 条任务", first_html)
        self.assertNotIn("listeningExerciseSegments", first_html)
        self.assertNotIn("LAZY_SEGMENT_SENTINEL", first_html)

        second = self.client.get("/tasks?page=2&page_size=10")
        self.assertEqual(second.status_code, 200, second.get_data(as_text=True))
        self.assertEqual(second.get_data(as_text=True).count('<tr data-id="'), 10)
        self.assertIn('aria-current="page"', second.get_data(as_text=True))

        filtered = self.client.get("/tasks?q=唯一筛选")
        self.assertEqual(filtered.status_code, 200, filtered.get_data(as_text=True))
        filtered_html = filtered.get_data(as_text=True)
        self.assertEqual(filtered_html.count('<tr data-id="'), 1)
        self.assertIn("唯一筛选任务", filtered_html)
        self.assertIn('value="唯一筛选"', filtered_html)

        pinyin = self.client.get("/tasks?student=luyouxuesheng")
        self.assertEqual(pinyin.status_code, 200, pinyin.get_data(as_text=True))
        self.assertEqual(pinyin.get_data(as_text=True).count('<tr data-id="'), 10)

    def test_legacy_sources_without_or_with_same_key_do_not_create_two_batches(self):
        no_key_first = self._post(idempotency_key=None)
        no_key_second = self._post(idempotency_key=None)
        self.assertEqual(no_key_first.status_code, 200, no_key_first.get_data(as_text=True))
        self.assertEqual(no_key_second.status_code, 200, no_key_second.get_data(as_text=True))
        self.assertTrue(no_key_second.get_json()["idempotent"])
        for source, fields in (
            (
                "material",
                {
                    "material_id": str(self.material_id),
                    "question_ids": json.dumps([self.question_id]),
                    "category": "材料练习",
                    "detail": "",
                },
            ),
            (
                "listening",
                {
                    "category": "雅思-听力-整套",
                    "detail": "",
                    "listening_exercise_id": "ielts10_test1",
                    "listening_resource_type": "cambridge_test",
                    "listening_section_number": "2",
                },
            ),
            (
                "reading",
                {
                    "category": "雅思-阅读-整套",
                    "detail": "",
                    "reading_test_id": "ielts14_test4_reading",
                    "reading_passage_number": "1",
                },
            ),
        ):
            first = self._post(task_source=source, idempotency_key=f"{source}-same", **fields)
            second = self._post(task_source=source, idempotency_key=f"{source}-same", **fields)
            self.assertEqual(first.status_code, 200, first.get_data(as_text=True))
            self.assertEqual(second.status_code, 200, second.get_data(as_text=True))
            self.assertTrue(second.get_json()["idempotent"])
        with self.app.app_context():
            self.assertEqual(Task.query.count(), 4)

    def test_material_listening_and_reading_contracts_publish(self):
        material = self._post(
            idempotency_key="material-key",
            task_source="material",
            material_id=str(self.material_id),
            question_ids=json.dumps([self.question_id]),
            category="材料练习",
            detail="",
        )
        self.assertEqual(material.status_code, 200, material.get_data(as_text=True))

        listening = self._post(
            idempotency_key="listening-key",
            task_source="listening",
            category="雅思-听力-整套",
            detail="",
            listening_exercise_id="ielts10_test1",
            listening_resource_type="cambridge_test",
            listening_section_number="2",
        )
        self.assertEqual(listening.status_code, 200, listening.get_data(as_text=True))

        reading = self._post(
            idempotency_key="reading-key",
            task_source="reading",
            category="雅思-阅读-整套",
            detail="",
            reading_test_id="ielts14_test4_reading",
            reading_passage_number="1",
        )
        self.assertEqual(reading.status_code, 200, reading.get_data(as_text=True))
        with self.app.app_context():
            rows = Task.query.order_by(Task.id).all()
            self.assertEqual(rows[0].question_ids, json.dumps([self.question_id]))
            self.assertEqual(json.loads(rows[1].question_ids)["listening_section_number"], 2)
            self.assertEqual(rows[2].reading_passage_number, 1)

    def test_writing_exercise_publishes_a_deep_linkable_resource_and_blocks_duplicate(self):
        first = self._post(
            idempotency_key="writing-first",
            task_source="writing",
            category="",
            detail="",
            writing_resource_type="exercise",
            writing_resource_id="t2-010",
        )
        self.assertEqual(first.status_code, 200, first.get_data(as_text=True))
        with self.app.app_context():
            task = Task.query.one()
            snapshot = json.loads(task.question_ids)
            self.assertEqual(task.grading_mode, "writing_practice")
            self.assertEqual(task.category, "雅思-写作-大作文")
            self.assertEqual(snapshot["writing_resource_type"], "exercise")
            self.assertEqual(snapshot["writing_resource_id"], "t2-010")
            self.assertEqual(task.plan_item.resource_type, "writing_exercise")
            self.assertEqual(task.plan_item.resource_id, "t2-010")
            practice_payload = app_module._practice_task_payload(task)
            self.assertEqual(practice_payload["url"], f"/writing/t2-010?task_id={task.id}")
            self.assertEqual(practice_payload["source_label"], "IELTS 写作真题")

        duplicate = self._post(
            idempotency_key="writing-second",
            task_source="writing",
            category="",
            detail="",
            writing_resource_type="exercise",
            writing_resource_id="t2-010",
        )
        self.assertEqual(duplicate.status_code, 409, duplicate.get_data(as_text=True))
        self.assertEqual(duplicate.get_json()["resource"]["kind"], "writing")
        self.assertNotIn("token=", duplicate.get_data(as_text=True))

    def test_writing_mother_topic_publishes_with_topic_resource_binding(self):
        response = self._post(
            idempotency_key="writing-topic",
            task_source="writing",
            category="",
            detail="",
            planned_minutes="",
            writing_resource_type="mother_topic",
            writing_resource_id="t01",
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        with self.app.app_context():
            task = Task.query.one()
            self.assertEqual(task.category, "雅思-写作-母题")
            self.assertEqual(task.planned_minutes, 30)
            self.assertEqual(task.plan_item.resource_type, "writing_mother_topic")

    def test_material_duplicate_returns_json_409_with_match_details_and_is_atomic(self):
        first = self._post(
            idempotency_key="material-first",
            task_source="material",
            material_id=str(self.material_id),
            question_ids=json.dumps([self.question_id]),
            category="材料练习",
            detail="",
        )
        self.assertEqual(first.status_code, 200, first.get_data(as_text=True))
        conflict = self._post(
            idempotency_key="material-second",
            task_source="material",
            material_id=str(self.material_id),
            question_ids=json.dumps([self.question_id]),
            category="材料练习",
            detail="",
        )
        self.assertEqual(conflict.status_code, 409, conflict.get_data(as_text=True))
        payload = conflict.get_json()
        self.assertEqual(payload["error"], "duplicate_assignment_conflict")
        self.assertEqual(payload["students"][0]["matches"][0]["overlap_type"], "exact")
        self.assertIn("view_url", payload["students"][0]["matches"][0])
        self.assertNotIn("token=", conflict.get_data(as_text=True))
        with self.app.app_context():
            self.assertEqual(Task.query.count(), 1)

    def test_listening_section_and_reading_passage_duplicates_return_409(self):
        for source, fields in (
            (
                "listening",
                {
                    "category": "雅思-听力-整套",
                    "detail": "",
                    "listening_exercise_id": "ielts10_test1",
                    "listening_resource_type": "cambridge_test",
                    "listening_section_number": "2",
                },
            ),
            (
                "reading",
                {
                    "category": "雅思-阅读-整套",
                    "detail": "",
                    "reading_test_id": "ielts14_test4_reading",
                    "reading_passage_number": "1",
                },
            ),
        ):
            first = self._post(task_source=source, idempotency_key=f"{source}-first", **fields)
            self.assertEqual(first.status_code, 200, first.get_data(as_text=True))
            second = self._post(task_source=source, idempotency_key=f"{source}-second", **fields)
            self.assertEqual(second.status_code, 409, second.get_data(as_text=True))
            self.assertEqual(second.get_json()["error"], "duplicate_assignment_conflict")
            self.assertEqual(second.get_json()["students"][0]["matches"][0]["overlap_type"], "exact")

    def test_legacy_schema_ensures_task_assignment_safety_columns_and_indexes(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
            db.session.execute(text("CREATE TABLE task (id INTEGER PRIMARY KEY)"))
            db.session.commit()
            app_module.ensure_legacy_schema()
            inspector = inspect(db.engine)
            columns = {column["name"] for column in inspector.get_columns("task")}
            indexes = {index["name"] for index in inspector.get_indexes("task")}
            self.assertIn("assignment_idempotency_key", columns)
            self.assertIn("ix_task_assignment_idempotency_key", indexes)
            self.assertIn("cancelled_at", columns)
            self.assertIn("ix_task_cancelled_at", indexes)

    @staticmethod
    def _cancelled_task(task_id):
        return db.session.execute(
            select(Task)
            .where(Task.id == task_id)
            .execution_options(include_cancelled_tasks=True)
        ).scalar_one_or_none()

    def test_student_role_cannot_open_staff_task_workspace(self):
        self._login_as(self.student_user_id)
        response = self.client.get("/tasks", headers={"Accept": "application/json"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error"], "forbidden")

    def test_student_role_cannot_delete_even_a_self_created_task(self):
        with self.app.app_context():
            task = Task(
                date=date.today().isoformat(),
                student_name=self.student_name,
                category="材料练习",
                detail="不应由学生删除",
                status="pending",
                created_by=self.student_user_id,
            )
            db.session.add(task)
            db.session.commit()
            task_id = task.id
        self._login_as(self.student_user_id)
        response = self.client.post(
            f"/api/tasks/{task_id}/delete",
            headers={"Accept": "application/json"},
        )
        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.get_json()["error"], "forbidden")
        with self.app.app_context():
            self.assertIsNotNone(db.session.get(Task, task_id))

    def test_assistant_can_delete_only_an_unstarted_task_and_an_audit_row_remains(self):
        with self.app.app_context():
            task = Task(
                date=date.today().isoformat(),
                student_name=self.student_name,
                category="材料练习",
                detail="误布置任务",
                status="pending",
                created_by=self.teacher_id,
            )
            db.session.add(task)
            db.session.commit()
            task_id = task.id
        self._login()
        response = self.client.post(
            f"/api/tasks/{task_id}/delete",
            headers={"Accept": "application/json"},
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        self.assertTrue(response.get_json()["ok"])
        with self.app.app_context():
            self.assertIsNone(db.session.get(Task, task_id))
            tombstone = self._cancelled_task(task_id)
            self.assertIsNotNone(tombstone)
            self.assertEqual(tombstone.status, Task.STATUS_CANCELLED)
            self.assertIsNotNone(tombstone.cancelled_at)
            audit = AuditLogEntry.query.filter_by(
                entity_type="task", entity_id=task_id, action="delete"
            ).one()
            self.assertEqual(audit.actor_id, self.staff_id)

    def test_deleting_an_unstarted_legacy_task_soft_deletes_its_plan_item(self):
        publish = self._post(idempotency_key="delete-plan-item")
        self.assertEqual(publish.status_code, 200, publish.get_data(as_text=True))
        task_id = publish.get_json()["task"]["id"]
        with self.app.app_context():
            plan_item_id = db.session.get(Task, task_id).plan_item_id
            self.assertIsNotNone(plan_item_id)
        response = self.client.post(
            f"/api/tasks/{task_id}/delete",
            headers={"Accept": "application/json"},
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        with self.app.app_context():
            self.assertIsNone(db.session.get(Task, task_id))
            self.assertTrue(db.session.get(PlanItem, plan_item_id).is_deleted)

    def test_deleting_one_of_two_tasks_does_not_soft_delete_the_shared_plan_item(self):
        publish = self._post(idempotency_key="shared-plan-item")
        self.assertEqual(publish.status_code, 200, publish.get_data(as_text=True))
        original_id = publish.get_json()["task"]["id"]
        with self.app.app_context():
            original = db.session.get(Task, original_id)
            plan_item_id = original.plan_item_id
            duplicate = Task(
                date=original.date,
                student_name=original.student_name,
                category=original.category,
                detail=original.detail,
                status="pending",
                created_by=self.teacher_id,
                plan_item_id=plan_item_id,
            )
            db.session.add(duplicate)
            db.session.commit()
            duplicate_id = duplicate.id
        response = self.client.post(
            f"/api/tasks/{duplicate_id}/delete",
            headers={"Accept": "application/json"},
        )
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
        with self.app.app_context():
            self.assertIsNone(db.session.get(Task, duplicate_id))
            self.assertIsNotNone(db.session.get(Task, original_id))
            self.assertFalse(db.session.get(PlanItem, plan_item_id).is_deleted)

    def test_cancelled_mistake_no_longer_blocks_a_clean_reassignment(self):
        fields = {
            "task_source": "material",
            "material_id": str(self.material_id),
            "question_ids": json.dumps([self.question_id]),
            "category": "材料练习",
            "detail": "",
        }
        first = self._post(idempotency_key="cancel-reassign-first", **fields)
        self.assertEqual(first.status_code, 200, first.get_data(as_text=True))
        first_id = first.get_json()["task"]["id"]
        deleted = self.client.post(
            f"/api/tasks/{first_id}/delete",
            headers={"Accept": "application/json"},
        )
        self.assertEqual(deleted.status_code, 200, deleted.get_data(as_text=True))

        second = self._post(idempotency_key="cancel-reassign-second", **fields)
        self.assertEqual(second.status_code, 200, second.get_data(as_text=True))
        self.assertNotEqual(second.get_json()["task"]["id"], first_id)
        with self.app.app_context():
            self.assertEqual(Task.query.count(), 1)
            self.assertEqual(self._cancelled_task(first_id).status, Task.STATUS_CANCELLED)
            self.assertIsNone(self._cancelled_task(first_id).assignment_idempotency_key)

    def test_delayed_progress_write_cannot_resurrect_a_cancelled_task(self):
        with self.app.app_context():
            task = Task(
                date=date.today().isoformat(),
                student_name=self.student_name,
                category="材料练习",
                detail="并发取消回归",
                status="pending",
                created_by=self.teacher_id,
            )
            db.session.add(task)
            db.session.commit()
            task_id = task.id

        self._login()
        deleted = self.client.post(
            f"/api/tasks/{task_id}/delete",
            headers={"Accept": "application/json"},
        )
        self.assertEqual(deleted.status_code, 200, deleted.get_data(as_text=True))

        with self.app.app_context():
            # Simulate a learner request that loaded the task before cancellation
            # and commits a stale status update after the delete transaction.
            db.session.execute(
                text("UPDATE task SET status = 'progress' WHERE id = :task_id"),
                {"task_id": task_id},
            )
            db.session.commit()
            db.session.expire_all()

            self.assertIsNone(db.session.get(Task, task_id))
            tombstone = self._cancelled_task(task_id)
            self.assertIsNotNone(tombstone)
            self.assertEqual(tombstone.status, "progress")
            self.assertIsNotNone(tombstone.cancelled_at)

    def test_teacher_can_delete_own_unstarted_task_but_not_another_teachers_task(self):
        with self.app.app_context():
            own_task = Task(
                date=date.today().isoformat(),
                student_name=self.student_name,
                category="普通任务",
                detail="教师自己的误布置任务",
                status="pending",
                created_by=self.teacher_id,
            )
            other_task = Task(
                date=date.today().isoformat(),
                student_name=self.student_name,
                category="普通任务",
                detail="其他教师的任务",
                status="pending",
                created_by=self.other_teacher_id,
            )
            db.session.add_all([own_task, other_task])
            db.session.commit()
            own_id = own_task.id
            other_id = other_task.id
        self._login_as(self.teacher_id)
        own_response = self.client.post(
            f"/api/tasks/{own_id}/delete",
            headers={"Accept": "application/json"},
        )
        self.assertEqual(own_response.status_code, 200, own_response.get_data(as_text=True))
        other_response = self.client.post(
            f"/api/tasks/{other_id}/delete",
            headers={"Accept": "application/json"},
        )
        self.assertEqual(other_response.status_code, 403)
        self.assertEqual(other_response.get_json()["error"], "no_permission")
        with self.app.app_context():
            self.assertIsNone(db.session.get(Task, own_id))
            self.assertIsNotNone(db.session.get(Task, other_id))

    def test_task_with_timer_history_is_preserved_instead_of_orphaned(self):
        with self.app.app_context():
            task = Task(
                date=date.today().isoformat(),
                student_name=self.student_name,
                category="材料练习",
                detail="已有计时记录",
                status="pending",
                created_by=self.staff_id,
            )
            db.session.add(task)
            db.session.flush()
            session = StudySession(
                task_id=task.id,
                started_at=datetime.utcnow(),
                seconds=0,
                created_by=self.staff_id,
            )
            db.session.add(session)
            db.session.commit()
            task_id = task.id
            session_id = session.id
        self._login()
        response = self.client.post(
            f"/api/tasks/{task_id}/delete",
            headers={"Accept": "application/json"},
        )
        self.assertEqual(response.status_code, 409, response.get_data(as_text=True))
        self.assertEqual(response.get_json()["error"], "task_has_activity")
        with self.app.app_context():
            self.assertIsNotNone(db.session.get(Task, task_id))
            self.assertEqual(db.session.get(StudySession, session_id).task_id, task_id)

    def test_activity_guard_covers_vocabulary_review_references(self):
        names = {table.name for table, _column in task_reference_columns()}
        self.assertIn("vocabulary_task_review", names)
        self.assertIn("vocabulary_task_settlement", names)
        self.assertIn("dictation_task_review", names)

    def test_task_with_vocabulary_snapshot_returns_conflict_instead_of_integrity_error(self):
        with self.app.app_context():
            task = Task(
                date=date.today().isoformat(),
                student_name=self.student_name,
                category="材料练习",
                detail="已有词汇快照",
                status="pending",
                created_by=self.staff_id,
            )
            book = DictationBook(title="删除保护词书", created_by=self.staff_id)
            sense = VocabularySense(canonical_key="delete-guard", lemma="guard")
            db.session.add_all([task, book, sense])
            db.session.flush()
            word = DictationWord(
                book_id=book.id,
                sense_id=sense.id,
                sequence=1,
                word="guard",
            )
            db.session.add(word)
            db.session.flush()
            review = VocabularyTaskReview(
                student_id=self.student_user_id,
                task_id=task.id,
                book_id=book.id,
                word_id=word.id,
                sense_id=sense.id,
                dimension="meaning_recall",
                source=VocabularyTaskReview.SOURCE_ASSIGNED,
                queue_index=0,
                question_id="delete-guard-question",
                question_snapshot_json="{}",
                answer_payload_json="{}",
            )
            db.session.add(review)
            db.session.commit()
            task_id = task.id
            review_id = review.id
        self._login()
        response = self.client.post(
            f"/api/tasks/{task_id}/delete",
            headers={"Accept": "application/json"},
        )
        self.assertEqual(response.status_code, 409, response.get_data(as_text=True))
        self.assertEqual(response.get_json()["error"], "task_has_activity")
        with self.app.app_context():
            self.assertIsNotNone(db.session.get(Task, task_id))
            self.assertEqual(db.session.get(VocabularyTaskReview, review_id).task_id, task_id)


if __name__ == "__main__":
    unittest.main()
