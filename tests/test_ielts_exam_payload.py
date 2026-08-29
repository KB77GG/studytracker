import json
import unittest
from pathlib import Path

from services.ielts_exam_payload import build_simulation_payload

ROOT = Path(__file__).resolve().parents[1]


def forbidden_paths(value, prefix=""):
    forbidden = {
        "answer",
        "answers",
        "correct_answer",
        "correct_answers",
        "analysis",
        "explanation",
        "answer_sentences",
        "transcript",
        "translation",
        "translations",
    }
    found = []
    if isinstance(value, dict):
        for key, child in value.items():
            path = f"{prefix}.{key}" if prefix else key
            if key.lower() in forbidden:
                found.append(path)
            found.extend(forbidden_paths(child, path))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found.extend(forbidden_paths(child, f"{prefix}[{index}]"))
    return found


class IeltsExamPayloadTest(unittest.TestCase):
    def test_listening_payload_removes_answers_transcript_and_analysis(self):
        source = json.loads(
            (ROOT / "static/listening_tests/ielts17_test1.json").read_text(encoding="utf-8")
        )
        safe = build_simulation_payload(source, "listening")
        self.assertEqual(forbidden_paths(safe), [])
        self.assertTrue(safe["simulation_payload"])
        self.assertIn("answer", source["sections"][0]["groups"][0]["questions"][0])
        self.assertIn("transcript", source["sections"][0])

    def test_response_shape_survives_answer_removal(self):
        payload = {
            "sections": [{
                "groups": [{
                    "type": 2,
                    "collect_option": {"list": [{"title": "A", "content": "One"}]},
                    "questions": [
                        {"id": 1, "answer": "A,B"},
                        {"id": 2, "answer": "A,B"},
                    ],
                }, {
                    "type": 9,
                    "questions": [{
                        "id": 3,
                        "answer": "B,D",
                        "analysis": "secret",
                        "options": [{"title": "A"}, {"title": "B"}, {"title": "D"}],
                    }],
                }],
                "transcript": [{"en": "secret"}],
            }]
        }
        safe = build_simulation_payload(payload, "listening")
        first, second = safe["sections"][0]["groups"]
        self.assertEqual(first["response_layout"], "combined_multi")
        self.assertEqual(first["max_selections"], 2)
        self.assertEqual(second["questions"][0]["response_kind"], "multiple_choice_multiple")
        self.assertEqual(second["questions"][0]["max_selections"], 2)
        self.assertEqual(forbidden_paths(safe), [])

    def test_reading_group_select_is_annotated_before_answer_removal(self):
        payload = {
            "passages": [{"groups": [{
                "collect_option": {"list": [{"key": "A", "text": "Paragraph A"}]},
                "questions": [{
                    "id": 9,
                    "answer": "A",
                    "options": [
                        {"key": "TRUE", "text": "TRUE"},
                        {"key": "FALSE", "text": "FALSE"},
                        {"key": "NOT GIVEN", "text": "NOT GIVEN"},
                    ],
                }],
            }]}]
        }
        safe = build_simulation_payload(payload, "reading")
        question = safe["passages"][0]["groups"][0]["questions"][0]
        self.assertTrue(question["uses_group_options"])
        self.assertEqual(question["response_kind"], "group_select")
        self.assertNotIn("answer", question)


if __name__ == "__main__":
    unittest.main()
