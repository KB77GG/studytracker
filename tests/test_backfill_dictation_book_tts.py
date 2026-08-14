import tempfile
import unittest
from pathlib import Path

from scripts.backfill_dictation_book_tts import (
    _looks_like_mp3,
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


if __name__ == "__main__":
    unittest.main()
