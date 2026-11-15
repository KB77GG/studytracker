"""Guard the evidence used to link a public hotlist to an existing answer key."""

import copy
import unittest

from scripts.audit_exam_sprint_matches import comparison_text, source_questions, verify_pair


class SprintMatchingTests(unittest.TestCase):
    def setUp(self):
        self.transcript = " ".join(f"word{index}" for index in range(150))
        self.local = {
            "part_number": 1,
            "content": [{"en_text": self.transcript}],
            "groups": [
                {
                    "items": [
                        {
                            "number": index,
                            "title": f"Question topic {index}",
                            "answer": "A",
                            "options": [{"title": "A", "content": "First option"}],
                        }
                        for index in range(1, 11)
                    ]
                }
            ],
        }
        self.source = {
            "data": {
                "id": "1234567890123456789",
                "channel": "listening",
                "parts": [
                    {
                        "id": "9876543210987654321",
                        "partNum": "Part 1",
                        "article": self.transcript,
                        "groups": [
                            {
                                "questions": [
                                    {
                                        "qNumber": str(index),
                                        "question": f"Question topic {index}",
                                        "options": [
                                            {"optionNum": "A", "optionContent": "First option"}
                                        ],
                                    }
                                    for index in range(1, 11)
                                ]
                            }
                        ],
                    }
                ],
            }
        }

    def verify(self, source=None, local=None):
        return verify_pair(source or self.source, local or self.local, "1234567890123456789")

    def test_complete_identical_pair_is_verified(self):
        self.assertEqual(self.verify()["question_count"], 10)
        self.assertEqual(self.verify()["source_transcript_token_coverage"], 1)

    def test_named_topic_with_changed_numeric_stem_is_rejected(self):
        source = copy.deepcopy(self.source)
        source["data"]["parts"][0]["groups"][0]["questions"][0]["question"] = "Question topic 130"
        with self.assertRaisesRegex(ValueError, "not identical"):
            self.verify(source)

    def test_changed_option_or_question_number_is_rejected(self):
        for field, value in [("qNumber", "12"), ("options", [])]:
            with self.subTest(field=field):
                source = copy.deepcopy(self.source)
                source["data"]["parts"][0]["groups"][0]["questions"][0][field] = value
                with self.assertRaisesRegex(ValueError, "not identical"):
                    self.verify(source)

    def test_existing_answer_key_is_required(self):
        local = copy.deepcopy(self.local)
        local["groups"][0]["items"][0]["answer"] = ""
        with self.assertRaisesRegex(ValueError, "answer key"):
            self.verify(local=local)

    def test_different_recording_text_is_rejected(self):
        source = copy.deepcopy(self.source)
        source["data"]["parts"][0]["article"] = " ".join(
            f"different{index}" for index in range(150)
        )
        with self.assertRaisesRegex(ValueError, "Transcript version"):
            self.verify(source)

    def test_new_diagram_is_not_treated_as_a_text_match(self):
        source = copy.deepcopy(self.source)
        source["data"]["parts"][0]["groups"][0]["image"] = "https://example.invalid/map.png"
        with self.assertRaisesRegex(ValueError, "visual review"):
            self.verify(source)

    def test_ambiguous_fill_placeholder_is_rejected(self):
        part = {
            "groups": [
                {
                    "questions": [{"qNumber": "1", "question": None}],
                    "contentHtml": '<tr><td><input placeholder="1"></td></tr>' * 2,
                }
            ]
        }
        with self.assertRaisesRegex(ValueError, "one source stem"):
            source_questions(part)

    def test_layout_normalization_preserves_numeric_information(self):
        self.assertEqual(
            comparison_text('Address: 45 <input placeholder="1"> Court'),
            comparison_text("Address: 45 1. ______ Court"),
        )
        self.assertNotEqual(
            comparison_text('Address: 130 <input placeholder="1"> Court'),
            comparison_text("Address: 45 1. ______ Court"),
        )


if __name__ == "__main__":
    unittest.main()
