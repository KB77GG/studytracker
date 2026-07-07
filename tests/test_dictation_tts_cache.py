"""默写 TTS 混合音源 (Youdao v1 真人 / Kokoro 兜底) 测试。

背景 (2026-07-02)：
- Youdao 对基础词返回 MPEG v1 真人录音（干净），对变形词退化成 v2 合成音
  （听感像"日语英语"）。
- Kokoro 是统一合成音，变形词没问题，但孤立词的词首会插一个多余元音。
proxy_tts 用 _is_high_quality_mp3 门控：只在 Youdao 给 v1 时用它，否则改用
预烤好的 Kokoro 缓存。
"""

import tempfile
import unittest

import api.dictation as dictation_mod
from app import app
from api.dictation import (
    _dictation_tts_cache_path,
    _dictation_tts_text,
    _is_high_quality_mp3,
)

# 最小 MPEG 帧头：v1 = 真人高质量，v2 = 合成音
MP3_V1 = b"\xff\xfb\x90\x64" + b"\x00" * 200
MP3_V2 = b"\xff\xf3\x90\x64" + b"\x00" * 200


class DictationTtsHybridTest(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.client = app.test_client()
        self._old_upload = app.config.get("UPLOAD_FOLDER")
        app.config["UPLOAD_FOLDER"] = self.tmpdir.name
        self._old_youdao = dictation_mod._youdao_tts

    def tearDown(self):
        app.config["UPLOAD_FOLDER"] = self._old_upload
        dictation_mod._youdao_tts = self._old_youdao
        self.tmpdir.cleanup()

    def _write_kokoro(self, word):
        with app.app_context():
            path = _dictation_tts_cache_path("kokoro", word, _dictation_tts_text(word))
            path.write_bytes(b"KOKORO-" + MP3_V1)
            return path

    def _write_youdao(self, word, payload):
        with app.app_context():
            path = _dictation_tts_cache_path("youdao", word, _dictation_tts_text(word))
            path.write_bytes(payload)
            return path

    def _fake_youdao(self, payload):
        def _fn(_text):
            return payload

        dictation_mod._youdao_tts = _fn

    # 1. 缓存里有 Youdao 真人录音 → 优先用它，即使 Kokoro 缓存也在
    def test_cached_youdao_v1_wins_over_kokoro(self):
        self._write_kokoro("specialist")
        self._write_youdao("specialist", MP3_V1 + b"YOUDAO")
        resp = self.client.get("/api/dictation/tts?word=specialist")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data.endswith(b"YOUDAO"))

    # 2. 缓存的 Youdao 是 v2 合成音 → 跳过，改用 Kokoro
    def test_cached_youdao_v2_falls_to_kokoro(self):
        self._write_kokoro("specialists")
        self._write_youdao("specialists", MP3_V2 + b"SYNTH")
        resp = self.client.get("/api/dictation/tts?word=specialists")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data.startswith(b"KOKORO-"))

    # 3. 无 Youdao 缓存，实时抓到 v1 → 用并落盘
    def test_live_youdao_v1_served_and_cached(self):
        self._write_kokoro("economy")
        self._fake_youdao(MP3_V1 + b"LIVE")
        resp = self.client.get("/api/dictation/tts?word=economy")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data.endswith(b"LIVE"))
        with app.app_context():
            cache = _dictation_tts_cache_path("youdao", "economy", _dictation_tts_text("economy"))
        self.assertTrue(cache.exists())

    # 4. 无 Youdao 缓存，实时只有 v2 → 落到 Kokoro（基础词干净、变形词一致）
    def test_live_youdao_v2_falls_to_kokoro(self):
        self._write_kokoro("economies")
        self._fake_youdao(MP3_V2 + b"SYNTH")
        resp = self.client.get("/api/dictation/tts?word=economies")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data.startswith(b"KOKORO-"))

    # 5. 无 Kokoro 缓存（自由输入词），Youdao 只有 v2 → 兜底也要出声
    def test_v2_last_resort_when_no_kokoro(self):
        self._fake_youdao(MP3_V2 + b"ONLYV2")
        resp = self.client.get("/api/dictation/tts?word=zzqqx")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.data.endswith(b"ONLYV2"))

    def test_is_high_quality_mp3_distinguishes_versions(self):
        self.assertTrue(_is_high_quality_mp3(MP3_V1))
        self.assertFalse(_is_high_quality_mp3(MP3_V2))
        self.assertFalse(_is_high_quality_mp3(b""))

    def test_default_provider_order_is_youdao_then_kokoro(self):
        from api.dictation import _dictation_tts_provider_order

        old = app.config.get("DICTATION_TTS_PROVIDER_ORDER")
        try:
            app.config["DICTATION_TTS_PROVIDER_ORDER"] = "youdao,kokoro"
            with app.app_context():
                self.assertEqual(_dictation_tts_provider_order(), ["youdao", "kokoro"])
        finally:
            app.config["DICTATION_TTS_PROVIDER_ORDER"] = old

    def test_tts_text_matches_configured_repeat(self):
        # 默认 DICTATION_TTS_REPEAT_COUNT=1：读一遍、补句号
        with app.app_context():
            self.assertEqual(_dictation_tts_text("apple"), "apple.")

    def test_youdao_query_strips_trailing_period(self):
        # dictvoice 对部分词的带句号文本返回 500，请求前必须去掉末尾句号
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
