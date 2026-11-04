import unittest

from tools.ielts_writing_ai import copytext, essay, review

from .test_review import ESSAY, evaluation, submission

GEN = {"model": "m-test", "prompt_version": "pv-test"}


class CopyTextTest(unittest.TestCase):
    def test_evaluation_copy_keeps_disclaimer_scores_and_unverified_marks(self):
        raw = evaluation()
        raw["criteria"]["lexical"]["issues"].append({"quote": "invented words", "comment": "x"})
        result = review.normalize_evaluation(raw, submission())
        text = copytext.evaluation_text(result, GEN)
        self.assertIn(copytext.DISCLAIMER, text)
        self.assertIn("预估总分：Band 6.5", text)
        self.assertIn("限制提示：", text)
        self.assertIn("“invented words”（未在原文中找到，不作为评分依据）", text)
        self.assertIn("模型 m-test · 提示词 pv-test", text)
        self.assertIn("理由：", text)

    def test_evaluation_copy_for_task1_without_chart_says_not_assessable(self):
        result = review.normalize_evaluation(
            evaluation(task=9), submission(task_type="task1", image_status="none")
        )
        text = copytext.evaluation_text(result, GEN)
        self.assertIn("总分：不可评", text)
        self.assertIn("Task Achievement（TA）：不可评", text)
        self.assertIn("未上传题图", text)
        self.assertNotIn("Band 9.0", text)
        self.assertNotIn("预估总分", text)

    def test_refine_copies_carry_footer_and_missing_sentence_notice(self):
        sentences = essay.split_sentences(ESSAY)
        result = review.normalize_refinement(
            {"sentences": [{"i": 1, "revised": "I don't agree with it.", "explanation": "撇号"}]},
            sentences,
        )
        copies = copytext.refine_texts(result, GEN, 7.0)
        self.assertTrue(copies["full"].startswith(result["refined_essay"]))
        self.assertIn("AI 逐句精修稿（目标 Band 7.0）", copies["full"])
        self.assertIn(copytext.DISCLAIMER, copies["full"])
        self.assertIn("2 句 AI 没有返回结果", copies["full"])
        self.assertIn("原句：i dont agree with it.", copies["changes"])
        self.assertIn(copytext.DISCLAIMER, copies["changes"])

    def test_rewrite_copies_carry_warnings(self):
        body = " ".join(["word"] * 160)
        result = review.normalize_rewrite(
            {"essay": body, "key_changes": ["k"], "band_rationale": "r"},
            submission(task_type="task1", image_status="failed"),
        )
        copies = copytext.rewrite_texts(result, GEN)
        for text in copies.values():
            self.assertIn(copytext.DISCLAIMER, text)
            self.assertIn("没有与题图核对", text)
        self.assertTrue(copies["essay"].startswith(body))
        result["key_changes"] = [{"before": "a b", "after": "c d", "why": "w"}]
        self.assertIn("1. “a b” → “c d”（w）", copytext.rewrite_texts(result, GEN)["with_notes"])

    def test_legacy_string_strengths_are_still_copyable(self):
        legacy = {
            "overall_band": 6.0,
            "criteria": [
                {
                    "label": "Task Response",
                    "short": "TR",
                    "band": 6.0,
                    "summary": "s",
                    "strengths": ["旧格式优点"],
                    "issues": [],
                }
            ],
        }
        self.assertIn("旧格式优点（未附原文引文）", copytext.evaluation_text(legacy, {}))


if __name__ == "__main__":
    unittest.main()
