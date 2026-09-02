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
  const selectorCalls = [];
  const document = {
    querySelectorAll(selector) {
      selectorCalls.push(selector);
      if (selector === rootSelector) return [directControl, wrapper];
      if (selector === '[data-clear-question]') return [clearButton];
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

  return { directControl, nestedControls, clearButton, selectorCalls };
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
    assert.deepEqual(result.selectorCalls, [scenario.rootSelector, '[data-clear-question]']);
  });

  test(`${scenario.label} leaves controls unchanged outside a read-only review`, () => {
    const result = runLockFunction({ ...scenario, readOnly: false });

    assert.equal(result.directControl.disabled, false);
    assert.equal(result.directControl.readOnly, false);
    result.nestedControls.forEach((control) => assert.equal(control.disabled, false));
    assert.equal(result.clearButton.disabled, false);
    assert.deepEqual(result.selectorCalls, []);
  });
}
