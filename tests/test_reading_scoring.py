import unittest

from app import _grade_reading_test_answers


class ReadingScoringTest(unittest.TestCase):
    def test_judgment_abbreviations_match_full_answers(self):
        payload = {
            "passages": [
                {
                    "groups": [
                        {
                            "questions": [
                                {"id": 1, "number": 1, "answer": "YES"},
                                {"id": 2, "number": 2, "answer": "NO"},
                                {"id": 3, "number": 3, "answer": "NOT GIVEN"},
                                {"id": 4, "number": 4, "answer": "TRUE"},
                                {"id": 5, "number": 5, "answer": "FALSE"},
                            ]
                        }
                    ]
                }
            ]
        }

        grade = _grade_reading_test_answers(
            payload,
            {"1": "Y", "2": "N", "3": "NG", "4": "T", "5": "F"},
        )

        self.assertEqual(grade["correct"], 5)
        self.assertEqual(grade["wrong_numbers"], [])
        self.assertTrue(all(row["correct"] for row in grade["results"]))

    def test_single_letter_matching_answer_is_not_treated_as_false(self):
        payload = {
            "passages": [
                {
                    "groups": [
                        {
                            "questions": [
                                {"id": 6, "number": 6, "answer": "F"},
                            ]
                        }
                    ]
                }
            ]
        }

        correct_grade = _grade_reading_test_answers(payload, {"6": "F"})
        wrong_grade = _grade_reading_test_answers(payload, {"6": "FALSE"})

        self.assertEqual(correct_grade["correct"], 1)
        self.assertEqual(wrong_grade["correct"], 0)

    def test_short_judgment_answers_accept_full_submissions_in_judgment_groups(self):
        payload = {
            "passages": [
                {
                    "groups": [
                        {
                            "desc": (
                                "Do the following statements agree with the information given "
                                "in Reading Passage? TRUE if the statement agrees, FALSE if "
                                "the statement contradicts, NOT GIVEN if there is no information."
                            ),
                            "questions": [
                                {"id": 7, "number": 7, "answer": "T"},
                                {"id": 8, "number": 8, "answer": "F"},
                                {"id": 9, "number": 9, "answer": "NG"},
                            ],
                        }
                    ]
                }
            ]
        }

        grade = _grade_reading_test_answers(
            payload,
            {"7": "TRUE", "8": "FALSE", "9": "NOT GIVEN"},
        )

        self.assertEqual(grade["correct"], 3)

    def test_unordered_multi_letter_groups_score_unique_letters_per_blank(self):
        payload = {
            "passages": [
                {
                    "groups": [
                        {
                            "desc": "Questions 10 and 11 Choose TWO letters, A-E.",
                            "collect_option": {
                                "list": [
                                    {"key": "A", "text": "Alpha"},
                                    {"key": "B", "text": "Beta"},
                                    {"key": "C", "text": "Gamma"},
                                ]
                            },
                            "questions": [
                                {"id": 10, "number": 10, "answer": "B, C"},
                                {"id": 11, "number": 11, "answer": "B, C"},
                            ],
                        }
                    ]
                }
            ]
        }

        both_correct = _grade_reading_test_answers(payload, {"10": "C", "11": "B"})
        duplicate = _grade_reading_test_answers(payload, {"10": "B", "11": "B"})
        one_wrong = _grade_reading_test_answers(payload, {"10": "B", "11": "D"})

        self.assertEqual(both_correct["correct"], 2)
        self.assertEqual(duplicate["correct"], 1)
        self.assertEqual(one_wrong["correct"], 1)

    def test_individual_multi_choice_requires_complete_selected_set(self):
        payload = {
            "passages": [
                {
                    "groups": [
                        {
                            "questions": [
                                {
                                    "id": 12,
                                    "number": 12,
                                    "answer": "A,B",
                                    "options": [
                                        {"key": "A", "text": "Alpha"},
                                        {"key": "B", "text": "Beta"},
                                        {"key": "C", "text": "Gamma"},
                                    ],
                                }
                            ]
                        }
                    ]
                }
            ]
        }

        complete = _grade_reading_test_answers(payload, {"12": "B,A"})
        incomplete = _grade_reading_test_answers(payload, {"12": "A"})

        self.assertEqual(complete["correct"], 1)
        self.assertEqual(incomplete["correct"], 0)

    def test_numeric_answers_with_commas_are_treated_as_text_alternatives(self):
        payload = {
            "passages": [
                {
                    "groups": [
                        {
                            "questions": [
                                {
                                    "id": 13,
                                    "number": 13,
                                    "answer": "1,000 kg / 1000 kg",
                                }
                            ]
                        }
                    ]
                }
            ]
        }

        grade = _grade_reading_test_answers(payload, {"13": "1000 kg"})

        self.assertEqual(grade["correct"], 1)


if __name__ == "__main__":
    unittest.main()
