"""纯逻辑单测：听力书目系列注册表（api/listening_series.py）。"""

import unittest

from api.listening_series import parse_intensive_id, parse_test_id, series_sort_key


class ParseTestIdTests(unittest.TestCase):
    def test_cambridge(self):
        info = parse_test_id("ielts18_test1")
        self.assertEqual(info["series"], "cambridge")
        self.assertEqual(info["book"], 18)
        self.assertEqual(info["test"], 1)
        self.assertEqual(info["label"], "剑雅 18")
        self.assertEqual(info["test_key"], "ielts18_test1")

    def test_jfdr(self):
        info = parse_test_id("jfdr6_test3")
        self.assertEqual(info["series"], "jfdr")
        self.assertEqual(info["book"], 6)
        self.assertEqual(info["test"], 3)
        self.assertEqual(info["label"], "9分达人 6")

    def test_no_match(self):
        self.assertIsNone(parse_test_id("catalog"))
        self.assertIsNone(parse_test_id("ielts18_test1_s1"))
        self.assertIsNone(parse_test_id(""))
        self.assertIsNone(parse_test_id(None))


class ParseIntensiveIdTests(unittest.TestCase):
    def test_cambridge_section(self):
        info = parse_intensive_id("ielts10_test2_s4")
        self.assertEqual(
            (info["series"], info["book"], info["test"], info["section"]),
            ("cambridge", 10, 2, 4),
        )
        self.assertEqual(info["test_key"], "ielts10_test2")

    def test_jfdr_section(self):
        info = parse_intensive_id("jfdr6_test1_s2")
        self.assertEqual(
            (info["series"], info["book"], info["test"], info["section"]),
            ("jfdr", 6, 1, 2),
        )
        self.assertEqual(info["title"], "9分达人听力6 Test 1 Part 2")

    def test_no_match(self):
        self.assertIsNone(parse_intensive_id("ielts18_test1"))
        self.assertIsNone(parse_intensive_id("jfdr6"))


class SortKeyTests(unittest.TestCase):
    def test_cambridge_before_jfdr_despite_same_book(self):
        cam6 = parse_test_id("ielts6_test1")
        jfdr6 = parse_test_id("jfdr6_test1")
        self.assertLess(series_sort_key(cam6), series_sort_key(jfdr6))

    def test_books_sorted_within_series(self):
        keys = [
            series_sort_key(parse_test_id(f"ielts{book}_test1")) for book in (4, 10, 20)
        ]
        self.assertEqual(keys, sorted(keys))


if __name__ == "__main__":
    unittest.main()
