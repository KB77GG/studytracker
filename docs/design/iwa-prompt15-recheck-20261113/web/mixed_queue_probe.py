"""Exercise legacy-result correction while a legitimate regeneration is queued.

Only real public routes, actual JobRunner thread scheduling and fake LLMs are used.
No direct DB mutation. All data are temporary/synthetic; transport is blocked.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--old-repo", required=True)
    parser.add_argument("--seed-probe", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(Path(args.repo).resolve()))

    def block_network(*args, **kwargs):
        raise AssertionError("No network is allowed in this offline probe")

    socket.create_connection = block_network
    from tools.ielts_writing_ai import create_app
    from tools.ielts_writing_ai.llm import FakeClient
    from tools.ielts_writing_ai.tests.helpers import TASK2_ESSAY, TASK2_PROMPT, settings_for
    from tools.ielts_writing_ai.tests.test_visual import StaticVision, reading

    class BlockingFake(FakeClient):
        def __init__(self):
            super().__init__()
            self.started = threading.Event()
            self.release = threading.Event()
            self.observed = []
            self.entered = 0
            self.mutex = threading.Lock()

        def complete(self, messages, **kwargs):
            if not self.release.is_set():
                with self.mutex:
                    self.entered += 1
                    if self.entered >= 2:
                        self.started.set()
                if not self.release.wait(15):
                    raise AssertionError("Probe failed to release first fake request")
            self.observed.append(
                {"kind": kwargs.get("context", {}).get("kind"), "messages": json.dumps(messages)}
            )
            return super().complete(messages, **kwargs)

    def login(app, code):
        c = app.test_client()
        html = c.get("/login").get_data(as_text=True)
        csrf = re.search(r'data-csrf="([^"]+)"', html).group(1)
        r = c.post("/api/login", json={"code": code}, headers={"X-IWA-CSRF": csrf})
        assert r.status_code == 200
        c.csrf = r.get_json()["csrf"]
        return c

    def view(c, pid):
        return c.get("/api/submissions/" + pid).get_json()["submission"]

    def digest(value):
        return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()

    observations = []
    checks = []

    def check(name, ok):
        checks.append({"name": name, "pass": bool(ok)})

    for action in ["confirm", "skip"]:
        with tempfile.TemporaryDirectory(prefix="iwa-mixed-queue-") as td:
            root = Path(td) / "legacy"
            env = {k: v for k, v in os.environ.items() if not k.startswith("IWA_")}
            subprocess.run(
                [
                    sys.executable,
                    "-B",
                    args.seed_probe,
                    "--repo",
                    args.old_repo,
                    "--seed",
                    str(root),
                ],
                env=env,
                capture_output=True,
                check=True,
                cwd=td,
            )
            meta = json.loads((root / "seed.private.json").read_text())
            fake = BlockingFake()
            app = create_app(
                settings_for(str(root), job_mode="thread", max_workers=2),
                client=fake,
                vision_client=StaticVision(reading()),
            )
            ctx = app.extensions["iwa"]
            client = login(app, meta["code"])
            headers = {"X-IWA-CSRF": client.csrf}
            pid = meta["pid"]
            before = view(client, pid)
            old_ids = {k: g["id"] for k, g in before["generations"].items()}
            old_results = {k: digest(g["result"]) for k, g in before["generations"].items()}
            try:
                check(
                    action + ".starts_as_legacy",
                    before["image"]["unchecked_legacy"] and not before["image"]["awaiting_check"],
                )
                rejected = client.post(
                    f"/api/submissions/{pid}/image-check",
                    json={"action": action, "description": before["image"]["description"]},
                    headers=headers,
                )
                check(action + ".completed_record_decision_refused", rejected.status_code == 409)
                # Occupy both real workers with an unrelated ordinary submission.
                busy = client.post(
                    "/api/submissions",
                    data={
                        "task_type": "task2",
                        "prompt_text": TASK2_PROMPT,
                        "essay_text": TASK2_ESSAY,
                        "target_band": "7.0",
                    },
                    headers=headers,
                )
                check(action + ".unrelated_submission_accepted", busy.status_code == 201)
                check(action + ".worker_busy", fake.started.wait(10))
                # A normal click on the historical evaluation's regenerate button.
                regen = client.post(
                    f"/api/submissions/{pid}/generations/evaluate", json={}, headers=headers
                )
                check(action + ".regenerate_accepted", regen.status_code == 202)
                waiting = view(client, pid)
                check(
                    action + ".new_evaluation_queued",
                    waiting["generations"]["evaluate"]["status"] == "queued",
                )
                check(
                    action + ".old_refine_rewrite_still_ready",
                    all(
                        waiting["generations"][k]["status"] == "ready"
                        for k in ["refine", "rewrite"]
                    ),
                )
                payload = {"action": action}
                if action == "confirm":
                    payload["description"] = before["image"]["description"].replace(
                        "Museum A = 140", "Museum A = 160"
                    )
                response = client.post(
                    f"/api/submissions/{pid}/image-check", json=payload, headers=headers
                )
                at_confirm = view(client, pid)
                fake.release.set()
                deadline = time.monotonic() + 8
                while time.monotonic() < deadline:
                    after = view(client, pid)
                    if after["generations"]["evaluate"]["status"] in {"ready", "failed"}:
                        break
                    time.sleep(0.02)
                unchanged = {
                    k: after["generations"][k]["id"] == old_ids[k]
                    and digest(after["generations"][k]["result"]) == old_results[k]
                    for k in ["refine", "rewrite"]
                }
                check(action + ".legacy_confirmation_must_be_refused", response.status_code == 409)
                check(
                    action + ".legacy_description_must_not_change",
                    after["image"]["description"] == before["image"]["description"],
                )
                check(action + ".legacy_check_must_remain_empty", after["image"]["check"] is None)
                observations.append(
                    {
                        "action": action,
                        "regen_status": regen.status_code,
                        "awaiting_after_regen": waiting["image"]["awaiting_check"],
                        "legacy_after_regen": waiting["image"]["unchecked_legacy"],
                        "confirmation_status": response.status_code,
                        "check_after_request": at_confirm["image"]["check"],
                        "old_ready_results_unchanged": unchanged,
                        "new_evaluation_status": after["generations"]["evaluate"]["status"],
                        "new_evaluation_prompt_version": after["generations"]["evaluate"][
                            "prompt_version"
                        ],
                        "old_refine_prompt_version": after["generations"]["refine"][
                            "prompt_version"
                        ],
                        "reading_has_correction": "Museum A = 160" in after["image"]["description"],
                        "legacy_label_after": after["image"]["unchecked_legacy"],
                        "direct_db_mutations": 0,
                    }
                )
            finally:
                fake.release.set()
                # Wait for all fake work before removing its temporary directory.
                ctx.jobs._pool.shutdown(wait=True)
                ctx.close()
    result = {
        "checks": checks,
        "passed": sum(c["pass"] for c in checks),
        "total": len(checks),
        "observations": observations,
        "real_calls": 0,
        "direct_db_mutations": 0,
        "scope": "Actual old-source ready record; genuine JobRunner busy workers; public regenerate and image-check routes only.",
    }
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return int(any(not c["pass"] for c in checks))


if __name__ == "__main__":
    raise SystemExit(main())
