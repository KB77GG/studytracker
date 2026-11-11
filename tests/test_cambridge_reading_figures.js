const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const root = path.resolve(__dirname, '..');
const source = fs.readFileSync(path.join(root, 'templates/reading/test_practice.html'), 'utf8');
const start = source.indexOf('function renderPassage(');
const end = source.indexOf('\nfunction ', start + 1);

function render(passage, simulationMode) {
  const panels = { passagePanel: { innerHTML: '' }, questionPanel: { innerHTML: '' } };
  const context = {
    isMockExamReview: false, experienceCapabilities: { simulationMode }, experienceMode: 'training', resultMode: false,
    document: { getElementById: id => panels[id] },
    escapeHtml: value => String(value || ''), renderGroup: () => '',
    bindInputs() {}, setExperienceMode() {}, lockReadOnlyReviewControls() {},
    requestAnimationFrame() {}, window: {},
  };
  vm.runInNewContext(source.slice(start, end), context);
  context.renderPassage(passage);
  return panels.passagePanel.innerHTML;
}

test('all four restored original figures render once at their source positions in training and simulation', () => {
  let count = 0;
  for (const id of ['ielts4_test1_reading', 'ielts7_test4_reading', 'ielts10_test3_reading']) {
    const payload = JSON.parse(fs.readFileSync(path.join(root, 'static/reading_tests', `${id}.json`), 'utf8'));
    const passage = payload.passages[2];
    for (const simulation of [false, true]) {
      const html = render(passage, simulation);
      for (const figure of passage.content.images) {
        const url = `/static/${figure.url}`;
        assert.equal(html.split(url).length - 1, 1);
        assert.ok(html.includes(`alt="${figure.alt}"`));
        const before = passage.content.paragraphs[figure.after_paragraph].text;
        const after = passage.content.paragraphs[figure.after_paragraph + 1]?.text;
        assert.ok(html.indexOf(before) < html.indexOf(url));
        if (after) assert.ok(html.indexOf(url) < html.indexOf(after));
        if (!simulation) count += 1;
      }
    }
  }
  assert.equal(count, 4);
});

test('unnumbered introduction does not shift a source figure into the wrong paragraph', () => {
  const passage = {
    title: 'Example', content: {
      paragraphs: [{ label: 'pre-A', text: 'Introduction.' }, { label: 'A', text: 'First body.' }, { label: 'B', text: 'Second body.' }],
      images: [{ url: 'reading_tests/images/example.png', alt: 'Source figure', after_paragraph: 0 }],
    },
  };
  const html = render(passage, true);
  assert.ok(html.indexOf('First body.') < html.indexOf('/static/reading_tests/images/example.png'));
  assert.ok(html.indexOf('/static/reading_tests/images/example.png') < html.indexOf('Second body.'));
  assert.ok(!html.includes('pre-A'));
});
