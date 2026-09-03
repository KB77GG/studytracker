import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class QuestionTypePracticeContractTest(unittest.TestCase):
    def test_full_test_templates_receive_specialty_context_without_new_renderer(self):
        listening = (ROOT / "templates/listening/test_practice.html").read_text(encoding="utf-8")
        reading = (ROOT / "templates/reading/test_practice.html").read_text(encoding="utf-8")
        for source in (listening, reading):
            self.assertIn("practiceContext", source)
            self.assertIn("persistenceContext", source)
            self.assertIn("practiceContext?.submit_url", source)
            self.assertIn("js/practice_renderers.js", source)
            self.assertIn("practiceContext?.task_type", source)
            self.assertIn("window.location.replace(data.next_url)", source)
        templates = list((ROOT / "templates/question_type_practice").glob("*.html"))
        self.assertTrue(templates)
        self.assertFalse(
            any("function renderGroup(" in path.read_text(encoding="utf-8") for path in templates)
        )

    def test_listening_read_only_lock_runs_after_render_and_section_switch(self):
        listening = (ROOT / "templates/listening/test_practice.html").read_text(
            encoding="utf-8"
        )
        switch_start = listening.index("function switchSection(")
        render_start = listening.index("function render()")
        self.assertIn("lockReadOnlyReviewControls();", listening[switch_start:render_start])
        self.assertIn("lockReadOnlyReviewControls();", listening[render_start:])

    def test_teacher_flow_keeps_preview_safety_and_repush_actions_visible(self):
        teacher = (ROOT / "templates/question_type_practice/teacher_index.html").read_text(
            encoding="utf-8"
        )
        result = (ROOT / "templates/question_type_practice/result.html").read_text(encoding="utf-8")
        tasks = (ROOT / "templates/tasks.html").read_text(encoding="utf-8")
        self.assertIn("发布前预览", teacher)
        self.assertIn("移除整组", teacher)
        self.assertIn("题面完整性检查通过", teacher)
        self.assertIn('data-repush="wrong"', result)
        self.assertIn('data-repush="same_type_new"', result)
        self.assertIn("question_type_practice.teacher_index", tasks)
        self.assertIn("逐题结果", tasks)

    def test_public_builder_and_dynamic_listening_preflight_copy(self):
        student = (ROOT / "templates/question_type_practice/student_index.html").read_text(
            encoding="utf-8"
        )
        listening = (ROOT / "templates/listening/test_practice.html").read_text(encoding="utf-8")
        reading = (ROOT / "templates/reading/test_practice.html").read_text(encoding="utf-8")
        self.assertIn("{% block content_public %}", student)
        self.assertIn('data-subject="listening"', student)
        self.assertIn("qtTypeTabs", student)
        self.assertIn("选择单个 Section", student)
        self.assertIn("data-unit-key", student)
        self.assertIn("点击一张卡片即可单篇练习", student)
        self.assertIn("/api/question-type-practice/catalog", student)
        self.assertIn("全部剑雅（${volumes.length}册）", student)
        self.assertNotIn('id="qtCount"', student)
        self.assertIn("simulationAudioResources.length", listening)
        self.assertNotIn("音频已准备：4 个 Part", listening)
        retry_markup = next(
            line for line in reading.splitlines() if "data-practice-save-retry" in line
        )
        self.assertNotIn("data-capability=", retry_markup)

    def test_reading_matching_workspace_does_not_double_split_the_question_pane(self):
        css = (ROOT / "static/css/practice_shell.css").read_text(encoding="utf-8")
        self.assertIn("body.practice-reading-page .matching-workspace", css)
        self.assertIn("grid-template-columns: minmax(0, 1fr);", css)
        self.assertIn("body.practice-reading-page .matching-row", css)
        self.assertIn("minmax(130px, 160px)", css)


if __name__ == "__main__":
    unittest.main()
