"""默写 TTS 缓存读取测试。

2026-07-02 生产事故回归：legacy 缓存（旧文本变体 / 旧 Kokoro 键）被读取链复活后，
安卓平板放不出声音。proxy_tts 只允许匹配当前文本的缓存。
"""

import tempfile
import unittest
from pathlib import Path

from app import app
from api.dictation import (
    _dictation_tts_cache_candidates,
    _dictation_tts_cache_path,
    _dictation_tts_cache_path_for_key,
    _dictation_tts_text,
)


class DictationTtsCacheTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.client = app.test_client()
        self._old_upload = app.config.get("UPLOAD_FOLDER")
        self._old_order = app.config.get("DICTATION_TTS_PROVIDER_ORDER")
        app.config["UPLOAD_FOLDER"] = self.tmpdir.name
        app.config["DICTATION_TTS_PROVIDER_ORDER"] = "youdao"

    def tearDown(self):
        app.config["UPLOAD_FOLDER"] = self._old_upload
        app.config["DICTATION_TTS_PROVIDER_ORDER"] = self._old_order
        self.tmpdir.cleanup()

    def test_proxy_tts_serves_current_text_cache(self):
        with app.app_context():
            tts_text = _dictation_tts_text("apple")
            current = _dictation_tts_cache_path("youdao", "apple", tts_text)
            current.write_bytes(b"CURRENT-TEXT")
            legacy = _dictation_tts_cache_path_for_key(
                "kokoro_af_heart_en-us_0.88", "apple", "apple"
            )
            legacy.write_bytes(b"LEGACY-KOKORO")

        resp = self.client.get("/api/dictation/tts?word=apple")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.data, b"CURRENT-TEXT")

    def test_read_candidates_exclude_legacy_texts_and_keys(self):
        with app.app_context():
            tts_text = _dictation_tts_text("apple")
            candidates = _dictation_tts_cache_candidates(
                "apple", tts_text, include_legacy=False
            )
            paths = {path for _, path in candidates}
            legacy_key_path = _dictation_tts_cache_path_for_key(
                "kokoro_af_heart_en-us_0.88", "apple", tts_text
            )
            legacy_text_path = _dictation_tts_cache_path("youdao", "apple", "apple")
            self.assertNotIn(legacy_key_path, paths)
            self.assertNotIn(legacy_text_path, paths)
            self.assertIn(_dictation_tts_cache_path("youdao", "apple", tts_text), paths)

    def test_default_provider_order_is_youdao_only(self):
        from api.dictation import _dictation_tts_provider_order

        with app.app_context():
            self.assertEqual(_dictation_tts_provider_order(), ["youdao"])
            app.config["DICTATION_TTS_PROVIDER_ORDER"] = ""
            self.assertEqual(_dictation_tts_provider_order(), ["youdao"])

    def test_tts_text_matches_configured_repeat(self):
        # 默认 DICTATION_TTS_REPEAT_COUNT=1：读一遍、补句号
        with app.app_context():
            self.assertEqual(_dictation_tts_text("apple"), "apple.")

    def test_youdao_query_strips_trailing_period(self):
        # dictvoice 对部分词的带句号文本返回 500，请求前必须去掉末尾句号
        import api.dictation as dictation_mod

        captured = {}

        class _FakeResp:
            status_code = 200
            content = b"AUDIO"

        def fake_get(url, timeout=None):
            captured["url"] = url
            return _FakeResp()

        original_get = dictation_mod.requests.get
        dictation_mod.requests.get = fake_get
        try:
            with app.app_context():
                result = dictation_mod._youdao_tts("inhabitant.")
        finally:
            dictation_mod.requests.get = original_get

        self.assertEqual(result, b"AUDIO")
        self.assertIn("audio=inhabitant&", captured["url"])


if __name__ == "__main__":
    unittest.main()
