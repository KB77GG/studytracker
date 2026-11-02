"""Exercise the real OpenAI-compatible client against a local stub server (no network)."""

import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from tools.ielts_writing_ai.llm import ChatClient, LLMError


class StubHandler(BaseHTTPRequestHandler):
    responses: list = []
    requests: list = []

    def log_message(self, *args):  # silence test output
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        StubHandler.requests.append(
            {"auth": self.headers.get("Authorization"), "body": json.loads(self.rfile.read(length))}
        )
        status, payload = StubHandler.responses.pop(0)
        data = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def ok(content, finish="stop"):
    return 200, {
        "model": "stub-model",
        "choices": [{"message": {"content": content}, "finish_reason": finish}],
        "usage": {"total_tokens": 12},
    }


class ChatClientTest(unittest.TestCase):
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

    def setUp(self):
        StubHandler.responses = []
        StubHandler.requests = []
        self.client = ChatClient(
            provider="deepseek", base_url=self.url, api_key="secret", model="m", timeout=5
        )

    def test_success_sends_json_mode_and_parses_result(self):
        StubHandler.responses = [ok('{"a": 1}')]
        result = self.client.complete(
            [{"role": "user", "content": "hi"}], json_mode=True, max_tokens=50
        )
        self.assertEqual(result.json(), {"a": 1})
        self.assertEqual(result.model, "stub-model")
        self.assertEqual(result.usage, {"total_tokens": 12})
        sent = StubHandler.requests[0]
        self.assertEqual(sent["auth"], "Bearer secret")
        self.assertEqual(sent["body"]["response_format"], {"type": "json_object"})
        self.assertEqual(sent["body"]["max_tokens"], 50)

    def test_retries_once_on_server_error(self):
        StubHandler.responses = [(503, {"error": "busy"}), ok("plain text")]
        result = self.client.complete([], json_mode=False, max_tokens=10)
        self.assertEqual(result.text, "plain text")
        self.assertNotIn("response_format", StubHandler.requests[1]["body"])

    def test_client_error_is_not_retried(self):
        StubHandler.responses = [(401, {"error": "bad key"})]
        with self.assertRaises(LLMError) as ctx:
            self.client.complete([], json_mode=True, max_tokens=10)
        self.assertEqual(ctx.exception.code, "http_401")
        self.assertNotIn("secret", ctx.exception.message)
        self.assertEqual(len(StubHandler.requests), 1)

    def test_truncated_and_empty_outputs(self):
        StubHandler.responses = [ok('{"a":', finish="length"), ok("  ")]
        with self.assertRaises(LLMError) as ctx:
            self.client.complete([], json_mode=True, max_tokens=10)
        self.assertEqual(ctx.exception.code, "truncated")
        with self.assertRaises(LLMError) as ctx:
            self.client.complete([], json_mode=True, max_tokens=10)
        self.assertEqual(ctx.exception.code, "empty")

    def test_missing_key_never_calls_out(self):
        client = ChatClient(
            provider="deepseek", base_url=self.url, api_key="", model="m", timeout=5
        )
        with self.assertRaises(LLMError) as ctx:
            client.complete([], json_mode=True, max_tokens=10)
        self.assertEqual(ctx.exception.code, "missing_api_key")
        self.assertEqual(StubHandler.requests, [])

    def test_network_failure(self):
        client = ChatClient(
            provider="deepseek", base_url="http://127.0.0.1:9/x", api_key="k", model="m", timeout=2
        )
        with self.assertRaises(LLMError) as ctx:
            client.complete([], json_mode=True, max_tokens=10, retries=0)
        self.assertEqual(ctx.exception.code, "network")


if __name__ == "__main__":
    unittest.main()
