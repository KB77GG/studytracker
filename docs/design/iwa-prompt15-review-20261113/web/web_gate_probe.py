"""Offline .15 web gate review, using temporary databases and fake clients only.

Usage: .venv/bin/python -B .../web_gate_probe.py --repo NEW --old-repo OLD --out RESULT
No keys/configs or live service are read. One subprocess seeds a genuine old-format
ready submission using OLD, then NEW opens that same temporary DB.
"""

from __future__ import annotations

import argparse
import concurrent.futures
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
from pathlib import Path


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--repo", required=True)
    p.add_argument("--old-repo")
    p.add_argument("--out")
    p.add_argument("--seed")
    a = p.parse_args()
    sys.path.insert(0, str(Path(a.repo).resolve()))

    # The transport cannot run even if a regression tried to create a real client.
    def blocked(*args, **kwargs):
        raise AssertionError("Network prohibited by offline review")

    socket.create_connection = blocked
    from tools.ielts_writing_ai import access, create_app, prompts
    from tools.ielts_writing_ai.llm import FakeClient
    from tools.ielts_writing_ai.tests.helpers import PNG_BYTES, TASK2_ESSAY, settings_for
    from tools.ielts_writing_ai.tests.test_visual import StaticVision, reading

    class Recorder(FakeClient):
        def __init__(self):
            super().__init__()
            self.observed = []

        def complete(self, messages, **kwargs):
            self.observed.append(
                {
                    "kind": kwargs.get("context", {}).get("kind"),
                    "messages": json.dumps(messages, ensure_ascii=False),
                }
            )
            return super().complete(messages, **kwargs)

    def new_app(root, recorder):
        app = create_app(
            settings_for(str(root)), client=recorder, vision_client=StaticVision(reading())
        )
        app.logger.disabled = True
        return app

    def add_user(app, name="A"):
        code = access.generate_code()
        store = app.extensions["iwa"].storage
        uid = store.create_user(
            name=name,
            code_hash=access.hash_code(code),
            code_hint=access.code_hint(code),
            daily_limit=99,
        )
        return uid, code

    def login(app, code):
        c = app.test_client()
        html = c.get("/login").get_data(as_text=True)
        csrf = re.search(r'data-csrf="([^"]+)"', html).group(1)
        r = c.post("/api/login", json={"code": code}, headers={"X-IWA-CSRF": csrf})
        assert r.status_code == 200
        c.csrf = r.get_json()["csrf"]
        return c

    def submit(c):
        r = c.post(
            "/api/submissions",
            data={
                "task_type": "task1",
                "prompt_text": "The chart below shows museum visitor numbers in 2020.",
                "essay_text": TASK2_ESSAY,
                "target_band": "7.0",
                "image": (io.BytesIO(PNG_BYTES), "chart.png"),
            },
            headers={"X-IWA-CSRF": c.csrf},
            content_type="multipart/form-data",
        )
        assert r.status_code == 201
        return r.get_json()["public_id"]

    def view(c, pid):
        return c.get("/api/submissions/" + pid).get_json()["submission"]

    def decide(c, pid, payload, csrf=True):
        return c.post(
            "/api/submissions/" + pid + "/image-check",
            json=payload,
            headers={"X-IWA-CSRF": c.csrf} if csrf else {},
        )

    if a.seed:
        root = Path(a.seed)
        recorder = Recorder()
        app = new_app(root, recorder)
        uid, code = add_user(app)
        c = login(app, code)
        pid = submit(c)
        v = view(c, pid)
        assert all(g["status"] == "ready" for g in v["generations"].values())
        meta = {
            "uid": uid,
            "code": code,
            "pid": pid,
            "generation_ids": {k: g["id"] for k, g in v["generations"].items()},
            "result_sha256": hashlib.sha256(
                json.dumps(v["generations"]["evaluate"]["result"], sort_keys=True).encode()
            ).hexdigest(),
            "old_overall": v["generations"]["evaluate"]["result"]["overall_band"],
        }
        path = root / "seed.private.json"
        path.write_text(json.dumps(meta))
        path.chmod(0o600)
        app.extensions["iwa"].close()
        return 0

    checks = []
    observations = {}
    findings = []

    def check(name, condition):
        checks.append({"name": name, "pass": bool(condition)})

    with tempfile.TemporaryDirectory(prefix="iwa-p15-web-independent-") as td:
        root = Path(td)
        recorder = Recorder()
        app = new_app(root / "normal", recorder)
        ctx = app.extensions["iwa"]
        uid, code = add_user(app)
        c = login(app, code)
        pid = submit(c)
        v = view(c, pid)
        original = v["image"]["description"]
        check("waiting_has_ready_image", v["image"]["status"] == "ready")
        check("waiting_requires_check", v["image"]["awaiting_check"])
        check("no_generation_before_check", recorder.observed == [])
        check("all_three_queued", {g["status"] for g in v["generations"].values()} == {"queued"})
        check("quota_reserved_once", ctx.storage.usage_today(uid) == 3)
        r = decide(c, pid, {"action": "confirm", "description": original}, csrf=False)
        check("csrf_enforced", r.status_code == 403)
        uid_b, code_b = add_user(app, "B")
        other = login(app, code_b)
        check(
            "other_user_cannot_confirm", decide(other, pid, {"action": "skip"}).status_code == 404
        )
        check("other_user_cannot_view", other.get("/api/submissions/" + pid).status_code == 404)
        for kind in ["evaluate", "refine", "rewrite"]:
            r = c.post(f"/api/submissions/{pid}/generations/{kind}", headers={"X-IWA-CSRF": c.csrf})
            check("waiting_regenerate_" + kind, r.status_code == 409)
        check("waiting_regeneration_no_quota", ctx.storage.usage_today(uid) == 3)
        # Restart the exact temporary app while waiting, retaining its session secret.
        ctx.close()
        app = new_app(root / "normal", recorder)
        ctx = app.extensions["iwa"]
        c = login(app, code)
        check("restart_keeps_waiting", view(c, pid)["image"]["awaiting_check"])
        check(
            "restart_keeps_queued",
            {g["status"] for g in view(c, pid)["generations"].values()} == {"queued"},
        )
        changed = original.replace("Museum A = 140", "Museum A = 160")
        r = decide(c, pid, {"action": "confirm", "description": changed})
        v = view(c, pid)
        check("corrected_confirm_accepted", r.status_code == 202)
        check(
            "three_kinds_started",
            {x["kind"] for x in recorder.observed} == {"evaluate", "refine", "rewrite"},
        )
        check(
            "corrected_reading_used_all",
            all(
                "Museum A = 160" in x["messages"] and "Museum A = 140" not in x["messages"]
                for x in recorder.observed
            ),
        )
        check(
            "confirmed_ta_scored",
            v["generations"]["evaluate"]["result"]["criteria"][0]["state"] == "scored",
        )
        check(
            "confirmed_overall_scored",
            v["generations"]["evaluate"]["result"]["overall_band"] is not None,
        )
        row = ctx.storage.get_owned_submission(pid, uid)
        audit = prompts.image_check(row)
        check("model_original_preserved", audit["model_description"] == original)
        check("modified_description_stored", row["image_description"] == changed)
        check("confirmation_no_extra_quota", ctx.storage.usage_today(uid) == 3)
        before_calls = len(recorder.observed)
        check(
            "repeat_confirm_refused",
            decide(c, pid, {"action": "confirm", "description": original}).status_code == 409,
        )
        check("repeat_skip_refused", decide(c, pid, {"action": "skip"}).status_code == 409)
        check("repeat_no_call", len(recorder.observed) == before_calls)
        check(
            "repeat_keeps_correction",
            ctx.storage.get_owned_submission(pid, uid)["image_description"] == changed,
        )

        pid2 = submit(c)
        recorder.observed.clear()
        r = decide(c, pid2, {"action": "skip"})
        v = view(c, pid2)
        check("skip_accepted", r.status_code == 202)
        check(
            "skip_all_three_generated",
            {x["kind"] for x in recorder.observed} == {"evaluate", "refine", "rewrite"},
        )
        check(
            "skip_all_prompts_without_visual",
            all(
                "visual_summary" not in x["messages"] and "Museum A = 140" not in x["messages"]
                for x in recorder.observed
            ),
        )
        ev = v["generations"]["evaluate"]["result"]
        check("skip_ta_not_assessable", ev["criteria"][0]["state"] == "not_assessable")
        check("skip_overall_null", ev["overall_band"] is None)
        check(
            "skip_copy_states_limitation",
            "未核对题图读数"
            in json.dumps(v["generations"]["evaluate"]["copy"], ensure_ascii=False),
        )

        pid3 = submit(c)
        recorder.observed.clear()
        c1 = login(app, code)
        c2 = login(app, code)
        barrier = threading.Barrier(2)
        original_set = ctx.storage.set_image_check
        claims = []
        original_claim = ctx.storage.claim_generation

        def counted_claim(gid, **kwargs):
            ok = original_claim(gid, **kwargs)
            if ok:
                claims.append(gid)
            return ok

        ctx.storage.claim_generation = counted_claim

        def simultaneous(*args, **kwargs):
            barrier.wait(timeout=10)
            return original_set(*args, **kwargs)

        ctx.storage.set_image_check = simultaneous
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            futures = [
                pool.submit(decide, client, pid3, {"action": "confirm", "description": original})
                for client in [c1, c2]
            ]
            statuses = sorted(f.result().status_code for f in futures)
        ctx.storage.set_image_check = original_set
        check("concurrent_one_winner", statuses == [202, 409])
        check("concurrent_three_unique_generation_claims", len(claims) == len(set(claims)) == 3)
        ctx.storage.claim_generation = original_claim
        check("concurrent_quota_reserved_once", ctx.storage.usage_today(uid) == 9)

        pid4 = submit(c)
        recorder.observed.clear()
        malformed = []
        for name, payload in [
            ("list", ["confirm"]),
            ("number", 1),
            ("description_list", {"action": "confirm", "description": ["x"]}),
            ("description_number", {"action": "confirm", "description": 7}),
        ]:
            status = decide(c, pid4, payload).status_code
            malformed.append({"case": name, "status": status})
        observations["malformed_payloads"] = malformed
        check("malformed_payload_no_calls", recorder.observed == [])
        check("malformed_payload_no_mutation", view(c, pid4)["image"]["awaiting_check"])
        if any(x["status"] >= 500 for x in malformed):
            findings.append(
                {
                    "id": "WEB-P3-1",
                    "severity": "P3",
                    "title": "New image-check API returns 500 on non-object JSON or non-string description",
                    "cases": malformed,
                }
            )
        ctx.close()

        legacy = root / "legacy"
        env = {k: v for k, v in os.environ.items() if not k.startswith("IWA_")}
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        subprocess.run(
            [
                sys.executable,
                "-B",
                str(Path(__file__).resolve()),
                "--repo",
                a.old_repo,
                "--seed",
                str(legacy),
            ],
            check=True,
            env=env,
            cwd=td,
            capture_output=True,
            text=True,
        )
        meta = json.loads((legacy / "seed.private.json").read_text())
        recorder = Recorder()
        app = new_app(legacy, recorder)
        ctx = app.extensions["iwa"]
        c = login(app, meta["code"])
        v = view(c, meta["pid"])
        before = v["generations"]["evaluate"]["result"]
        check(
            "legacy_ready_result_preserved_on_open",
            hashlib.sha256(json.dumps(before, sort_keys=True).encode()).hexdigest()
            == meta["result_sha256"],
        )
        initial = {
            "awaiting": v["image"]["awaiting_check"],
            "overall": before["overall_band"],
            "status": v["generations"]["evaluate"]["status"],
            "version": v["generations"]["evaluate"]["prompt_version"],
        }
        r = decide(
            c,
            meta["pid"],
            {
                "action": "confirm",
                "description": v["image"]["check_text"].replace("Museum A = 140", "Museum A = 160"),
            },
        )
        v = view(c, meta["pid"])
        after = v["generations"]["evaluate"]["result"]
        observations["legacy_correction"] = {
            "before": initial,
            "confirm_status": r.status_code,
            "edited": v["image"]["check"]["edited"],
            "calls_after_confirm": len(recorder.observed),
            "new_description_has_correction": "Museum A = 160" in v["image"]["description"],
            "generation_ids_unchanged": {k: g["id"] for k, g in v["generations"].items()}
            == meta["generation_ids"],
            "evaluation_unchanged": before == after,
            "overall": after["overall_band"],
            "version": v["generations"]["evaluate"]["prompt_version"],
        }
        if (
            r.status_code == 202
            and v["image"]["check"]["edited"]
            and before == after
            and not recorder.observed
        ):
            findings.append(
                {
                    "id": "WEB-P2-1",
                    "severity": "P2",
                    "title": "Correcting a migrated completed chart reading relabels it as checked but leaves all existing results bound to the old reading",
                    "evidence": observations["legacy_correction"],
                }
            )
        ctx.close()

    result = {
        "source": str(Path(a.repo).resolve()),
        "checks": checks,
        "passed": sum(x["pass"] for x in checks),
        "total": len(checks),
        "findings": findings,
        "observations": observations,
        "paid_calls": 0,
        "live_service_touched": False,
        "private_sources_read": False,
    }
    if a.out:
        out = Path(a.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps({k: v for k, v in result.items() if k != "checks"}, ensure_ascii=False, indent=2)
    )
    return int(bool(findings) or any(not x["pass"] for x in checks))


if __name__ == "__main__":
    raise SystemExit(main())
