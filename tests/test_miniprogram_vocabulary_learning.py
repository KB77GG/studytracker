import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class VocabularyLearningMiniProgramStructureTest(unittest.TestCase):
    def read(self, relative):
        return (ROOT / relative).read_text(encoding="utf-8")

    def test_v2_page_is_registered_and_server_state_is_visible(self):
        app_config = json.loads(self.read("miniprogram/app.json"))
        self.assertIn("pages/student/vocabulary-learning/index", app_config["pages"])
        markup = self.read("miniprogram/pages/student/vocabulary-learning/index.wxml")
        script = self.read("miniprogram/pages/student/vocabulary-learning/index.js")
        self.assertIn("第 {{groupNumber}} / {{groupCount}} 组", markup)
        self.assertIn("当前阶段：{{phaseLabel}}", markup)
        self.assertIn("vocabulary-learning/familiarity", script)
        self.assertIn("queue_token", script)
        for field in (
            "learning_question_id",
            "queue_item_id",
            "question_id",
            "word_id",
            "sense_id",
            "dimension",
        ):
            self.assertIn(field, script)

    def test_v2_mutations_redirect_or_refresh_on_server_errors(self):
        script = self.read("miniprogram/pages/student/vocabulary-learning/index.js")
        self.assertIn("handleMutationError", script)
        self.assertIn("vocabulary_review_required", script)
        self.assertIn("returnTaskId=${this.data.taskId}", script)
        self.assertIn("state_conflict", script)
        self.assertIn("question_not_current", script)
        self.assertIn("this.fetchQueue()", script)
        self.assertIn("duration_seconds", script)
        self.assertIn("Date.now() - this.data.startedAt", script)

    def test_legacy_pages_redirect_v2_after_gate_before_old_words_contract(self):
        practice = self.read("miniprogram/pages/student/dictation/practice/index.js")
        spell = self.read("miniprogram/pages/student/dictation/spell/index.js")
        for source in (practice, spell):
            gate_index = source.index("vocabulary-review/preflight")
            redirect_index = source.index("pages/student/vocabulary-learning/index")
            self.assertGreater(redirect_index, gate_index)
        self.assertIn("if (vocabularyV2)", practice)
        self.assertIn("if (task.vocabulary_goal)", spell)
        practice_gate = practice[practice.index("if (vocabularyV2)") : practice.index("this.startBackendTimer")]
        self.assertIn("pages/student/vocabulary-learning/index", practice_gate)
        self.assertGreater(
            spell.index("pages/student/vocabulary-learning/index"),
            spell.index("this.reviewDone = true"),
        )

    def test_narrow_screen_styles_have_safe_wrapping(self):
        styles = self.read("miniprogram/pages/student/vocabulary-learning/index.wxss")
        self.assertIn("@media (max-width: 360px)", styles)
        self.assertIn("overflow-wrap: anywhere", styles)
        self.assertIn("min-width: 0", styles)

    def test_context_fill_shows_labeled_chinese_support_in_learning_and_review(self):
        for page in ("vocabulary-learning", "vocabulary-review"):
            markup = self.read(f"miniprogram/pages/student/{page}/index.wxml")
            self.assertIn("question.prompt.translation_label", markup)
            self.assertIn("question.prompt.translation", markup)
            self.assertIn("中文提示", markup)

    def test_listening_meaning_uses_choices_and_reliable_audio(self):
        learning_markup = self.read("miniprogram/pages/student/vocabulary-learning/index.wxml")
        review_markup = self.read("miniprogram/pages/student/vocabulary-review/index.wxml")
        for markup in (learning_markup, review_markup):
            self.assertIn("听音 → 选择中文释义", markup)
            self.assertIn("!isMeaningChoice", markup)
            self.assertIn('class="play-icon"', markup)
            self.assertNotIn("▶ 播放发音", markup)
        for page in ("vocabulary-learning", "vocabulary-review"):
            script = self.read(f"miniprogram/pages/student/{page}/index.js")
            self.assertIn("createReliableAudioPlayer", script)
            self.assertIn("buildMeaningChoiceOptions", script)
            self.assertIn("audioButtonLabel", script)
        styles = self.read("miniprogram/pages/student/vocabulary-learning/index.wxss")
        self.assertIn("#087f77", styles)
        self.assertNotIn("#e46b37", styles)

    def test_answer_feedback_is_post_submit_and_result_action_is_compact(self):
        component_markup = self.read(
            "miniprogram/components/vocabulary-feedback-card/index.wxml"
        )
        component_styles = self.read(
            "miniprogram/components/vocabulary-feedback-card/index.wxss"
        )
        self.assertIn("核心义", component_markup)
        self.assertIn("必要搭配", component_markup)
        self.assertIn("feedback.example_en", component_markup)
        self.assertIn("feedback.example_zh", component_markup)
        self.assertIn("用法提醒", component_markup)
        self.assertIn("speaker-wave-outline.svg", component_markup)
        self.assertIn("min-height: 88rpx", component_styles)

        for page in ("vocabulary-learning", "vocabulary-review"):
            markup = self.read(f"miniprogram/pages/student/{page}/index.wxml")
            script = self.read(f"miniprogram/pages/student/{page}/index.js")
            styles = self.read(f"miniprogram/pages/student/{page}/index.wxss")
            config = json.loads(
                self.read(f"miniprogram/pages/student/{page}/index.json")
            )
            self.assertIn("vocabulary-feedback-card", config["usingComponents"])
            self.assertIn('wx:if="{{showResult && answerFeedback}}"', markup)
            self.assertIn(
                '<input wx:if="{{!showResult && !isMeaningChoice',
                markup,
            )
            self.assertNotIn("english-keyboard", markup)
            self.assertIn('wx:if="{{showResult}}" class="primary-btn next-question-btn"', markup)
            self.assertNotIn('show-next="{{showResult}}"', markup)
            self.assertIn("normalizeAnswerFeedback", script)
            self.assertIn("answerFeedback: null", script)
            self.assertIn(".next-question-btn", styles)
            self.assertIn("width: 520rpx", styles)

        learning_script = self.read(
            "miniprogram/pages/student/vocabulary-learning/index.js"
        )
        review_script = self.read(
            "miniprogram/pages/student/vocabulary-review/index.js"
        )
        self.assertIn("normalizeAnswerFeedback(res, this.feedbackFallback(question))", learning_script)
        self.assertIn("answer_feedback: res.answer_feedback", review_script)

    def test_v2_answer_submit_recovers_quickly_and_exposes_progress(self):
        for page in ("vocabulary-learning", "vocabulary-review"):
            markup = self.read(f"miniprogram/pages/student/{page}/index.wxml")
            script = self.read(f"miniprogram/pages/student/{page}/index.js")
            self.assertIn('confirm-type="done"', markup)
            self.assertIn("input_mode: 'native'", script)
            self.assertIn("timeout: 15000", script)
            self.assertIn("this.setData({ submitting: false })", script)


if __name__ == "__main__":
    unittest.main()
