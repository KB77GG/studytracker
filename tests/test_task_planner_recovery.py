"""Synthetic recovery inbox contracts; never load production app/data."""

import copy
import json
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path
from unittest.mock import patch

from models import DictationWord, PlanItem, StudentProfile, Task, VocabularyTaskSettlement, db
from models_task_planner import TaskPlannerEntry, TaskPlannerRecoveryDecision, TaskPlannerSeriesItem
from services import task_planner as planner
from services import task_planner_bundles as bundles
from services import task_planner_recovery as recovery
from services import task_planner_resources as resources
from services import task_planner_series as series
from tests.test_task_planner import NOW, PlannerFixture


class TaskPlannerRecoveryTest(PlannerFixture):
    def setUp(self):
        super().setUp()
        db.session.add_all([DictationWord(book_id=self.book_id, sequence=i, word=f"word{i}", translation="词义")
                            for i in range(9, 81)])
        db.session.commit()
        root = Path(self.directory.name) / "static/reading_tests"
        root.mkdir(parents=True)
        for number in range(1, 4):
            test_id = f"ielts10_test{number}_reading"
            passages = [{"passage": p, "content": {"paragraphs": [{"text": "Synthetic text."}]},
                         "groups": [{"group_id": f"g{p}", "type": 1, "desc": "TRUE FALSE NOT GIVEN",
                                     "questions": [{"id": f"q{q}", "number": q, "title": "Synthetic question.",
                                                    "answer": "TRUE", "options": [
                                                        {"key": key, "text": key}
                                                        for key in ("TRUE", "FALSE", "NOT GIVEN")]}
                                                   for q in range(start, end + 1)]}]}
                        for p, (start, end) in enumerate(((1, 13), (14, 26), (27, 40)), 1)]
            (root / f"{test_id}.json").write_text(json.dumps({"id": test_id,
                "title": f"Cambridge 10 Test {number}", "passages": passages}), encoding="utf-8")

    def line(self, days=3, kind="dictation", **changes):
        data = {"name": "合成学习线", "kind": kind, "student_id": self.student_id,
                "start_date": NOW.date().isoformat(), "end_date": (NOW + timedelta(days=days - 1)).date().isoformat(),
                "weekday_counts": [1] * 7, "selection": {"book_id": self.book_id, "word_start": 1,
                                                        "vocabulary_goal": "reading"},
                "planned_minutes": 20, "wait_for_previous": True, "skip_assigned": True,
                "request_key": str(uuid.uuid4())}
        if kind == "reading_test":
            data.update(selection={}, source_scopes=["cambridge:10"], start_resource_id="ielts10_test1_reading:all")
        data.update(changes)
        data["preview_hash"] = series.preview_series(data, self.staff_id, now=NOW)["preview_hash"]
        line = series.create_series(data, self.staff_id, now=NOW)
        series.confirm_series(line.id, line.version, self.staff_id, now=NOW)
        entries = [db.session.get(TaskPlannerEntry, item.entry_id) for item in series._items(line.id)]
        planner.publish_entry(entries[0].id, self.staff_id, entries[0].version, now=NOW)
        return line, entries

    def preview(self, line, action="makeup", day=1, source_day=0):
        data = {"series_id": line.id, "source_date": (NOW + timedelta(days=source_day)).date().isoformat(),
                "action": action}
        result = recovery.preview_recovery(data, self.staff_id, now=NOW + timedelta(days=day))
        return data, result

    def apply(self, line, action="makeup", day=1, source_day=0):
        data, preview = self.preview(line, action, day, source_day)
        self.assertTrue(preview["can_apply"], preview["blockers"])
        data.update(preview_hash=preview["preview_hash"], request_key=str(uuid.uuid4()))
        result = recovery.apply_recovery(data, self.staff_id, now=NOW + timedelta(days=day))
        return result, data

    def settle(self, task_id):
        task = db.session.get(Task, task_id)
        if task.vocabulary_goal:
            db.session.add(VocabularyTaskSettlement(student_id=self.user_id, task_id=task.id,
                queue_token=f"recovery-{task.id}", result_json="{}", settled_at=NOW.replace(tzinfo=None)))
        else:
            task.status = "submitted"
            task.submitted_at = NOW.replace(tzinfo=None)
            task.plan_item.student_status = "submitted"
        db.session.commit()

    def test_makeup_three_day_gate_then_completed_new_task_resumes_shifted_plan(self):
        line, entries = self.line()
        old_task = db.session.get(Task, entries[0].published_task_id)
        original = (old_task.date, old_task.status, old_task.plan_item_id)
        planner.publish_entry(entries[1].id, self.staff_id, entries[1].version, now=NOW + timedelta(days=1))
        self.assertEqual(entries[1].status, "blocked")
        before = (Task.query.count(), PlanItem.query.count(), TaskPlannerEntry.query.count())
        _data, preview = self.preview(line)
        self.assertEqual(before, (Task.query.count(), PlanItem.query.count(), TaskPlannerEntry.query.count()))
        self.assertEqual([item["to"] for item in preview["changes"]], ["2026-10-31", "2026-11-01"])
        result, _data = self.apply(line)
        self.assertEqual((old_task.date, old_task.status, old_task.plan_item_id), original)
        self.assertEqual(entries[1].status, "ready")
        makeup = db.session.get(Task, result["created_task_ids"][0])
        self.assertEqual(makeup.date, "2026-10-30")
        self.assertEqual(result["task_mappings"][0]["source_task_id"], old_task.id)
        self.assertIn("顺延", series.series_payload(line)["recovery_notice"])
        self.settle(makeup.id)
        published = planner.publish_entry(entries[1].id, self.staff_id, entries[1].version,
                                          now=NOW + timedelta(days=2))
        self.assertEqual(published.status, "published")
        self.assertEqual(published.target_date.isoformat(), "2026-10-31")

    def test_unfinished_makeup_reappears_and_chain_only_exempts_ancestors(self):
        line, entries = self.line()
        first, _data = self.apply(line)
        inbox = recovery.list_inbox(now=NOW + timedelta(days=2))
        self.assertEqual([(item["source_date"], item["tasks"][0]["id"]) for item in inbox],
                         [("2026-10-30", first["created_task_ids"][0])])
        second, _data = self.apply(line, day=2, source_day=1)
        self.assertEqual(second["task_mappings"][0]["source_task_id"], first["created_task_ids"][0])
        self.assertEqual(entries[1].target_date.isoformat(), "2026-11-01")
        self.settle(second["created_task_ids"][0])
        published = planner.publish_entry(entries[1].id, self.staff_id, entries[1].version,
                                          now=NOW + timedelta(days=3))
        self.assertEqual(published.status, "published")

    def test_unrelated_same_content_task_blocks_makeup_even_when_ancestor_is_exempt(self):
        line, entries = self.line()
        choice = json.loads(entries[0].prepared_json)
        resources.create_resource_task(planner._student(self.student_id), choice, creator_id=self.staff_id,
            due_date="2026-10-28", planned_minutes=20, note="独立重复", idempotency_key="independent-repeat")
        db.session.commit()
        _data, preview = self.preview(line)
        self.assertFalse(preview["can_apply"])
        self.assertTrue(any("其他任务或安排重叠" in item for item in preview["blockers"]))

    def test_continue_recovers_today_blocked_without_auto_enrollment_or_time_window(self):
        line, entries = self.line()
        planner.publish_entry(entries[1].id, self.staff_id, entries[1].version, now=NOW + timedelta(days=1))
        data, preview = self.preview(line, "continue")
        data.update(preview_hash=preview["preview_hash"], request_key=str(uuid.uuid4()))
        result = recovery.apply_recovery(data, self.staff_id, now=(NOW + timedelta(days=1)).replace(hour=20))
        self.assertEqual(entries[1].status, "published")
        self.assertTrue(line.wait_for_previous)
        self.assertEqual(result["created_task_ids"], [entries[1].published_task_id])
        self.assertEqual(recovery.list_inbox(now=NOW + timedelta(days=1)), [])
        self.settle(entries[1].published_task_id)
        planner.publish_entry(entries[2].id, self.staff_id, entries[2].version, now=NOW + timedelta(days=2))
        self.assertEqual(entries[2].status, "published")

    def test_overdue_makeup_moves_earliest_pending_to_tomorrow_with_uniform_delta(self):
        line, entries = self.line(days=5)
        _data, preview = self.preview(line, day=4)
        self.assertEqual([item["to"] for item in preview["changes"]],
                         ["2026-11-03", "2026-11-04", "2026-11-05", "2026-11-06"])
        result, _data = self.apply(line, day=4)
        self.assertEqual(db.session.get(Task, result["created_task_ids"][0]).date, "2026-11-02")
        self.assertEqual([entry.target_date.isoformat() for entry in entries[1:]],
                         [item["to"] for item in preview["changes"]])

    def test_continue_lists_and_audits_overdue_skip_then_publishes_today(self):
        line, entries = self.line(days=4)
        _data, preview = self.preview(line, "continue", day=3)
        self.assertEqual([item["entry_id"] for item in preview["skipped_entries"]], [entries[1].id, entries[2].id])
        self.apply(line, "continue", day=3)
        self.assertEqual([entry.status for entry in entries], ["published", "cancelled", "cancelled", "published"])
        decision = TaskPlannerRecoveryDecision.query.one()
        self.assertEqual(json.loads(decision.snapshot_json)["waived_entry_ids"], [entry.id for entry in entries[:3]])

    def test_partial_reading_bundle_becomes_one_native_makeup_and_future_bundle_stays_valid(self):
        line, entries = self.line(kind="reading_test", days=2)
        self.settle(entries[0].published_task_id)
        self.settle(entries[2].published_task_id)
        result, _data = self.apply(line)
        new_entry = db.session.get(TaskPlannerEntry, result["published_entry_ids"][0])
        self.assertEqual(len(result["created_task_ids"]), 1)
        self.assertEqual(json.loads(new_entry.selection_json)["passage_number"], 2)
        self.assertIsNone(bundles._bundle(new_entry))
        self.assertEqual(TaskPlannerSeriesItem.query.filter_by(entry_id=new_entry.id).one().unit_count, 1)
        self.settle(new_entry.published_task_id)
        planner.publish_entry(entries[3].id, self.staff_id, entries[3].version, now=NOW + timedelta(days=2))
        self.assertEqual([entry.status for entry in entries[3:]], ["published"] * 3)

    def test_full_reading_makeup_gets_new_atomic_bundle_and_continue_checks_all_three(self):
        line, entries = self.line(kind="reading_test", days=2)
        result, _data = self.apply(line)
        new_entries = [db.session.get(TaskPlannerEntry, entry_id) for entry_id in result["published_entry_ids"]]
        self.assertEqual(len(new_entries), 3)
        self.assertEqual({entry.id for entry, _index in bundles._bundle(new_entries[0])[0]},
                         {entry.id for entry in new_entries})
        frozen = json.loads(line.definition_json)["rows"]
        self.assertNotEqual(frozen[0]["bundle_id"], frozen[-1]["bundle_id"])
        self.assertEqual([TaskPlannerSeriesItem.query.filter_by(entry_id=e.id).one().unit_count for e in new_entries],
                         [1, 0, 0])

    def test_continue_refuses_partial_cancelled_bundle(self):
        line, entries = self.line(kind="reading_test", days=2)
        entries[4].status = "cancelled"
        db.session.commit()
        _data, preview = self.preview(line, "continue")
        self.assertFalse(preview["can_apply"])
        self.assertTrue(any("整套阅读" in item for item in preview["blockers"]))
        self.assertEqual(Task.query.count(), 3)

    def test_late_returned_completed_sibling_reopens_same_day_without_waiving_it(self):
        line, entries = self.line(kind="reading_test", days=1)
        self.settle(entries[0].published_task_id)
        self.settle(entries[2].published_task_id)
        self.apply(line, "continue")
        p1 = db.session.get(Task, entries[0].published_task_id)
        p1.plan_item.review_status = "rejected"
        db.session.commit()
        inbox = recovery.list_inbox(now=NOW + timedelta(days=1))
        self.assertEqual([task["id"] for task in inbox[0]["tasks"]], [p1.id])
        self.apply(line, "continue")
        self.assertEqual(TaskPlannerRecoveryDecision.query.count(), 2)
        resolved = recovery.list_inbox(view="resolved", now=NOW + timedelta(days=1))
        self.assertGreater(resolved[0]["decision"]["id"], resolved[1]["decision"]["id"])

    def test_success_retry_across_beijing_day_is_idempotent_and_unapplied_old_preview_is_stale(self):
        line, _entries = self.line()
        result, data = self.apply(line)
        original_count = Task.query.count()
        replay = recovery.apply_recovery(data, self.staff_id, now=NOW + timedelta(days=2))
        self.assertEqual(replay, result)
        self.assertEqual(Task.query.count(), original_count)
        fresh, preview = self.preview(line, day=2, source_day=1)
        fresh.update(preview_hash=preview["preview_hash"], request_key=str(uuid.uuid4()))
        with self.assertRaises(planner.TaskPlannerError) as raised:
            recovery.apply_recovery(fresh, self.staff_id, now=NOW + timedelta(days=3))
        self.assertEqual(raised.exception.code, "preview_changed")

    def test_state_change_and_request_key_payload_reuse_are_rejected(self):
        line, entries = self.line()
        data, preview = self.preview(line)
        data.update(preview_hash=preview["preview_hash"], request_key=str(uuid.uuid4()))
        self.settle(entries[0].published_task_id)
        with self.assertRaises(planner.TaskPlannerError) as raised:
            recovery.apply_recovery(data, self.staff_id, now=NOW + timedelta(days=1))
        self.assertEqual(raised.exception.code, "preview_changed")
        self.assertEqual(TaskPlannerRecoveryDecision.query.count(), 0)

    def test_second_makeup_write_failure_rolls_back_tasks_planitems_dates_and_decision(self):
        line, entries = self.line(kind="reading_test", days=2)
        data, preview = self.preview(line)
        data.update(preview_hash=preview["preview_hash"], request_key=str(uuid.uuid4()))
        original = resources.create_resource_task
        count = 0
        def fail_second(*args, **kwargs):
            nonlocal count
            task = original(*args, **kwargs)
            count += 1
            if count == 2:
                raise RuntimeError("synthetic late write failure")
            return task
        before = [(entry.target_date, entry.status, entry.version) for entry in entries]
        definition = line.definition_json
        with patch.object(resources, "create_resource_task", side_effect=fail_second), self.assertRaises(RuntimeError):
            recovery.apply_recovery(data, self.staff_id, now=NOW + timedelta(days=1))
        self.assertEqual(Task.query.count(), 3)
        self.assertEqual(PlanItem.query.count(), 3)
        self.assertEqual(TaskPlannerEntry.query.count(), 6)
        self.assertEqual(TaskPlannerRecoveryDecision.query.count(), 0)
        self.assertEqual(before, [(entry.target_date, entry.status, entry.version) for entry in entries])
        self.assertEqual(line.definition_json, definition)
        recovery.apply_recovery(data, self.staff_id, now=NOW + timedelta(days=1))
        self.assertEqual(Task.query.count(), 6)

    def test_competing_requests_use_writer_lock_and_only_one_decision_wins(self):
        line, _entries = self.line()
        data, preview = self.preview(line)
        data.update(preview_hash=preview["preview_hash"], request_key=str(uuid.uuid4()))
        other = copy.deepcopy(data)
        other["request_key"] = str(uuid.uuid4())
        actor = self.staff_id
        barrier = threading.Barrier(2)
        db.session.remove()
        def invoke(payload):
            with self.app.app_context():
                barrier.wait(timeout=10)
                try:
                    return recovery.apply_recovery(payload, actor, now=NOW + timedelta(days=1))["decision_id"]
                except planner.TaskPlannerError as exc:
                    return exc.code
                finally:
                    db.session.remove()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(invoke, [data, other]))
        self.assertEqual(sum(isinstance(result, int) for result in results), 1)
        self.assertIn("preview_changed", results)
        self.assertEqual(TaskPlannerRecoveryDecision.query.count(), 1)
        self.assertEqual(Task.query.count(), 2)

    def test_published_today_blocks_makeup_but_continue_preserves_date_mode(self):
        line, entries = self.line(wait_for_previous=False)
        planner.publish_entry(entries[1].id, self.staff_id, entries[1].version, now=NOW + timedelta(days=1))
        _data, preview = self.preview(line)
        self.assertFalse(preview["can_apply"])
        self.assertTrue(any("今天或之后已有" in item for item in preview["blockers"]))
        self.apply(line, "continue")
        self.assertFalse(line.wait_for_previous)
        self.assertEqual(entries[2].target_date.isoformat(), "2026-10-31")

    def test_inbox_excludes_manual_work_valid_submission_and_cancelled_invalid_students(self):
        self.prerequisite()
        self.assertEqual(recovery.list_inbox(now=NOW + timedelta(days=1)), [])
        line, entries = self.line()
        task = db.session.get(Task, entries[0].published_task_id)
        task.status = "submitted"
        db.session.commit()
        self.assertEqual(len(recovery.list_inbox(now=NOW + timedelta(days=1))), 1)
        self.settle(task.id)
        self.assertEqual(recovery.list_inbox(now=NOW + timedelta(days=1)), [])
        task.plan_item.review_status = "partial"
        db.session.commit()
        self.assertEqual(len(recovery.list_inbox(now=NOW + timedelta(days=1))), 1)
        db.session.get(StudentProfile, self.student_id).is_deleted = True
        db.session.commit()
        self.assertEqual(recovery.list_inbox(now=NOW + timedelta(days=1)), [])

    def test_source_task_wrong_student_or_date_rejected_for_both_actions(self):
        line, entries = self.line()
        task = db.session.get(Task, entries[0].published_task_id)
        task.date = "2026-10-28"
        db.session.commit()
        for action in ("makeup", "continue"):
            with self.subTest(action=action), self.assertRaises(planner.TaskPlannerError):
                self.preview(line, action)

    def test_api_auth_csrf_and_result_shapes(self):
        line, _entries = self.line()
        self.assertEqual(self.client.get("/api/task-planner/inbox").status_code, 401)
        self.login(self.user_id)
        self.assertEqual(self.client.get("/api/task-planner/inbox").status_code, 403)
        self.login()
        headers = self.csrf_headers()
        data = {"series_id": line.id, "source_date": NOW.date().isoformat(), "action": "makeup"}
        self.assertEqual(self.client.post("/api/task-planner/inbox/preview", json=data).status_code, 403)
        for invalid in ([], {}, None, 1):
            bad = dict(data, action=invalid)
            self.assertEqual(self.client.post("/api/task-planner/inbox/preview", json=bad, headers=headers).status_code, 400)
        with patch.object(recovery, "beijing_now", return_value=NOW + timedelta(days=1)):
            items = self.client.get("/api/task-planner/inbox").get_json()["items"]
            self.assertEqual(items[0]["series_id"], line.id)
            response = self.client.post("/api/task-planner/inbox/preview", json=data, headers=headers)
            self.assertEqual(response.status_code, 200)
            preview = response.get_json()["preview"]
            data.update(preview_hash=preview["preview_hash"], request_key=str(uuid.uuid4()))
            response = self.client.post("/api/task-planner/inbox/apply", json=data, headers=headers)
            self.assertEqual(response.status_code, 200, response.get_json())
            self.assertEqual(response.get_json()["message"], response.get_json()["result"]["message"])
            resolved = self.client.get("/api/task-planner/inbox?view=resolved").get_json()["items"]
            self.assertEqual(resolved[0]["status"], "resolved")
            self.assertEqual(resolved[0]["decision"]["action"], "makeup")

    def test_legacy_single_kind_frozen_rows_without_kind_remain_recoverable(self):
        line, entries = self.line(skip_assigned=False)
        definition = json.loads(line.definition_json)
        self.assertNotIn("kind", definition["rows"][0])
        result, _data = self.apply(line)
        self.assertEqual(len(result["created_task_ids"]), 1)
        self.settle(result["created_task_ids"][0])
        planner.publish_entry(entries[1].id, self.staff_id, entries[1].version, now=NOW + timedelta(days=2))
        self.assertEqual(entries[1].status, "published")

    def test_waived_nearest_day_does_not_fall_back_to_older_unfinished_work(self):
        line, entries = self.line(wait_for_previous=False)
        planner.publish_entry(entries[1].id, self.staff_id, entries[1].version, now=NOW + timedelta(days=1))
        line.wait_for_previous = True
        db.session.commit()
        self.apply(line, "continue", day=2, source_day=1)
        self.assertEqual(entries[2].status, "published")
        inbox = recovery.list_inbox(now=NOW + timedelta(days=2))
        self.assertEqual([item["source_date"] for item in inbox], ["2026-10-29"])

    def test_explicit_unfinished_prerequisite_is_not_waived_by_series_decision(self):
        line, entries = self.line()
        other = self.prerequisite()
        entries[1].prerequisite_task_id = other.id
        db.session.commit()
        for action in ("makeup", "continue"):
            with self.subTest(action=action):
                _data, preview = self.preview(line, action)
                self.assertFalse(preview["can_apply"])
                self.assertTrue(any("关联前置" in item for item in preview["blockers"]))
        self.assertEqual(TaskPlannerRecoveryDecision.query.count(), 0)

    def test_shift_over_90_days_is_blocked_without_writes(self):
        line, entries = self.line()
        far = NOW.date() + timedelta(days=91)
        entries[-1].target_date = far
        definition = json.loads(line.definition_json)
        definition["rows"][-1]["target_date"] = far.isoformat()
        line.definition_json = planner._dump(definition)
        db.session.commit()
        _data, preview = self.preview(line)
        self.assertFalse(preview["can_apply"])
        self.assertTrue(any("未来90天" in item for item in preview["blockers"]))
        self.assertEqual(TaskPlannerRecoveryDecision.query.count(), 0)

    def test_resource_failure_is_not_cleared_by_continue_or_makeup(self):
        line, entries = self.line(kind="reading_test", days=2)
        target = Path(self.directory.name) / "static/reading_tests/ielts10_test2_reading.json"
        payload = json.loads(target.read_text())
        payload["passages"][1]["groups"] = []
        target.write_text(json.dumps(payload))
        for action in ("makeup", "continue"):
            with self.subTest(action=action):
                _data, preview = self.preview(line, action)
                self.assertFalse(preview["can_apply"])
        self.assertEqual([entry.status for entry in entries[3:]], ["ready"] * 3)
        self.assertEqual(Task.query.count(), 3)

    def test_same_request_key_replays_once_and_reuse_for_other_action_is_rejected(self):
        line, _entries = self.line()
        result, data = self.apply(line)
        replay = recovery.apply_recovery(data, self.staff_id, now=NOW + timedelta(days=1))
        self.assertEqual(replay, result)
        data["action"] = "continue"
        with self.assertRaises(planner.TaskPlannerError) as raised:
            recovery.apply_recovery(data, self.staff_id, now=NOW + timedelta(days=1))
        self.assertEqual(raised.exception.code, "idempotency_conflict")
        self.assertEqual(Task.query.count(), 2)

    def test_resolved_record_uses_valid_vocabulary_settlement_status(self):
        line, entries = self.line(days=1)
        self.apply(line, "continue")
        self.settle(entries[0].published_task_id)
        item = recovery.list_inbox(view="resolved", now=NOW + timedelta(days=1))[0]
        self.assertEqual(item["tasks"][0]["status_label"], "词汇已有效结算")

    def test_competing_different_actions_have_only_one_winner(self):
        line, _entries = self.line()
        payloads = []
        for action in ("makeup", "continue"):
            data, preview = self.preview(line, action)
            data.update(preview_hash=preview["preview_hash"], request_key=str(uuid.uuid4()))
            payloads.append(data)
        actor = self.staff_id
        barrier = threading.Barrier(2)
        db.session.remove()
        def invoke(payload):
            with self.app.app_context():
                barrier.wait(timeout=10)
                try:
                    return recovery.apply_recovery(payload, actor, now=NOW + timedelta(days=1))["action"]
                except planner.TaskPlannerError as exc:
                    return exc.code
                finally:
                    db.session.remove()
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(invoke, payloads))
        self.assertEqual(results.count("preview_changed"), 1)
        self.assertEqual(TaskPlannerRecoveryDecision.query.count(), 1)
        self.assertEqual(Task.query.count(), 2)
