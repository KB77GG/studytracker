const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../templates/reading/test_practice.html'), 'utf8');
function extract(name) {
  const start = source.indexOf(`function ${name}(`);
  const end = source.indexOf('\nfunction ', start + 1);
  assert.notEqual(start, -1, name);
  assert.notEqual(end, -1, name);
  return source.slice(start, end);
}
function fixture() {
  return {
    id: 1, title: 'Passage',
    content: { paragraphs: [
      { label: 'pre-A', text: 'Unlabelled introduction.' },
      { label: 'A', text: 'First labelled paragraph.' },
      { label: 'B', text: 'Second labelled paragraph.' },
    ] },
    groups: [{ desc: 'Choose the correct heading for each paragraph.', questions: [
      { id: 1, number: 1, title: 'Paragraph A' }, { id: 2, number: 2, title: 'Paragraph B' },
    ] }],
  };
}

test('intro does not shift paragraph matching options or explicit heading labels', () => {
  const passage = fixture();
  const context = { testData: { passages: [passage] } };
  vm.createContext(context);
  for (const name of ['passageForQuestion', 'groupInstruction', 'passageLetterOptions', 'displayQuestionPrompt']) {
    vm.runInContext(extract(name), context);
  }
  const group = passage.groups[0];
  assert.deepEqual(Array.from(context.passageLetterOptions(group.questions[0]), row => row.key), ['A', 'B']);
  assert.equal(context.displayQuestionPrompt(group.questions[0], group), 'Paragraph A');
  assert.equal(context.displayQuestionPrompt(group.questions[1], group), 'Paragraph B');
});

test('ordinary and simulation passage display keeps introduction without its technical label', () => {
  for (const simulationMode of [false, true]) {
    const panels = { passagePanel: { innerHTML: '' }, questionPanel: { innerHTML: '' } };
    const context = {
      experienceCapabilities: { simulationMode }, experienceMode: 'training', resultMode: false,
      document: { getElementById: id => panels[id] },
      escapeHtml: value => String(value || ''), renderGroup: () => '',
      bindInputs() {}, setExperienceMode() {}, lockReadOnlyReviewControls() {},
      requestAnimationFrame() {}, window: {},
    };
    vm.runInNewContext(extract('renderPassage'), context);
    context.renderPassage(fixture());
    assert.ok(panels.passagePanel.innerHTML.includes('Unlabelled introduction.'));
    assert.ok(!panels.passagePanel.innerHTML.includes('pre-A'));
    assert.ok(panels.passagePanel.innerHTML.includes('paragraph-label">A</span>'));
  }
});
