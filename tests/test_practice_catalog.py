"""纯逻辑单测：书本进度与继续刷题推荐。"""

import unittest

from api.practice_catalog import (
    decorate_reading_books,
    pick_continue_target,
    summarize_book_progress,
    summarize_jijing_book_progress,
)


def _status(accuracy, submitted_at):
    return {"accuracy": accuracy, "submitted_at": submitted_at, "label": "已刷"}


def _test(book, number, *, status=None, reading=False):
    suffix = "_reading" if reading else ""
    row = {
        "id": f"ielts{book}_test{number}{suffix}",
        "test": number,
    }
    if reading:
        row["passage_count"] = 3
    if status:
        row["practice_status"] = status
    return row


class SummarizeBookProgressTests(unittest.TestCase):
    def test_progress_counts_and_rounds_average_accuracy(self):
        books = [
            {
                "book": 12,
                "tests": [
                    _test(12, 1, status=_status(80, None)),
                    _test(12, 2, status=_status(83, None)),
                    _test(12, 3),
                ],
            }
        ]

        summarize_book_progress(books)

        self.assertEqual(
            books[0]["progress"],
            {"done": 2, "total": 3, "avg_accuracy": 82},
        )


class DecorateReadingBooksTests(unittest.TestCase):
    def test_adds_workspace_fields_without_overwriting_existing_values(self):
        books = [
            {"book": 12, "tests": [_test(12, 1, reading=True)]},
            {
                "book": 13,
                "series": "custom",
                "label": "自定义阅读",
                "tests": [{**_test(13, 1, reading=True), "series": "custom-test"}],
            },
        ]

        decorate_reading_books(books)

        self.assertEqual(books[0]["series"], "cambridge")
        self.assertEqual(books[0]["label"], "剑雅 12")
        self.assertEqual(books[0]["tests"][0]["series"], "cambridge")
        self.assertEqual(books[1]["series"], "custom")
        self.assertEqual(books[1]["label"], "自定义阅读")
        self.assertEqual(books[1]["tests"][0]["series"], "custom-test")

    def test_supports_reading_jijing_labels_and_series(self):
        books = [{"book": 57, "tests": [{"id": "reading_jijing_57_test_1"}]}]

        decorate_reading_books(books, series="jijing", label_prefix="机经")

        self.assertEqual(books[0]["series"], "jijing")
        self.assertEqual(books[0]["label"], "机经 57")
        self.assertEqual(books[0]["tests"][0]["series"], "jijing")


class SummarizeJijingBookProgressTests(unittest.TestCase):
    def test_counts_completed_parts_across_tests(self):
        books = [
            {
                "tests": [
                    {
                        "parts": [
                            {"id": "part-1", "practice_status": _status(80, None)},
                            {"id": "part-2"},
                        ]
                    },
                    {"parts": [{"id": "part-3", "practice_status": _status(90, None)}]},
                ]
            }
        ]

        summarize_jijing_book_progress(books)

        self.assertEqual(books[0]["progress"], {"done": 2, "total": 3})


class PickContinueTargetTests(unittest.TestCase):
    def test_recommends_next_unfinished_test_in_same_book(self):
        books = [
            {
                "series": "cambridge",
                "book": 12,
                "label": "剑雅 12",
                "tests": [
                    _test(12, 1, status=_status(76, "2026-07-12T10:00:00")),
                    _test(12, 2),
                    _test(12, 3),
                ],
            }
        ]

        target = pick_continue_target(books)

        self.assertEqual(target["last"]["test"], 1)
        self.assertEqual(target["last"]["accuracy"], 76)
        self.assertEqual(target["next"]["test"], 2)
        self.assertEqual(target["next"]["url"], "/listening/test/ielts12_test2")

    def test_recommends_first_unfinished_test_in_next_book(self):
        books = [
            {
                "series": "cambridge",
                "book": 12,
                "label": "剑雅 12",
                "tests": [
                    _test(12, 1, status=_status(70, None)),
                    _test(12, 2, status=_status(81, "2026-07-12T11:00:00")),
                ],
            },
            {
                "series": "cambridge",
                "book": 13,
                "label": "剑雅 13",
                "tests": [_test(13, 1), _test(13, 2)],
            },
        ]

        target = pick_continue_target(books)

        self.assertEqual(target["last"]["test"], 2)
        self.assertEqual(target["next"]["label"], "剑雅 13")
        self.assertEqual(target["next"]["test"], 1)

    def test_returns_no_next_target_when_all_tests_are_finished(self):
        books = [
            {
                "book": 12,
                "tests": [
                    _test(
                        12,
                        1,
                        status=_status(88, "2026-07-12T12:00:00Z"),
                        reading=True,
                    )
                ],
            }
        ]

        target = pick_continue_target(books)

        self.assertEqual(target["last"]["label"], "剑雅 12")
        self.assertEqual(target["last"]["url"], "/reading/test/ielts12_test1_reading")
        self.assertIsNone(target["next"])


if __name__ == "__main__":
    unittest.main()
