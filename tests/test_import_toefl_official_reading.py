import unittest

from scripts.import_toefl_official_reading import (
    OG_FILL_RE,
    PRACTICE_FILL_RE,
    complete_practice_fill_answers,
    item_count,
    parse_options,
    valid_question_matches,
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

    def test_practice_fill_ignores_hyphenated_compound_words(self):
        words = complete_practice_fill_answers(
            "It is a laboratory-based sci_ _ _ _ that comb_ _ _ _ two fields.",
            ["ence", "ines"],
        )
        self.assertEqual(words, ["science", "combines"])

    def test_practice_fill_accepts_hyphen_blanks(self):
        words = complete_practice_fill_answers(
            "We mi- - - think th- - people danced.",
            ["ght", "at"],
        )
        self.assertEqual(words, ["might", "that"])

    def test_numbered_passage_lines_are_not_questions(self):
        page = (
            "1. Noise Levels: Please keep noise to a minimum.\n"
            "2. Electronic Devices: Set phones to silent mode.\n"
            "13. What can be concluded about the library?\n"
            "(A) First answer\n(B) Second answer\n"
            "(C) Third answer\n(D) Fourth answer\n"
        )
        matches = valid_question_matches(page, 20)
        self.assertEqual([match.group("number") for match in matches], ["13"])


if __name__ == "__main__":
    unittest.main()
