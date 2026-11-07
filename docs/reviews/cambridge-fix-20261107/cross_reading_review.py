"""Independent review of the reading agent's narrow manifest against source."""
import hashlib
import html
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RAW = Path("/Users/zhouxin/Desktop/studytracker/data/idictation_reading/raw.json")
manifest_path = ROOT / "data/cambridge_content_corrections/reading.json"
manifest = json.loads(manifest_path.read_text())
raw = json.loads(RAW.read_text())
questions, introductions = [], []
for test, correction in manifest["tests"].items():
    path = ROOT / "static/reading_tests" / f"{test}.json"
    data = json.loads(path.read_text())
    baseline = json.loads(
        subprocess.check_output(["git", "show", f"40cd8225:static/reading_tests/{test}.json"], cwd=ROOT)
    )
    for passage in data["passages"]:
        previous = next(p for p in baseline["passages"] if p["id"] == passage["id"])
        by_number = {q["number"]: q for g in previous["groups"] for q in g["questions"]}
        for group in passage["groups"]:
            for question in group["questions"]:
                edits = correction.get("questions", {}).get(str(question["number"]), {})
                assert {k: v for k, v in question.items() if k not in edits} == {
                    k: v for k, v in by_number[question["number"]].items() if k not in edits
                }
                if not edits:
                    continue
                assert not (set(edits) - {"analysis", "central_sentences", "locating_words"})
                for evidence in question["central_sentences"]:
                    target = evidence["target_para"]
                    paragraphs = passage["content"]["paragraphs"]
                    paragraph = paragraphs[target] if isinstance(target, int) else next(p for p in paragraphs if p["label"] == target)
                    assert paragraph["text"].find(evidence["sentence"]) == evidence["index"]
                    assert len(evidence["sentence"]) == evidence["length"]
                questions.append({"test": test, "question": question["number"], "answer_unchanged": question["answer"], "evidence_positions_exact": True})
        if str(passage["passage"]) not in correction.get("passages", {}):
            assert passage["content"] == previous["content"]
            continue
        source = raw["parts"]["academic"][str(passage["part_id"])]
        source = source.get("values") or source.get("data") or source
        introduction = html.unescape(source["content"]["pre-A"]).strip()
        assert passage["content"]["paragraphs"][0] == {"label": "pre-A", "text": introduction}
        assert passage["content"]["paragraphs"][1:] == previous["content"]["paragraphs"]
        introductions.append({"test": test, "passage": passage["passage"], "matches_source": True, "existing_paragraphs_unchanged": True})

result = {"manifest_sha256": hashlib.sha256(manifest_path.read_bytes()).hexdigest(),
          "raw_sha256": hashlib.sha256(RAW.read_bytes()).hexdigest(),
          "questions": questions, "introductions": introductions}
Path(__file__).with_suffix(".json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
print(json.dumps({"questions": len(questions), "introductions": len(introductions), "status": "pass"}))
