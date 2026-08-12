import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class MiniprogramTaskRoutingRegressionTest(unittest.TestCase):
    def read(self, relative):
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_home_routes_vocabulary_only_when_a_dictation_book_is_bound(self):
        source = self.read("miniprogram/pages/student/home/index.js")
        self.assertEqual(
            source.count("task && task.dictationBookId && task.vocabularyGoal"),
            2,
        )

    def test_generic_detail_ignores_stray_goal_on_listening_tasks(self):
        source = self.read("miniprogram/pages/student/task/index.js")
        self.assertIn(
            "res.task.dictation_book_id && res.task.vocabulary_goal",
            source,
        )

    def test_hidden_goal_control_cannot_submit_for_other_task_sources(self):
        source = self.read("templates/tasks.html")
        self.assertIn(
            'id="vocabularyGoalSelect" name="vocabulary_goal" class="form-select" disabled',
            source,
        )
        self.assertIn("vocabularyGoalSelect.disabled = false", source)
        self.assertIn("vocabularyGoalSelect.disabled = true", source)


if __name__ == "__main__":
    unittest.main()
