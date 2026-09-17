import unittest
from pathlib import Path
from types import SimpleNamespace

from services.task_assignment_history import serialize_previous_day_assignments

ROOT = Path(__file__).resolve().parents[1]


def task(**overrides):
    values = {
        "id": 1,
        "student_name": "测试学生",
        "category": "材料练习",
        "detail": "旧任务标题",
        "grading_mode": "image",
        "status": "pending",
        "student_submitted": False,
        "planned_minutes": 20,
        "note": "继续复习",
        "material_id": None,
        "question_ids": None,
        "dictation_book_id": None,
        "vocabulary_goal": None,
        "dictation_mode": "audio_to_en",
        "dictation_order": "sequence",
        "dictation_word_start": 1,
        "dictation_word_end": None,
        "speaking_book_id": None,
        "speaking_phrase_start": 1,
        "speaking_phrase_end": None,
        "listening_resource_type": None,
        "listening_exercise_id": None,
        "reading_test_id": None,
        "reading_passage_number": None,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class TaskAssignmentHistoryTest(unittest.TestCase):
    def test_dictation_task_exposes_book_range_and_repeat_fields(self):
        book = SimpleNamespace(id=7, title="四级单词 Day18", word_count=51)
        grouped = serialize_previous_day_assignments(
            [
                task(
                    id=3342,
                    dictation_book_id=7,
                    dictation_word_start=11,
                    dictation_word_end=30,
                    vocabulary_goal="comprehensive",
                    dictation_order="random",
                )
            ],
            dictation_books={7: book},
        )

        item = grouped["测试学生"][0]
        self.assertEqual(item["id"], 3342)
        self.assertEqual(item["title"], "四级单词 Day18")
        self.assertEqual(item["resource_meta"], "词书 · 第 11–30 词")
        self.assertTrue(item["repeatable"])
        self.assertEqual(item["repeat"]["source"], "material")
        self.assertEqual(item["repeat"]["material_value"], "dictation-7")
        self.assertEqual(item["repeat"]["dictation_word_start"], 11)
        self.assertEqual(item["repeat"]["dictation_word_end"], 30)
        self.assertEqual(item["repeat"]["vocabulary_goal"], "comprehensive")
        self.assertEqual(item["repeat"]["dictation_order"], "random")

    def test_open_ended_dictation_range_uses_book_count_for_display_only(self):
        book = SimpleNamespace(id=3, title="WL 3", word_count=80)
        grouped = serialize_previous_day_assignments(
            [task(dictation_book_id=3, dictation_word_start=61)],
            dictation_books={3: book},
        )

        item = grouped["测试学生"][0]
        self.assertEqual(item["range_label"], "第 61–80 词")
        self.assertIsNone(item["repeat"]["dictation_word_end"])

    def test_submitted_task_is_not_offered_for_repeat(self):
        grouped = serialize_previous_day_assignments(
            [task(status="progress", student_submitted=True)]
        )

        item = grouped["测试学生"][0]
        self.assertEqual(item["status"], "submitted")
        self.assertEqual(item["status_label"], "已提交，待批改")
        self.assertFalse(item["repeatable"])

    def test_cambridge_section_is_recovered_from_legacy_question_payload(self):
        grouped = serialize_previous_day_assignments(
            [
                task(
                    listening_exercise_id="ielts20_test2",
                    listening_resource_type="cambridge_test",
                    question_ids='{"listening_section_number": 4}',
                )
            ]
        )

        repeat = grouped["测试学生"][0]["repeat"]
        self.assertEqual(repeat["source"], "listening")
        self.assertEqual(repeat["listening_exercise_id"], "ielts20_test2")
        self.assertEqual(repeat["listening_section_number"], 4)
        self.assertEqual(repeat["question_ids"], [])

    def test_blank_student_names_are_not_serialized(self):
        grouped = serialize_previous_day_assignments([task(student_name="  ")])
        self.assertEqual(grouped, {})

    def test_writing_task_can_be_repeated_from_yesterday_without_losing_identity(self):
        grouped = serialize_previous_day_assignments(
            [
                task(
                    detail="T01 · 教育目标、课程与方法",
                    grading_mode="writing_practice",
                    question_ids='{"writing_resource_type":"mother_topic","writing_resource_id":"t01","title":"T01 · 教育目标、课程与方法"}',
                )
            ]
        )

        item = grouped["测试学生"][0]
        self.assertEqual(item["resource_kind"], "writing")
        self.assertEqual(item["resource_meta"], "大作文母题")
        self.assertEqual(item["repeat"]["source"], "writing")
        self.assertEqual(item["repeat"]["writing_resource_type"], "mother_topic")
        self.assertEqual(item["repeat"]["writing_resource_id"], "t01")

    def test_question_type_task_repeats_the_same_groups_and_exposes_safe_history(self):
        snapshot = {
            "subject": "reading",
            "standard_type": "judgment",
            "pace": "training",
            "group_ids": ["reading:test-1:passage-1:judgment:1-2"],
            "payload": {"answer": "must-not-be-copied-to-repeat-payload"},
        }
        grouped = serialize_previous_day_assignments(
            [
                task(
                    id=77,
                    detail="阅读 · 判断题 · 1组/2题 · 训练节奏",
                    category="雅思-阅读-题型专项",
                    grading_mode="question_type_practice",
                    question_ids=__import__("json").dumps(snapshot, ensure_ascii=False),
                )
            ]
        )

        item = grouped["测试学生"][0]
        repeat = item["repeat"]
        self.assertEqual(item["resource_kind"], "question_type")
        self.assertEqual(item["resource_meta"], "题型专项 · 阅读 · 1 个完整题组")
        self.assertEqual(item["history_url"], "/tasks/question-types/77/result")
        self.assertTrue(item["repeatable"])
        self.assertEqual(repeat["source"], "question_type")
        self.assertEqual(repeat["question_type_subject"], "reading")
        self.assertEqual(repeat["question_type_standard_type"], "judgment")
        self.assertEqual(
            repeat["question_type_group_ids"],
            ["reading:test-1:passage-1:judgment:1-2"],
        )
        self.assertEqual(repeat["question_type_pace"], "training")
        self.assertNotIn("payload", repeat)
        self.assertNotIn("must-not-be-copied", str(repeat))

    def test_broken_question_type_snapshot_is_visible_but_not_repeatable(self):
        grouped = serialize_previous_day_assignments(
            [
                task(
                    grading_mode="question_type_practice",
                    question_ids='{"subject":"reading"}',
                )
            ]
        )
        item = grouped["测试学生"][0]
        self.assertEqual(item["resource_kind"], "question_type")
        self.assertFalse(item["repeatable"])

    def test_submitted_question_type_snapshot_is_not_offered_as_unfinished_repeat(self):
        snapshot = {
            "subject": "listening",
            "standard_type": "matching",
            "group_ids": ["listening:test-1:section-1:matching:1-2"],
        }
        grouped = serialize_previous_day_assignments(
            [
                task(
                    status="progress",
                    grading_mode="question_type_practice",
                    question_ids=__import__("json").dumps(snapshot),
                    submitted_at=object(),
                )
            ]
        )
        item = grouped["测试学生"][0]
        self.assertEqual(item["status"], "submitted")
        self.assertEqual(item["status_label"], "已提交，待批改")
        self.assertFalse(item["repeatable"])

    def test_tasks_template_contains_accessible_yesterday_panel_and_prefill(self):
        markup = (ROOT / "templates/tasks.html").read_text(encoding="utf-8")
        history_markup = (
            ROOT / "templates/question_type_practice/history.html"
        ).read_text(encoding="utf-8")
        app_source = (ROOT / "app.py").read_text(encoding="utf-8")

        self.assertIn('id="previousDayPanel"', markup)
        self.assertIn('aria-label="昨日任务列表"', markup)
        self.assertIn('tabindex="0"', markup)
        self.assertIn('aria-live="polite"', markup)
        self.assertIn("previousDayTaskRecordsByName", markup)
        self.assertIn("applyRepeatPreset", markup)
        self.assertIn("taskQtaLoadRepeatPreset", markup)
        self.assertIn("question_type_group_ids", markup)
        self.assertIn("requires_confirmation", markup)
        self.assertIn('href="/tasks/question-types/{{ t.id }}/result"', markup)
        self.assertIn(">专项记录</a>", markup)
        self.assertIn("openTaskManager", markup)
        self.assertIn("previous-day-manage", markup)
        self.assertIn("document.getElementById('taskStudent')?.value", markup)
        self.assertIn("确认无误后点击“添加”", markup)
        self.assertIn("load_previous_day_assignments(previous_day.isoformat())", app_source)
        self.assertIn("previous_day_tasks=previous_day_tasks", app_source)
        self.assertIn("本页只是查看记录，不会开始任务", history_markup)
        self.assertIn("暂无可展示成绩", history_markup)
        self.assertNotIn("snapshot_hash", history_markup)
        self.assertNotIn("task_cutoff_at", history_markup)
        self.assertNotIn('type="submit"', history_markup)


if __name__ == "__main__":
    unittest.main()
