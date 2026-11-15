"""Conversion contracts using synthetic papers and the existing real graders."""

import copy
import json
import unittest

from services.exam_sprint import content_digest
from services.ielts_practice_scoring import (
    grade_listening_jijing_answers,
    grade_reading_test_answers,
)
from services.ninefen_content import NinefenContentError, convert_ninefen_unit

IMAGE = "https://static.9fnnn.com/practice/example.png"
AUDIO = "https://static.9fnnn.com/practice/example.mp3"
MEDIA = {IMAGE: "/practice/sprint/assets/image.png", AUDIO: "/practice/sprint/assets/audio.mp3"}


def options(*values):
    return [{"optionNum": chr(65 + i), "optionContent": value} for i, value in enumerate(values)]


def question(number, kind, group_id, **extra):
    return {
        "id": f"21027112315099914{number:02d}",
        "qNumber": str(number),
        "questionGroupId": group_id,
        "type": kind,
        "options": [],
        "question": f"Synthetic prompt {number}",
        "rightAnswer": "WRONG_SOURCE_ANSWER",
        "analyses": [],
        **extra,
    }


def paper(subject="reading", *, multiple=False):
    part_id = "2102711231451271169"
    if multiple:
        kind = "multiple-choice"
        group = {
            "id": "101",
            "partId": part_id,
            "type": kind,
            "description": "Choose TWO letters.",
            "qRange": "Questions 1-2",
            "questions": [
                question(
                    1,
                    kind,
                    "101",
                    question="Two benefits?",
                    options=options("Alpha", "Beta", "Gamma"),
                ),
                question(2, kind, "101", question="Two benefits?"),
            ],
        }
        groups = [group]
        answers = {group["questions"][0]["id"]: "A", group["questions"][1]["id"]: "C"}
    else:
        groups = [
            {
                "id": "101",
                "partId": part_id,
                "type": "fill-in-the-blank",
                "description": "Write <strong>ONE WORD ONLY</strong>.",
                "qRange": "Questions 1-2",
                "imageUrl": IMAGE,
                "contentHtml": '<table style="color:red"><tr><th colspan="2">Parts</th></tr><tr><td>Machine <input placeholder="1"></td><td>Handle <input placeholder="2"></td></tr></table>',
                "questions": [
                    question(1, "fill-in-the-blank", "101", question=None),
                    question(2, "fill-in-the-blank", "101", question=None),
                ],
            },
            {
                "id": "102",
                "partId": part_id,
                "type": "single-choice",
                "description": "Choose TRUE if correct, FALSE if incorrect, or NOT GIVEN if unknown.",
                "qRange": "Questions 3-4",
                "questions": [
                    question(
                        3, "single-choice", "102", options=options("TRUE", "FALSE", "NOT GIVEN")
                    ),
                    question(
                        4, "single-choice", "102", options=options("TRUE", "FALSE", "NOT GIVEN")
                    ),
                ],
            },
        ]
        answers = {
            q["id"]: answer
            for q, answer in zip(
                [q for g in groups for q in g["questions"]],
                ["drum", "crank", "A", "C"],
                strict=True,
            )
        }
    segments = [
        {"sentences": [{"text": "A Synthetic paragraph one."}]},
        {"sentences": [{"text": "B Synthetic paragraph two."}]},
    ]
    if subject == "listening":
        segments = [{"text": "Synthetic audio transcript.", "start_time": 1.2, "end_time": 4.5}]
    part = {
        "id": part_id,
        "channel": subject,
        "entryMode": "exam",
        "partNum": "Part 2",
        "total": sum(len(g["questions"]) for g in groups),
        "groups": groups,
        "articleJson": json.dumps({"title": "Synthetic passage", "segments": segments}),
        "audioUrl": AUDIO if subject == "listening" else None,
    }
    return {
        "code": 200,
        "data": {
            "id": "2102715008296194050",
            "title": "Synthetic unit V2",
            "channel": subject,
            "parts": [part],
        },
    }, answers


def convert(payload, answers, **kwargs):
    return convert_ninefen_unit(
        payload,
        answers_by_question_id=answers,
        media_map=kwargs.get("media_map", MEDIA),
        expected_source_sha256=kwargs.get("digest", content_digest(payload)),
    )


class NinefenContentTest(unittest.TestCase):
    def test_reading_diagram_table_judgment_and_version_metadata(self):
        raw, answers = paper()
        before = copy.deepcopy(raw)
        result = convert(raw, answers)
        document = result["documents"][0]
        payload = document["payload"]
        passage = payload["passages"][0]
        self.assertEqual(payload["source"], "ninefen")
        self.assertIn(content_digest(raw)[:12], payload["id"])
        self.assertEqual(passage["source_part_number"], 2)
        self.assertEqual(passage["passage"], 1)
        self.assertEqual(document["part_number"], 1)
        self.assertEqual(
            passage["content"]["paragraphs"][0], {"label": "A", "text": "Synthetic paragraph one."}
        )
        group = passage["groups"][0]
        self.assertEqual(group["img_url"], MEDIA[IMAGE])
        self.assertIn('colspan="2"', group["collect"])
        self.assertNotIn("style=", group["collect"])
        self.assertNotIn("<input", group["collect"])
        self.assertIn(f'${group["questions"][0]["id"]}$', group["collect"])
        judgments = passage["groups"][1]["questions"]
        self.assertEqual([q["answer"] for q in judgments], ["TRUE", "NOT GIVEN"])
        self.assertEqual(judgments[0]["options"][0]["key"], "TRUE")
        submitted = {q["id"]: q["answer"] for g in passage["groups"] for q in g["questions"]}
        grade = grade_reading_test_answers(payload, submitted, passage_number=1)
        self.assertEqual((grade["correct"], grade["total"]), (4, 4))
        self.assertEqual(raw, before)

    def test_answers_are_required_despite_source_answer_and_analysis(self):
        raw, answers = paper()
        qid = next(iter(answers))
        del answers[qid]
        with self.assertRaisesRegex(NinefenContentError, "Missing independently supplied"):
            convert(raw, answers)

    def test_version_drift_is_rejected_and_changes_local_id(self):
        raw, answers = paper()
        old = content_digest(raw)
        first_id = convert(raw, answers)["documents"][0]["id"]
        raw["data"]["title"] = "Changed V3"
        with self.assertRaisesRegex(NinefenContentError, "source version"):
            convert(raw, answers, digest=old)
        self.assertNotEqual(convert(raw, answers)["documents"][0]["id"], first_id)

    def test_listening_combined_multi_has_partial_credit_and_overselect_guard(self):
        raw, answers = paper("listening", multiple=True)
        payload = convert(raw, answers)["documents"][0]["payload"]
        group = payload["groups"][0]
        self.assertEqual(group["type"], 2)
        self.assertEqual([q["answer"] for q in group["items"]], ["A,C", "A,C"])
        self.assertEqual(payload["audio"]["local_path"], MEDIA[AUDIO])
        self.assertEqual(payload["content"][0]["start_time"], 1200)
        for value, score in (("A,C", 2), ("C", 1), ("A,B,C", 0)):
            grade = grade_listening_jijing_answers(payload, {group["desc"]: value})
            self.assertEqual((grade["correct"], grade["total"]), (score, 2))

    def test_reading_combined_multi_uses_individual_selects_without_double_credit(self):
        raw, answers = paper(multiple=True)
        payload = convert(raw, answers)["documents"][0]["payload"]
        group = payload["passages"][0]["groups"][0]
        qids = [q["id"] for q in group["questions"]]
        self.assertTrue(all(q["uses_group_options"] for q in group["questions"]))
        self.assertTrue(all(not q["options"] for q in group["questions"]))
        self.assertEqual(
            grade_reading_test_answers(payload, dict(zip(qids, ["C", "A"], strict=True)))[
                "correct"
            ],
            2,
        )
        self.assertEqual(
            grade_reading_test_answers(payload, dict(zip(qids, ["A", "A"], strict=True)))[
                "correct"
            ],
            1,
        )

    def test_invalid_option_and_incomplete_multi_answers_fail(self):
        raw, answers = paper(multiple=True)
        qid = next(iter(answers))
        answers[qid] = "Z"
        with self.assertRaises(NinefenContentError):
            convert(raw, answers)
        answers[qid] = "C"
        with self.assertRaisesRegex(NinefenContentError, "Selection count"):
            convert(raw, answers)

    def test_missing_or_unsafe_media_fails_closed(self):
        raw, answers = paper()
        for mapping in (
            {},
            {IMAGE: "https://example.org/x.png"},
            {IMAGE: "/practice/sprint/assets/../secret"},
            {IMAGE: "/practice/sprint/assets/%2e%2e/secret"},
        ):
            with self.subTest(mapping=mapping), self.assertRaises(NinefenContentError):
                convert(raw, answers, media_map=mapping)

    def test_active_html_and_unknown_numbered_input_are_rejected(self):
        for markup in (
            "<script>alert(1)</script>",
            '<img src="x" onerror="alert(1)">',
            '<input placeholder="99">',
        ):
            raw, answers = paper()
            raw["data"]["parts"][0]["groups"][0]["contentHtml"] = markup
            with self.subTest(markup=markup), self.assertRaises(NinefenContentError):
                convert(raw, answers)

    def test_duplicate_missing_and_foreign_question_references_are_rejected(self):
        mutations = [
            lambda part: part.update(total=99),
            lambda part: part["groups"][0].update(type="unknown"),
            lambda part: part["groups"][0].update(partId="999"),
            lambda part: part["groups"][0]["questions"][0].update(questionGroupId="999"),
            lambda part: part["groups"][0]["questions"][1].update(qNumber="1"),
            lambda part: part["groups"][0]["questions"][0].update(id=123),
        ]
        for mutation in mutations:
            raw, answers = paper()
            mutation(raw["data"]["parts"][0])
            with self.subTest(mutation=mutation), self.assertRaises(NinefenContentError):
                convert(raw, answers)

    def test_answer_map_cannot_contain_unknown_ids_or_empty_answers(self):
        for value in ("", None, [], [""]):
            raw, answers = paper()
            answers[next(iter(answers))] = value
            with self.subTest(value=value), self.assertRaises(NinefenContentError):
                convert(raw, answers)
        raw, answers = paper()
        answers["123"] = "extraneous"
        with self.assertRaisesRegex(NinefenContentError, "unknown question IDs"):
            convert(raw, answers)

    def test_explicit_fill_alternatives_reuse_existing_grader(self):
        raw, answers = paper()
        qid = next(iter(answers))
        answers[qid] = ["drum", "cylinder"]
        payload = convert(raw, answers)["documents"][0]["payload"]
        self.assertEqual(grade_reading_test_answers(payload, {qid: "cylinder"})["correct"], 1)


if __name__ == "__main__":
    unittest.main()
