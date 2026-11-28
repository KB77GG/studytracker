"""Weekly sprint page rendering without app startup or student database access."""

import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from flask import Flask, render_template

from api.exam_sprint import exam_sprint_bp

ROOT = Path(__file__).resolve().parents[1]


def sprint_view(subject="reading", *, available=True, stale=False):
    groups = [{"part": part, "items": []} for part in range(1, 4 if subject == "reading" else 5)]
    if available:
        groups[0]["items"] = [
            {
                "source_id": "ready-1",
                "title": "A ready practice",
                "title_zh": "可练习题目",
                "rank": 1,
                "heat_label": "近期反馈 12 次",
                "practice_url": "/reading/jijing/reading_jijing_5_test_59?passage=1",
                "unavailable_reason": "",
            },
            {
                "source_id": "pending-2",
                "title": "A pending practice",
                "title_zh": "待补齐题目",
                "rank": 2,
                "heat_label": "",
                "practice_url": None,
                "unavailable_reason": "练习内容正在准备",
            },
        ]
    return {
        "available": available,
        "stale": stale,
        "groups": groups,
        "total": 2 if available else 0,
        "ready_count": 1 if available else 0,
        "updated_at_label": "2026-11-16 06:00" if available else "",
        "source_updated_at_label": "2026-11-15" if available else "",
        "next_update_label": "2026-11-23 06:00",
    }


class ExamSprintRoutesTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__, root_path=str(ROOT))
        self.app.config.update(TESTING=True)
        self.app.jinja_env.globals["current_user"] = SimpleNamespace(is_authenticated=False)
        for endpoint, path in (
            ("practice_library", "/practice"),
            ("listening_test_index", "/listening/tests"),
            ("reading_test_index", "/reading/tests"),
            ("listening_jijing_index", "/listening/jijing"),
            ("reading_jijing_index", "/reading/jijing"),
            ("writing_library.index", "/writing/"),
        ):
            self.app.add_url_rule(path, endpoint, lambda: "")
        self.app.register_blueprint(exam_sprint_bp)
        self.client = self.app.test_client()

    def get_page(self, subject="reading", **kwargs):
        with patch(
            "services.exam_sprint.load_sprint_view", return_value=sprint_view(subject, **kwargs)
        ) as loader:
            response = self.client.get(f"/practice/sprint/{subject}")
        loader.assert_called_once_with(str(ROOT), subject)
        self.assertEqual(response.status_code, 200)
        return response.get_data(as_text=True)

    def test_subjects_have_correct_part_counts_and_public_routes(self):
        for subject, count in (("reading", 3), ("listening", 4)):
            with self.subTest(subject=subject):
                html = self.get_page(subject)
                self.assertEqual(html.count("data-book-target="), count)
                self.assertEqual(html.count("data-book-panel="), count)
                self.assertIn("data-open-catalog", html)
                self.assertIn("data-catalog-scrim", html)
                self.assertIn("九分学长 · 7天热榜", html)
                self.assertIn("每周一 06:00 更新（北京时间）", html)
                self.assertIn("根据考生近期反馈整理，仅供复习参考。", html)
                for target in ("/practice", "/listening/tests", "/reading/tests", "/writing/", "/practice/question-types"):
                    self.assertIn(f'href="{target}" data-practice-nav', html)
                self.assertEqual(html.count("data-practice-home"), 1)
                self.assertEqual(html.count("data-practice-module-back"), 1)

    def test_only_ready_entries_get_practice_links_and_preserve_passage(self):
        html = self.get_page()
        self.assertIn('href="/reading/jijing/reading_jijing_5_test_59?passage=1"', html)
        self.assertEqual(html.count("data-practice-entry"), 1)
        self.assertIn("A pending practice", html)
        self.assertIn("待补齐", html)
        self.assertIn("1 / 2 篇可练习", html)
        self.assertIn("sourceMode: 'exam_sprint'", html)

    def test_empty_snapshot_has_helpful_fallback_without_start_links(self):
        html = self.get_page(available=False)
        self.assertIn("本期热榜正在准备", html)
        self.assertIn('href="/reading/tests">练习剑雅真题', html)
        self.assertNotIn("data-practice-entry", html)
        self.assertNotIn("本周热榜暂未更新", html)

    def test_stale_snapshot_keeps_entries_and_reports_real_timestamps(self):
        html = self.get_page(stale=True)
        self.assertIn("本周热榜暂未更新", html)
        self.assertIn("来源更新：2026-11-15", html)
        self.assertIn("同步时间：2026-11-16 06:00", html)
        self.assertIn("A ready practice", html)
        self.assertIn("data-practice-entry", html)

    def test_invalid_subject_is_not_loaded(self):
        with patch("services.exam_sprint.load_sprint_view") as loader:
            for subject in ("writing", "Reading", "unknown"):
                self.assertEqual(self.client.get(f"/practice/sprint/{subject}").status_code, 404)
        loader.assert_not_called()

    def test_source_text_is_escaped(self):
        view = sprint_view()
        view["groups"][0]["items"][0]["title"] = '<script>alert("title")</script>'
        view["groups"][0]["items"][1]["unavailable_reason"] = '<img src=x onerror="bad()">'
        with patch("services.exam_sprint.load_sprint_view", return_value=view):
            html = self.client.get("/practice/sprint/reading").get_data(as_text=True)
        self.assertNotIn('<script>alert("title")</script>', html)
        self.assertNotIn("<img src=x", html)
        self.assertIn("&lt;script&gt;", html)

    def test_all_four_existing_catalogs_link_to_matching_sprint(self):
        with self.app.test_request_context():
            for subject in ("listening", "reading"):
                for template in ("test_index", "jijing_index"):
                    with self.subTest(subject=subject, template=template):
                        html = render_template(
                            f"{subject}/{template}.html",
                            books=[],
                            sections=[],
                            catalog={},
                            test_count=0,
                        )
                        self.assertIn(f'href="/practice/sprint/{subject}"', html)
                        self.assertIn("考前冲刺", html)


if __name__ == "__main__":
    unittest.main()
