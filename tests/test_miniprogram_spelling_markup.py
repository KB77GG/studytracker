import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MINI = ROOT / "miniprogram"


class DictationSpellingMarkupTest(unittest.TestCase):
    WORD_TASK_PAGE_ROOTS = {
        "pages/student/dictation/spell/index",
        "pages/student/dictation/practice/index",
        "pages/student/dictation/review/index",
        "pages/student/vocabulary-review/index",
        "pages/student/vocabulary-learning/index",
    }

    def read(self, relative):
        return (MINI / relative).read_text(encoding="utf-8")

    def test_every_word_answer_page_uses_native_input(self):
        for root in self.WORD_TASK_PAGE_ROOTS:
            markup = self.read(f"{root}.wxml")
            script = self.read(f"{root}.js")
            config = json.loads(self.read(f"{root}.json"))
            self.assertIn("<input", markup, root)
            self.assertNotIn("english-keyboard", markup, root)
            self.assertNotIn("input-mode-switcher", markup, root)
            self.assertNotIn("inputPolicy", markup, root)
            self.assertNotIn("inputMode", markup, root)
            self.assertIn("input_mode: 'native'", script, root)
            self.assertNotIn("input_grant_id", script, root)
            self.assertNotIn("/dictation/input-policy", script, root)
            self.assertNotIn("/dictation/input-grants", script, root)
            self.assertNotIn("english-keyboard", config.get("usingComponents", {}), root)
            self.assertNotIn("input-mode-switcher", config.get("usingComponents", {}), root)

    def test_removed_keyboard_components_are_not_shipped_or_registered(self):
        self.assertFalse((MINI / "components/english-keyboard/index.js").exists())
        self.assertFalse((MINI / "components/input-mode-switcher/index.js").exists())
        for path in (MINI / "pages").rglob("*.json"):
            source = path.read_text(encoding="utf-8")
            self.assertNotIn("/components/english-keyboard/index", source, str(path))
            self.assertNotIn("/components/input-mode-switcher/index", source, str(path))

    def test_wrong_answer_paths_keep_correction_before_reveal(self):
        for relative in (
            "pages/student/dictation/spell/index.wxml",
            "pages/student/dictation/practice/index.wxml",
            "pages/student/dictation/review/index.wxml",
        ):
            markup = self.read(relative)
            self.assertIn("!resultRevealed", markup, relative)
            self.assertIn("暂时跳过", markup, relative)
            self.assertIn("重新", markup, relative)

    def test_replay_remains_separate_from_answer_input(self):
        for relative in (
            "pages/student/dictation/spell/index.js",
            "pages/student/dictation/practice/index.js",
            "pages/student/dictation/review/index.js",
        ):
            self.assertIn("已重播", self.read(relative), relative)

        spell = self.read("pages/student/dictation/spell/index.wxml")
        self.assertEqual(spell.count('bindtap="replayCurrentWord"'), 1)
        self.assertIn("/images/icons/speaker-wave-outline.svg", spell)
        practice = self.read("pages/student/dictation/practice/index.wxml")
        self.assertIn('bindtap="replayCurrentWord"', practice)
        review = self.read("pages/student/dictation/review/index.wxml")
        self.assertIn('bindtap="replayAudio"', review)

    def test_mixed_listening_fill_in_pages_remain_native(self):
        for relative in (
            "pages/student/listening/practice/index.wxml",
            "pages/student/listening/cambridge/index.wxml",
        ):
            markup = self.read(relative)
            self.assertIn("<input", markup, relative)
            self.assertNotIn("english-keyboard", markup, relative)

    def test_policy_helper_is_only_used_to_identify_word_answer_modes(self):
        policy_pages = set()
        for path in (MINI / "pages").rglob("*.js"):
            source = path.read_text(encoding="utf-8")
            if "dictation-input-policy.js" in source:
                policy_pages.add(path.relative_to(MINI).with_suffix("").as_posix())
        self.assertEqual(
            policy_pages,
            {
                "pages/student/dictation/practice/index",
                "pages/student/dictation/review/index",
            },
        )
        helper = self.read("utils/dictation-input-policy.js")
        self.assertIn("isEnglishSpellingMode", helper)
        for removed in (
            "INPUT_STRICT",
            "chooseInputMode",
            "answerSeparators",
            "inputModeStorageKey",
        ):
            self.assertNotIn(removed, helper)

    def test_autonomous_review_keeps_server_gate_and_local_return_target(self):
        source = self.read("pages/student/vocabulary-review/index.js")
        practice = self.read("pages/student/dictation/practice/index.js")
        spell = self.read("pages/student/dictation/spell/index.js")
        self.assertIn("createReliableAudioPlayer", source)
        self.assertIn("if (this.returnTaskId)", source)
        self.assertNotIn("res.origin_task_id || this.data.originTaskId", source)
        self.assertIn("firstUnanswered", source)
        self.assertIn("vocabulary_review_required", practice)
        self.assertIn("vocabulary_review_required", spell)

    def test_teacher_input_authorization_entry_is_removed(self):
        source = self.read("pages/teacher/students/index.js")
        markup = self.read("pages/teacher/students/index.wxml")
        styles = self.read("pages/teacher/students/index.wxss")
        combined = "\n".join((source, markup, styles))
        self.assertNotIn("/dictation/input-grants", combined)
        self.assertNotIn("authorizeCompatibleInput", combined)
        self.assertNotIn("单词任务实体键盘", combined)
        self.assertNotIn("input-grant-button", combined)

    def test_spell_sage_path_visual_has_no_first_letter_hint(self):
        markup = self.read("pages/student/dictation/spell/index.wxml")
        source = self.read("pages/student/dictation/spell/index.js")
        styles = self.read("pages/student/dictation/spell/index.wxss")

        self.assertIn("/images/growth-path-background.jpg", markup)
        self.assertIn("/images/logo.jpg", markup)
        self.assertIn('class="progress-count"', markup)
        self.assertIn('class="slot-char">{{item.char}}</text>', markup)
        self.assertIn("buildSpellSlots('', this.data.currentWord.word)", source)
        self.assertIn("inputValue: ''", source)
        self.assertIn("max-width: 900px", styles)
        self.assertIn("@media (orientation: landscape)", styles)
        self.assertIn("env(safe-area-inset-bottom)", styles)
        self.assertNotIn(".slot.active::after", styles)

        combined = "\n".join((markup, source))
        for forbidden in (
            "首字母",
            "firstLetter",
            "hintLetter",
            "实体键盘需教师授权",
            "严格拼写",
        ):
            self.assertNotIn(forbidden, combined)

        for asset in (
            "images/growth-path-background.jpg",
            "images/icons/speaker-wave-outline.svg",
            "images/icons/check-outline.svg",
            "images/icons/flag-outline.svg",
        ):
            self.assertTrue((MINI / asset).is_file(), asset)


if __name__ == "__main__":
    unittest.main()
