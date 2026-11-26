"""Read public current data, compose all 20 ranked sets, grade/render, no DB/network."""

import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from services.exam_sprint_catalog import load_sprint_catalog
from services.exam_sprint_papers import compose_sprint_paper, load_sprint_paper, save_sprint_paper
from services.ielts_exam_payload import build_simulation_payload
from services.ielts_practice_scoring import grade_listening_test_answers, grade_reading_test_answers


def canonical(paper, subject):
    answers = {}
    for unit in paper["sections" if subject == "listening" else "passages"]:
        for group in unit["groups"]:
            questions = group["questions"]
            first = str(questions[0]["answer"])
            shared = [x.strip() for x in first.split(",")]
            combined = (
                len(shared) > 1
                and len(shared) == len(questions)
                and all(re.fullmatch("[A-Z]", x) for x in shared)
                and all(q["answer"] == first for q in questions)
            )
            for index, q in enumerate(questions):
                answers[q["id"]] = shared[index] if combined else str(q["answer"]).split("/")[0]
    return answers


def main():
    checks = []
    rendered = []
    for subject in ("listening", "reading"):
        catalog = load_sprint_catalog(ROOT, subject)
        assert catalog["total"] == (80 if subject == "listening" else 60), catalog["total"]
        for rank in range(20):
            selected = [g["items"][rank]["selection_id"] for g in catalog["groups"]]
            paper = compose_sprint_paper(ROOT, subject, selected, catalog=catalog)
            grader = (
                grade_listening_test_answers
                if subject == "listening"
                else grade_reading_test_answers
            )
            result = grader(paper, canonical(paper, subject))
            assert result["correct"] == result["total"] == 40, (
                subject,
                rank,
                result["wrong_numbers"],
            )
            with (
                tempfile.TemporaryDirectory() as temporary,
                patch.dict(os.environ, {"EXAM_SPRINT_STATE_DIR": temporary}),
            ):
                identifier = save_sprint_paper(ROOT, paper)
                loaded = load_sprint_paper(ROOT, subject, identifier)[0]
                assert loaded["sources"] == paper["sources"]
                Path(temporary, "current.json").write_text("{}")
                assert load_sprint_paper(ROOT, subject, identifier)[0] == loaded
            rendered.append(
                {"subject": subject, "payload": build_simulation_payload(loaded, subject)}
            )
            checks.append(
                {"subject": subject, "rank": rank + 1, "total": 40, "correct": 40, "id": identifier}
            )
    node = subprocess.run(
        ["node", str(Path(__file__).with_name("verify_composed_render.js"))],
        input=json.dumps(rendered),
        text=True,
        capture_output=True,
    )
    assert node.returncode == 0, node.stderr
    report = {
        "passed": True,
        "papers": len(checks),
        "questions": sum(c["total"] for c in checks),
        "renderer": json.loads(node.stdout),
        "checks": checks,
        "scope": "Local public files only; no source API or learner DB writes.",
    }
    Path(__file__).with_name("current-papers-acceptance.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    print(json.dumps({k: v for k, v in report.items() if k != "checks"}))


if __name__ == "__main__":
    main()
