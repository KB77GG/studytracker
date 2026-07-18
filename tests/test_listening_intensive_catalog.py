import json
import tempfile
import unittest
from pathlib import Path

from api.listening_intensive import (
    build_intensive_catalog,
    load_registered_intensive_exercise,
)


def _write_exercise(root: Path, exercise_id: str, title: str, segment_count: int):
    (root / f"{exercise_id}.json").write_text(
        json.dumps(
            {
                "title": title,
                "parts": [
                    {
                        "name": title.rsplit(" ", 1)[-1],
                        "segments": [{"id": index} for index in range(segment_count)],
                    }
                ],
            }
        ),
        encoding="utf-8",
    )


class ListeningIntensiveCatalogTests(unittest.TestCase):
    def test_groups_registered_assets_and_sorts_series_book_test_part(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_exercise(root, "jfdr6_test2_s2", "JFDR 6 Test 2 Part 2", 2)
            _write_exercise(root, "jfdr6_test1_s2", "JFDR 6 Test 1 Part 2", 3)
            _write_exercise(root, "jfdr6_test1_s1", "JFDR 6 Test 1 Part 1", 1)
            _write_exercise(root, "ielts6_test1_s1", "IELTS 6 Test 1 Section 1", 4)
            _write_exercise(root, "not_registered_s1", "Ignore me", 99)
            (root / "ielts6_test1.json").write_text("{}", encoding="utf-8")
            (root / "ielts6_test2_s1.json").write_text("not json", encoding="utf-8")

            books = build_intensive_catalog(root)

        self.assertEqual(
            [(book["series"], book["book"]) for book in books],
            [("cambridge", 6), ("jfdr", 6)],
        )
        self.assertEqual([test["test"] for test in books[1]["tests"]], [1, 2])
        self.assertEqual(
            [part["number"] for part in books[1]["tests"][0]["parts"]],
            [1, 2],
        )
        self.assertEqual(books[1]["tests"][0]["parts"][1]["id"], "jfdr6_test1_s2")
        self.assertEqual(books[1]["tests"][0]["parts"][1]["segment_count"], 3)
        self.assertEqual(books[1]["tests"][0]["segment_count"], 4)

    def test_loader_requires_registered_exact_filename_and_existing_file(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _write_exercise(root, "jfdr6_test1_s2", "Part 2", 1)

            payload, info, safe_id = load_registered_intensive_exercise(
                root, "jfdr6_test1_s2"
            )
            self.assertEqual(payload["title"], "Part 2")
            self.assertEqual(info["section"], 2)
            self.assertEqual(safe_id, "jfdr6_test1_s2")
            self.assertEqual(
                load_registered_intensive_exercise(root, "jfdr6_test1")[0], None
            )
            self.assertEqual(
                load_registered_intensive_exercise(root, "../jfdr6_test1_s2")[0], None
            )
            self.assertEqual(
                load_registered_intensive_exercise(root, "jfdr6_test1_s9")[0], None
            )


if __name__ == "__main__":
    unittest.main()
