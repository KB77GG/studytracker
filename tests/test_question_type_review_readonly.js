const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const ROOT = path.resolve(__dirname, '..');

function extractLockFunction(templatePath, nextFunctionName) {
  const source = fs.readFileSync(path.join(ROOT, templatePath), 'utf8');
  const startMarker = 'function lockReadOnlyReviewControls() {';
  const endMarker = `\n\nfunction ${nextFunctionName}`;
  const start = source.indexOf(startMarker);
  const end = source.indexOf(endMarker, start);

  assert.notEqual(start, -1, `${templatePath} must define ${startMarker}`);
  assert.notEqual(end, -1, `${templatePath} must keep ${nextFunctionName} after the lock helper`);
  return source.slice(start, end);
}

function makeControl() {
  return {
    disabled: false,
    readOnly: false,
    querySelectorAll() {
      return [];
    }
  };
}

function runLockFunction({ templatePath, nextFunctionName, rootSelector, readOnly }) {
  const directControl = makeControl();
  const nestedControls = [makeControl(), makeControl(), makeControl(), makeControl()];
  const wrapper = {
    querySelectorAll(selector) {
      assert.equal(selector, 'input, select, textarea, button');
      return nestedControls;
    }
  };
  const clearButton = makeControl();
  const capabilityButtons = [makeControl(), makeControl()];
  const selectorCalls = [];
  const document = {
    querySelectorAll(selector) {
      selectorCalls.push(selector);
      if (selector === rootSelector) return [directControl, wrapper];
      if (selector === '[data-clear-question]') return [clearButton];
      if (selector === "[data-capability='canResetAnswers'], [data-capability='canSubmitForScoring']") {
        return capabilityButtons;
      }
      throw new Error(`Unexpected selector: ${selector}`);
    }
  };
  const functionSource = extractLockFunction(templatePath, nextFunctionName);

  vm.runInNewContext(
    `${functionSource}\nlockReadOnlyReviewControls();`,
    {
      document,
      practiceContext: { read_only: readOnly }
    }
  );

  return { directControl, nestedControls, clearButton, capabilityButtons, selectorCalls };
}

for (const scenario of [
  {
    label: 'listening',
    templatePath: 'templates/listening/test_practice.html',
    nextFunctionName: 'findUnitByQuestionId',
    rootSelector: '.answer-unit'
  },
  {
    label: 'reading',
    templatePath: 'templates/reading/test_practice.html',
    nextFunctionName: 'bindInputs',
    rootSelector: '[data-qid]'
  }
]) {
  test(`${scenario.label} locks every answer control in a read-only review`, () => {
    const result = runLockFunction({ ...scenario, readOnly: true });

    assert.equal(result.directControl.disabled, true);
    assert.equal(result.directControl.readOnly, true);
    result.nestedControls.forEach((control) => assert.equal(control.disabled, true));
    assert.equal(result.clearButton.disabled, true);
    result.capabilityButtons.forEach((control) => assert.equal(control.disabled, true));
    assert.deepEqual(result.selectorCalls, [
      scenario.rootSelector,
      '[data-clear-question]',
      "[data-capability='canResetAnswers'], [data-capability='canSubmitForScoring']"
    ]);
  });

  test(`${scenario.label} leaves controls unchanged outside a read-only review`, () => {
    const result = runLockFunction({ ...scenario, readOnly: false });

    assert.equal(result.directControl.disabled, false);
    assert.equal(result.directControl.readOnly, false);
    result.nestedControls.forEach((control) => assert.equal(control.disabled, false));
    assert.equal(result.clearButton.disabled, false);
    result.capabilityButtons.forEach((control) => assert.equal(control.disabled, false));
    assert.deepEqual(result.selectorCalls, []);
  });
}

for (const subject of ['listening', 'reading']) {
  test(`${subject} restores a saved mock review without touching a practice draft`, async () => {
    const source = fs.readFileSync(path.join(ROOT, `templates/${subject}/test_practice.html`), 'utf8');
    const extract = name => {
      const start = source.indexOf(`function ${name}(`);
      assert.notEqual(start, -1);
      return source.slice(start, source.indexOf('\n}', start) + 2);
    };
    const elements = new Map();
    const storageCalls = [];
    const answers = {};
    const statuses = [];
    const noop = () => {};
    const context = {
      practiceContext: {
        task_type: 'mock_exam_review', read_only: true,
        initial_review: { answers: { 1: 'saved answer' }, result: { correct: 1, total: 1, results: [] } }
      },
      isMockExamReview: true, practiceRedo: { skipRestore: () => false },
      localStorage: Object.fromEntries(['getItem', 'setItem', 'removeItem'].map(method => [method, (...args) => { storageCalls.push([method, ...args]); return '{}'; }])),
      storageKey: 'ordinary draft', examDraftStorageKey: 'ordinary draft',
      answers, serverResult: null, resultMode: false, currentPassageId: 'p1', currentQuestionId: '1',
      testData: { passages: [{ id: 'p1' }] },
      document: { body: { classList: { add: noop } }, getElementById(id) {
        if (!elements.has(id)) elements.set(id, {});
        return elements.get(id);
      } },
      applyAnswerRows: rows => Object.assign(answers, rows), applyServerResults: noop,
      setExperienceMode: noop, renderPassage: noop, paintResults: noop, updateSummary: noop,
      setSyncStatus: status => statuses.push(status), lockReadOnlyReviewControls: noop,
      syncQuestionNav: noop, openReviewCard: noop,
      practiceShellController: { markSaved: noop },
      resultHtml: (...args) => { statuses.push(args.at(-1)); return 'review'; }
    };
    vm.createContext(context);
    const restoreName = subject === 'listening' ? 'restoreAnswers' : 'restoreExamDraft';
    vm.runInContext(`${extract(restoreName)}\nasync ${extract('loadExistingSubmission')}`, context);
    context[restoreName]();
    await context.loadExistingSubmission();
    assert.deepEqual(storageCalls, []);
    assert.deepEqual(answers, { 1: 'saved answer' });
    assert.ok(statuses.includes('已加载模考原题与作答记录'));
    assert.equal(elements.get(subject === 'listening' ? 'practiceShellMode' : 'practiceCrumbTail').textContent, '模考复盘');
  });
}
