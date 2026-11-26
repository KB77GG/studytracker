"""Presentation contracts that protect hidden answers across all six modes."""

import json
import subprocess
import unittest
from pathlib import Path
from types import SimpleNamespace

from services.practice_vocabulary_web import (
    answer_feedback,
    meaning_choice_options,
    sanitize_flow,
    sanitize_question,
    sanitize_review,
    sanitized_error_details,
    task_metadata,
)


class VocabularyWebPresentationTest(unittest.TestCase):
    def test_task_metadata_uses_shared_trimmed_title_and_range_contract(self):
        task = SimpleNamespace(
            id=7,
            dictation_book_id=12,
            detail="  ",
            vocabulary_goal=" Reading ",
            dictation_word_start=None,
            dictation_word_end=8,
        )
        metadata = task_metadata(task, book_titles={12: "合成词书"})
        self.assertEqual(metadata["title"], "合成词书 · 第1–8词")
        self.assertEqual(metadata["scope"], "第1–8词")
        self.assertEqual(metadata["goal_label"], "阅读词汇")
        self.assertEqual((metadata["word_start"], metadata["word_end"]), (None, 8))
        task.detail = "  指定标题  "
        self.assertEqual(task_metadata(task, book_titles={})["title"], "指定标题")
        self.assertEqual(task_metadata(task, book_titles={})["book_title"], "词汇学习")

    def test_retry_and_error_snapshot_do_not_reveal_answers(self):
        payload = {
            "phase": "retry",
            "familiarity": [
                {
                    "word_id": 1,
                    "viewed": True,
                    "word": "secret",
                    "meaning": "秘密",
                    "example_en": "secret example",
                }
            ],
            "current_question": {
                "mode": "zh_to_en",
                "question": {
                    "mode": "zh_to_en",
                    "prompt": {"meaning": "秘密", "word": "secret", "audio_tts_url": "secret.mp3"},
                    "answer": "secret",
                },
                "first_answer": "secret",
                "revealed_answer": "secret",
                "retry_answer": "secret",
            },
            "forgot_items": [{"revealed_answer": "secret"}],
            "last_saved_response": {"answer_feedback": {"word": "secret"}},
            "group_results": [{"index": 1}, {"index": 2}],
        }
        clean = sanitize_flow(payload)
        self.assertNotIn("secret", json.dumps(clean))
        self.assertEqual(clean["group_results"], [{"index": 2}])
        self.assertIn("word", payload["familiarity"][0])
        self.assertEqual(sanitized_error_details({"state": payload})["state"], clean)

    def test_corrective_copy_keeps_previously_revealed_answer(self):
        clean = sanitize_flow(
            {
                "phase": "active_recall",
                "correction_required": True,
                "current_question": {
                    "mode": "zh_to_en",
                    "revealed_answer": "depend",
                    "correction_count": 1,
                    "question": {"prompt": {"meaning": "依赖"}},
                },
            }
        )
        self.assertEqual(clean["current_question"]["revealed_answer"], "depend")
        self.assertEqual(clean["current_question"]["correction_count"], 1)

    def test_six_modes_only_expose_allowed_prompts(self):
        for mode in (
            "en_to_zh",
            "zh_to_en",
            "audio_to_en",
            "audio_to_zh",
            "context_choice",
            "context_fill",
        ):
            with self.subTest(mode=mode):
                clean = sanitize_question(
                    {
                        "mode": mode,
                        "question": {
                            "mode": mode,
                            "answer": "hidden",
                            "prompt": {
                                "answer": "hidden",
                                "word": "depend",
                                "meaning": "依赖",
                                "phonetic": "phonetic",
                                "audio_tts_url": "/tts",
                                "sentence": "We ____ on it.",
                                "instruction": "回答",
                                "target_word": "depend",
                                "input_hint": "输入",
                            },
                            "options": [{"id": "a", "label": "choice", "correct": True}],
                        },
                    }
                )
                self.assertNotIn("hidden", json.dumps(clean))
                prompt = clean["question"]["prompt"]
                if mode == "audio_to_en":
                    self.assertNotIn("phonetic", prompt)
                    self.assertNotIn("word", prompt)
                if mode in {"zh_to_en", "context_choice", "context_fill"}:
                    self.assertNotIn("audio_tts_url", prompt)
                for option in clean["question"].get("options", []):
                    self.assertNotIn("correct", option)

    def test_meaning_options_match_actual_miniprogram_algorithm(self):
        vectors = [
            {
                "question": {"word_id": 1, "question_id": "种子😀", "question": {}},
                "familiarity": [
                    {"word_id": i, "meaning": label}
                    for i, label in enumerate(
                        ["", "目标", "选项二", "选项三", "选项四", "选项五"], 0
                    )
                ],
            },
            {
                "question": {
                    "question_id": "q1",
                    "question": {
                        "options": [
                            {"id": "a", "label": "重复"},
                            {"id": "b", "label": "重复"},
                            {"id": "c", "label": "另一个"},
                        ]
                    },
                },
                "familiarity": [],
            },
            {"question": {"word_id": 10, "question": {}}, "familiarity": []},
        ]
        script = "const m=require('./miniprogram/utils/vocabulary-interaction.js'); let s='';process.stdin.on('data',d=>s+=d);process.stdin.on('end',()=>console.log(JSON.stringify(JSON.parse(s).map(x=>m.buildMeaningChoiceOptions(x.question,x.familiarity)))));"
        output = subprocess.check_output(
            ["node", "-e", script],
            input=json.dumps(vectors).encode(),
            cwd=Path(__file__).resolve().parents[1],
        )
        self.assertEqual(
            [meaning_choice_options(row["question"], row["familiarity"]) for row in vectors],
            json.loads(output),
        )

    def test_fallback_built_before_familiarity_is_hidden(self):
        clean = sanitize_flow(
            {
                "phase": "active_recall",
                "familiarity": [
                    {"word_id": 1, "word": "answer", "meaning": "正确释义"},
                    {"word_id": 2, "meaning": "干扰"},
                ],
                "current_question": {
                    "mode": "audio_to_zh",
                    "word_id": 1,
                    "question_id": "q1",
                    "question": {"prompt": {}},
                },
            }
        )
        self.assertEqual(
            {row["label"] for row in clean["current_question"]["question"]["options"]},
            {"正确释义", "干扰"},
        )
        self.assertNotIn("meaning", clean["familiarity"][0])

    def test_review_only_answered_items_reveal_feedback(self):
        item = {
            "mode": "audio_to_en",
            "question": {"prompt": {"phonetic": "leak", "audio_tts_url": "/tts"}},
            "first_answer": "answer",
            "revealed_answer": "answer",
            "answer_feedback": {"word": "answer"},
        }
        result = sanitize_review({"items": [dict(item, answered=False), dict(item, answered=True)]})
        self.assertNotIn("revealed_answer", result["items"][0])
        self.assertEqual(result["items"][1]["revealed_answer"], "answer")
        self.assertNotIn("phonetic", result["items"][1]["question"]["prompt"])
        self.assertEqual(result["words"], result["items"])

    def test_feedback_missing_material_and_numeric_audio(self):
        word = SimpleNamespace(
            id=1,
            word="12.50",
            accepted_answers=None,
            phonetic=None,
            core_meaning_zh=None,
            translation="",
            usage_pattern=None,
            example_en=None,
            example_zh=None,
            usage_note=None,
        )
        question = SimpleNamespace(
            question_snapshot_json=json.dumps(
                {"prompt": {"audio_tts_url": "/dictation/words/1/tts?numeric=1"}}
            )
        )
        self.assertEqual(
            answer_feedback(word, question)["audio_tts_url"], "/dictation/words/1/tts?numeric=1"
        )
        self.assertEqual(answer_feedback(None), {})


if __name__ == "__main__":
    unittest.main()
