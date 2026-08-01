import unittest
from datetime import datetime
from types import SimpleNamespace

from api.mock_exam_admin import _repair_legacy_not_given_grade
from services import mock_exam_review as review


def _listening_payload():
    return {
        "sections": [
            {
                "title": "Self-drive tours",
                "source_title": "Part 1",
                "transcript": [
                    {
                        "start": 10.0,
                        "end": 13.0,
                        "en": "We grow lettuces here.",
                        "cn": "我们在这里种生菜。",
                    },
                    {
                        "start": 14.0,
                        "end": 17.0,
                        "en": "Herbs grow beside them.",
                        "cn": "香草种在旁边。",
                    },
                ],
                "groups": [
                    {
                        "title": "SELF-DRIVE TOURS IN THE USA",
                        "desc": "Questions 1-2\nComplete the notes below.\nWrite ONE WORD.",
                        "collect": "Plants: $1$ and $2$",
                        "questions": [
                            {"id": 1, "number": 1, "start": 10, "end": 13},
                            {
                                "id": 2,
                                "number": 2,
                                "start": 14,
                                "end": 17,
                                "analysis": "Herbs is the plural clue.",
                            },
                        ],
                    }
                ],
            },
            {
                "groups": [
                    {
                        "title": "",
                        "desc": "Questions 3-4",
                        "questions": [{"id": 3, "number": 3}, {"id": 4, "number": 4}],
                    }
                ]
            },
        ]
    }


def _reading_payload():
    return {
        "passages": [
            {
                "title": "Urban farming in Paris",
                "question_name": "Q1-13",
                "content": {
                    "title": "Urban farming",
                    "paragraphs": [{"label": "A", "text": "Rooftop farms are expanding."}],
                },
                "groups": [
                    {
                        "title": "Urban farming",
                        "desc": "Questions 1-2  Complete the sentences below.",
                        "questions": [
                            {
                                "id": 1,
                                "number": 1,
                                "title": "Rooftop farms are becoming more common.",
                                "options": [{"key": "TRUE", "text": "TRUE"}],
                                "central_sentences": {
                                    "sentences": ["Rooftop farms are expanding."]
                                },
                            },
                            {"id": 2, "number": 2},
                        ],
                    }
                ],
            }
        ]
    }


def _result(qid, number, answer, value, awarded=1, marks=1, status="correct"):
    return {
        "ids": [str(qid)],
        "numbers": [number],
        "q": str(number),
        "answer": answer,
        "value": value,
        "marks": marks,
        "awarded": awarded,
        "correct": awarded >= marks,
        "status": status,
        "status_label": "正确" if awarded >= marks else "错误",
    }


class QuestionIndexTest(unittest.TestCase):
    def test_listening_sections_are_labelled(self):
        index = review.build_question_index(_listening_payload(), "listening")
        self.assertEqual(index["1"]["unit_label"], "Section 1 · Self-drive tours")
        self.assertEqual(index["1"]["group_title"], "SELF-DRIVE TOURS IN THE USA")
        self.assertIn("Complete the notes below.", index["1"]["instruction"])
        # 无标题的 section 退回序号标签
        self.assertEqual(index["3"]["unit_label"], "Section 2")

    def test_reading_passages_are_labelled(self):
        index = review.build_question_index(_reading_payload(), "reading")
        self.assertEqual(index["2"]["unit_label"], "Passage 1 · Urban farming in Paris · Q1-13")

    def test_redundant_title_is_not_repeated(self):
        payload = {
            "sections": [
                {
                    "title": "Section 1",
                    "question_name": "Q1-10",
                    "groups": [{"questions": [{"id": 1, "number": 1}]}],
                }
            ]
        }
        index = review.build_question_index(payload, "listening")
        self.assertEqual(index["1"]["unit_label"], "Section 1 · Q1-10")

    def test_flat_group_payload_and_missing_payload(self):
        flat = {"groups": [{"questions": [{"id": 9, "number": 9}]}]}
        self.assertEqual(
            review.build_question_index(flat, "listening")["9"]["unit_label"], "Section 1"
        )
        self.assertEqual(review.build_question_index(None, "reading"), {})

    def test_long_instruction_is_preserved(self):
        payload = {
            "sections": [{"groups": [{"desc": "x" * 400, "questions": [{"id": 1, "number": 1}]}]}]
        }
        instruction = review.build_question_index(payload, "listening")["1"]["instruction"]
        self.assertEqual(instruction, "x" * 400)

    def test_question_context_and_source_are_indexed(self):
        listening = review.build_question_index(_listening_payload(), "listening")
        self.assertEqual(listening["1"]["group_prompt"], "Plants: 【Q1】 and 【Q2】")
        self.assertEqual(listening["1"]["evidence"][0]["text"], "We grow lettuces here.")
        self.assertEqual(listening["1"]["source"]["transcript"][0]["time"], "00:10")

        reading = review.build_question_index(_reading_payload(), "reading")
        self.assertEqual(reading["1"]["question_stem"], "Rooftop farms are becoming more common.")
        self.assertEqual(reading["1"]["evidence"][0]["text"], "Rooftop farms are expanding.")
        self.assertEqual(reading["1"]["source"]["paragraphs"][0]["label"], "A")


class WritingReviewTest(unittest.TestCase):
    def test_writing_image_is_mapped_to_static_asset(self):
        tasks = review.build_writing_review_tasks(
            {
                "tasks": [
                    {"task": 1, "image": "images/task1.png"},
                    {"task": 2, "image": None},
                ]
            }
        )
        self.assertEqual(tasks[0]["image_src"], "/static/writing_tests/images/task1.png")
        self.assertEqual(tasks[1]["image_src"], "")

    def test_existing_static_prefix_is_not_duplicated(self):
        tasks = review.build_writing_review_tasks(
            {"tasks": [{"image": "/static/writing_tests/images/task1.png"}]}
        )
        self.assertEqual(tasks[0]["image_src"], "/static/writing_tests/images/task1.png")

    def test_parent_path_is_not_exposed(self):
        tasks = review.build_writing_review_tasks({"tasks": [{"image": "../secret.png"}]})
        self.assertEqual(tasks[0]["image_src"], "")


class ReviewUnitsTest(unittest.TestCase):
    def test_rows_are_grouped_by_section_with_scores(self):
        index = review.build_question_index(_listening_payload(), "listening")
        results = [
            _result(1, 1, "lettuces", "lettuces"),
            _result(2, 2, "herbs", "herb", awarded=0, status="wrong"),
            _result(3, 3, "A", "A"),
            _result(4, 4, "B", ""),
        ]
        units = review.build_review_units(results, index)

        self.assertEqual([u["label"] for u in units], ["Section 1 · Self-drive tours", "Section 2"])
        self.assertEqual(units[0]["correct"], 1)
        self.assertEqual(units[0]["total"], 2)
        self.assertEqual(units[0]["wrong"], 1)

        rows = units[0]["groups"][0]["rows"]
        self.assertEqual(rows[0]["label"], "Q1")
        self.assertTrue(rows[0]["is_correct"])
        self.assertFalse(rows[1]["is_correct"])
        self.assertEqual(rows[1]["student_answer"], "herb")
        self.assertEqual(units[0]["groups"][0]["prompt"], "Plants: 【Q1】 and 【Q2】")
        self.assertEqual(rows[1]["evidence"][0]["text"], "Herbs grow beside them.")
        self.assertEqual(rows[1]["question_analysis"], "Herbs is the plural clue.")
        self.assertTrue(rows[1]["has_context"])

        blank_row = units[1]["groups"][0]["rows"][1]
        self.assertFalse(blank_row["answered"])
        self.assertEqual(blank_row["student_answer"], review.UNANSWERED_TEXT)

    def test_partial_credit_row(self):
        results = [_result(1, 1, "A,B,C", "A,B", awarded=2, marks=3, status="partial")]
        rows = review.build_review_units(results, {})[0]["groups"][0]["rows"]
        self.assertTrue(rows[0]["is_partial"])
        self.assertFalse(rows[0]["is_correct"])

    def test_multi_number_unit_keeps_combined_label(self):
        result = _result(31, 31, "A,B", "A,B", awarded=2, marks=2)
        result["numbers"] = [31, 32]
        result["q"] = "31,32"
        rows = review.build_review_units([result], {})[0]["groups"][0]["rows"]
        self.assertEqual(rows[0]["label"], "Q31,32")

    def test_unknown_questions_fall_back_to_one_bucket(self):
        units = review.build_review_units([_result(99, 99, "A", "A")], {})
        self.assertEqual(units[0]["label"], "未归类")

    def test_dirty_results_do_not_break(self):
        self.assertEqual(review.build_review_units(["oops", None], {}), [])
        self.assertEqual(review.parse_json_list("{not json"), [])
        self.assertEqual(review.parse_json_list('{"a": 1}'), [])
        self.assertEqual(review.parse_json_list(None), [])
        self.assertEqual(review.parse_json_dict("[]"), {})
        self.assertEqual(review.parse_json_dict("{not json"), {})

    def test_only_legacy_split_not_given_misgrade_is_detected(self):
        self.assertTrue(
            review.has_legacy_not_given_misgrade(
                [{"answer": "NG", "value": "NOT", "marks": 1, "awarded": 0}]
            )
        )
        self.assertFalse(
            review.has_legacy_not_given_misgrade(
                [{"answer": "NG", "value": "NOT", "marks": 1, "awarded": 1}]
            )
        )
        self.assertFalse(
            review.has_legacy_not_given_misgrade(
                [{"answer": "N", "value": "YES", "marks": 1, "awarded": 0}]
            )
        )


class SummaryTest(unittest.TestCase):
    def test_local_time_and_duration_text(self):
        # 库里是 naive UTC，展示要 +8 小时
        self.assertEqual(review.local_time_text(datetime(2026, 7, 27, 2, 11)), "2026-07-27 10:11")
        self.assertEqual(review.local_time_text(None), "")
        self.assertEqual(review.duration_text(1930), "32 分 10 秒")
        self.assertEqual(review.duration_text(None), "0 分 0 秒")
        self.assertEqual(review.duration_text(-5), "0 分 0 秒")

    def test_overall_band_rounds_quarters_up(self):
        # 雅思口径：平均分尾数 .25 进到半分、.75 进到整分（round() 的取偶会把 6.25 压成 6.0）
        self.assertEqual(review.overall_band(6.0, 6.5), 6.5)  # 6.25
        self.assertEqual(review.overall_band(6.5, 7.0), 7.0)  # 6.75
        self.assertEqual(review.overall_band(5.0, 5.5), 5.5)  # 5.25
        self.assertEqual(review.overall_band(5.5, 6.0), 6.0)  # 5.75
        # 整分与半分本身不变
        self.assertEqual(review.overall_band(6.0, 7.0), 6.5)
        self.assertEqual(review.overall_band(6.5, 6.5), 6.5)
        self.assertEqual(review.overall_band(6.0, 6.0), 6.0)
        self.assertIsNone(review.overall_band(6.0, None))
        self.assertIsNone(review.overall_band(None, None))

    def test_summarize_session(self):
        sess = SimpleNamespace(
            id=5,
            exam_id=3,
            student_name="顾闻哲",
            status="submitted",
            current_section="finished",
            started_at=datetime(2026, 7, 27, 1, 0),
            finished_at=datetime(2026, 7, 27, 2, 30),
            listening_correct=28,
            listening_total=40,
            listening_accuracy=70.0,
            listening_ielts_score=6.5,
            listening_duration_seconds=1800,
            listening_submitted_at=datetime(2026, 7, 27, 1, 30),
            listening_auto_submitted=True,
            reading_correct=30,
            reading_total=40,
            reading_accuracy=75.0,
            reading_ielts_score=7.0,
            reading_duration_seconds=3600,
            reading_submitted_at=datetime(2026, 7, 27, 2, 30),
            reading_auto_submitted=False,
            writing_submitted_at=None,
            writing_task1_words=None,
            writing_task2_words=None,
            writing_duration_seconds=None,
            writing_auto_submitted=False,
        )
        summary = review.summarize_session(sess)
        self.assertEqual(summary["status_text"], "已交卷")
        self.assertEqual(summary["started_at_text"], "2026-07-27 09:00")
        self.assertEqual(summary["overall_band"], 7.0)
        self.assertTrue(summary["listening"]["auto_submitted"])
        self.assertEqual(summary["reading"]["duration_text"], "60 分 0 秒")
        self.assertFalse(summary["writing"]["submitted"])
        self.assertEqual(summary["writing"]["task1_words"], 0)


class LegacyReadingRepairTest(unittest.TestCase):
    def test_split_not_given_misgrade_is_regraded_from_saved_answers(self):
        payload = {
            "passages": [
                {
                    "groups": [
                        {
                            "desc": "Write TRUE, FALSE or NOT GIVEN.",
                            "questions": [{"id": 10, "number": 10, "answer": "NG"}],
                        }
                    ]
                }
            ]
        }
        sess = SimpleNamespace(
            reading_answers_json='{"10": "NOT"}',
            reading_results_json=(
                '[{"ids":["10"],"numbers":[10],"q":"10","answer":"NG",'
                '"value":"NOT","marks":1,"awarded":0}]'
            ),
            reading_correct=0,
            reading_total=1,
            reading_accuracy=0.0,
            reading_ielts_score=None,
            reading_wrong_numbers_json="[10]",
        )

        self.assertTrue(_repair_legacy_not_given_grade(sess, payload))
        self.assertEqual(sess.reading_correct, 1)
        self.assertEqual(sess.reading_accuracy, 100.0)
        self.assertEqual(sess.reading_wrong_numbers_json, "[]")
        self.assertFalse(_repair_legacy_not_given_grade(sess, payload))


if __name__ == "__main__":
    unittest.main()
