"""Numeric audio routes and cache isolation, with all TTS providers mocked."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from flask import Flask

import api.dictation as dictation_mod
from dictation_numeric import classify_numeric_dictation
from models import DictationBook, DictationWord, User, db

MP3 = b"\xff\xfb\x90\x64" + b"\x00" * 200


class DictationNumericAudioTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.app = Flask(__name__)
        self.app.config.update(
            TESTING=True,
            SECRET_KEY="numeric-audio-test",
            SQLALCHEMY_DATABASE_URI="sqlite:///:memory:",
            SQLALCHEMY_TRACK_MODIFICATIONS=False,
            UPLOAD_FOLDER=self.tmpdir.name,
            DICTATION_TTS_REPEAT_COUNT=1,
            DICTATION_TTS_GENERATION_PROVIDER_ORDER="dashscope",
        )
        db.init_app(self.app)
        self.app.register_blueprint(dictation_mod.dictation_bp)
        self.client = self.app.test_client()
        self.responses = []
        with self.app.app_context():
            db.create_all()
            teacher = User(
                username="numeric_audio_teacher",
                password_hash="test",
                role=User.ROLE_TEACHER,
            )
            db.session.add(teacher)
            db.session.flush()
            book = DictationBook(title="Numeric audio fixture", created_by=teacher.id)
            db.session.add(book)
            db.session.commit()
            self.book_id = book.id

        # Guard every provider entry point used by the proxy. No test invokes
        # a remote service or produces a billable audio generation request.
        provider_patch = patch.object(dictation_mod, "_tts_provider_audio", return_value=None)
        youdao_patch = patch.object(dictation_mod, "_youdao_tts", return_value=None)
        self.provider = provider_patch.start()
        self.youdao = youdao_patch.start()
        self.addCleanup(provider_patch.stop)
        self.addCleanup(youdao_patch.stop)

    def tearDown(self):
        for response in self.responses:
            response.close()
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
            db.engine.dispose()
        self.tmpdir.cleanup()

    def _word(self, text, **kwargs):
        with self.app.app_context():
            word = DictationWord(
                book_id=self.book_id, sequence=1, word=text, **kwargs
            )
            db.session.add(word)
            db.session.commit()
            return word.id

    def _get(self, word_id, query="?numeric=1"):
        response = self.client.get(f"/api/dictation/words/{word_id}/tts{query}")
        self.responses.append(response)
        return response

    def test_new_numeric_url_uses_classified_spoken_form(self):
        for text, kind in [
            ("0217856361", "digit_sequence"),
            ("28th June", "date"),
            ("£13.50", "currency"),
            ("4.30", "number"),
            ("40%", "percentage"),
            ("09:30", "time"),
            ("03/04/2026", "literal"),
        ]:
            with self.subTest(text=text):
                numeric = classify_numeric_dictation(text)
                self.assertEqual(numeric["kind"], kind)
                word_id = self._word(text)
                with patch.object(
                    dictation_mod, "_proxy_tts_for_word", return_value=("audio", 200)
                ) as proxy:
                    response = self._get(word_id)
                self.assertEqual(response.status_code, 200)
                proxy.assert_called_once_with(
                    text,
                    preferred_providers=["dashscope"],
                    spoken_text=numeric["tts_text"],
                    allow_legacy_cache=False,
                )
                with self.app.app_context():
                    self.assertEqual(db.session.get(DictationWord, word_id).word, text)

    def test_phone_provider_receives_zero_and_individual_digits(self):
        word_id = self._word("0217856361")
        self.provider.return_value = MP3 + b"PHONE"
        response = self._get(word_id)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, MP3 + b"PHONE")
        self.provider.assert_called_once_with(
            "dashscope", "zero two one seven eight five six three six one."
        )
        self.youdao.assert_not_called()

    def test_numeric_generation_reuses_spoken_form_cache(self):
        word_id = self._word("0217856361")
        self.provider.return_value = MP3 + b"CACHED"
        first = self._get(word_id)
        second = self._get(word_id)
        self.assertEqual(first.data, second.data)
        self.assertEqual(second.status_code, 200)
        self.provider.assert_called_once()

    def test_numeric_route_does_not_fall_back_to_raw_digit_cache(self):
        text = "0217856361"
        word_id = self._word(text)
        with self.app.app_context():
            old_path = dictation_mod._dictation_tts_cache_path("kokoro", text)
            old_path.write_bytes(MP3 + b"OLD-RAW-DIGITS")
        response = self._get(word_id)
        self.assertEqual(response.status_code, 502)
        self.assertEqual(response.json["error"], "tts_fetch_failed")
        # History still plays its original cached recording; no cache is
        # deleted or overwritten when the new spoken form is unavailable.
        legacy = self._get(word_id, query="")
        self.assertEqual(legacy.status_code, 200)
        self.assertEqual(legacy.data, MP3 + b"OLD-RAW-DIGITS")
        self.assertEqual(old_path.read_bytes(), MP3 + b"OLD-RAW-DIGITS")

    def test_numeric_route_can_use_cache_of_same_spoken_form(self):
        text = "0217856361"
        word_id = self._word(text)
        with self.app.app_context():
            spoken = dictation_mod._dictation_tts_text(
                classify_numeric_dictation(text)["tts_text"]
            )
            cache = dictation_mod._dictation_tts_cache_path("kokoro", text, spoken)
            cache.write_bytes(MP3 + b"DIGIT-BY-DIGIT")
        response = self._get(word_id)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, MP3 + b"DIGIT-BY-DIGIT")

    def test_spoken_rule_change_uses_a_different_cache(self):
        text = "0217856361"
        with self.app.app_context():
            first = dictation_mod._dictation_tts_cache_path(
                "dashscope", text, "zero two one seven eight five six three six one."
            )
            changed = dictation_mod._dictation_tts_cache_path(
                "dashscope", text, "zero, two, one, seven, eight, five, six, three, six, one."
            )
        self.assertNotEqual(first, changed)

    def test_existing_word_url_keeps_legacy_numeric_behavior(self):
        word_id = self._word("28th June")
        with patch.object(
            dictation_mod, "_proxy_tts_for_word", return_value=("legacy audio", 200)
        ) as proxy:
            response = self._get(word_id, query="")
        self.assertEqual(response.status_code, 200)
        proxy.assert_called_once_with("28th June", preferred_providers=["dashscope"])

    def test_numeric_opt_in_does_not_change_ordinary_english(self):
        for text, providers in [("apple", None), ("B2B", ["dashscope"])]:
            with self.subTest(text=text):
                self.assertIsNone(classify_numeric_dictation(text))
                word_id = self._word(text)
                with patch.object(
                    dictation_mod, "_proxy_tts_for_word", return_value=("audio", 200)
                ) as proxy:
                    response = self._get(word_id)
                self.assertEqual(response.status_code, 200)
                proxy.assert_called_once_with(text, preferred_providers=providers)

    def test_bound_recording_still_has_priority_for_numeric_route(self):
        recording = Path(self.tmpdir.name) / "bound-phone.mp3"
        recording.write_bytes(MP3 + b"BOUND")
        word_id = self._word("0217856361", audio_us=str(recording))
        with patch.object(dictation_mod, "_proxy_tts_for_word") as proxy:
            response = self._get(word_id)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, MP3 + b"BOUND")
        proxy.assert_not_called()
        self.provider.assert_not_called()
        self.youdao.assert_not_called()

    def test_legacy_free_text_endpoint_keeps_its_contract(self):
        with patch.object(
            dictation_mod, "_proxy_tts_for_word", return_value=("audio", 200)
        ) as proxy:
            response = self.client.get("/api/dictation/tts?word=apple")
        self.assertEqual(response.status_code, 200)
        proxy.assert_called_once_with("apple")


if __name__ == "__main__":
    unittest.main()
