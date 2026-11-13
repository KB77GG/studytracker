"""After the official Task 2 run of 2026-11-13
(docs/design/ielts-writing-ai-official-t2-pro-20261113-results): the argument map cut a
9-paragraph essay at 8 paragraphs; the question copied at the top of the essay was
neither marked nor discounted; image reading could only go through a generic
provider with a 700-token budget and the text timeout. Synthetic texts only (the
official script itself stays out of the repository)."""

import io
import json
import threading
import unittest
from http.server import HTTPServer

from tools.ielts_writing_ai import argument, essay, prompts, review
from tools.ielts_writing_ai.config import load_settings
from tools.ielts_writing_ai.llm import ChatClient, FakeClient

from .helpers import PNG_BYTES, AppTestCase
from .test_llm import StubHandler, ok
from .test_visual import reading

QUESTION = (
    "City parks bring many benefits to residents. At the same time, there is worry about "
    "their cost to local councils and the space they take up. Do the advantages of city "
    "parks outweigh the disadvantages?"
)
COPIED_OPENING = (
    "City parks bring many benefits to residents. At the same time there is worry about "
    "it's costing to local councils and the space they take up.\n"
    "Do the advantages of city parks outweight the disadvantages?\n"
)
OWN_TEXT = (
    "In my opinion parks are good for a city because people can relax there after work.\n"
    "Firstly, children have a safe place to play and families meet their neighbours.\n"
    "Secondly, trees clean the air and make the summer less hot in busy streets.\n"
    "However, parks need money every year and some councils have very small budgets.\n"
    "To sum up, I think the advantages are bigger than the problems if parks are planned well."
)


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


class CopiedQuestionTest(unittest.TestCase):
    def test_near_verbatim_sentences_are_found_with_their_words(self):
        found = essay.copied_from_prompt(COPIED_OPENING + OWN_TEXT, QUESTION)
        self.assertEqual([c["p"] for c in found], [1, 1, 2])
        self.assertEqual(sum(c["words"] for c in found), essay.count_words(COPIED_OPENING))

    def test_reusing_some_words_of_the_question_is_not_copying(self):
        for text in (
            "Parks bring benefits, but councils worry about what they cost.",  # paraphrase
            "City parks bring many benefits.",  # under six words
            "Residents bring councils many parks at the same cost time worry.",  # no long run
            OWN_TEXT,
        ):
            with self.subTest(text=text[:40]):
                self.assertEqual(essay.copied_from_prompt(text, QUESTION), [])
        self.assertEqual(essay.copied_from_prompt(COPIED_OPENING, ""), [])

    def submission(self, text):
        return {
            "task_type": "task2",
            "prompt_text": QUESTION,
            "essay_text": text,
            "word_count": essay.count_words(text),
            "target_band": 7.0,
        }

    def test_the_model_is_told_only_when_something_was_copied(self):
        copied = self.submission(COPIED_OPENING + OWN_TEXT)
        messages, _ = prompts.build_evaluate(copied, essay.split_sentences(copied["essay_text"]))
        payload = json.loads(messages[1]["content"].split("\n", 1)[1].rsplit("\n", 1)[0])
        self.assertEqual([c["p"] for c in payload["copied_from_question"]], [1, 1, 2])
        self.assertEqual(payload["word_count_without_copied"], essay.count_words(OWN_TEXT))
        self.assertIn("do not count towards the word count", payload["copied_note"])
        own = self.submission(OWN_TEXT)
        own_messages, _ = prompts.build_evaluate(own, essay.split_sentences(OWN_TEXT))
        self.assertNotIn("copied_from_question", own_messages[1]["content"])
        self.assertEqual(own_messages[0], messages[0])  # the rules themselves are unchanged

    def evaluated(self, text):
        submission = self.submission(text)
        _messages, context = prompts.build_evaluate(submission, essay.split_sentences(text))
        raw = FakeClient._evaluate(context)  # a valid evaluation of this essay
        return review.normalize_evaluation(raw, submission)

    def test_the_page_warns_with_both_counts(self):
        text = COPIED_OPENING + OWN_TEXT
        result = self.evaluated(text)
        own = essay.count_words(OWN_TEXT)
        warning = next(w for w in result["warnings"] if "与题目几乎逐字相同" in w)
        self.assertIn("第 1 段、第 2 段有 3 句", warning)
        self.assertIn(f"去掉后约 {own} 词", warning)
        self.assertEqual(
            sum(c["words"] for c in result["copied_from_question"]),
            essay.count_words(COPIED_OPENING),
        )
        clean = self.evaluated(OWN_TEXT)
        self.assertEqual(clean["copied_from_question"], [])
        self.assertFalse(any("与题目几乎逐字相同" in w for w in clean["warnings"]))


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
