const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const TEMPLATE = fs.readFileSync(
  path.resolve(__dirname, '../templates/listening/test_practice.html'),
  'utf8'
);

function between(startMarker, endMarker) {
  const start = TEMPLATE.indexOf(startMarker);
  const end = TEMPLATE.indexOf(endMarker, start);
  assert.notEqual(start, -1, `missing ${startMarker}`);
  assert.notEqual(end, -1, `missing ${endMarker}`);
  return TEMPLATE.slice(start, end);
}

test('the score controls are relocated once into the persistent bottom action area', () => {
  const footer = TEMPLATE.indexOf('<footer class="bottom-nav">');
  assert.notEqual(footer, -1);
  for (const id of [
    'activeSectionLabel',
    'questionCount',
    'answeredCount',
    'submitBtn',
    'resultBox'
  ]) {
    assert.equal((TEMPLATE.match(new RegExp(`id="${id}"`, 'g')) || []).length, 1, id);
    assert.ok(TEMPLATE.indexOf(`id="${id}"`) > footer, `${id} must live in the footer`);
  }
  assert.doesNotMatch(TEMPLATE, /<aside class="card side"/);
  assert.equal((TEMPLATE.match(/id="submitBtn"/g) || []).length, 1);
  assert.match(TEMPLATE, /practiceMeta'\)\.textContent = `\$\{test\.sections\.length\} 个 Section · \$\{questionTotal\} 题`/);
});

test('Section groups retain every question and distinguish repeated specialty sources', () => {
  const helpers = between('function allQuestions()', '\n\nfunction resultIds(');
  const context = {
    test: {
      sections: [
        {
          section: 1,
          source_test_id: 'ielts20_test1',
          groups: [{ questions: [{ id: 11, number: 1 }, { id: 12, number: 2 }] }]
        },
        {
          section: 1,
          source_test_id: 'ielts19_test4',
          groups: [{ questions: [{ id: 13, number: 3 }] }]
        },
        {
          section: 2,
          groups: [{ questions: [{ id: 14, number: 4 }] }]
        }
      ]
    }
  };
  vm.createContext(context);
  vm.runInContext(helpers, context);
  const groups = JSON.parse(vm.runInContext('JSON.stringify(sectionQuestionGroups())', context));

  assert.equal(groups.length, 3);
  assert.deepEqual(groups.map((group) => group.questions.map((question) => question.id)), [[11, 12], [13], [14]]);
  assert.deepEqual(groups.map((group) => group.label), ['C20 T1 · S1', 'C19 T4 · S1', 'S2']);
  assert.notEqual(groups[0].label, groups[1].label);
});

test('answer focus resolves text/select controls and nested radio or combined checkbox sets', () => {
  const helpers = between('function focusableAnswerControl(', '\n\nfunction syncQuestionNav(');
  const direct = { matches: () => true };
  const checked = { name: 'checked' };
  const first = { name: 'first' };
  const wrapper = {
    matches: () => false,
    querySelector(selector) {
      return selector.startsWith('input:checked') ? checked : first;
    }
  };
  const uncheckedWrapper = {
    matches: () => false,
    querySelector(selector) {
      return selector.startsWith('input:checked') ? null : first;
    }
  };
  const context = {};
  vm.createContext(context);
  vm.runInContext(helpers, context);

  context.direct = direct;
  context.wrapper = wrapper;
  context.uncheckedWrapper = uncheckedWrapper;
  context.combined = { dataset: { id: '21,22' } };
  assert.equal(vm.runInContext('focusableAnswerControl(direct)', context), direct);
  assert.equal(vm.runInContext('focusableAnswerControl(wrapper)', context), checked);
  assert.equal(vm.runInContext('focusableAnswerControl(uncheckedWrapper)', context), first);
  assert.equal(vm.runInContext("questionIdForFocusedUnit(combined, '22')", context), '22');
  assert.equal(vm.runInContext("questionIdForFocusedUnit(combined, '99')", context), '21');
});

test('only the latest explicit navigation callback may move focus after a Section change', () => {
  const helpers = between('function focusableAnswerControl(', '\n\nfunction syncQuestionNav(');
  const frames = [];
  const focused = [];
  const scrolled = [];
  const sections = [];
  const targets = new Map(['a', 'b'].map((id) => [id, {
    matches: () => false,
    querySelector: () => ({ focus: () => focused.push(id) }),
    closest: () => null
  }]));
  const context = {
    CSS: { escape: (value) => value },
    document: {
      querySelector(selector) {
        const id = selector.endsWith('"a"]') ? 'a' : 'b';
        return { scrollIntoView: () => scrolled.push(id) };
      }
    },
    findUnitByQuestionId: (id) => targets.get(id),
    requestAnimationFrame: (callback) => frames.push(callback),
    switchSection: (index) => sections.push(index),
    syncQuestionNav: () => {},
    Number,
    String
  };
  vm.createContext(context);
  vm.runInContext(`
    let questionFocusRevision = 0;
    let currentQuestionId = '';
    let latestResults = null;
    ${helpers}
  `, context);

  vm.runInContext("navigateToQuestion('a', 0); navigateToQuestion('b', 1);", context);
  while (frames.length) frames.shift()();

  assert.deepEqual(sections, [0, 1]);
  assert.deepEqual(scrolled, ['b']);
  assert.deepEqual(focused, ['b']);
});

test('read-only locking is reapplied after mode capabilities redraw the controls', () => {
  const renderBlock = between('function render()', '\n\ndocument.getElementById(\'submitBtn\')');
  assert.match(renderBlock, /setExperienceMode\(experienceMode\);\s+lockReadOnlyReviewControls\(\);/);
});
