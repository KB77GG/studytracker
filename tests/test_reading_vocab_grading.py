"""阅读词汇判分纯函数的单测（零 DB，只 import api.reading_vocab_grading）。

钉住从 submit_reading_vocab_practice() 抽出的判分行为，覆盖
choice / auto_text / writing / uncertain / redo_wrong / 边界 各分支。
"""

import unittest

from api.reading_vocab_grading import grade_reading_vocab_submission

OPTS_AB = [{"key": "A", "text": "apple"}, {"key": "B", "text": "banana"}]


def _qv(qid, input_mode, *, options=None, reference_answer="", hint="", word="w",
        task_id=1, task_title="T"):
    return {
        "question_id": qid,
        "input_mode": input_mode,
        "options": options or [],
        "reference_answer": reference_answer,
        "hint": hint,
        "word": word,
        "task_id": task_id,
        "task_title": task_title,
    }


def _grade(views, *, answer_map=None, text_answer_map=None, uncertain_ids=None,
           prior_by_qid=None, resubmit_qids=None):
    return grade_reading_vocab_submission(
        views,
        answer_map=answer_map or {},
        text_answer_map=text_answer_map or {},
        uncertain_ids=uncertain_ids or set(),
        prior_by_qid=prior_by_qid or {},
        resubmit_qids=resubmit_qids or set(),
    )


class ChoiceGradingTests(unittest.TestCase):
    def test_correct(self):
        # reference 'a' 小写，应被归一化为 correct_key 'A'
        r = _grade([_qv(1, "choice", options=OPTS_AB, reference_answer="a")],
                   answer_map={1: "A"}, resubmit_qids={1})
        self.assertEqual(r.correct_count, 1)
        self.assertEqual(r.objective_total, 1)
        self.assertEqual(r.answered_count, 1)
        self.assertEqual(r.total, 1)
        self.assertEqual(r.accuracy, 100.0)
        self.assertEqual(r.completion_rate, 100.0)
        self.assertEqual(r.wrong_items, [])
        self.assertEqual(r.note_suffix, "")
        self.assertEqual(len(r.records), 1)
        rec = r.records[0]
        self.assertEqual(rec["answer_type"], "choice")
        self.assertEqual(rec["text_answer"], "A")
        self.assertTrue(rec["is_correct"])
        self.assertTrue(rec["reviewed"])
        self.assertFalse(rec["is_uncertain"])
        # records 不含 task_id/student_id/submitted_at（由 handler 补）
        self.assertNotIn("task_id", rec)
        self.assertNotIn("submitted_at", rec)

    def test_wrong(self):
        r = _grade([_qv(1, "choice", options=OPTS_AB, reference_answer="A", word="词")],
                   answer_map={1: "B"}, resubmit_qids={1})
        self.assertEqual(r.correct_count, 0)
        self.assertEqual(r.accuracy, 0.0)
        self.assertEqual(len(r.wrong_items), 1)
        w = r.wrong_items[0]
        self.assertEqual(w["selected_key"], "B")
        self.assertEqual(w["selected_text"], "banana")
        self.assertEqual(w["correct_key"], "A")
        self.assertEqual(w["correct_text"], "apple")
        self.assertFalse(w["is_uncertain"])

    def test_unanswered_counts_as_wrong_and_incomplete(self):
        r = _grade([_qv(1, "choice", options=OPTS_AB, reference_answer="A")])
        self.assertEqual(r.answered_count, 0)
        self.assertEqual(r.completion_rate, 0.0)
        self.assertEqual(len(r.wrong_items), 1)
        self.assertEqual(r.wrong_items[0]["selected_key"], "未作答")
        self.assertEqual(r.records[0]["text_answer"], "")

    def test_illegal_key_treated_as_unanswered(self):
        r = _grade([_qv(1, "choice", options=OPTS_AB, reference_answer="A")],
                   answer_map={1: "C"}, resubmit_qids={1})
        self.assertEqual(r.answered_count, 0)
        self.assertFalse(r.records[0]["is_correct"])
        self.assertEqual(r.records[0]["text_answer"], "")

    def test_uncertain_correct_still_in_wrong_items(self):
        r = _grade([_qv(1, "choice", options=OPTS_AB, reference_answer="A")],
                   answer_map={1: "A"}, uncertain_ids={1}, resubmit_qids={1})
        self.assertEqual(r.correct_count, 1)
        self.assertEqual(len(r.wrong_items), 1)
        self.assertTrue(r.wrong_items[0]["is_uncertain"])
        self.assertTrue(r.records[0]["is_uncertain"])
        self.assertIn("已标记不清楚", r.note_suffix)


class AutoTextGradingTests(unittest.TestCase):
    def test_hit_alternatives_with_normalization(self):
        # 多备选 + 大小写 + 标点 + 首尾空白 都应归一化命中
        r = _grade([_qv(2, "auto_text", reference_answer="run/ran or running")],
                   text_answer_map={2: "  RAN. "}, resubmit_qids={2})
        self.assertEqual(r.correct_count, 1)
        self.assertEqual(r.objective_total, 1)
        self.assertEqual(r.accuracy, 100.0)
        self.assertEqual(r.wrong_items, [])
        rec = r.records[0]
        self.assertEqual(rec["answer_type"], "text")
        self.assertTrue(rec["reviewed"])
        self.assertTrue(rec["is_correct"])

    def test_miss(self):
        r = _grade([_qv(2, "auto_text", reference_answer="run/ran", word="动词")],
                   text_answer_map={2: "walk"}, resubmit_qids={2})
        self.assertEqual(r.correct_count, 0)
        self.assertEqual(len(r.wrong_items), 1)
        w = r.wrong_items[0]
        self.assertEqual(w["selected_key"], "walk")
        self.assertEqual(w["selected_text"], "walk")
        self.assertEqual(w["correct_key"], "run/ran")


class WritingGradingTests(unittest.TestCase):
    def test_writing_saved_not_graded(self):
        r = _grade([_qv(3, "writing")], text_answer_map={3: "my essay"}, resubmit_qids={3})
        self.assertEqual(r.writing_total, 1)
        self.assertEqual(r.writing_answered, 1)
        self.assertEqual(r.answered_count, 1)
        self.assertEqual(r.objective_total, 0)
        self.assertEqual(r.accuracy, 0.0)  # 无客观题
        self.assertEqual(r.completion_rate, 100.0)
        self.assertEqual(r.wrong_items, [])  # 写作题不入错题
        rec = r.records[0]
        self.assertEqual(rec["answer_type"], "text")
        self.assertFalse(rec["reviewed"])
        self.assertIsNone(rec["is_correct"])

    def test_writing_blank_not_answered(self):
        r = _grade([_qv(3, "writing")], resubmit_qids={3})
        self.assertEqual(r.writing_answered, 0)
        self.assertEqual(r.answered_count, 0)
        self.assertEqual(r.records[0]["text_answer"], "")


class RedoWrongReuseTests(unittest.TestCase):
    def test_reuse_prior_correct_not_repersisted(self):
        views = [
            _qv(1, "choice", options=OPTS_AB, reference_answer="A"),
            _qv(2, "choice", options=OPTS_AB, reference_answer="A"),
        ]
        r = _grade(
            views,
            answer_map={2: "B"},  # 只重做 q2，答错
            resubmit_qids={2},
            prior_by_qid={1: {"text_answer": "A", "is_correct": True, "is_uncertain": False}},
        )
        self.assertEqual(r.objective_total, 2)
        self.assertEqual(r.correct_count, 1)  # q1 复用旧正确
        self.assertEqual(r.answered_count, 2)
        self.assertEqual(r.accuracy, 50.0)
        self.assertEqual(len(r.records), 1)  # 只重新入库 q2
        self.assertEqual(r.records[0]["question_id"], 2)
        self.assertEqual(len(r.wrong_items), 1)
        self.assertEqual(r.wrong_items[0]["question_id"], 2)

    def test_reuse_prior_wrong_enters_wrong_items_no_record(self):
        r = _grade(
            [_qv(1, "choice", options=OPTS_AB, reference_answer="A")],
            prior_by_qid={1: {"text_answer": "B", "is_correct": False, "is_uncertain": False}},
        )
        self.assertEqual(r.correct_count, 0)
        self.assertEqual(r.records, [])  # 复用，不重新入库
        self.assertEqual(len(r.wrong_items), 1)
        w = r.wrong_items[0]
        self.assertEqual(w["selected_key"], "B")
        self.assertEqual(w["selected_text"], "banana")
        self.assertEqual(w["correct_key"], "A")


class AggregateAndEdgeTests(unittest.TestCase):
    def test_empty_question_set(self):
        r = _grade([])
        self.assertEqual(r.total, 0)
        self.assertEqual(r.accuracy, 0.0)
        self.assertEqual(r.completion_rate, 0.0)
        self.assertEqual(r.records, [])
        self.assertEqual(r.note_suffix, "")

    def test_note_suffix_format(self):
        r = _grade([_qv(1, "choice", options=OPTS_AB, reference_answer="A", word="apple")],
                   answer_map={1: "B"}, resubmit_qids={1})
        self.assertTrue(r.note_suffix.startswith("[阅读词汇待复习] "))
        self.assertIn("apple", r.note_suffix)
        self.assertIn("你选B:banana", r.note_suffix)
        self.assertIn("正确A:apple", r.note_suffix)

    def test_mixed_objective_and_writing_accuracy_denominator(self):
        # 1 客观答对 + 1 写作 → accuracy 只按客观(=100)，completion 按全部
        views = [
            _qv(1, "choice", options=OPTS_AB, reference_answer="A"),
            _qv(2, "writing"),
        ]
        r = _grade(views, answer_map={1: "A"}, text_answer_map={2: "essay"},
                   resubmit_qids={1, 2})
        self.assertEqual(r.objective_total, 1)
        self.assertEqual(r.writing_total, 1)
        self.assertEqual(r.accuracy, 100.0)
        self.assertEqual(r.completion_rate, 100.0)


if __name__ == "__main__":
    unittest.main()
