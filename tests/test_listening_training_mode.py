import unittest
from types import SimpleNamespace

from services.listening_training import (
    MODE_BASIC,
    MODE_CHALLENGE,
    MODE_REVIEW,
    MODE_STANDARD,
    challenge_allowed,
    effective_dictation_level,
    task_training_policy,
    validate_first_attempt_level,
)


def exercise_with(segment):
    return {"parts": [{"segments": [segment]}]}


class ListeningTrainingModePolicyTest(unittest.TestCase):
    def test_legacy_task_stays_unlocked(self):
        task = SimpleNamespace(listening_training_mode=None)
        policy = task_training_policy(task)
        self.assertFalse(policy["locked"])
        self.assertEqual(policy["label"], "学生自选")

    def test_system_recommends_standard_but_reduces_long_segments(self):
        short = {"start": 0, "end": 7, "text": "WOMAN: We booked a quiet room near the station."}
        long = {"start": 0, "end": 21, "text": short["text"]}
        self.assertEqual(effective_dictation_level("system", short), MODE_STANDARD)
        self.assertEqual(effective_dictation_level("system", long), MODE_BASIC)

    def test_challenge_is_blocked_by_duration_or_working_memory_load(self):
        duration_long = {"start": 0, "end": 15.1, "text": "A short sentence."}
        words_long = {
            "start": 0,
            "end": 10,
            "text": " ".join(f"word{index}" for index in range(21)),
        }
        self.assertFalse(challenge_allowed(duration_long))
        self.assertFalse(challenge_allowed(words_long))
        self.assertEqual(effective_dictation_level(MODE_CHALLENGE, duration_long), MODE_STANDARD)
        self.assertEqual(effective_dictation_level(MODE_CHALLENGE, words_long), MODE_STANDARD)

    def test_policy_annotates_each_segment_with_server_owned_level(self):
        task = SimpleNamespace(listening_training_mode="challenge")
        exercise = exercise_with({"start": 0, "end": 18, "text": "A useful but long sentence."})
        policy = task_training_policy(task, exercise)
        segment = exercise["parts"][0]["segments"][0]
        self.assertTrue(policy["locked"])
        self.assertFalse(segment["challenge_allowed"])
        self.assertEqual(segment["assigned_training_level"], MODE_STANDARD)

    def test_first_attempt_must_match_assigned_level(self):
        task = SimpleNamespace(listening_training_mode="standard")
        exercise = exercise_with(
            {"start": 0, "end": 5, "text": "WOMAN: Book the quiet room today."}
        )
        self.assertEqual(
            validate_first_attempt_level(
                task,
                exercise,
                0,
                submitted_level="standard",
                hidden_word_indices=[2, 4],
            ),
            MODE_STANDARD,
        )
        with self.assertRaisesRegex(ValueError, "training_level_mismatch"):
            validate_first_attempt_level(
                task,
                exercise,
                0,
                submitted_level="basic",
                hidden_word_indices=[2],
            )

    def test_review_task_rejects_dictation_submission(self):
        task = SimpleNamespace(listening_training_mode=MODE_REVIEW)
        with self.assertRaisesRegex(ValueError, "listening_review_task"):
            validate_first_attempt_level(
                task,
                exercise_with({"start": 0, "end": 5, "text": "Listen first."}),
                0,
                submitted_level="standard",
                hidden_word_indices=[0],
            )

    def test_pre_upgrade_client_keeps_working_during_rollout(self):
        segment = {
            "start": 0,
            "end": 5,
            "text": "WOMAN: Book the quiet room near the station today.",
        }
        exercise = exercise_with(segment)
        challenge_task = SimpleNamespace(listening_training_mode=MODE_CHALLENGE)
        self.assertEqual(
            validate_first_attempt_level(
                challenge_task,
                exercise,
                0,
                submitted_level=None,
                hidden_word_indices=[2, 4, 6],
            ),
            MODE_STANDARD,
        )
        review_task = SimpleNamespace(listening_training_mode=MODE_REVIEW)
        self.assertEqual(
            validate_first_attempt_level(
                review_task,
                exercise,
                0,
                submitted_level=None,
                hidden_word_indices=[2, 4],
            ),
            MODE_STANDARD,
        )


if __name__ == "__main__":
    unittest.main()
