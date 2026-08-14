import tempfile
import unittest
from pathlib import Path

from scripts.backfill_dictation_book_tts import (
    _load_spoken_text_overrides,
    _looks_like_mp3,
    _one_pass_tts_text,
    _valid_mp3_file,
    _write_atomic,
)


class BackfillDictationBookTtsTest(unittest.TestCase):
    def test_mp3_validation_accepts_id3_and_frame_sync(self):
        self.assertTrue(_looks_like_mp3(b"ID3" + b"\x00" * 1021))
        self.assertTrue(_looks_like_mp3(b"\x00" * 8 + b"\xff\xfb" + b"\x00" * 1014))
        self.assertFalse(_looks_like_mp3(b"\x00" * 2048))
        self.assertFalse(_looks_like_mp3(b"ID3"))

    def test_atomic_write_produces_valid_cache_file(self):
        payload = b"ID3" + b"\x00" * 1021
        with tempfile.TemporaryDirectory() as tmpdir:
            target = Path(tmpdir) / "nested" / "clip.mp3"
            _write_atomic(target, payload)
            self.assertEqual(target.read_bytes(), payload)
            self.assertTrue(_valid_mp3_file(target))
            self.assertEqual(list(target.parent.glob("*.tmp")), [])

    def test_one_pass_override_is_normalized_without_repetition(self):
        self.assertEqual(_one_pass_tts_text("  nine,   four  "), "nine, four.")
        self.assertEqual(_one_pass_tts_text("oh."), "oh.")
        with self.assertRaisesRegex(ValueError, "must not be blank"):
            _one_pass_tts_text("  ")

    def test_phone_postcode_map_is_pinned_and_strictly_character_wise(self):
        path = (
            Path(__file__).resolve().parent.parent
            / "data"
            / "dictation_tts_overrides"
            / "ielts_sun_number_dictation_phone_postcode.json"
        )
        book_id, book_title, overrides = _load_spoken_text_overrides(path)

        self.assertEqual(book_id, 196)
        self.assertEqual(book_title, "雅思听力数字练习（sun老师数字听写）")
        self.assertEqual(len(overrides), 19)
        self.assertEqual(
            overrides[31],
            ("94635550", "nine, four, six, three, five, five, five, oh."),
        )
        self.assertEqual(
            overrides[116],
            ("BG241DJ", "bee, gee, two, four, one, dee, jay."),
        )
        character_names = {
            **dict(
                zip(
                    "0123456789",
                    ("oh", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine"),
                    strict=True,
                )
            ),
            **dict(
                zip(
                    "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
                    (
                        "ay",
                        "bee",
                        "see",
                        "dee",
                        "ee",
                        "eff",
                        "gee",
                        "aitch",
                        "eye",
                        "jay",
                        "kay",
                        "ell",
                        "em",
                        "en",
                        "oh",
                        "pee",
                        "cue",
                        "are",
                        "ess",
                        "tee",
                        "you",
                        "vee",
                        "double-you",
                        "ex",
                        "why",
                        "zed",
                    ),
                    strict=True,
                )
            ),
        }
        for word, spoken_text in overrides.values():
            self.assertFalse(any(character.isdigit() for character in spoken_text))
            self.assertEqual(
                spoken_text,
                ", ".join(character_names[character] for character in word) + ".",
            )

    def test_pronunciation_map_rejects_duplicate_sequences(self):
        payload = """{
          "book_id": 196,
          "book_title": "Pinned",
          "items": [
            {"sequence": 1, "word": "123", "spoken_text": "one, two, three"},
            {"sequence": 1, "word": "456", "spoken_text": "four, five, six"}
          ]
        }"""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "duplicates.json"
            path.write_text(payload, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate pronunciation sequence: 1"):
                _load_spoken_text_overrides(path)


if __name__ == "__main__":
    unittest.main()
