'use strict';
// Node subprocess bridge: actual template rendering and actual save paths.
const fs = require('node:fs');
const { templateRuntime, controls } = require('./practice_template_runtime.js');
const cases = JSON.parse(fs.readFileSync(0, 'utf8'));
const result = cases.map(item => {
  const context = templateRuntime(item.subject, item.payload, {
    practiceContext: {}, persistExamDraft: () => true, practiceShellController: null,
    resultMode: false, updateSummary() {}, syncQuestionNav() {}
  });
  const unitKey = item.subject === 'listening' ? 'sections' : 'passages';
  const group = item.payload[unitKey].flatMap(unit => unit.groups).find(group => group.questions.some(question => String(question.id) === item.id));
  const html = context.renderGroup(group, 0);
  const control = controls(html, item.subject).find(control => control.id === item.id);
  if (control?.kind !== 'text-parts') throw Error(`Expected compound control: ${item.name}`);
  const inputs = item.parts.map(value => ({ value }));
  const unit = {
    dataset: { id: item.id, qid: item.id, kind: 'text-parts', separator: control.attrs['data-separator'] },
    querySelectorAll: () => inputs
  };
  let value;
  if (item.subject === 'listening') value = context.unitValue(unit);
  else {
    context.handleAnswerChange({ target: { closest: () => unit } });
    value = context.answers[item.id];
  }
  return { name: item.name, value, id: item.id };
});
process.stdout.write(JSON.stringify(result));
