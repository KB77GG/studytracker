"""静态音频响应头测试。

安卓微信 MediaPlayer 依据首次 200 响应的 Accept-Ranges 判断能否 seek，
缺失时精听单句 seek 会退化成从头播放整段（iOS AVPlayer 不受影响）。
"""

import unittest

from app import app

AUDIO_PATH = "/static/listening/ielts10_test1_s1.mp3"


class StaticAudioHeadersTest(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_plain_200_advertises_accept_ranges(self):
        resp = self.client.get(AUDIO_PATH)
        try:
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.headers.get("Accept-Ranges"), "bytes")
        finally:
            resp.close()

    def test_range_request_still_returns_206(self):
        resp = self.client.get(AUDIO_PATH, headers={"Range": "bytes=0-1023"})
        try:
            self.assertEqual(resp.status_code, 206)
            self.assertEqual(resp.headers.get("Accept-Ranges"), "bytes")
            self.assertTrue(resp.headers.get("Content-Range", "").startswith("bytes 0-1023/"))
        finally:
            resp.close()

    def test_non_audio_200_untouched(self):
        resp = self.client.get("/static/listening/ielts10_test1_s1.json")
        try:
            self.assertEqual(resp.status_code, 200)
            self.assertIsNone(resp.headers.get("Accept-Ranges"))
        finally:
            resp.close()


if __name__ == "__main__":
    unittest.main()
