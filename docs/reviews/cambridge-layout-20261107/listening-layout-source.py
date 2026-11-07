"""Compare source layout and before/after renderer ownership without app/DB access."""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
BASE = "be9b122f"
RAW = Path("/Users/zhouxin/Desktop/studytracker/data/idictation_xyy_listening/raw.json")
JS = r"""
const fs = require('fs'), vm = require('vm');
const source = JSON.parse(fs.readFileSync(0, 'utf8'));
const sandbox = {module: {exports: {}}};
vm.runInNewContext(source, sandbox);
const r = sandbox.module.exports;
const norm = text => r.plainText(text).replace(/[^\p{L}\p{N}]+/gu, ' ').trim().toLowerCase();
const out = {forms: 0, questions: 0, shared_clusters: 0, shared_questions: 0,
  shared_multi_source_clusters: 0, checked_suffixes: 0, columns: [], suffix_mismatches: [],
  shared_rows: [], split_static_rows: [], repeated_previous_line_candidates: []};
for (const filename of fs.readdirSync('static/listening_tests').filter(n => /^ielts\d+_test\d+\.json$/.test(n))) {
  const paper = JSON.parse(fs.readFileSync('static/listening_tests/' + filename));
  for (const section of paper.sections) for (const group of section.groups) {
    if (!r.isFormGroup(group)) continue;
    const ref = {test: paper.id, section: section.section, group: group.group_id};
    const fields = r.formFields(group), html = r.renderForm(group, q => `[Q${q.number}]`);
    const rows = [...html.matchAll(/<div class="practice-form__(?:shared-source|content)">([\s\S]*?)<\/div>/g)].map(m => m[1]);
    const facts = [...html.matchAll(/<div class="practice-form__(?:line|subheading)">([^<]*)<\/div>/g)].map(m => r.plainText(m[1]));
    out.forms += 1; out.questions += fields.length;
    if (html.includes('data-layout="columns"')) out.columns.push({...ref, questions: fields.map(f => f.question.number)});
    for (const field of fields) {
      if (!field.target) continue;
      const target = r.targetSource(field), last = [...target.matchAll(/\$(\d+)\$/g)].at(-1);
      const row = rows.find(row => row.includes(`[Q${field.question.number}]`));
      if (last && last[1] === String(field.question.id)) {
        const suffix = norm(target.slice(last.index + last[0].length));
        if (suffix) {
          out.checked_suffixes += 1;
          if (!norm(row).includes(suffix)) out.suffix_mismatches.push({...ref, number: field.question.number,
            source_line: field.target.line, source: target, suffix, rendered_row: r.plainText(row)});
        }
      }
      const previous = field.cells[field.targetIndex - 1];
      if (previous && previous.line < field.target.line && !/\$\d+\$/.test(previous.raw)) {
        const previousText = norm(previous.text);
        if (previousText.length > 30 && norm(field.question.title).startsWith(previousText)
          && norm(html).split(previousText).length > 2) out.repeated_previous_line_candidates.push({
            ...ref, number: field.question.number, previous: previous.text, title: field.question.title});
      }
    }
    const cells = fields[0].cells;
    const lineIndexes = [...new Set(cells.map(cell => cell.line))];
    for (const line of lineIndexes) {
      const sourceCells = cells.filter(cell => cell.line === line);
      if (sourceCells.length < 2 || sourceCells.some(cell => /\$\d+\$/.test(cell.raw))) continue;
      if (!/:$/.test(sourceCells[0].text.trim())) continue;
      if (sourceCells.every(cell => facts.includes(cell.text))) out.split_static_rows.push({
        ...ref, line, cells: sourceCells.map(cell => cell.text)});
    }
    let offset = 0;
    const sharedRows = [...html.matchAll(/<div class="practice-form__shared-source">([\s\S]*?)<\/div>/g)].map(m => r.plainText(m[1]));
    for (const cluster of r.sharedFormClusters(fields)) {
      const targets = [];
      for (const field of cluster.fields) if (!targets.length || targets.at(-1).index !== field.targetIndex)
        targets.push({index: field.targetIndex, line: field.target?.line, source: r.targetSource(field)});
      out.shared_clusters += 1; out.shared_questions += cluster.fields.length;
      if (targets.length > 1) out.shared_multi_source_clusters += 1;
      out.shared_rows.push({...ref, numbers: cluster.fields.map(f => f.question.number),
        source: targets, rendered_rows: sharedRows.slice(offset, offset + targets.length)});
      offset += targets.length;
    }
  }
}
console.log(JSON.stringify(out));
"""


def renderer_audit(source: str) -> dict:
    return json.loads(
        subprocess.check_output(["node", "-e", JS], input=json.dumps(source).encode(), cwd=ROOT)
    )


def main() -> None:
    raw_data = RAW.read_bytes()
    raw = json.loads(raw_data)["parts"]
    source_comparison = {"tests": 0, "groups": 0, "tables": 0, "coordinate_refs": 0}
    differences = []
    invalid_references = []
    for path in (ROOT / "static/listening_tests").glob("ielts*.json"):
        paper = json.loads(path.read_text())
        source_comparison["tests"] += 1
        for section in paper["sections"]:
            part = raw[str(section["part_id"])]
            part = part.get("values") or part.get("data") or part
            groups = {str(group["group_id"]): group for group in part["question"]}
            for group in section["groups"]:
                source_comparison["groups"] += 1
                ref = {
                    "test": paper["id"],
                    "section": section["section"],
                    "group": group["group_id"],
                }
                for key in ("collect", "table"):
                    if (group.get(key) or None) != (
                        groups[str(group["group_id"])].get(key) or None
                    ):
                        differences.append({**ref, "field": key})
                table = group.get("table")
                if not table:
                    continue
                source_comparison["tables"] += 1
                rows = table.get("content") or []
                for row_index, row in enumerate(rows):
                    for column_index, value in enumerate(row if isinstance(row, list) else [row]):
                        if not (
                            isinstance(value, list)
                            and len(value) == 2
                            and all(isinstance(item, int) for item in value)
                        ):
                            continue
                        source_comparison["coordinate_refs"] += 1
                        if not (0 <= value[0] < len(rows) and 0 <= value[1] < len(rows[value[0]])):
                            invalid_references.append(
                                {**ref, "cell": [row_index, column_index], "target": value}
                            )
    baseline = subprocess.check_output(
        ["git", "show", f"{BASE}:static/js/practice_renderers.js"], cwd=ROOT, text=True
    )
    current_path = ROOT / "static/js/practice_renderers.js"
    current = current_path.read_text()
    report = {
        "baseline": BASE,
        "current_renderer_sha256": hashlib.sha256(current.encode()).hexdigest(),
        "source_raw_sha256": hashlib.sha256(raw_data).hexdigest(),
        "source_comparison": source_comparison,
        "collect_table_differences": differences,
        "invalid_coordinate_references": invalid_references,
        "before": renderer_audit(baseline),
        "after": renderer_audit(current),
        "boundaries": "Structure and source-line ownership only; no full semantic/image/audio review.",
    }
    output = Path(__file__).with_suffix(".json")
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(
        json.dumps(
            {
                "source": source_comparison,
                "source_differences": len(differences),
                "invalid_coordinates": len(invalid_references),
                "before_suffix_mismatches": len(report["before"]["suffix_mismatches"]),
                "after_suffix_mismatches": len(report["after"]["suffix_mismatches"]),
                "before_columns": len(report["before"]["columns"]),
                "after_columns": len(report["after"]["columns"]),
                "before_split_static_rows": len(report["before"]["split_static_rows"]),
                "after_split_static_rows": len(report["after"]["split_static_rows"]),
                "before_repeated_prefix_candidates": len(
                    report["before"]["repeated_previous_line_candidates"]
                ),
                "after_repeated_prefix_candidates": len(
                    report["after"]["repeated_previous_line_candidates"]
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
