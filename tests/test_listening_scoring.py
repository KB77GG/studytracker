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
        self.assertEqual(partial["results"][0]["status"], "partial")
        self.assertEqual(partial["results"][0]["status_label"], "部分正确 1/2")
        states = {row["key"]: row["status"] for row in partial["results"][0]["option_states"]}
        self.assertEqual(states["B"], "selected_correct")
        self.assertEqual(states["C"], "missed_correct")
        self.assertEqual(states["D"], "selected_wrong")
        self.assertEqual(complete["correct"], 2)
        self.assertEqual(complete["results"][0]["status"], "correct")
        self.assertEqual(too_many["correct"], 0)
        self.assertEqual(too_many["results"][0]["selection_error"], "too_many")

    def test_single_checkbox_is_all_or_nothing_but_explains_each_option(self):
        payload = {
            "sections": [
                {
                    "groups": [
                        {
                            "questions": [
                                {
                                    "id": 20,
                                    "number": 20,
                                    "answer": "A,B",
                                    "options": [{"title": key} for key in "ABC"],
                                }
                            ]
                        }
                    ]
                }
            ]
        }

        for value, expected in (("A", 0), ("B,A", 1), ("A,C", 0)):
            grade = _grade_listening_test_answers(payload, {"20": value})
            self.assertEqual(grade["correct"], expected)
            self.assertEqual(grade["total"], 1)
        extra = _grade_listening_test_answers(payload, {"20": "A,C"})["results"][0]
        states = {row["key"]: row["status"] for row in extra["option_states"]}
        self.assertEqual(states["C"], "selected_wrong")
        self.assertEqual(states["B"], "missed_correct")

    def test_slash_separated_letter_alternatives_accept_either_single_answer(self):
        payload = {
            "sections": [
                {
                    "groups": [
                        {
                            "questions": [
                                {"id": 30, "number": 30, "answer": "A/B"},
                            ]
                        }
                    ]
                }
            ]
        }

        self.assertEqual(_grade_listening_test_answers(payload, {"30": "A"})["correct"], 1)
        self.assertEqual(_grade_listening_test_answers(payload, {"30": "B"})["correct"], 1)
        self.assertEqual(_grade_listening_test_answers(payload, {"30": "C"})["correct"], 0)


if __name__ == "__main__":
    unittest.main()
