import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class TaskDateGateDisplayContractTest(unittest.TestCase):
    def assert_contains(self, relative_path, text):
        source = (ROOT / relative_path).read_text(encoding="utf-8")
        self.assertIn(text, source, relative_path)

    def test_read_only_banners_prioritize_workflow_status_over_date_label(self):
        expected = [
            (
                "miniprogram/pages/student/task/index.wxml",
                "task.status_label || task.task_status_label || statusText || task.availability_label",
            ),
            (
                "miniprogram/pages/student/material-choice/practice/index.wxml",
                "task.status_label || task.task_status_label || dateStatusText || task.availability_label",
            ),
            (
                "miniprogram/pages/student/listening/practice/index.wxml",
                "task.status_label || task.task_status_label || dateStatusText || task.availability_label",
            ),
            (
                "miniprogram/pages/student/listening/cambridge/index.wxml",
                "task.status_label || task.task_status_label || dateStatusText || task.availability_label",
            ),
            (
                "miniprogram/pages/student/reading/cambridge/index.wxml",
                "task.status_label || task.task_status_label || dateStatusText || task.availability_label",
            ),
            (
                "templates/listening/jijing_part.html",
                "task.status_label || task.task_status_label || task.availability_label",
            ),
            (
                "templates/listening/player.html",
                "d.task?.status_label || d.task?.task_status_label || d.task?.availability_label",
            ),
            (
                "templates/listening/test_practice.html",
                "practice_context.status_label or practice_context.availability_label",
            ),
            (
                "templates/reading/test_practice.html",
                "practice_context.status_label or practice_context.availability_label",
            ),
        ]
        for path, text in expected:
            self.assert_contains(path, text)

    def test_date_gate_error_and_home_display_helpers_prioritize_status(self):
        self.assert_contains(
            "miniprogram/utils/request.js",
            "payload.status_label || payload.task_status_label || payload.availability_label",
        )
        self.assert_contains(
            "miniprogram/pages/student/home/index.js",
            "availabilityLabel: t.status_label || t.task_status_label || t.availability_label",
        )
        self.assert_contains(
            "templates/listening/index.html",
            "task.status_label || task.task_status_label || task.availability_label",
        )

    def test_dictation_appeal_and_content_report_are_not_date_gated(self):
        source = (ROOT / "api/dictation.py").read_text(encoding="utf-8")
        self.assertNotIn("assert_task_write_allowed", source)
        self.assertNotIn("TaskDateGateError", source)

    def test_cambridge_retry_stays_available_only_while_task_is_writable(self):
        for subject in ("listening", "reading"):
            root = f"miniprogram/pages/student/{subject}/cambridge/index"
            script = (ROOT / f"{root}.js").read_text(encoding="utf-8")
            template = (ROOT / f"{root}.wxml").read_text(encoding="utf-8")
            self.assertIn("isTaskDateGateError(res)", script)
            self.assertIn("nextTask.read_only", script)
            self.assertIn("read_only: true", script)
            self.assertIn(
                "resultDisplay.hasWrong && !task.read_only",
                template,
            )

    def test_assignment_notifications_use_the_shared_next_day_cutoff(self):
        expected = {
            "app.py": 'task_cutoff.strftime("%Y-%m-%d %H:%M")',
            "api/miniprogram.py": 'task_cutoff.strftime("%Y-%m-%d %H:%M")',
            "api/question_type_practice.py": 'task_cutoff.strftime("%Y-%m-%d %H:%M")',
        }
        for path, text in expected.items():
            self.assert_contains(path, text)


if __name__ == "__main__":
    unittest.main()
