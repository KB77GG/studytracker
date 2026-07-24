import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MINI = ROOT / "miniprogram"


class DictationSpellingMarkupTest(unittest.TestCase):
    WORD_TASK_PAGE_ROOTS = {
        "pages/student/dictation/spell/index",
        "pages/student/dictation/practice/index",
        "pages/student/dictation/review/index",
    }

    def read(self, relative):
        return (MINI / relative).read_text(encoding="utf-8")

    def test_shared_keyboard_exposes_the_required_controls(self):
        markup = self.read("components/english-keyboard/index.wxml")
        component = self.read("components/english-keyboard/index.js")
        for event in (
            "emitKey",
            "emitBackspace",
            "emitConfirm",
            "emitRetry",
            "emitSkip",
            "emitNext",
        ):
            self.assertIn(f'bindtap="{event}"', markup)
            self.assertIn(f"triggerEvent('{event.removeprefix('emit').lower()}", component)
        self.assertIn("answerSeparators", component)
        self.assertIn("showValue", component)
        self.assertNotIn("showReplay", component)
        self.assertNotIn("emitReplay", component)
        self.assertIn("/images/icons/backspace-outline.svg", markup)

    def test_english_pages_have_no_native_input_in_strict_state(self):
        page_paths = (
            "pages/student/dictation/spell/index.wxml",
            "pages/student/dictation/practice/index.wxml",
            "pages/student/dictation/review/index.wxml",
        )
        for relative in page_paths:
            markup = self.read(relative)
            self.assertIn("english-keyboard", markup, relative)
            self.assertIn("input-mode-switcher", markup, relative)
            self.assertNotIn("实体键盘需教师授权", markup, relative)
            self.assertNotIn("严格拼写", markup, relative)

        spell = self.read("pages/student/dictation/spell/index.wxml")
        self.assertIn('wx:if="{{inputMode === \'compatible\'}}"', spell)
        self.assertNotIn("inputMode === 'strict' &&", spell)

        practice = self.read("pages/student/dictation/practice/index.wxml")
        self.assertIn("!isEnglishSpelling || inputMode === 'compatible'", practice)
        review = self.read("pages/student/dictation/review/index.wxml")
        self.assertIn("!isEnglishSpelling || inputMode === 'compatible'", review)

    def test_wrong_answer_paths_keep_answer_hidden_until_skip(self):
        for relative in (
            "pages/student/dictation/spell/index.wxml",
            "pages/student/dictation/practice/index.wxml",
            "pages/student/dictation/review/index.wxml",
        ):
            markup = self.read(relative)
            self.assertIn("!resultRevealed", markup, relative)
            self.assertIn("暂时跳过", markup, relative)
            self.assertIn("重新", markup, relative)

    def test_replay_is_neutral_and_does_not_render_answer_in_advance(self):
        for relative in (
            "pages/student/dictation/spell/index.js",
            "pages/student/dictation/practice/index.js",
            "pages/student/dictation/review/index.js",
        ):
            source = (MINI / relative).read_text(encoding="utf-8")
            self.assertIn("已重播", source, relative)

        keyboard_markup = self.read("components/english-keyboard/index.wxml")
        self.assertIn('class="typed-answer status-{{status}}"', keyboard_markup)
        self.assertIn("你的拼写", keyboard_markup)
        self.assertIn("{{value}}", keyboard_markup)
        self.assertIn('class="action-button-label"', keyboard_markup)
        self.assertNotIn("{{answer}}", keyboard_markup)
        self.assertNotIn("重听", keyboard_markup)

        spell_markup = self.read("pages/student/dictation/spell/index.wxml")
        self.assertIn('class="replay-pill"', spell_markup)
        self.assertIn('bindtap="replayCurrentWord"', spell_markup)
        self.assertIn("/images/icons/speaker-wave-outline.svg", spell_markup)

    def test_replay_is_present_once_without_duplicate_keyboard_controls(self):
        spell = self.read("pages/student/dictation/spell/index.wxml")
        self.assertEqual(spell.count('bindtap="replayCurrentWord"'), 1)
        self.assertNotIn("show-replay", spell)
        self.assertNotIn('bind:replay="replayCurrentWord"', spell)

        practice = self.read("pages/student/dictation/practice/index.wxml")
        self.assertIn('bindtap="replayCurrentWord"', practice)
        self.assertNotIn('show-replay="{{true}}"', practice)
        self.assertNotIn('bind:replay="replayCurrentWord"', practice)

        review = self.read("pages/student/dictation/review/index.wxml")
        self.assertIn('bindtap="replayAudio"', review)
        self.assertNotIn('show-replay="{{true}}"', review)
        self.assertNotIn('bind:replay="replayAudio"', review)

        for markup in (spell, practice, review):
            self.assertIn("inputPolicy.compatibleAllowed", markup)

    def test_strict_layout_removes_empty_bars_and_is_responsive(self):
        keyboard_styles = self.read("components/english-keyboard/index.wxss")
        self.assertIn("max-width: 560px", keyboard_styles)
        self.assertIn(".typed-answer", keyboard_styles)
        self.assertIn("height: 42px", keyboard_styles)
        key_rule = keyboard_styles.split(".letter-key,\n.separator-key {", 1)[1].split("}", 1)[0]
        self.assertIn("display: flex", key_rule)
        self.assertIn("align-items: center", key_rule)
        self.assertIn("justify-content: center", key_rule)
        self.assertIn("transform: translateY(2px)", keyboard_styles)
        self.assertIn("@media (max-width: 360px)", keyboard_styles)
        self.assertIn("@media (max-height: 700px)", keyboard_styles)
        self.assertIn("env(safe-area-inset-bottom)", keyboard_styles)

        spell_markup = self.read("pages/student/dictation/spell/index.wxml")
        spell_styles = self.read("pages/student/dictation/spell/index.wxss")
        self.assertIn(
            'class="mode-switch-row" wx:if="{{inputPolicy.compatibleAllowed}}"',
            spell_markup,
        )
        self.assertIn("min-height: 0", spell_styles)
        self.assertIn('show-value="{{false}}"', spell_markup)
        self.assertIn(".growth-path-background", spell_styles)
        self.assertIn(".path-dot.current", spell_styles)
        self.assertIn("clamp(24px, 7.4vw, 34px)", spell_styles)

        practice_markup = self.read("pages/student/dictation/practice/index.wxml")
        practice_styles = self.read("pages/student/dictation/practice/index.wxss")
        self.assertIn("strict-practice", practice_markup)
        self.assertIn('class="strict-keyboard-wrap"', practice_markup)
        self.assertIn(
            'class="action-bar" wx:if="{{!isEnglishSpelling || inputMode !== \'strict\'}}"',
            practice_markup,
        )
        self.assertIn(".practice-container.strict-practice", practice_styles)
        self.assertIn("max-width: 760px", practice_styles)
        self.assertIn("overflow-y: auto", practice_styles)

        review_markup = self.read("pages/student/dictation/review/index.wxml")
        self.assertIn(
            'class="action-bar" wx:if="{{!isEnglishSpelling || inputMode !== \'strict\'}}"',
            review_markup,
        )

    def test_mixed_listening_fill_in_pages_remain_native(self):
        for relative in (
            "pages/student/listening/practice/index.wxml",
            "pages/student/listening/cambridge/index.wxml",
        ):
            markup = self.read(relative)
            self.assertIn("<input", markup, relative)
            self.assertNotIn("english-keyboard", markup, relative)

    def test_component_registration_is_limited_to_word_task_whitelist(self):
        keyboard_pages = set()
        switcher_pages = set()
        for path in (MINI / "pages").rglob("*.json"):
            source = path.read_text(encoding="utf-8")
            page_root = path.relative_to(MINI).with_suffix("").as_posix()
            if '"/components/english-keyboard/index"' in source:
                keyboard_pages.add(page_root)
            if '"/components/input-mode-switcher/index"' in source:
                switcher_pages.add(page_root)

        self.assertEqual(keyboard_pages, self.WORD_TASK_PAGE_ROOTS)
        self.assertEqual(switcher_pages, self.WORD_TASK_PAGE_ROOTS)

    def test_policy_behavior_is_not_referenced_by_reading_listening_or_global_code(self):
        forbidden_tokens = (
            "dictation-input-policy",
            "english-keyboard",
            "input-mode-switcher",
            "/dictation/input-policy",
            "/dictation/input-grants",
        )
        restricted_paths = [
            MINI / "pages/student/listening",
            MINI / "pages/student/reading",
            MINI / "app.js",
            MINI / "app.json",
            MINI / "app.wxss",
        ]
        for target in restricted_paths:
            files = (
                [target]
                if target.is_file()
                else [
                    path
                    for path in target.rglob("*")
                    if path.suffix in {".js", ".json", ".wxml", ".wxss"}
                ]
            )
            for path in files:
                source = path.read_text(encoding="utf-8", errors="ignore")
                for token in forbidden_tokens:
                    self.assertNotIn(token, source, str(path.relative_to(MINI)))

    def test_page_level_policy_imports_are_limited_to_word_task_whitelist(self):
        policy_pages = set()
        for path in (MINI / "pages").rglob("*.js"):
            source = path.read_text(encoding="utf-8")
            if "dictation-input-policy.js" in source:
                policy_pages.add(path.relative_to(MINI).with_suffix("").as_posix())
        self.assertEqual(policy_pages, self.WORD_TASK_PAGE_ROOTS)

    def test_teacher_grant_entry_is_word_task_scoped(self):
        grant_pages = set()
        for path in (MINI / "pages").rglob("*.js"):
            source = path.read_text(encoding="utf-8")
            if "/dictation/input-grants" in source:
                grant_pages.add(path.relative_to(MINI).with_suffix("").as_posix())
        self.assertEqual(grant_pages, {"pages/teacher/students/index"})
        teacher_markup = self.read("pages/teacher/students/index.wxml")
        self.assertIn("单词任务实体键盘", teacher_markup)

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
        for forbidden in ("首字母", "firstLetter", "hintLetter", "实体键盘需教师授权", "严格拼写"):
            self.assertNotIn(forbidden, combined)

        for asset in (
            "images/growth-path-background.jpg",
            "images/icons/backspace-outline.svg",
            "images/icons/speaker-wave-outline.svg",
            "images/icons/check-outline.svg",
            "images/icons/flag-outline.svg",
        ):
            self.assertTrue((MINI / asset).is_file(), asset)


if __name__ == "__main__":
    unittest.main()
