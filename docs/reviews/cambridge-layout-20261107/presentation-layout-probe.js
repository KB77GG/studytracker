'use strict';
const fs = require('node:fs');
const path = require('node:path');
const root = path.resolve(__dirname, '../../..');
const R = require(path.join(root, 'static/js/practice_renderers.js'));
const { templateRuntime } = require(path.join(root, 'tests/helpers/practice_template_runtime.js'));
const rows = [];
for (const file of fs.readdirSync(path.join(root, 'static/listening_tests')).filter(name => /^ielts\d+_test\d+\.json$/.test(name))) {
  const payload = JSON.parse(fs.readFileSync(path.join(root, 'static/listening_tests', file)));
  const runtime = templateRuntime('listening', payload);
  payload.sections.forEach((section, si) => (section.groups || []).forEach((group, gi) => {
    if (!R.isFormGroup(group)) return;
    const fields = R.formFields(group);
    const html = runtime.renderGroup(group, si);
    const cells = R.visualCells(group.collect);
    const questionLines = new Map();
    for (const field of fields) {
      const line = field.target?.line;
      if (!questionLines.has(line)) questionLines.set(line, []);
      questionLines.get(line).push({ number: field.question.number, column: field.target?.column });
    }
    const staticPairs = cells.filter(cell => cell.labels.length && !/\$\d+\$/.test(cell.raw)).flatMap(cell => {
      const siblings = cells.filter(other => other !== cell && other.line === cell.line && !/\$\d+\$/.test(other.raw));
      return siblings.length ? [{ line: cell.line, label: cell.text, value: siblings.map(x => x.text).join(' ') }] : [];
    });
    const splitLabelPairs = staticPairs.filter(pair => {
      const a = R.escapeHtml(pair.label), b = R.escapeHtml(pair.value);
      return html.includes(`>${a}</div>`) && html.includes(`>${b}</div>`);
    });
    const minusHeadings = [...html.matchAll(/<div class="practice-form__subheading">(−[^<]*)<\/div>/g)].map(match => match[1]);
    const singleQuestionPerSourceLine = [...questionLines.values()].every(list => list.length === 1);
    rows.push({
      test: payload.id, section: si + 1, group: gi, numbers: fields.map(f => f.question.number),
      layout: html.match(/data-layout="([^"]+)"/)?.[1],
      single_question_per_source_line: singleQuestionPerSourceLine,
      question_lines: [...questionLines].map(([line, questions]) => ({ line, questions })),
      split_static_label_values: splitLabelPairs, minus_subheadings: minusHeadings,
      compounds: fields.filter(f => /(?:【\s*】|\[\s*\])\s*(?:and|or|to)\s*(?:【\s*】|\[\s*\])/i.test(f.question.title || '')).map(f => f.question.number),
    });
  }));
}
const columns = rows.filter(row => row.layout === 'columns');
console.log(JSON.stringify({
  summary: {
    form_groups: rows.length, columns_groups: columns.length,
    columns_with_one_question_per_source_line: columns.filter(row => row.single_question_per_source_line).length,
    split_static_label_value_groups: rows.filter(row => row.split_static_label_values.length).length,
    minus_misclassified_subheading_groups: rows.filter(row => row.minus_subheadings.length).length,
  }, rows,
}, null, 2));
