"""Render public/staff practice views without importing the application or DB."""

import unittest
from html.parser import HTMLParser
from pathlib import Path
from types import SimpleNamespace

from jinja2 import Environment, FileSystemLoader


class Elements(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.rows = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        self.rows.append((tag, dict(attrs)))

    def with_class(self, name):
        return [attrs for _, attrs in self.rows if name in attrs.get("class", "").split()]

    def with_attr(self, name):
        return [attrs for _, attrs in self.rows if name in attrs]


def render_practice(*, role=None, path="/practice", endpoint="practice_library"):
    env = Environment(
        loader=FileSystemLoader(Path(__file__).resolve().parents[1] / "templates"),
        autoescape=True,
    )
    urls = {
        "practice_library": "/practice",
        "tasks_page": "/tasks",
        "login": "/login",
    }
    env.globals.update(
        url_for=lambda name, **kw: (
            "/static/" + kw["filename"] if name == "static" else urls.get(name, "/" + name)
        ),
        get_flashed_messages=lambda: [],
        config={},
    )
    counts = dict(
        cambridge_books=1, cambridge_tests=4, cambridge_questions=160,
        jijing_books=1, jijing_tests=2, jijing_questions=80,
        jijing_parts=8, intensive_sections=16,
    )
    return env.get_template("practice/index.html").render(
        current_user=SimpleNamespace(
            is_authenticated=role is not None, role=role,
            username="fixture", display_name="Fixture",
        ),
        request=SimpleNamespace(path=path, endpoint=endpoint),
        practice_staff_mode=role in {"teacher", "assistant", "admin"},
        practice_staff_label="Fixture",
        practice_staff_hint="Fixture staff mode",
        summary={
            "listening": counts, "reading": counts,
            "toefl": {"exam_count": 1, "subject_count": 4, "question_count": 20},
        },
    )


class PracticeCenterBatch1Test(unittest.TestCase):
    def test_public_and_student_views_do_not_render_staff_controls(self):
        for role in (None, "student"):
            with self.subTest(role=role):
                html = render_practice(role=role)
                elements = Elements(html)
                for name in (
                    "practice-suite-filters", "practice-suite-preview", "practice-exam-switch",
                ):
                    self.assertEqual(elements.with_class(name), [])
                self.assertNotIn("布置给学生", html)
                self.assertTrue(elements.with_class("practice-subjects"))
                self.assertTrue(elements.with_class("js-practice-resource"))

    def test_staff_layout_and_working_subject_controls_remain(self):
        for role in ("teacher", "assistant", "admin"):
            with self.subTest(role=role):
                html = render_practice(role=role)
                elements = Elements(html)
                self.assertTrue(elements.with_class("admin-suite-v2"))
                self.assertEqual(len(elements.with_class("practice-suite-filters")), 1)
                self.assertEqual(len(elements.with_class("practice-suite-preview")), 1)
                self.assertEqual(len(elements.with_class("practice-exam-switch")), 1)
                self.assertEqual(len(elements.with_attr("data-practice-target-index")), 4)
                self.assertIn("布置给学生", html)
                self.assertFalse(any(
                    tag == "input" and attrs.get("type") == "checkbox"
                    for tag, attrs in elements.rows
                ))

    def test_root_omits_self_back_link_but_child_pages_keep_it(self):
        root = Elements(render_practice())
        self.assertEqual(root.with_attr("data-practice-module-back"), [])
        self.assertEqual(len(root.with_attr("data-practice-module-exit")), 1)
        child = Elements(render_practice(
            path="/practice/question-types", endpoint="question_type_practice.student_index",
        ))
        self.assertEqual(child.with_attr("data-practice-module-back")[0]["href"], "/practice")


if __name__ == "__main__":
    unittest.main()
