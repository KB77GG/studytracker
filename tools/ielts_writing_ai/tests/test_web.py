import io
import json
import re
import shutil
import tempfile
import unittest
from datetime import timedelta
from pathlib import Path

from tools.ielts_writing_ai import access, create_app, essay
from tools.ielts_writing_ai.instance import InstanceLocked
from tools.ielts_writing_ai.llm import FakeClient, LLMResult
from tools.ielts_writing_ai.storage import iso, utcnow

from .helpers import PNG_BYTES, TASK2_ESSAY, AppTestCase, settings_for


class UnreasonedFirstClient(FakeClient):
    """Returns the reviewer's bad output ("four 9s, no reasons") for the first N
    evaluation calls, then a normal demo evaluation."""

    def __init__(self, bad_attempts: int):
        super().__init__()
        self.bad_attempts = bad_attempts

    def complete(
        self, messages, *, json_mode, max_tokens, temperature=0.2, context=None, retries=1
    ):
        context = context or {}
        if context.get("kind") == "evaluate" and self.bad_attempts > 0:
            self.bad_attempts -= 1
            self.calls.append("evaluate")
            body = json.dumps({"criteria": {k: {"band": 9} for k in essay.CRITERIA}})
            return LLMResult(body, self.model, 1, {})
        return super().complete(
            messages,
            json_mode=json_mode,
            max_tokens=max_tokens,
            temperature=temperature,
            context=context,
            retries=retries,
        )


class AuthTest(AppTestCase):
    def test_pages_and_api_require_login(self):
        client = self.app.test_client()
        response = client.get("/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/login", response.headers["Location"])
        self.assertEqual(client.get("/api/submissions").status_code, 401)
        self.assertEqual(client.get("/healthz").status_code, 200)

    def test_login_with_formatted_code_and_cookie_name(self):
        _uid, code = self.add_user()
        client = self.login(f"  {code.lower().replace('-', ' ')} ")
        self.assertEqual(client.login_response.status_code, 200)
        cookie = client.login_response.headers.get("Set-Cookie", "")
        self.assertIn("iwa_session=", cookie)
        self.assertIn("HttpOnly", cookie)
        self.assertEqual(client.get("/").status_code, 200)

    def test_login_requires_csrf(self):
        _uid, code = self.add_user()
        client = self.app.test_client()
        client.get("/login")
        self.assertEqual(client.post("/api/login", json={"code": code}).status_code, 403)

    def test_wrong_code_and_lockout(self):
        self.add_user()
        client = self.app.test_client()
        statuses = []
        for _ in range(9):
            statuses.append(
                self.login("IWA-AAAA-BBBB-CCCC-DDDD", client).login_response.status_code
            )
        self.assertEqual(statuses[:8], [401] * 8)
        self.assertEqual(statuses[8], 429)

    def test_disabled_and_expired_users_cannot_login(self):
        uid, code = self.add_user()
        self.storage.update_user(uid, disabled_at=iso(utcnow()))
        self.assertEqual(self.login(code).login_response.get_json()["error"], "login_disabled")
        _uid2, code2 = self.add_user(name="B", expires_at=utcnow() - timedelta(minutes=1))
        self.assertEqual(self.login(code2).login_response.get_json()["error"], "login_expired")

    def test_reset_code_signs_out_existing_sessions(self):
        uid, code = self.add_user()
        client = self.login(code)
        self.assertEqual(client.get("/api/me").status_code, 200)
        self.storage.update_user(uid, code_hash=access.hash_code("IWA-NEW"), bump_epoch=True)
        self.assertEqual(client.get("/api/me").status_code, 401)
        self.assertEqual(self.login(code).login_response.status_code, 401)

    def test_mutations_require_csrf_header(self):
        _uid, code = self.add_user()
        client = self.login(code)
        response = client.post("/api/submissions", data={"task_type": "task2"})
        self.assertEqual(response.status_code, 403)

    def test_draft_key_is_per_user_opaque_and_stable(self):
        _uid_a, code_a = self.add_user("A")
        _uid_b, code_b = self.add_user("B")

        def user_key(client):
            html = client.get("/").get_data(as_text=True)
            return re.search(r'data-user-key="([^"]*)"', html).group(1)

        key_a = user_key(self.login(code_a))
        key_b = user_key(self.login(code_b))
        self.assertRegex(key_a, r"^[0-9a-f]{32}$")
        self.assertNotEqual(key_a, key_b)
        self.assertEqual(user_key(self.login(code_a)), key_a)  # same user, new login
        login_page = self.app.test_client().get("/login").get_data(as_text=True)
        self.assertIn('data-user-key=""', login_page)

    def test_html_pages_are_not_cached(self):
        _uid, code = self.add_user()
        client = self.login(code)
        for path in ("/", "/history", "/login"):
            response = client.get(path, follow_redirects=True)
            self.assertEqual(response.headers["Cache-Control"], "no-store", path)
        self.assertIn('autocomplete="off"', client.get("/").get_data(as_text=True))

    def test_security_headers(self):
        response = self.app.test_client().get("/login")
        self.assertIn("script-src 'self'", response.headers["Content-Security-Policy"])
        self.assertEqual(response.headers["X-Frame-Options"], "DENY")


class SubmissionFlowTest(AppTestCase):
    def setUp(self):
        super().setUp()
        self.uid, code = self.add_user()
        self.client = self.login(code)

    def test_full_flow_generates_three_results_and_keeps_original(self):
        response = self.submit(self.client)
        self.assertEqual(response.status_code, 201)
        public_id = response.get_json()["public_id"]
        data = self.client.get(f"/api/submissions/{public_id}").get_json()
        sub = data["submission"]
        self.assertEqual(sub["essay_text"], TASK2_ESSAY)
        self.assertEqual(
            {k: v["status"] for k, v in sub["generations"].items()},
            {"evaluate": "ready", "refine": "ready", "rewrite": "ready"},
        )
        evaluation = sub["generations"]["evaluate"]["result"]
        self.assertEqual(len(evaluation["criteria"]), 4)
        self.assertIsNotNone(evaluation["overall_band"])
        refine = sub["generations"]["refine"]["result"]
        self.assertTrue(all(s["original"] in TASK2_ESSAY for s in refine["sentences"]))
        self.assertGreater(refine["changed_count"], 0)
        self.assertEqual(data["quota"]["used"], 3)
        self.assertEqual(self.client_llm.calls, ["evaluate", "refine", "rewrite"])
        # The stored original is byte-identical after all generations ran.
        stored = self.storage.get_owned_submission(public_id, self.uid)
        self.assertEqual(stored["essay_text"], TASK2_ESSAY)

    def test_validation_errors(self):
        response = self.submit(
            self.client,
            prompt_text="short",
            essay_text="Too few words here.",
            target_band="9.0",
            task_type="task3",
        )
        self.assertEqual(response.status_code, 422)
        self.assertEqual(
            set(response.get_json()["fields"]),
            {"task_type", "prompt_text", "essay_text", "target_band"},
        )
        self.assertEqual(self.storage.usage_today(self.uid), 0)

    def test_history_lists_only_own_records(self):
        self.submit(self.client)
        self.submit(self.client)
        _other, code = self.add_user(name="学生B")
        other = self.login(code)
        self.submit(other)
        items = self.client.get("/api/submissions").get_json()["items"]
        self.assertEqual(len(items), 2)
        self.assertEqual(len(other.get("/api/submissions").get_json()["items"]), 1)
        self.assertIsNotNone(items[0]["overall_band"])

    def test_history_pagination(self):
        for _ in range(3):
            self.storage.create_submission(
                public_id=f"p{_}",
                user_id=self.uid,
                task_type="task2",
                prompt_text="x" * 20,
                essay_text="y",
                essay_sha256="z",
                word_count=1,
                target_band=7.0,
                image_path=None,
                image_mime=None,
                image_status="none",
                daily_limit=999,
            )
        first = self.client.get("/api/submissions").get_json()
        self.assertFalse(first["has_more"])
        cursor = first["items"][0]["cursor"]
        older = self.client.get(f"/api/submissions?before={cursor}").get_json()["items"]
        self.assertEqual(len(older), 2)

    def test_other_users_cannot_read_regenerate_or_delete(self):
        public_id = self.submit(self.client).get_json()["public_id"]
        _other, code = self.add_user(name="学生B")
        other = self.login(code)
        headers = {"X-IWA-CSRF": other.csrf}
        self.assertEqual(other.get(f"/api/submissions/{public_id}").status_code, 404)
        self.assertEqual(other.get(f"/s/{public_id}").status_code, 404)
        self.assertEqual(other.get(f"/api/submissions/{public_id}/image").status_code, 404)
        self.assertEqual(
            other.post(
                f"/api/submissions/{public_id}/generations/rewrite", headers=headers
            ).status_code,
            404,
        )
        self.assertEqual(
            other.delete(f"/api/submissions/{public_id}", headers=headers).status_code, 404
        )
        self.assertEqual(self.client.get(f"/api/submissions/{public_id}").status_code, 200)

    def test_delete_removes_record(self):
        public_id = self.submit(self.client).get_json()["public_id"]
        response = self.client.delete(
            f"/api/submissions/{public_id}", headers={"X-IWA-CSRF": self.client.csrf}
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get(f"/api/submissions/{public_id}").status_code, 404)
        # Quota is not refunded by deleting.
        self.assertEqual(self.storage.usage_today(self.uid), 3)


class QuotaAndRetryTest(AppTestCase):
    def test_daily_quota_blocks_submission_and_regeneration(self):
        uid, code = self.add_user(daily_limit=4)
        client = self.login(code)
        public_id = self.submit(client).get_json()["public_id"]
        self.assertEqual(self.submit(client).status_code, 429)
        headers = {"X-IWA-CSRF": client.csrf}
        self.assertEqual(
            client.post(
                f"/api/submissions/{public_id}/generations/refine", headers=headers
            ).status_code,
            202,
        )
        self.assertEqual(
            client.post(
                f"/api/submissions/{public_id}/generations/refine", headers=headers
            ).status_code,
            429,
        )
        self.assertEqual(self.storage.usage_today(uid), 4)

    def _with_client(self, client):
        self.client_llm = client
        self.app = self.make_app()
        self.storage = self.app.extensions["iwa"].storage
        uid, code = self.add_user()
        return uid, self.login(code)

    def test_incomplete_evaluation_is_retried_once_then_accepted(self):
        uid, client = self._with_client(UnreasonedFirstClient(bad_attempts=1))
        public_id = self.submit(client).get_json()["public_id"]
        evaluation = client.get(f"/api/submissions/{public_id}").get_json()["submission"][
            "generations"
        ]["evaluate"]
        self.assertEqual(evaluation["status"], "ready")
        self.assertEqual(self.client_llm.calls.count("evaluate"), 2)
        self.assertEqual(self.storage.usage_today(uid), 3)  # the retry costs no quota

    def test_repeatedly_incomplete_evaluation_fails_without_a_score(self):
        uid, client = self._with_client(UnreasonedFirstClient(bad_attempts=5))
        public_id = self.submit(client).get_json()["public_id"]
        evaluation = client.get(f"/api/submissions/{public_id}").get_json()["submission"][
            "generations"
        ]["evaluate"]
        self.assertEqual(evaluation["status"], "failed")
        self.assertEqual(evaluation["error"]["code"], "invalid_output")
        self.assertIsNone(evaluation["result"])
        self.assertIsNone(evaluation["copy"])
        self.assertEqual(self.client_llm.calls.count("evaluate"), 2)
        self.assertEqual(self.storage.usage_today(uid), 3)

    def test_failed_generation_can_be_regenerated(self):
        self.client_llm = FakeClient(fail_kinds={"rewrite"})
        self.app = self.make_app()
        self.storage = self.app.extensions["iwa"].storage
        _uid, code = self.add_user()
        client = self.login(code)
        public_id = self.submit(client).get_json()["public_id"]
        gens = client.get(f"/api/submissions/{public_id}").get_json()["submission"]["generations"]
        self.assertEqual(gens["rewrite"]["status"], "failed")
        self.assertEqual(gens["rewrite"]["error"]["code"], "http_503")
        self.assertIsNone(gens["rewrite"]["result"])
        self.assertEqual(gens["evaluate"]["status"], "ready")

        self.client_llm.fail_kinds.clear()
        response = client.post(
            f"/api/submissions/{public_id}/generations/rewrite", headers={"X-IWA-CSRF": client.csrf}
        )
        self.assertEqual(response.status_code, 202)
        gens = client.get(f"/api/submissions/{public_id}").get_json()["submission"]["generations"]
        self.assertEqual(gens["rewrite"]["status"], "ready")

    def test_regeneration_refused_while_running_and_unknown_kind(self):
        uid, code = self.add_user()
        client = self.login(code)
        public_id = self.submit(client).get_json()["public_id"]
        sub = self.storage.get_owned_submission(public_id, uid)
        gen_id, error = self.storage.queue_regeneration(sub["id"], "refine", uid, 99)
        self.assertIsNone(error)
        headers = {"X-IWA-CSRF": client.csrf}
        response = client.post(f"/api/submissions/{public_id}/generations/refine", headers=headers)
        self.assertEqual(response.status_code, 409)
        self.assertEqual(
            client.post(
                f"/api/submissions/{public_id}/generations/other", headers=headers
            ).status_code,
            404,
        )

    def test_restart_marks_unfinished_work_failed(self):
        uid, code = self.add_user()
        client = self.login(code)
        public_id = self.submit(client).get_json()["public_id"]
        sub = self.storage.get_owned_submission(public_id, uid)
        self.storage.queue_regeneration(sub["id"], "evaluate", uid, 99)
        restarted = self.make_app()
        client2 = self.login(code, restarted.test_client())
        gens = client2.get(f"/api/submissions/{public_id}").get_json()["submission"]["generations"]
        self.assertEqual(gens["evaluate"]["status"], "failed")
        self.assertEqual(gens["evaluate"]["error"]["code"], "interrupted")

    def test_duplicate_start_fails_without_touching_running_work(self):
        uid, code = self.add_user()
        client = self.login(code)
        public_id = self.submit(client).get_json()["public_id"]
        sub = self.storage.get_owned_submission(public_id, uid)
        gen_id, _ = self.storage.queue_regeneration(sub["id"], "evaluate", uid, 99)

        # A second server on the same database while the first is still alive.
        with self.assertRaises(InstanceLocked):
            create_app(settings_for(self.tmpdir), client=FakeClient())
        self.assertEqual(self.storage.get_generation(gen_id)["status"], "queued")
        # The first instance keeps working normally.
        self.assertEqual(client.get(f"/api/submissions/{public_id}").status_code, 200)

        # Different data dir but the same database file is still the same instance.
        other_dir = tempfile.mkdtemp(prefix="iwa-test-other-")
        self.addCleanup(shutil.rmtree, other_dir, ignore_errors=True)
        with self.assertRaises(InstanceLocked):
            create_app(
                settings_for(other_dir, db_path=str(self.storage.db_path)), client=FakeClient()
            )
        self.assertEqual(self.storage.get_generation(gen_id)["status"], "queued")

    def test_lock_is_released_when_the_instance_closes(self):
        self.app.extensions["iwa"].close()
        app = create_app(settings_for(self.tmpdir), client=FakeClient())
        self.addCleanup(app.extensions["iwa"].close)
        self.assertTrue(app.extensions["iwa"].lock.held)


class ImageTest(AppTestCase):
    def setUp(self):
        super().setUp()
        self.uid, code = self.add_user()
        self.client = self.login(code)

    def submit_image(self, payload, name="chart.png", **fields):
        return self.submit(
            self.client,
            task_type="task1",
            prompt_text="The chart below shows household spending in three countries in 2020.",
            image=(io.BytesIO(payload), name),
            **fields,
        )

    def test_rejects_non_image_content_even_with_png_name(self):
        response = self.submit_image(b"GIF89a not allowed")
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.get_json()["error"], "image_type")
        self.assertEqual(self.storage.usage_today(self.uid), 0)

    def test_rejects_oversized_image(self):
        response = self.submit_image(PNG_BYTES + b"\x00" * (5 * 1024 * 1024))
        self.assertEqual(response.status_code, 422)
        self.assertEqual(response.get_json()["error"], "image_too_large")

    def test_without_vision_image_is_stored_and_flagged(self):
        public_id = self.submit_image(PNG_BYTES).get_json()["public_id"]
        sub = self.client.get(f"/api/submissions/{public_id}").get_json()["submission"]
        self.assertEqual(sub["image"]["status"], "skipped")
        warnings = sub["generations"]["evaluate"]["result"]["warnings"]
        self.assertTrue(any("未配置识图模型" in w for w in warnings))
        image = self.client.get(sub["image"]["url"])
        self.assertEqual(image.status_code, 200)
        self.assertEqual(image.mimetype, "image/png")
        self.assertEqual(image.data, PNG_BYTES)
        image.close()

        stored = self.storage.get_owned_submission(public_id, self.uid)
        path = Path(self.app.extensions["iwa"].settings.upload_dir) / stored["image_path"]
        self.assertTrue(path.is_file())
        self.client.delete(
            f"/api/submissions/{public_id}", headers={"X-IWA-CSRF": self.client.csrf}
        )
        self.assertFalse(path.exists())

    def test_with_vision_description_feeds_generation(self):
        vision = FakeClient(model="fake-vision")
        self.app = self.make_app(vision_client=vision)
        self.storage = self.app.extensions["iwa"].storage
        _uid, code = self.add_user(name="C")
        self.client = self.login(code)
        public_id = self.submit_image(PNG_BYTES).get_json()["public_id"]
        sub = self.client.get(f"/api/submissions/{public_id}").get_json()["submission"]
        self.assertEqual(sub["image"]["status"], "ready")
        self.assertIn("演示", sub["image"]["description"])
        self.assertEqual(vision.calls, ["describe_image"])
        evaluation = sub["generations"]["evaluate"]
        self.assertEqual(evaluation["status"], "ready")
        # A successfully read chart is the only case where TA and the overall band exist.
        self.assertEqual(evaluation["result"]["criteria"][0]["state"], "scored")
        self.assertIsNotNone(evaluation["result"]["overall_band"])
        self.assertIn("预估总分", evaluation["copy"]["evaluation"])

    def test_task1_without_readable_chart_is_not_scored_end_to_end(self):
        no_image = self.submit(
            self.client,
            task_type="task1",
            prompt_text="The chart below shows household spending in three countries in 2020.",
        ).get_json()["public_id"]
        unread_image = self.submit_image(PNG_BYTES).get_json()["public_id"]
        for public_id in (no_image, unread_image):
            sub = self.client.get(f"/api/submissions/{public_id}").get_json()["submission"]
            evaluation = sub["generations"]["evaluate"]
            result = evaluation["result"]
            self.assertIsNone(result["overall_band"])
            self.assertEqual(result["criteria"][0]["state"], "not_assessable")
            self.assertIsNone(result["criteria"][0]["band"])
            self.assertIn("总分：不可评", evaluation["copy"]["evaluation"])
            rewrite_copy = sub["generations"]["rewrite"]["copy"]["essay"]
            self.assertIn("没有与题图核对", rewrite_copy)
        items = self.client.get("/api/submissions").get_json()["items"]
        self.assertEqual({i["overall_state"] for i in items}, {"not_assessable"})
        self.assertEqual({i["overall_band"] for i in items}, {None})

    def test_image_ignored_for_task2(self):
        response = self.submit(self.client, image=(io.BytesIO(PNG_BYTES), "x.png"))
        public_id = response.get_json()["public_id"]
        sub = self.client.get(f"/api/submissions/{public_id}").get_json()["submission"]
        self.assertIsNone(sub["image"])


if __name__ == "__main__":
    unittest.main()
