from __future__ import annotations

import unittest

from scripts.map_toefl_answers_to_practice_docs import (
    parse_chinese_sections,
    parse_english_modules,
)


class MapToeflAnswersToPracticeDocsTest(unittest.TestCase):
    def test_parse_english_module_answer_layout(self):
        text = """
Reading, Module1:
1 They
2 change
21 A
22 B
Module2:
1 pots
11 C
Listening module1
1 B
2 D
Listening module2
1 A
Writing
Build a sentence.
1. do you know if it changed?
Speaking
"""
        result = parse_english_modules(text)
        by_key = {
            (row.subject, row.module, row.source_question_no): row
            for row in result.answers
        }
        self.assertEqual(by_key[("reading", "m1", 21)].correct_answer, "A")
        self.assertEqual(by_key[("reading", "m1", 1)].answer_type, "fill")
        self.assertEqual(by_key[("listening", "m2", 1)].correct_answer, "A")
        self.assertEqual(
            by_key[("writing", "m1", 1)].answer_type,
            "order",
        )

    def test_parse_chinese_main_and_extra_layout(self):
        text = """
阅读
1this 2helps 21b 22a
加试
1reasoning 11c 12d
听力
1a 2d
第二部份
1b 2c
写作
1. i could not attend
口语
1. welcome
"""
        result = parse_chinese_sections(text)
        by_key = {
            (row.subject, row.module, row.source_question_no): row
            for row in result.answers
        }
        self.assertEqual(by_key[("reading", "m1", 21)].correct_answer, "B")
        self.assertEqual(by_key[("reading", "m2", 11)].correct_answer, "C")
        self.assertEqual(by_key[("listening", "m2", 2)].correct_answer, "C")
        self.assertEqual(
            by_key[("writing", "m1", 1)].correct_answer,
            "i could not attend",
        )


if __name__ == "__main__":
    unittest.main()
