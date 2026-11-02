import unittest

from tools.ielts_writing_ai import essay


class SentenceSplitTest(unittest.TestCase):
    def texts(self, value):
        return [s.text for s in essay.split_sentences(value)]

    def test_basic_paragraphs_and_sentences(self):
        sentences = essay.split_sentences("First one. Second one!\n\nThird? Fourth")
        self.assertEqual(
            [s.text for s in sentences], ["First one.", "Second one!", "Third?", "Fourth"]
        )
        self.assertEqual([s.paragraph for s in sentences], [0, 0, 1, 1])
        self.assertEqual([s.index for s in sentences], [0, 1, 2, 3])

    def test_abbreviations_initials_and_decimals_do_not_split(self):
        self.assertEqual(
            self.texts(
                "Costs rose by 3.5 percent, e.g. in Japan. Mr. J. Smith disagreed. It ended."
            ),
            ["Costs rose by 3.5 percent, e.g. in Japan.", "Mr. J. Smith disagreed.", "It ended."],
        )

    def test_closing_quotes_stay_with_sentence(self):
        self.assertEqual(
            self.texts('He said "this is wrong." Then he left.'),
            ['He said "this is wrong."', "Then he left."],
        )

    def test_single_newline_is_a_paragraph_break(self):
        sentences = essay.split_sentences("Intro line.\nBody line.\r\nEnd line.")
        self.assertEqual([s.paragraph for s in sentences], [0, 1, 2])

    def test_join_rebuilds_paragraphs(self):
        sentences = essay.split_sentences("A b. C d.\nE f.")
        self.assertEqual(essay.join_sentences(sentences), "A b. C d.\n\nE f.")
        self.assertEqual(essay.join_sentences(sentences, ["X.", "Y.", "Z."]), "X. Y.\n\nZ.")


class WordAndBandTest(unittest.TestCase):
    def test_word_count_handles_contractions_and_hyphens(self):
        self.assertEqual(essay.count_words("It's a well-known fact, isn't it? 2024 data."), 8)
        self.assertEqual(essay.count_words(""), 0)

    def test_snap_band(self):
        self.assertEqual(essay.snap_band(6.3), 6.5)
        self.assertEqual(essay.snap_band("7"), 7.0)
        self.assertEqual(essay.snap_band(6.2), 6.0)
        self.assertIsNone(essay.snap_band(9.5))
        self.assertIsNone(essay.snap_band("abc"))
        self.assertIsNone(essay.snap_band(float("nan")))

    def test_overall_band_rounding(self):
        self.assertEqual(essay.overall_band([6.0, 6.0, 6.5, 6.5]), 6.5)  # 6.25 -> 6.5
        self.assertEqual(essay.overall_band([6.5, 6.5, 7.0, 7.0]), 7.0)  # 6.75 -> 7.0
        self.assertEqual(essay.overall_band([6.0, 6.0, 6.0, 6.5]), 6.0)  # 6.125 -> 6.0
        self.assertIsNone(essay.overall_band([6.0, None]))

    def test_contains_quote_is_whitespace_case_and_quote_insensitive(self):
        text = "Governments  don’t have\nunlimited budgets."
        self.assertTrue(essay.contains_quote(text, "governments don't have unlimited"))
        self.assertFalse(essay.contains_quote(text, "budgets are unlimited"))
        self.assertFalse(essay.contains_quote(text, "  "))


if __name__ == "__main__":
    unittest.main()
