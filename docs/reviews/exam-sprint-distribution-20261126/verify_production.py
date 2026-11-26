"""Production read-only code/catalog/composition acceptance; no app or DB import."""

import argparse
import json
import subprocess
from urllib.request import urlopen

parser = argparse.ArgumentParser()
parser.add_argument("--expected-head", required=True)
args = parser.parse_args()
head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
assert head == args.expected_head, (head, args.expected_head)
tracked = subprocess.check_output(
    ["git", "status", "--porcelain", "--untracked-files=no"], text=True
).strip()
assert not tracked, tracked
service = subprocess.check_output(
    ["systemctl", "show", "studytracker", "--property=ActiveState,SubState,NRestarts,MainPID"],
    text=True,
).strip()
assert "ActiveState=active" in service and "SubState=running" in service
properties = dict(line.split("=", 1) for line in service.splitlines() if "=" in line)
workers = subprocess.check_output(["pgrep", "-P", properties["MainPID"]], text=True).split()
assert len(workers) == 1, len(workers)
from services.exam_sprint_catalog import load_sprint_catalog
from services.exam_sprint_papers import compose_sprint_paper
from services.ielts_exam_payload import build_simulation_payload
from services.ielts_practice_scoring import grade_listening_test_answers, grade_reading_test_answers

rows = []
for subject, total in [("listening", 80), ("reading", 60)]:
    catalog = load_sprint_catalog(".", subject)
    assert catalog["total"] == total, (subject, catalog["total"])
    paper = compose_sprint_paper(
        ".", subject, [g["items"][0]["selection_id"] for g in catalog["groups"]], catalog=catalog
    )
    units = paper["sections" if subject == "listening" else "passages"]
    answers = {}
    for unit in units:
        for group in unit["groups"]:
            questions = group["questions"]
            values = str(questions[0]["answer"]).split(",")
            shared = (
                len(values) > 1
                and len(values) == len(questions)
                and all(q["answer"] == questions[0]["answer"] for q in questions)
            )
            for index, q in enumerate(questions):
                answers[q["id"]] = values[index] if shared else str(q["answer"]).split("/")[0]
    grade = (
        grade_listening_test_answers if subject == "listening" else grade_reading_test_answers
    )(paper, answers)
    assert grade["correct"] == grade["total"] == 40
    safe = json.dumps(build_simulation_payload(paper, subject))
    assert '"answer":' not in safe and '"analysis":' not in safe
    with urlopen("http://127.0.0.1:5002/practice/sprint/" + subject, timeout=15) as response:
        html = response.read().decode()
        assert response.status == 200
    assert catalog["updated_at_label"] in html
    rows.append(
        {
            "subject": subject,
            "ready": total,
            "edition": catalog["updated_at_label"],
            "correct": grade["correct"],
            "total": grade["total"],
            "http": 200,
        }
    )
print(
    json.dumps(
        {
            "passed": True,
            "head": head,
            "tracked_clean": True,
            "service": service,
            "workers": len(workers),
            "catalogs": rows,
            "scope": "Read-only files and anonymous loopback GET; no app/model import, no learner writes, no saved mock.",
        },
        ensure_ascii=False,
        indent=2,
    )
)
