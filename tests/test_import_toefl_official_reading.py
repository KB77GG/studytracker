import unittest

from scripts.import_toefl_official_reading import (
    OG_FILL_RE,
    PRACTICE_FILL_RE,
    complete_practice_fill_answers,
    item_count,
    parse_options,
)


class ImportToeflOfficialReadingTest(unittest.TestCase):
    def test_parse_parenthesized_options(self):
        prompt, options = parse_options(
            "11. What is the purpose?\n"
            "(A) First answer\n(B) Second answer\n"
            "(C) Third answer\n(D) Fourth answer"
        )
        self.assertEqual(prompt, "11. What is the purpose?")
        self.assertEqual([option["key"] for option in options], ["A", "B", "C", "D"])

    def test_parse_plain_options(self):
        prompt, options = parse_options(
            "21. What is suggested?\n"
            "A. First answer\nB. Second answer\n"
            "C. Third answer\nD. Fourth answer"
        )
        self.assertEqual(prompt, "21. What is suggested?")
        self.assertEqual(options[1]["text"], "Second answer")

    def test_item_count_expands_fill_ranges(self):
        questions = [
            {"response_type": "fill", "answer": {"words": ["a", "b", "c"]}},
            {"response_type": "mc", "answer": {"keys": ["A"]}},
        ]
        self.assertEqual(item_count(questions), 4)

    def test_practice_fill_keeps_multiline_paragraph(self):
        page = (
            "Fill in the missing letters in the paragraph.\n"
            "(Questions 1-10)\n"
            "First line of the paragraph.\n"
            "Second line of the paragraph.\n\n"
            "Read a notice.\nNotice body"
        )
        match = PRACTICE_FILL_RE.search(page)
        self.assertIsNotNone(match)
        self.assertIn("Second line", match.group("body"))
        self.assertNotIn("Read a notice", match.group("body"))

    def test_og_fill_stops_before_module_two_article(self):
        page = (
            "1–10.\nFill in the missing letters in the paragraph.\n"
            "First line.\nSecond line.\n\n"
            "Urbanization and Social Geography\n"
            "Article body"
        )
        match = OG_FILL_RE.search(page)
        self.assertIsNotNone(match)
        self.assertIn("Second line", match.group("body"))
        self.assertNotIn("Urbanization", match.group("body"))

    def test_practice_fill_fragments_become_complete_words(self):
        words = complete_practice_fill_answers(
            "We mi_ _ _ think th_ _ people danced.",
            ["ght", "at"],
        )
        self.assertEqual(words, ["might", "that"])


if __name__ == "__main__":
    unittest.main()
