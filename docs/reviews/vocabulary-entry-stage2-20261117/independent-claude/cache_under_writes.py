"""Synthetic-only: does the 30 s display-count cache hold while other students write?

``_DueCache`` publishes a freshly loaded count only if its *global* version did
not change while the loader ran, and every vocabulary write by any student
bumps that version.  This measures the warm-hit rate of student A's home
summary while other students keep answering review questions.

Usage (cwd = repository): python -B <this file> [--backlog 2400] [--output f.json]
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "vocabulary-flow-latency-20261116"))
import probe_vocabulary_flow as flow  # noqa: E402

SUMMARY = "/api/miniprogram/student/vocabulary-review/summary"


def measure(h, reader, writers, write_gap_s, rounds):
    """Reader loads the summary twice in a row per round; was the second one warm?"""

    stop = threading.Event()
    writes = {"n": 0}

    def writer(student):
        # Keep answering batch after batch (answer 20, settle, claim the next) until told to stop.
        while not stop.is_set():
            session = h.call("c", "GET", "/api/miniprogram/student/vocabulary-review/today", student)["json"] or {}
            sid, token = session.get("session_id"), session.get("session_token")
            if not sid:
                return
            for item in session["items"]:
                if stop.is_set():
                    return
                if item.get("answered"):
                    continue
                h.call("a", "POST", f"/api/miniprogram/student/vocabulary-review/sessions/{sid}/answers", student, {
                    "session_token": token, "review_item_id": item["review_item_id"],
                    "question_id": item["question_id"], "word_id": item["word_id"], "sense_id": item["sense_id"],
                    "dimension": item["dimension"], "input_mode": "native",
                    "answer": h.stored_answer("vocabulary_review_item", item["review_item_id"]),
                    "attempt_id": f"cw:{sid}:{item['review_item_id']}",
                })
                writes["n"] += 1
                stop.wait(write_gap_s)
            h.call("t", "POST", f"/api/miniprogram/student/vocabulary-review/sessions/{sid}/settle", student,
                   {"session_token": token, "queue_token": session.get("queue_token"), "duration_seconds": 0})

    threads = [threading.Thread(target=writer, args=(s,)) for s in writers]
    for thread in threads:
        thread.start()
    time.sleep(0.3 if writers else 0)
    first, second = [], []
    for _ in range(rounds):
        # Start each round cold for the reader without touching other users.
        with h.app.app_context():
            from services.vocabulary_due_cache import _cache
            _cache().invalidate({reader["id"]})
        first.append(h.call("s", "GET", SUMMARY, reader)["elapsed_s"])
        second.append(h.call("s", "GET", SUMMARY, reader)["elapsed_s"])
    stop.set()
    for thread in threads:
        thread.join(timeout=60)
    cold = statistics.median(first)
    warm_hits = sum(1 for value in second if value < cold / 5)
    return {
        "other_students_writing": len(writers),
        "seconds_between_each_students_answers": write_gap_s if writers else None,
        "answers_written_during_run": writes["n"],
        "rounds": rounds,
        "cold_summary_median_ms": round(cold * 1000, 1),
        "second_read_median_ms": round(statistics.median(second) * 1000, 1),
        "second_read_served_from_cache": warm_hits,
        "second_read_recomputed": rounds - warm_hits,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default=".")
    parser.add_argument("--backlog", type=int, default=2400)
    parser.add_argument("--rounds", type=int, default=12)
    parser.add_argument("--output")
    args = parser.parse_args()
    repo = Path(args.repo).resolve()
    sys.path.insert(0, str(repo))
    report = {"synthetic_only": True, "reader_due_backlog_words": args.backlog, "cases": []}
    with tempfile.TemporaryDirectory(prefix="studytracker-cachewrites-") as tmp:
        h = flow.Harness(repo, Path(tmp))
        try:
            reader = h.seed_student(args.backlog, "context")
            for count, gap in ((0, 0.0), (1, 3.0), (3, 3.0), (6, 3.0)):
                writers = [h.seed_student(400, "meaning") for _ in range(count)]
                report["cases"].append(measure(h, reader, writers, gap, args.rounds))
        finally:
            h.close()
    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
