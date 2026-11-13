"""Offline adjacent checks of the first-check window and per-result reading binding.

Uses synthetic temporary databases, fake clients and public routes. Explicit storage
edge cases are labelled; no live configuration, user database or network is used.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import threading
from contextlib import contextmanager
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", required=True)
    parser.add_argument("--old-repo", required=True)
    parser.add_argument("--seed-probe", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    sys.path.insert(0, str(Path(args.repo).resolve()))
    network_attempts = []

    def blocked(*_args, **_kwargs):
        network_attempts.append(True)
        raise AssertionError("Network prohibited in offline review")

    socket.create_connection = blocked
    socket.socket.connect = blocked
    from tools.ielts_writing_ai import access, create_app, review
    from tools.ielts_writing_ai.llm import FakeClient
    from tools.ielts_writing_ai.tests.helpers import (
        PNG_BYTES,
        TASK2_ESSAY,
        TASK2_PROMPT,
        settings_for,
    )
    from tools.ielts_writing_ai.tests.test_visual import StaticVision, reading

    checks = []
    observations = {}

    def check(name, condition):
        checks.append({"name": name, "pass": bool(condition)})

    class Recorder(FakeClient):
        def __init__(self, *, block=False):
            super().__init__()
            self.messages = []
            self.entered = 0
            self.mutex = threading.Lock()
            self.busy = threading.Event()
            self.release = threading.Event()
            if not block:
                self.release.set()
            self.callback = None

        def complete(self, messages, **kwargs):
            if not self.release.is_set():
                with self.mutex:
                    self.entered += 1
                    if self.entered == 2:
                        self.busy.set()
                if not self.release.wait(20):
                    raise AssertionError("Fake workers not released")
            self.messages.append(json.dumps(messages, ensure_ascii=False))
            if self.callback:
                callback, self.callback = self.callback, None
                callback()
            return super().complete(messages, **kwargs)

    def login(app, code):
        c = app.test_client()
        html = c.get("/login").get_data(as_text=True)
        csrf = re.search(r'data-csrf="([^"]+)"', html).group(1)
        response = c.post("/api/login", json={"code": code}, headers={"X-IWA-CSRF": csrf})
        assert response.status_code == 200
        c.csrf = response.get_json()["csrf"]
        return c

    @contextmanager
    def fixture(root, recorder=None, *, threaded=False, code=None):
        fake = recorder or Recorder()
        app = create_app(
            settings_for(str(root), job_mode="thread" if threaded else "inline", max_workers=2),
            client=fake,
            vision_client=StaticVision(reading()),
        )
        ctx = app.extensions["iwa"]
        if code is None:
            code = access.generate_code()
            ctx.storage.create_user(
                name="Synthetic reviewer",
                code_hash=access.hash_code(code),
                code_hint=access.code_hint(code),
                daily_limit=99,
            )
        try:
            yield ctx, login(app, code), fake
        finally:
            fake.release.set()
            if ctx.jobs._pool:
                ctx.jobs._pool.shutdown(wait=True)
            ctx.close()

    def view(c, pid):
        return c.get(f"/api/submissions/{pid}").get_json()["submission"]

    def submit(c, *, task="task1", image=True):
        data = {
            "task_type": task,
            "prompt_text": (
                "The chart below shows museum visitors." if task == "task1" else TASK2_PROMPT
            ),
            "essay_text": TASK2_ESSAY,
            "target_band": "7.0",
        }
        if image:
            data["image"] = (io.BytesIO(PNG_BYTES), "chart.png")
        response = c.post(
            "/api/submissions",
            data=data,
            headers={"X-IWA-CSRF": c.csrf},
            content_type="multipart/form-data",
        )
        assert response.status_code == 201
        return response.get_json()["public_id"]

    def decide(c, pid, action="confirm", description=None):
        payload = {"action": action}
        if action == "confirm":
            payload["description"] = description or view(c, pid)["image"]["check_text"]
        return c.post(
            f"/api/submissions/{pid}/image-check",
            json=payload,
            headers={"X-IWA-CSRF": c.csrf},
        )

    def regen(c, pid, kind):
        return c.post(
            f"/api/submissions/{pid}/generations/{kind}",
            json={},
            headers={"X-IWA-CSRF": c.csrf},
        )

    # Historical attempts, not only the latest attempt for each kind, close the window.
    with tempfile.TemporaryDirectory(prefix="iwa-adjacent-legacy-") as td:
        root = Path(td) / "old"
        env = {k: v for k, v in os.environ.items() if not k.startswith("IWA_")}
        subprocess.run(
            [sys.executable, "-B", args.seed_probe, "--repo", args.old_repo, "--seed", str(root)],
            env=env,
            cwd=td,
            capture_output=True,
            check=True,
        )
        meta = json.loads((root / "seed.private.json").read_text())
        fake = Recorder(block=True)
        with fixture(root, fake, threaded=True, code=meta["code"]) as (ctx, c, _):
            pid = meta["pid"]
            before = view(c, pid)
            check(
                "legacy.no_snapshot",
                all("chart_reading" not in g["result"] for g in before["generations"].values()),
            )
            check("legacy.keeps_legacy_banner", before["image"]["unchecked_legacy"])
            check(
                "legacy.unknown_snapshot_not_claimed_mismatch",
                not any(g["reading_mismatch"] for g in before["generations"].values()),
            )
            submit(c, task="task2", image=False)
            check("legacy.two_real_workers_busy", fake.busy.wait(10))
            for kind in ("evaluate", "refine", "rewrite"):
                check(f"legacy.regen_{kind}_accepted", regen(c, pid, kind).status_code == 202)
            queued = view(c, pid)
            sid = ctx.storage.get_owned_submission(pid, meta["uid"])["id"]
            check(
                "legacy.latest_all_three_queued",
                all(g["status"] == "queued" for g in queued["generations"].values()),
            )
            check("legacy.history_closes_window", not ctx.storage.check_window_open(sid))
            check(
                "legacy.all_queued_still_old",
                queued["image"]["unchecked_legacy"] and not queued["image"]["awaiting_check"],
            )
            for action in ("confirm", "skip"):
                response = decide(c, pid, action, before["image"]["description"])
                check(f"legacy.all_queued_{action}_409", response.status_code == 409)
            check(
                "legacy.atomic_store_rejects",
                not ctx.storage.set_image_check(sid, {"status": "skipped"}, waiting_only=True),
            )
            fake.release.set()
            ctx.jobs._pool.shutdown(wait=True)
            after = view(c, pid)
            for kind, generation in after["generations"].items():
                check(f"legacy.new_{kind}_ready", generation["status"] == "ready")
                check(
                    f"legacy.new_{kind}_unchecked_snapshot",
                    generation["result"].get("chart_reading") == {"checked": False, "sha256": None},
                )
                check(f"legacy.new_{kind}_matches_unchecked", not generation["reading_mismatch"])
            check(
                "legacy.new_evaluation_has_no_TA",
                after["generations"]["evaluate"]["result"]["criteria"][0]["state"]
                == "not_assessable",
            )
            check(
                "legacy.new_results_no_chart_sent",
                not any("Museum A = 140" in message for message in fake.messages),
            )
            check("legacy.banner_survives_all_regens", after["image"]["unchecked_legacy"])
            observations["legacy"] = {
                "latest_queued": 3,
                "historical_ready": 3,
                "window_open": False,
            }

    # Synthetic storage-only boundary: all rows queued, but one has a start timestamp.
    # This is deliberately labelled a manipulated temporary fixture, not a public-path bug.
    with tempfile.TemporaryDirectory(prefix="iwa-adjacent-started-") as td:
        with fixture(td) as (ctx, c, fake):
            pid = submit(c)
            sid = ctx.storage.get_owned_submission(pid, 1)["id"]
            check("started.fresh_window_open", ctx.storage.check_window_open(sid))
            gid = ctx.storage.queued_generation_ids(sid)[0]
            with ctx.storage.connect() as conn:
                conn.execute(
                    "UPDATE generation SET started_at = ? WHERE id = ?",
                    ("2026-11-13T00:00:00Z", gid),
                )
            check(
                "started.all_still_queued",
                all(g["status"] == "queued" for g in view(c, pid)["generations"].values()),
            )
            check("started.timestamp_closes_window", not ctx.storage.check_window_open(sid))
            for action in ("confirm", "skip"):
                check(
                    f"started.{action}_409",
                    decide(c, pid, action, "synthetic description").status_code == 409,
                )
            check(
                "started.atomic_store_rejects",
                not ctx.storage.set_image_check(sid, {"status": "skipped"}, waiting_only=True),
            )
            check("started.no_text_calls", not fake.messages)
            check("started.missing_submission_closed", not ctx.storage.check_window_open(99999))

    with tempfile.TemporaryDirectory(prefix="iwa-adjacent-snapshot-") as td:
        with fixture(td) as (ctx, c, fake):
            pid = submit(c)
            description = view(c, pid)["image"]["check_text"].replace(
                "Museum A = 140", "Museum A = 160"
            )
            check(
                "checked.confirm_accepted",
                decide(c, pid, description=description).status_code == 202,
            )
            stored = ctx.storage.get_owned_submission(pid, 1)
            expected = {
                "checked": True,
                "sha256": hashlib.sha256(stored["image_description"].encode()).hexdigest(),
            }
            for kind, generation in view(c, pid)["generations"].items():
                check(
                    f"checked.{kind}_bound",
                    generation["result"].get("chart_reading") == expected
                    and not generation["reading_mismatch"],
                )
                check(f"checked.{kind}_regen_accepted", regen(c, pid, kind).status_code == 202)
                generation = view(c, pid)["generations"][kind]
                check(
                    f"checked.{kind}_regen_bound",
                    generation["result"].get("chart_reading") == expected
                    and not generation["reading_mismatch"],
                )
            check(
                "checked.corrected_reading_reaches_all_calls",
                all("Museum A = 160" in message for message in fake.messages),
            )
            check("checked.reconfirmation_refused", decide(c, pid).status_code == 409)

            # Change the database after the fake has received its input. The output
            # must retain that input's snapshot and mark itself different from the DB.
            def mutate_after_request():
                with ctx.storage.connect() as conn:
                    conn.execute(
                        "UPDATE submission SET image_description = image_description || ' changed' WHERE id = ?",
                        (stored["id"],),
                    )

            fake.callback = mutate_after_request
            check("snapshot.inflight_regen_accepted", regen(c, pid, "evaluate").status_code == 202)
            current = view(c, pid)
            check(
                "snapshot.input_was_original_confirmed_reading",
                "Museum A = 160" in fake.messages[-1],
            )
            check(
                "snapshot.inflight_result_keeps_original_hash",
                current["generations"]["evaluate"]["result"].get("chart_reading") == expected,
            )
            check(
                "snapshot.all_outputs_flagged_after_drift",
                all(g["reading_mismatch"] for g in current["generations"].values()),
            )
            before_hashes = {
                kind: hashlib.sha256(json.dumps(g["result"], sort_keys=True).encode()).hexdigest()
                for kind, g in current["generations"].items()
            }
            changed = dict(stored, image_description=stored["image_description"] + " changed")
            check(
                "snapshot.invalidated_check_mismatches",
                all(
                    review.reading_mismatch(g["result"], changed)
                    for g in current["generations"].values()
                ),
            )
            after = view(c, pid)
            check(
                "snapshot.view_never_rewrites_results",
                before_hashes
                == {
                    kind: hashlib.sha256(
                        json.dumps(g["result"], sort_keys=True).encode()
                    ).hexdigest()
                    for kind, g in after["generations"].items()
                },
            )

    with tempfile.TemporaryDirectory(prefix="iwa-adjacent-skipped-") as td:
        with fixture(td) as (ctx, c, fake):
            pid = submit(c)
            check("skipped.accepted", decide(c, pid, "skip").status_code == 202)
            check(
                "skipped.every_output_records_unchecked",
                all(
                    g["result"].get("chart_reading") == {"checked": False, "sha256": None}
                    and not g["reading_mismatch"]
                    for g in view(c, pid)["generations"].values()
                ),
            )
            check(
                "skipped.no_chart_data_sent", not any("Museum A = 140" in m for m in fake.messages)
            )
            for task in ("task1", "task2"):
                pid = submit(c, task=task, image=False)
                check(
                    f"no_image.{task}_omits_snapshot",
                    all(
                        "chart_reading" not in g["result"] and not g["reading_mismatch"]
                        for g in view(c, pid)["generations"].values()
                    ),
                )

    check("transport.no_network_attempts", not network_attempts)
    result = {
        "source": str(Path(args.repo).resolve()),
        "passed": sum(row["pass"] for row in checks),
        "total": len(checks),
        "checks": checks,
        "observations": observations,
        "real_calls": 0,
        "network_attempts": len(network_attempts),
        "live_service_touched": False,
        "private_sources_read": False,
        "fixture_mutations": [
            "one synthetic generation.started_at",
            "one synthetic submission.image_description during fake request",
        ],
        "limitations": [
            "No browser rendering",
            "Pre-snapshot results remain unknown; existing .14 records retain legacy banner",
        ],
    }
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "passed": result["passed"],
                "total": result["total"],
                "failures": [row["name"] for row in checks if not row["pass"]],
            },
            ensure_ascii=False,
        )
    )
    return int(result["passed"] != result["total"])


if __name__ == "__main__":
    raise SystemExit(main())
