'use strict';
const fs = require('node:fs');
const { templateRuntime, controls } = require('../../../tests/helpers/practice_template_runtime.js');
const data = JSON.parse(fs.readFileSync(0, 'utf8'));
const report = { counts: {}, issues: [], sourceWordCandidates: [], blocked: data.blocked, details: [] };
for (const item of data.cases) {
  const key = `${item.subject}:${item.mode}`;
  const stats = report.counts[key] ||= { tests: 0, groups: 0, questions: 0, logicalControls: 0, multiBlankQuestions: 0 };
  stats.tests++;
  const context = templateRuntime(item.subject, item.payload);
  const units = item.payload[item.subject === 'listening' ? 'sections' : 'passages'];
  for (const [unitIndex, unit] of units.entries()) for (const [groupIndex, group] of unit.groups.entries()) {
    const html = context.renderGroup(group, unitIndex);
    const actual = controls(html, item.subject);
    const actualIds = actual.flatMap(control => control.id.split(','));
    const expected = group.questions.map(q => String(q.id));
    const record = { subject: item.subject, mode: item.mode, test: item.test, unit: unitIndex, group: groupIndex, type: group.type };
    stats.groups++; stats.questions += expected.length; stats.logicalControls += actualIds.length;
    stats.multiBlankQuestions += actual.filter(control => control.kind === 'text-parts').length;
    const missing = expected.filter(id => !actualIds.includes(id));
    const duplicates = [...new Set(actualIds.filter((id, i) => actualIds.indexOf(id) !== i))];
    const extras = actualIds.filter(id => !expected.includes(id));
    if (missing.length || duplicates.length || extras.length) report.issues.push({ ...record, missing, duplicates, extras });
    for (const control of actual) {
      const ids = control.id.split(',');
      const numbers = control.number?.split(',');
      if (numbers && ids.some((id, i) => String(group.questions.find(q => String(q.id) === id)?.number) !== numbers[i])) report.issues.push({ ...record, reason: 'id-number-mismatch', control });
    }
    const leaked = html.match(/\$\d+\$|【\s*\d+\s*】/g);
    if (leaked) report.issues.push({ ...record, reason: 'unrendered-marker', leaked });
    const words = value => context.PracticeRenderers.plainText(String(value || '').replace(/>\s*</g, '> <')).replace(/\$\d+\$/g, ' ').toLowerCase().match(/[a-z]{3,}/g) || [];
    const visible = new Set(words(html));
    const collect = item.test === 'ielts6_test2' ? String(group.collect || '').replace('The Lighis ofNew York', 'The Lights of New York') : group.collect;
    const missingWords = [...new Set(words(collect))].filter(word => !visible.has(word) && !['nbsp', 'label', 'example', 'answer'].includes(word));
    if (missingWords.length) report.sourceWordCandidates.push({ ...record, missingWords });
    report.details.push({ ...record, controls: actual.map(({ id, number, kind }) => ({ id, number, kind })), sourceNumbers: group.questions.map(q => q.source_number || q.number) });
  }
}
process.stdout.write(JSON.stringify(report, null, 2) + '\n');
