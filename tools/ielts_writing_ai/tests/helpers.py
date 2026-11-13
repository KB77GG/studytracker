from __future__ import annotations

import json
import re
import shutil
import tempfile
import unittest

from tools.ielts_writing_ai import access, create_app, load_settings, visual
from tools.ielts_writing_ai.llm import FakeClient

PNG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64

TASK2_PROMPT = (
    "Some people believe that university education should be free for all students. "
    "To what extent do you agree or disagree?"
)
TASK2_ESSAY = (
    "Nowadays, many people argue that university should be free. i think this idea has "
    "advantages and disadvantages.\n"
    "On the one hand, free education can help poor students. They dont need to worry about "
    "money, so they can focus on study. For example, my cousin worked two jobs during "
    "university and his grades were low.\n"
    "On the other hand, governments have limited budgets. If universities are free, taxes "
    "will increase alot and other services like hospitals may suffer.\n"
    "In conclusion, I partly agree that university should be free, but governments should "
    "support only students who really need help."
)


# A person confirmed the chart reading: only then is Task 1 TA scored (2026-11-13).
# The confirmation is bound to the exact reading text (review of .15).
CHART_READING = "Type: bar_chart\nData: Museum A = 140; Museum B = 90; Museum C = 200"


def confirmed_image(description=CHART_READING):
    return json.dumps(
        {
            "status": "confirmed",
            "at": "2026-11-13T00:00:00Z",
            "edited": False,
            "reading_sha256": visual.reading_sha256(description),
        }
    )


CONFIRMED_IMAGE = confirmed_image()


def settings_for(tmpdir, **overrides):
    values = {"data_dir": tmpdir, "job_mode": "inline", "vision_provider": "none", "lock_wait": 0}
    values.update(overrides)
    return load_settings(env={}, env_file="/nonexistent/.env", **values)


class AppTestCase(unittest.TestCase):
    settings_overrides: dict = {}

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp(prefix="iwa-test-")
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        self.client_llm = FakeClient()
        self.app = self.make_app()
        self.storage = self.app.extensions["iwa"].storage

    def make_app(self, **overrides):
        """(Re)start the app on the same data dir: the previous instance is stopped
        first, exactly like stop.sh followed by start.sh."""
        current = getattr(self, "app", None)
        if current is not None:
            current.extensions["iwa"].close()
        values = {**self.settings_overrides, **overrides}
        vision = values.pop("vision_client", None)
        app = create_app(
            settings_for(self.tmpdir, **values), client=self.client_llm, vision_client=vision
        )
        self.addCleanup(app.extensions["iwa"].close)
        return app

    def add_user(self, name="学生A", **kwargs):
        code = access.generate_code()
        user_id = self.storage.create_user(
            name=name,
            code_hash=access.hash_code(code),
            code_hint=access.code_hint(code),
            **kwargs,
        )
        return user_id, code

    def login(self, code, client=None):
        client = client or self.app.test_client()
        page = client.get("/login")
        csrf = re.search(r'data-csrf="([^"]+)"', page.get_data(as_text=True)).group(1)
        response = client.post("/api/login", json={"code": code}, headers={"X-IWA-CSRF": csrf})
        client.csrf = response.get_json().get("csrf") if response.status_code == 200 else csrf
        client.login_response = response
        return client

    def check_image(self, client, public_id, action="confirm", description=None):
        """The user's check of the chart reading (2026-11-13); confirm keeps the
        model's reading unless a corrected description is given."""
        if action == "confirm" and description is None:
            sub = client.get(f"/api/submissions/{public_id}").get_json()["submission"]
            description = sub["image"]["check_text"]
        payload = {"action": action}
        if description is not None:
            payload["description"] = description
        return client.post(
            f"/api/submissions/{public_id}/image-check",
            json=payload,
            headers={"X-IWA-CSRF": client.csrf},
        )

    def submit(self, client, **fields):
        data = {
            "task_type": "task2",
            "prompt_text": TASK2_PROMPT,
            "essay_text": TASK2_ESSAY,
            "target_band": "7.0",
        }
        data.update(fields)
        return client.post(
            "/api/submissions",
            data=data,
            headers={"X-IWA-CSRF": client.csrf},
            content_type="multipart/form-data",
        )
