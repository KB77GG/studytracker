import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LANDING_WXML = ROOT / "miniprogram/pages/index/index.wxml"
LANDING_JS = ROOT / "miniprogram/pages/index/index.js"
LANDING_WXSS = ROOT / "miniprogram/pages/index/index.wxss"
STUDENT_HOME_JS = ROOT / "miniprogram/pages/student/home/index.js"


class MiniprogramGuestAccessTest(unittest.TestCase):
    def test_guest_entry_is_visible_before_feature_cards(self):
        markup = LANDING_WXML.read_text(encoding="utf-8")

        self.assertIn("免登录体验学生端", markup)
        self.assertLess(markup.index("免登录体验学生端"), markup.index('class="feature-list"'))
        self.assertNotIn("handleLandingPrivacyChange", markup)

    def test_privacy_consent_is_only_in_optional_login_section(self):
        markup = LANDING_WXML.read_text(encoding="utf-8")

        self.assertEqual(markup.count("<checkbox "), 1)
        login_start = markup.index('class="login-section"')
        checkbox_position = markup.index("<checkbox ")
        self.assertGreater(checkbox_position, login_start)

    def test_guest_entry_does_not_call_wechat_login(self):
        source = LANDING_JS.read_text(encoding="utf-8")
        match = re.search(r"enterPreview\(e\) \{(?P<body>.*?)\n    \},", source, re.S)

        self.assertIsNotNone(match)
        body = match.group("body")
        self.assertIn("guestMode = true", body)
        self.assertIn("wx.reLaunch", body)
        self.assertNotIn("wx.login", body)

    def test_login_header_keeps_back_action_compact_and_label_visible(self):
        markup = LANDING_WXML.read_text(encoding="utf-8")
        styles = LANDING_WXSS.read_text(encoding="utf-8")

        self.assertIn('class="auth-back" size="mini"', markup)
        self.assertNotIn('class="auth-head-spacer"', markup)
        self.assertIn("width: 132rpx !important", styles)
        self.assertIn("max-width: 132rpx", styles)
        self.assertIn("flex: 0 0 132rpx", styles)
        self.assertIn("white-space: nowrap", styles)

    def test_guest_task_browsing_does_not_force_login(self):
        source = STUDENT_HOME_JS.read_text(encoding="utf-8")

        self.assertIn("this.showDemoTaskDetail(task)", source)
        self.assertIn("cancelText: '继续浏览'", source)
        self.assertIn("if (!isGuest) this.restoreTimerIfNeeded()", source)


if __name__ == "__main__":
    unittest.main()
