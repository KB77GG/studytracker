"""Execute production/current question lookup helpers against all Cambridge IDs."""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).with_suffix(".json")
BASE = "40cd8225db1b0a5da188b1dd99d4521dc5853328"


def baseline(path: str) -> str:
    return subprocess.check_output(["git", "show", f"{BASE}:{path}"], cwd=ROOT, text=True)


def function(source: str, name: str) -> str:
    start = source.index(f"function {name}(")
    end = source.index("\n}", start) + 2
    return source[start:end]


def protected(data: dict, units: str) -> list:
    return [
        (q["id"], q["number"])
        for unit in data[units]
        for group in unit.get("groups", [])
        for q in group.get("questions", [])
    ]


runner = r"""
const vm = require('vm');
const fs = require('fs');
const input = JSON.parse(fs.readFileSync(0, 'utf8'));
const output = [];
for (const entry of input) {
  const oldContext = vm.createContext({test: entry.payload, testData: entry.payload});
  const newContext = vm.createContext({test: entry.payload, testData: entry.payload});
  vm.runInContext(entry.oldSource, oldContext);
  vm.runInContext(entry.newSource, newContext);
  const expected = vm.runInContext('allQuestions()', oldContext);
  const oldWrong = [];
  const newWrong = [];
  const numericCollisions = [];
  const ids = new Map();
  const brief = q => q ? {id:q.id, number:q.number, sectionIndex:q.sectionIndex ?? null} : null;
  const same = (a,b) => a && b && String(a.id) === String(b.id) && String(a.number) === String(b.number);
  for (const q of expected) {
    const key = String(entry.subject === 'listening' ? (q.id || q.number || '') : q.id);
    ids.set(key, [...(ids.get(key) || []), q.number]);
    oldContext.lookupKey = key;
    newContext.lookupKey = key;
    const selectedOld = vm.runInContext(`${entry.helper}(lookupKey)`, oldContext);
    const selectedNew = vm.runInContext(`${entry.helper}(lookupKey)`, newContext);
    const row = selected => ({lookup_key:key, expected:brief(q), selected:brief(selected), cross_section:selected ? q.sectionIndex !== selected.sectionIndex : null});
    if (!same(q, selectedOld)) oldWrong.push(row(selectedOld));
    if (!same(q, selectedNew)) newWrong.push(row(selectedNew));
    const collisions = expected.filter(other => String(other.number) === key && !same(q, other));
    if (collisions.length) numericCollisions.push({lookup_key:key, expected:brief(q), same_number_questions:collisions.map(brief)});
  }
  output.push({subject:entry.subject,test_id:entry.payload.id,questions:expected.length,
    missing_ids:expected.filter(q => !q.id).length,
    duplicate_lookup_keys:[...ids].filter(([_,numbers]) => numbers.length > 1).map(([key,numbers]) => ({key,numbers})),
    id_number_collisions:numericCollisions,old_wrong:oldWrong,new_wrong:newWrong});
}
process.stdout.write(JSON.stringify(output));
"""


def main() -> None:
    entries = []
    helpers = {}
    for subject, helper in [("listening", "questionForId"), ("reading", "questionById")]:
        template = f"templates/{subject}/test_practice.html"
        old = baseline(template)
        new = (ROOT / template).read_text()
        old_source = function(old, "allQuestions") + "\n" + function(old, helper)
        new_source = function(new, "allQuestions") + "\n" + function(new, helper)
        helpers[subject] = {
            "template": template,
            "old_source": old_source,
            "new_source": new_source,
            "new_source_sha256": hashlib.sha256(new_source.encode()).hexdigest(),
        }
        for path in sorted((ROOT / f"static/{subject}_tests").glob("ielts*.json")):
            if not re.fullmatch(
                r"ielts(?:[4-9]|1[0-9]|2[01])_test\d+(?:_reading)?\.json", path.name
            ):
                continue
            relative = str(path.relative_to(ROOT))
            payload = json.loads(baseline(relative))
            current = json.loads(path.read_text())
            units = "sections" if subject == "listening" else "passages"
            assert protected(payload, units) == protected(current, units), relative
            entries.append(
                {
                    "subject": subject,
                    "helper": helper,
                    "payload": payload,
                    "oldSource": old_source,
                    "newSource": new_source,
                }
            )
    results = json.loads(
        subprocess.check_output(["node", "-e", runner], input=json.dumps(entries), text=True)
    )
    summary = {}
    for subject in helpers:
        rows = [row for row in results if row["subject"] == subject]
        wrong = [q for row in rows for q in row["old_wrong"]]
        affected = [row for row in rows if row["old_wrong"]]
        by_book = Counter()
        for row in affected:
            book = re.match(r"ielts(\d+)", row["test_id"]).group(1)
            by_book[book] += len(row["old_wrong"])
        summary[subject] = {
            "tests": len(rows),
            "questions": sum(row["questions"] for row in rows),
            "missing_ids": sum(row["missing_ids"] for row in rows),
            "duplicate_lookup_keys": sum(len(row["duplicate_lookup_keys"]) for row in rows),
            "potential_id_number_collision_questions": sum(
                len(row["id_number_collisions"]) for row in rows
            ),
            "old_wrong_lookup_questions": len(wrong),
            "old_wrong_lookup_tests": len(affected),
            "old_wrong_cross_section_questions": sum(bool(q["cross_section"]) for q in wrong),
            "old_wrong_questions_by_book": dict(
                sorted(by_book.items(), key=lambda pair: int(pair[0]))
            ),
            "old_wrong_questions_by_test": {
                row["test_id"]: len(row["old_wrong"]) for row in affected
            },
            "new_wrong_lookup_questions": sum(len(row["new_wrong"]) for row in rows),
            "new_wrong_lookup_tests": sum(bool(row["new_wrong"]) for row in rows),
        }
    report = {
        "baseline": BASE,
        "data_source": "git baseline; all current ID/number/order signatures asserted equal",
        "method": "Extract and directly execute actual old and current JavaScript helpers in Node vm; call each question's emitted UI lookup key, compare returned id and number with expected question.",
        "helpers": helpers,
        "summary": summary,
        "tests": results,
    }
    OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
