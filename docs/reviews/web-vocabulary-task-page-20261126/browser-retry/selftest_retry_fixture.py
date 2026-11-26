"""HTTP-only self-check for QA tooling; not a browser acceptance test."""

import json
import re
import subprocess
import sys
import time
from pathlib import Path

import requests

HERE = Path(__file__).resolve().parent
BASE = "http://127.0.0.1:5115"
AUDIT = HERE / "selftest-audit-5115.jsonl"
RESULT = HERE / "selftest-result.json"
assert not AUDIT.exists(), "Preserve prior evidence; choose a fresh audit path before rerunning."

with (HERE / "selftest-server-5115.log").open("w", encoding="utf-8") as log:
    server = subprocess.Popen(
        [sys.executable, str(HERE / "serve_retry_fixture.py"), "--port", "5115",
         "--audit-file", str(AUDIT)], stdout=log, stderr=subprocess.STDOUT,
        cwd=HERE.parents[3],
    )
    try:
        client = requests.Session()
        for attempt in range(40):
            try:
                response = client.get(BASE + "/__qa/stats", timeout=1)
                response.raise_for_status()
                break
            except requests.RequestException:
                if server.poll() is not None:
                    raise RuntimeError("QA server exited before ready")
                time.sleep(0.25)
        else:
            raise RuntimeError("QA server did not become ready")

        page = client.get(BASE + "/__qa/start/writing?fault=transport_drop_once", timeout=5)
        page.raise_for_status()
        boot = json.loads(re.search(r'<script id="pv-boot"[^>]*>(.*?)</script>', page.text, re.S)[1])
        task_id = boot["task_id"]
        api = BASE + f"/api/practice/vocabulary/tasks/{task_id}/"
        headers = {"X-CSRF-Token": boot["csrf_token"],
                   "X-Practice-Identity": boot["identity_key"], "Origin": BASE}

        def post(kind, payload=None):
            result = client.post(api + kind, json=payload or {}, headers=headers, timeout=5)
            result.raise_for_status()
            return result.json()

        def stats(attempt_id=None):
            result = client.get(BASE + "/__qa/stats", params={"task_id": task_id,
                                "attempt_id": attempt_id}, timeout=5)
            result.raise_for_status()
            return result.json()["tasks"][0]

        flow = post("sync")["flow"]
        while flow["phase"] == "familiarity":
            word = next(w for w in flow["familiarity"] if not w["viewed"])
            flow = post("familiarity", {"queue_token": flow["queue_token"],
                                       "word_id": word["word_id"]})["flow"]

        def payload_for(flow, attempt_id, answer):
            q = flow["current_question"]
            return {**{key: q[key] for key in ("learning_question_id", "queue_item_id",
                    "question_id", "word_id", "sense_id", "dimension")},
                    "queue_token": flow["queue_token"], "retry": bool(flow.get("retry")),
                    "attempt_id": attempt_id, "answer": answer,
                    "response_kind": "answer", "supports_correction": True}

        durable_attempt = "qa-transport-drop-first"
        payload = payload_for(flow, durable_attempt, "xxx")
        dropped = False
        network_error_type = None
        try:
            client.post(api + "answers", json=payload, headers=headers, timeout=5)
        except requests.ConnectionError as error:
            dropped = True
            network_error_type = type(error).__name__
        assert dropped, "Expected connection failure, not a synthetic HTTP error reply"
        after_drop = stats(durable_attempt)
        assert after_drop["attempt_record_count"] == 1
        saved_question = next(q for q in after_drop["questions"] if q["first_attempt_id"] == durable_attempt)
        replay = post("answers", payload)
        assert replay["feedback"]["idempotent"] is True
        after_replay = stats(durable_attempt)
        assert after_replay["attempt_record_count"] == 1
        assert after_drop["attempt_record_ids"] == after_replay["attempt_record_ids"]
        assert saved_question == next(q for q in after_replay["questions"] if q["id"] == saved_question["id"])
        assert after_drop["record_count"] == after_replay["record_count"]

        # Exercise settlement audit with real product endpoints, known synthetic
        # words only. This is an HTTP helper check, not browser/IME evidence.
        for index in range(100):
            flow = post("sync")["flow"]
            if flow["completed"]:
                break
            q = flow["current_question"]
            if flow.get("correction_required"):
                post("corrections", {"queue_token": flow["queue_token"],
                     "learning_question_id": q["learning_question_id"],
                     "attempt_id": f"qa-correction-{index}", "answer": q["revealed_answer"]})
            else:
                post("answers", payload_for(flow, f"qa-complete-{index}",
                                             {1: "depend", 2: "focus"}[q["word_id"]]))
        else:
            raise AssertionError("synthetic writing task did not complete")
        settle = {"queue_token": flow["queue_token"], "duration_seconds": 17}
        post("settle", settle)
        before_replay = stats(durable_attempt)
        post("settle", dict(settle, duration_seconds=777))
        final = stats(durable_attempt)
        assert final["settlement_count"] == 1
        assert final["db_task_actual_seconds"] == 17
        assert before_replay["settlements"] == final["settlements"]
        events = [json.loads(line) for line in AUDIT.read_text().splitlines()]
        assert len([e for e in events if e["event"] == "transport_socket_closed"]) == 1
        settled = [e for e in events if e["event"] == "post_committed_response" and e.get("path", "").endswith("/settle")]
        assert [e["request_duration_seconds"] for e in settled] == [17, 777]
        assert [e["db_task_actual_seconds"] for e in settled] == [17, 17]
        RESULT.write_text(json.dumps({
            "ok": True, "kind": "HTTP-only QA wrapper self-check, not browser acceptance",
            "port": 5115, "network_error": network_error_type,
            "successful_server_response_intentionally_lost": True,
            "http_503_used": False, "transport_drop_events": 1,
            "after_drop": after_drop, "after_same_attempt_replay": after_replay,
            "settlement_replay_request_seconds": [17, 777],
            "settlement_replay_database_seconds": [17, 17],
            "settlement_count": final["settlement_count"],
            "product_javascript_modified": False,
        }, ensure_ascii=False, indent=2) + "\n")
        print("PASS: real connection closed after save; same attempt one row; settlement remains 17 seconds")
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()
            server.wait(timeout=5)
        print(f"Stopped self-test server PID {server.pid}; returncode {server.returncode}")
