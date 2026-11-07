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
        "central_sentences",
        "locating_words",
        "audio_review",
        "practice_audio",
        "audio_timeline",
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
    def test_real_reading_answer_evidence_is_not_sent_during_simulation(self):
        source = json.loads((ROOT / "static/reading_tests/ielts18_test1_reading.json").read_text())
        original = json.dumps(source, sort_keys=True)
        question = source["passages"][0]["groups"][0]["questions"][0]
        self.assertIn("lettuces", json.dumps(question["central_sentences"]).lower())
        safe = build_simulation_payload(source, "reading")
        self.assertEqual(forbidden_paths(safe), [])
        self.assertEqual(safe["passages"][0]["content"], source["passages"][0]["content"])
        self.assertEqual(json.dumps(source, sort_keys=True), original)

    def test_all_144_cambridge_simulation_payloads_remove_solution_metadata(self):
        tests = questions = 0
        for subject in ("listening", "reading"):
            for path in sorted((ROOT / "static" / f"{subject}_tests").glob("ielts*.json")):
                with self.subTest(test=path.stem):
                    source = json.loads(path.read_text())
                    safe = build_simulation_payload(source, subject)
                    self.assertEqual(forbidden_paths(safe), [])
                    unit_key = "sections" if subject == "listening" else "passages"
                    questions += sum(
                        len(group["questions"])
                        for unit in safe[unit_key]
                        for group in unit["groups"]
                    )
                    tests += 1
        self.assertEqual(tests, 144)
        self.assertEqual(questions, 5760)

    def test_derived_audio_evidence_is_also_removed_without_mutating_review_payload(self):
        payload = {
            "sections": [
                {
                    "audio_timeline": {"basis": "sidecar_current"},
                    "groups": [
                        {
                            "practice_audio": {"start": 7},
                            "questions": [
                                {
                                    "id": 1,
                                    "number": 1,
                                    "audio_review": {"evidence": [{"text": "answer sentence"}]},
                                }
                            ],
                        }
                    ],
                }
            ]
        }
        safe = build_simulation_payload(payload, "listening")
        self.assertEqual(forbidden_paths(safe), [])
        self.assertIn("audio_review", payload["sections"][0]["groups"][0]["questions"][0])

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
            "sections": [
                {
                    "groups": [
                        {
                            "type": 2,
                            "collect_option": {"list": [{"title": "A", "content": "One"}]},
                            "questions": [
                                {"id": 1, "answer": "A,B"},
                                {"id": 2, "answer": "A,B"},
                            ],
                        },
                        {
                            "type": 9,
                            "questions": [
                                {
                                    "id": 3,
                                    "answer": "B,D",
                                    "analysis": "secret",
                                    "options": [{"title": "A"}, {"title": "B"}, {"title": "D"}],
                                }
                            ],
                        },
                    ],
                    "transcript": [{"en": "secret"}],
                }
            ]
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
            "passages": [
                {
                    "groups": [
                        {
                            "collect_option": {"list": [{"key": "A", "text": "Paragraph A"}]},
                            "questions": [
                                {
                                    "id": 9,
                                    "answer": "A",
                                    "options": [
                                        {"key": "TRUE", "text": "TRUE"},
                                        {"key": "FALSE", "text": "FALSE"},
                                        {"key": "NOT GIVEN", "text": "NOT GIVEN"},
                                    ],
                                }
                            ],
                        }
                    ]
                }
            ]
        }
        safe = build_simulation_payload(payload, "reading")
        question = safe["passages"][0]["groups"][0]["questions"][0]
        self.assertTrue(question["uses_group_options"])
        self.assertEqual(question["response_kind"], "group_select")
        self.assertNotIn("answer", question)


if __name__ == "__main__":
    unittest.main()
