"""No-network, no-database contract tests for numeric listening answers."""

import unittest

from dictation_numeric import classify_numeric_dictation, is_numeric_answer_correct


class NumericDictationTests(unittest.TestCase):
    def assert_equivalent(self, expected, candidates, rejected=()):
        rule = classify_numeric_dictation(expected)
        self.assertIsNotNone(rule)
        for answer in candidates:
            with self.subTest(expected=expected, accepted=answer):
                self.assertTrue(is_numeric_answer_correct(answer, rule["canonical"], rule["kind"]))
        for answer in rejected:
            with self.subTest(expected=expected, rejected=answer):
                self.assertFalse(is_numeric_answer_correct(answer, rule["canonical"], rule["kind"]))

    def test_numbers_preserve_decimal_sign_and_grouping_meaning(self):
        self.assert_equivalent(
            "1.30", ["1.3", "01.30", "+1.300"], ["130", "1,30", "1:30", "13", "-1.3"]
        )
        self.assert_equivalent(
            "10,000", ["10000", "10,000", "10000.0"], ["10.000", "10 000", "10,00"]
        )
        self.assert_equivalent("-16.50", ["-16.5", "-16.50"], ["16.5", "-1650"])
        self.assert_equivalent("0.1", [".1", "0.10"], ["1", "01", "1e-1"])
        self.assert_equivalent("0", ["0", "0.0"], ["", None, "NaN", "Infinity"])

    def test_phone_preserves_leading_zero_and_country_marker(self):
        self.assert_equivalent(
            "07958847222",
            ["07958847222", "0795 884 7222", "(0795) 884-7222"],
            ["7958847222", "+07958847222", "079588472220", "07958847222.0"],
        )
        self.assert_equivalent(
            "+44 2079460385",
            ["+442079460385", "+44 (20) 7946-0385"],
            ["442079460385", "00442079460385"],
        )
        self.assert_equivalent("007", ["007", "0 0 7"], ["7", "0007"])

    def test_percentage_does_not_equal_unqualified_decimal(self):
        self.assert_equivalent(
            "40%", ["40%", "40 percent", "40.0 per cent"], ["40", "0.4", ".4%", "400%"]
        )
        self.assert_equivalent("1.3%", ["1.30%", "1.3 percent"], ["13%", "1.3"])

    def test_currency_requires_same_unit_and_value(self):
        self.assert_equivalent(
            "£16.50",
            ["16.5 pounds", "GBP 16.50", "£16.500"],
            ["16.50", "$16.50", "£1650", "16.50 euros"],
        )
        self.assert_equivalent(
            "$1,250.50", ["USD 1250.5", "1250.50 dollars"], ["1250.5", "$125050"]
        )
        self.assert_equivalent("€0.50", ["0.5 euros", "EUR .50"], ["50 euros", "0.50 pounds"])

    def test_dates_only_accept_explicit_same_day_month_year(self):
        self.assert_equivalent(
            "June 27",
            ["27 June", "June 27th", "27th of Jun"],
            ["27/06", "06/27", "2026-06-27", "June 28", "July 27"],
        )
        self.assert_equivalent(
            "27 June 2026",
            ["2026-06-27", "June 27th, 2026", "27th Jun 2026"],
            ["27 June", "2025-06-27", "2026-27-06", "06/27/2026"],
        )
        self.assert_equivalent(
            "2024-02-29", ["29 February 2024", "Feb 29th 2024"], ["2023-02-29", "29 Feb"]
        )

    def test_ambiguous_or_invalid_date_uses_exact_literal(self):
        for value in ["03/04", "03/04/2026", "03-04-2026", "2026-02-30", "0000-01-01"]:
            with self.subTest(value=value):
                self.assertEqual(classify_numeric_dictation(value)["kind"], "literal")
        self.assert_equivalent("03/04", ["03/04"], ["04/03", "3/4", "0304", "April 3", "March 4"])
        self.assert_equivalent(
            "03-04-2026", ["03-04-2026"], ["03042026", "03/04/2026", "2026-04-03"]
        )
        self.assertFalse(is_numeric_answer_correct("11 June", "11st June"))

    def test_time_and_decimal_are_distinct(self):
        self.assert_equivalent(
            "7:45pm",
            ["19:45", "7:45 PM", "745 pm", "7.45 p.m."],
            ["7:45", "07:45", "7.45", "745", "19:54"],
        )
        self.assert_equivalent("12:00 am", ["00:00", "12 am"], ["12:00", "12 pm"])
        self.assert_equivalent("530 pm", ["5:30 pm", "17:30"], ["530", "5.30", "05:30"])
        self.assertEqual(classify_numeric_dictation("4.30")["kind"], "number")
        self.assert_equivalent("4.30", ["4.3"], ["4:30", "4.30am"])
        self.assertEqual(classify_numeric_dictation("25:99")["kind"], "literal")

    def test_ordinary_alphanumeric_english_stays_on_existing_path(self):
        for value in [
            "B2B",
            "MP3",
            "B2B marketing",
            "H2O",
            "A320",
            "21st-century",
            "second",
            "roof",
        ]:
            with self.subTest(value=value):
                self.assertIsNone(classify_numeric_dictation(value))
        self.assertFalse(is_numeric_answer_correct("mp3", "MP3"))

    def test_mixed_unsupported_material_is_literal_not_lost(self):
        for value in [
            "463 Beacon",
            "older than 40",
            "12.5 degrees",
            "0.1 centimeters",
            "3.6 million",
            "10 years",
            "model 3",
        ]:
            with self.subTest(value=value):
                self.assertEqual(classify_numeric_dictation(value)["kind"], "literal")
                self.assert_equivalent(
                    value, [value, value.upper()], [value.replace(".", "").replace(" ", "")]
                )
        self.assert_equivalent(
            "12.5 degrees", ["12.5 degrees"], ["125 degrees", "12,5 degrees", "12.50 degrees"]
        )

    def test_speech_is_category_specific_without_paid_generation(self):
        examples = {
            "0217856361": ("digit_sequence", "zero two one seven eight five six three six one"),
            "16.50": ("number", "sixteen point five zero"),
            "40%": ("percentage", "forty percent"),
            "£16.50": ("currency", "sixteen pounds fifty pence"),
            "$0.01": ("currency", "zero dollars one cent"),
            "June 27": ("date", "June twenty seventh"),
            "2026-06-27": ("date", "June twenty seventh two thousand twenty six"),
            "7:45pm": ("time", "seven forty five p m"),
            "03/04": ("literal", "zero three slash zero four"),
            "463 Beacon": ("literal", "463 Beacon"),
        }
        for source, (kind, speech) in examples.items():
            with self.subTest(source=source):
                actual = classify_numeric_dictation(source)
                self.assertEqual(actual["kind"], kind)
                self.assertEqual(actual["tts_text"], speech)
                self.assertEqual(actual["canonical"], source)
                self.assertTrue(actual["input_hint"])

    def test_snapshot_kind_cannot_select_a_more_permissive_comparator(self):
        self.assertFalse(is_numeric_answer_correct("123", "0123", "number"))
        self.assertFalse(is_numeric_answer_correct("1.3", "1.30", "literal"))
        self.assertFalse(is_numeric_answer_correct("03/04", "03/04", "date"))
        self.assertFalse(is_numeric_answer_correct("anything", "", "literal"))

    def test_width_and_outer_whitespace_are_harmless(self):
        self.assert_equivalent("16.50", [" １６．５０ ", "16.50"], ["１６５０"])
        self.assert_equivalent("07958847222", ["０７９５８８４７２２２"], ["７９５８８４７２２２"])

    def test_compatibility_unicode_is_not_a_numeric_equivalence(self):
        self.assert_equivalent("10²", ["10²"], ["102"])
        self.assert_equivalent("1①", ["1①"], ["11"])
        self.assert_equivalent("1½", ["1½"], ["11/2", "1.5"])


if __name__ == "__main__":
    unittest.main()
