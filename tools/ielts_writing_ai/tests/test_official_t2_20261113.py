"""After the official Task 2 run of 2026-11-13
(docs/design/ielts-writing-ai-official-t2-pro-20261113-results): the argument map cut a
9-paragraph essay at 8 paragraphs; image reading could only go through a generic
provider with a 700-token budget and the text timeout. The question copied at the top
of the essay is handled in test_copied_question_20261113 (review f46756f replaced the
first, similarity-based attempt). Synthetic texts only (the official script itself stays
out of the repository)."""

import io
import threading
import unittest
from http.server import HTTPServer

from tools.ielts_writing_ai import argument
from tools.ielts_writing_ai.config import load_settings
from tools.ielts_writing_ai.llm import ChatClient

from .helpers import PNG_BYTES, AppTestCase
from .test_llm import StubHandler, ok
from .test_visual import reading


class ParagraphCapTest(unittest.TestCase):
    def test_every_real_paragraph_is_kept(self):
        paragraphs = [f"Paragraph number {n} makes its own point here." for n in range(1, 10)]
        text = "\n".join(paragraphs)
        raw = {
            "position": None,
            "paragraphs": [
                {
                    "p": n,
                    "role": "body",
                    "main_point": p,
                    "verdict": "supports",
                    "comment": "说明。",
                }
                for n, p in enumerate(paragraphs, 1)
            ],
            "problems": [],
            "improvements": [],
        }
        mapped = argument.normalize(raw, text)
        self.assertEqual([p["p"] for p in mapped["paragraphs"]], list(range(1, 10)))
        self.assertEqual((mapped["real_paragraphs"], mapped["over_limit"]), (9, 0))


class DeepSeekVisionSettingsTest(unittest.TestCase):
    def settings(self, **env):
        return load_settings(env={f"IWA_{k}": v for k, v in env.items()}, env_file="/nonexistent")

    def test_flash_reads_images_with_the_text_key_and_its_own_budget(self):
        s = self.settings(LLM_PROVIDER="deepseek", LLM_API_KEY="k", VISION_PROVIDER="deepseek")
        s.validate()
        self.assertEqual(
            (s.vision_base_url, s.vision_model, s.vision_api_key),
            ("https://api.deepseek.com/chat/completions", "deepseek-flash", "k"),
        )
        self.assertEqual((s.vision_max_tokens, s.vision_timeout), (2000, 180.0))
        s = self.settings(
            VISION_PROVIDER="deepseek",
            VISION_API_KEY="v",
            VISION_MAX_TOKENS="3000",
            VISION_TIMEOUT="240",
        )
        self.assertEqual((s.vision_max_tokens, s.vision_timeout), (3000, 240.0))
        self.assertEqual(s.public_summary()["vision_max_tokens"], 3000)


class DeepSeekVisionRequestTest(AppTestCase):
    settings_overrides = {"vision_max_tokens": 2000, "vision_timeout": 180.0}

    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), StubHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f"http://127.0.0.1:{cls.server.server_port}/v1/chat/completions"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()

    def test_the_reading_request_turns_thinking_off_and_uses_the_image_budget(self):
        StubHandler.requests = []
        StubHandler.responses = [ok(reading())]
        vision = ChatClient(
            provider="deepseek", base_url=self.url, api_key="k", model="deepseek-flash", timeout=120
        )
        timeouts = []
        original = vision._open
        vision._open = lambda request, timeout=None: (
            timeouts.append(timeout),
            original(request, timeout),
        )[1]
        self.app = self.make_app(vision_client=vision)
        _uid, code = self.add_user()
        client = self.login(code)
        public_id = self.submit(
            client,
            task_type="task1",
            prompt_text="The chart below shows visitors to four museums in 2020.",
            image=(io.BytesIO(PNG_BYTES), "chart.png"),
        ).get_json()["public_id"]
        body = StubHandler.requests[0]["body"]
        self.assertEqual(body["model"], "deepseek-flash")
        self.assertEqual(body["thinking"], {"type": "disabled"})
        self.assertEqual(body["max_tokens"], 2000)
        self.assertEqual(body["messages"][0]["content"][0]["type"], "image_url")
        self.assertTrue(
            body["messages"][0]["content"][0]["image_url"]["url"].startswith(
                "data:image/png;base64,"
            )
        )
        self.assertEqual(timeouts, [180.0])
        sub = client.get(f"/api/submissions/{public_id}").get_json()["submission"]
        self.assertEqual(sub["image"]["status"], "ready")


if __name__ == "__main__":
    unittest.main()
