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


if __name__ == "__main__":
    unittest.main()
