import unittest

from app import _grade_listening_test_answers


class ListeningScoringTest(unittest.TestCase):
    def test_text_answers_ignore_case_and_accept_listed_singular_plural_forms(self):
        payload = {
            "sections": [
                {
                    "groups": [
                        {
                            "questions": [
                                {"id": 1, "number": 1, "answer": "beaches / beach"},
                                {"id": 2, "number": 2, "answer": "photo card / photo cards"},
                                {"id": 3, "number": 3, "answer": "8.30 / 8:30"},
                            ]
                        }
                    ]
                }
            ]
        }

        grade = _grade_listening_test_answers(
            payload,
            {"1": "Beach", "2": "PHOTO CARDS", "3": "8:30"},
        )

        self.assertEqual(grade["correct"], 3)

    def test_combined_multi_choice_awards_partial_credit_without_extra_answers(self):
        payload = {
            "sections": [
                {
                    "groups": [
                        {
                            "type": 2,
                            "collect_option": {
                                "list": [
                                    {"title": "A", "content": "Alpha"},
                                    {"title": "B", "content": "Beta"},
                                    {"title": "C", "content": "Gamma"},
                                    {"title": "D", "content": "Delta"},
                                ]
                            },
                            "questions": [
                                {"id": 10, "number": 10, "answer": "B,C"},
                                {"id": 11, "number": 11, "answer": "B,C"},
                            ],
                        }
                    ]
                }
            ]
        }

        partial = _grade_listening_test_answers(payload, {"10,11": "B,D"})
        complete = _grade_listening_test_answers(payload, {"10,11": "C,B"})
        too_many = _grade_listening_test_answers(payload, {"10,11": "A,B,C"})

        self.assertEqual(partial["correct"], 1)
        self.assertFalse(partial["results"][0]["correct"])
        self.assertEqual(complete["correct"], 2)
        self.assertEqual(too_many["correct"], 0)


if __name__ == "__main__":
    unittest.main()
