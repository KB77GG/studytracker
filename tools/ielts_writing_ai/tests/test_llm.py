"""Exercise the real OpenAI-compatible client against a local stub server (no network)."""

import json
import ssl
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import patch

from tools.ielts_writing_ai.llm import ChatClient, LLMError


class StubHandler(BaseHTTPRequestHandler):
    responses: list = []
    requests: list = []

    def log_message(self, *args):  # silence test output
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        StubHandler.requests.append(
            {
                "method": "POST",
                "auth": self.headers.get("Authorization"),
                "body": json.loads(self.rfile.read(length)),
            }
        )
        status, payload, *extras = StubHandler.responses.pop(0)
        data = payload if isinstance(payload, bytes) else json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        for name, value in (extras[0] if extras else {}).items():
            self.send_header(name, value)
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        # Detect the extra GET urllib normally emits after redirecting a POST.
        StubHandler.requests.append({"method": "GET", "auth": self.headers.get("Authorization")})
        self.send_response(200)
        self.end_headers()


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
        self.assertEqual(sent["body"]["thinking"], {"type": "disabled"})

    def test_other_providers_do_not_receive_deepseek_thinking_option(self):
        self.client.provider = "qwen"
        StubHandler.responses = [ok("plain text")]
        self.client.complete([], json_mode=False, max_tokens=10)
        self.assertNotIn("thinking", StubHandler.requests[0]["body"])

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
        self.assertTrue(ctx.exception.response_received)
        self.assertEqual(ctx.exception.http_status, 401)
        self.assertIsNone(ctx.exception.usage)
        self.assertEqual(len(StubHandler.requests), 1)

    def test_redirect_never_sends_another_request_with_the_key(self):
        for status in (301, 302, 303, 307, 308):
            with self.subTest(status=status):
                StubHandler.responses = [(status, {}, {"Location": self.url + "-redirected"})]
                before = len(StubHandler.requests)
                with self.assertRaises(LLMError) as ctx:
                    self.client.complete([], json_mode=True, max_tokens=10)
                self.assertEqual(ctx.exception.code, f"http_{status}")
                self.assertEqual(ctx.exception.http_status, status)
                self.assertTrue(ctx.exception.response_received)
                self.assertEqual(len(StubHandler.requests), before + 1)

    def test_unusable_outputs_keep_usage_and_successful_transport(self):
        usage = {"prompt_tokens": 100, "completion_tokens": 2800, "total_tokens": 2900}
        truncated = ok('{"a":', finish="length")[1]
        empty = ok("  ")[1]
        missing_choices = {"model": "stub-model"}
        for code, payload in (
            ("truncated", truncated),
            ("empty", empty),
            ("invalid_response", missing_choices),
        ):
            with self.subTest(code=code):
                payload["usage"] = usage
                StubHandler.responses = [(200, payload)]
                before = len(StubHandler.requests)
                with self.assertRaises(LLMError) as ctx:
                    self.client.complete([], json_mode=True, max_tokens=3000)
                error = ctx.exception
                self.assertEqual(error.code, code)
                self.assertTrue(error.response_received)
                self.assertEqual(error.http_status, 200)
                self.assertEqual(error.usage, usage)
                self.assertEqual(len(StubHandler.requests), before + 1)
                self.assertNotIn("secret", str(error))

    def test_invalid_response_has_unknown_usage_but_received_http_response(self):
        for payload in (b"not JSON", [], {"choices": []}):
            with self.subTest(payload=payload):
                StubHandler.responses = [(200, payload)]
                with self.assertRaises(LLMError) as ctx:
                    self.client.complete([], json_mode=True, max_tokens=10)
                self.assertEqual(ctx.exception.code, "invalid_response")
                self.assertTrue(ctx.exception.response_received)
                self.assertEqual(ctx.exception.http_status, 200)
                self.assertIsNone(ctx.exception.usage)

    def test_missing_key_never_calls_out(self):
        client = ChatClient(
            provider="deepseek", base_url=self.url, api_key="", model="m", timeout=5
        )
        with self.assertRaises(LLMError) as ctx:
            client.complete([], json_mode=True, max_tokens=10)
        self.assertEqual(ctx.exception.code, "missing_api_key")
        self.assertFalse(ctx.exception.response_received)
        self.assertIsNone(ctx.exception.http_status)
        self.assertIsNone(ctx.exception.usage)
        self.assertEqual(StubHandler.requests, [])

    def test_network_failure(self):
        client = ChatClient(
            provider="deepseek", base_url="http://127.0.0.1:9/x", api_key="k", model="m", timeout=2
        )
        with self.assertRaises(LLMError) as ctx:
            client.complete([], json_mode=True, max_tokens=10, retries=0)
        self.assertEqual(ctx.exception.code, "network")
        self.assertFalse(ctx.exception.response_received)
        self.assertIsNone(ctx.exception.http_status)
        self.assertIsNone(ctx.exception.usage)


class TrustStoreTest(unittest.TestCase):
    def test_empty_system_trust_store_gets_trusted_ca_without_disabling_verification(self):
        empty = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        self.assertEqual(empty.get_ca_certs(), [])
        with patch("tools.ielts_writing_ai.llm.ssl.create_default_context", return_value=empty):
            ChatClient(
                provider="deepseek",
                base_url="https://example.invalid",
                api_key="synthetic",
                model="deepseek-flash",
                timeout=5,
            )
        self.assertGreater(len(empty.get_ca_certs()), 0)
        self.assertEqual(empty.verify_mode, ssl.CERT_REQUIRED)
        self.assertTrue(empty.check_hostname)


if __name__ == "__main__":
    unittest.main()
