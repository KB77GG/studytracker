"""Read-only whole-bank evidence verification for the Cambridge display repair."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from services.mock_exam_review import build_question_index  # noqa: E402
from services.question_type_review import derive_listening_payload, reading_evidence  # noqa: E402

report = {
    "listening": {"tests": 0, "questions": 0, "with_evidence": 0, "unavailable": []},
    "reading": {"tests": 0, "questions": 0, "with_source_evidence": 0, "with_mock_evidence": 0},
    "c18t1": [],
    "boundary": "Corrected JSON and sidecars; ignored MP3 files absent. No live media verification.",
}
for path in sorted((ROOT / "static/listening_tests").glob("ielts*_test*.json")):
    payload = json.loads(path.read_text())
    derived = derive_listening_payload(payload, static_root=ROOT / "static", audio_root=ROOT / "static/listening")
    report["listening"]["tests"] += 1
    for section in derived["sections"]:
        for group in section["groups"]:
            for question in group["questions"]:
                review = question["audio_review"]
                report["listening"]["questions"] += 1
                report["listening"]["with_evidence"] += bool(review.get("evidence"))
                if not review["available"]:
                    report["listening"]["unavailable"].append({"test": path.stem, "number": question["number"], "reason": review.get("reason")})
                if path.stem == "ielts18_test1" and question["number"] in (14, 15, 29, 30):
                    report["c18t1"].append({"number": question["number"], "clip": [review.get("start"), review.get("end")], "evidence": [row["text"] for row in review.get("evidence", [])]})
for path in sorted((ROOT / "static/reading_tests").glob("ielts*_test*_reading.json")):
    payload = json.loads(path.read_text())
    index = build_question_index(payload, "reading")
    report["reading"]["tests"] += 1
    for passage in payload["passages"]:
        for group in passage["groups"]:
            for question in group["questions"]:
                report["reading"]["questions"] += 1
                report["reading"]["with_source_evidence"] += bool(reading_evidence(question))
                report["reading"]["with_mock_evidence"] += bool(index[str(question["id"])]["evidence"])
Path(__file__).with_name("presentation-corpus.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({key: value for key, value in report.items() if key != "c18t1"}, ensure_ascii=False, indent=2))
