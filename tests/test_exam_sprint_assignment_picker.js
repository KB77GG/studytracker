const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const source = fs.readFileSync(path.join(__dirname, '../templates/tasks.html'), 'utf8');

class Element {
  constructor() {
    this.children = []; this.events = {}; this.dataset = {}; this.style = {};
    this.value = ''; this.textContent = ''; this.attributes = {};
    this.classList = { add() {}, toggle() {} };
  }
  set innerHTML(value) { this.markup = value; this.children = []; }
  get innerHTML() { return this.markup || ''; }
  append(...children) { this.children.push(...children); }
  appendChild(child) { this.children.push(child); }
  setAttribute(key, value) { this.attributes[key] = value; }
  getAttribute(key) { return this.attributes[key]; }
  addEventListener(key, callback) { this.events[key] = callback; }
  dispatchEvent(event) { this.events[event.type]?.(event); }
  click() { this.events.click?.({}); }
  querySelector() { return this.children.find(child => child.className === 'listening-option'); }
  querySelectorAll() { return []; }
}

test('listening hotlist filter keeps the existing jijing task type and distinct picker values', () => {
  const nodes = Object.fromEntries([
    'listeningPicker', 'listeningExerciseSelect', 'listeningPickerSearch',
    'listeningPickerResults', 'listeningPickerSelected'
  ].map(id => [id, new Element()]));
  const select = nodes.listeningExerciseSelect;
  select.options = [
    { value: '', dataset: {}, textContent: '' },
    { value: 'legacy_p1', dataset: { resourceType: 'jijing', title: 'Legacy practice' }, textContent: 'Legacy practice (10题)' },
    { value: 'sprint:legacy_p1', dataset: { resourceType: 'jijing', catalogSource: 'exam_sprint', title: '7天热榜 · P1 #1 · Current' }, textContent: '7天热榜 · P1 #1 · Current (10题)' }
  ];
  Object.defineProperty(select, 'selectedIndex', { get() { return this.options.findIndex(option => option.value === this.value); } });
  const buttons = ['intensive', 'cambridge_test', 'jijing', 'exam_sprint'].map(key => {
    const button = new Element(); button.dataset.listeningFilter = key; return button;
  });
  const context = {
    document: { getElementById: id => nodes[id], querySelectorAll: () => buttons, createElement: () => new Element() },
    window: {}, Event: class { constructor(type) { this.type = type; } }
  };
  const start = source.indexOf('    function initListeningPicker()');
  const end = source.indexOf('    function initWritingAssignmentPicker()', start);
  vm.runInNewContext(source.slice(start, end), context);
  buttons[3].click();
  assert.equal(nodes.listeningPickerResults.children.length, 1);
  nodes.listeningPickerResults.children[0].click();
  assert.equal(select.value, 'sprint:legacy_p1');
  assert.match(nodes.listeningPickerSelected.textContent, /^7天热榜：/);
  assert.equal(select.options[select.selectedIndex].dataset.resourceType, 'jijing');
  buttons[2].click();
  assert.equal(nodes.listeningPickerResults.children.length, 1);
  nodes.listeningPickerResults.children[0].click();
  assert.equal(select.value, 'legacy_p1');
});

test('reading hotlist exposes only its fixed passage and legacy selections retain full-test choice', () => {
  const nodes = Object.fromEntries([
    'readingExerciseSelect', 'readingPassageRow', 'readingPassageChoices', 'taskDetail', 'taskPlanned'
  ].map(id => [id, new Element()]));
  const option = new Element();
  option.dataset.catalogSource = 'exam_sprint';
  option.setAttribute('data-title', '7天热榜 · P2 #1 · Current');
  nodes.readingExerciseSelect.options = [option];
  nodes.readingExerciseSelect.selectedIndex = 0;
  nodes.readingExerciseSelect.value = 'versioned_test@1';
  const context = {
    document: { getElementById: id => nodes[id] },
    readingExercisePassages: { 'versioned_test@1': [{ number: 1, label: '热榜 P2 · 本篇' }] },
    resetReadingPassageSelection() { nodes.readingPassageChoices.innerHTML = ''; }
  };
  const start = source.indexOf('    function renderReadingPassageChoices(');
  const end = source.indexOf('    function updateDictationRangeSuggestion(', start);
  vm.runInNewContext(source.slice(start, end) + '\nhandleReadingExerciseChange();', context);
  assert.match(nodes.readingPassageChoices.innerHTML, /value="1" checked/);
  assert.doesNotMatch(nodes.readingPassageChoices.innerHTML, /整套 Test|value=""/);
  assert.equal(nodes.taskPlanned.placeholder, '例如 20');
  option.dataset.catalogSource = '';
  vm.runInNewContext('handleReadingExerciseChange();', context);
  assert.match(nodes.readingPassageChoices.innerHTML, /整套 Test/);
});

function repeatHarness(subject, values) {
  const selectId = subject === 'listening' ? 'listeningExerciseSelect' : 'readingExerciseSelect';
  const nodes = Object.fromEntries([
    'listeningExerciseSelect', 'readingExerciseSelect', 'taskStudent',
    'listeningResourceType', 'taskPlanned', 'taskNote', 'taskDetail'
  ].map(id => [id, new Element()]));
  nodes.listeningExerciseSelect.options = [];
  nodes.readingExerciseSelect.options = [];
  nodes[selectId].options = values.map(value => ({ value }));
  nodes[selectId].value = 'unchanged-selection';
  const radios = ['', '1', '2'].map(value => ({ value, checked: false }));
  const calls = { changes: [], statuses: [], toggles: 0 };
  const context = {
    document: {
      getElementById: id => nodes[id],
      querySelector: () => ({}),
      querySelectorAll: selector => selector.includes('reading_passage_number') ? radios : []
    },
    window: {},
    setStatus: (message, error = false) => calls.statuses.push({ message, error }),
    toggleTaskSource() { calls.toggles += 1; nodes[selectId].value = ''; },
    handleListeningExerciseChange: async () => calls.changes.push(nodes[selectId].value),
    handleReadingExerciseChange: () => calls.changes.push(nodes[selectId].value),
    setQuestionSelection() {}
  };
  const helperStart = source.indexOf('      const hasOption =');
  const helperEnd = source.indexOf('      const setQuestionSelection =', helperStart);
  const start = source.indexOf('      async function applyRepeatPreset(');
  const end = source.indexOf('      function renderPreviousDayTasks(', start);
  vm.runInNewContext(source.slice(helperStart, helperEnd) + source.slice(start, end), context);
  return { nodes, calls, radios, apply: context.applyRepeatPreset, selectId };
}

test('repeat preset restores the exact hotlist version and reading passage', async () => {
  for (const subject of ['listening', 'reading']) {
    const id = 'ninefen_1201_aaaaaaaaaaaa';
    const expected = subject === 'listening' ? `sprint:${id}` : `${id}@1`;
    const harness = repeatHarness(subject, [expected]);
    await harness.apply('Synthetic student', { title: 'Synthetic task', repeat: {
      source: subject, listening_exercise_id: id, listening_resource_type: 'jijing',
      reading_test_id: id, reading_passage_number: 1
    } });
    assert.equal(harness.nodes[harness.selectId].value, expected);
    assert.deepEqual(harness.calls.changes, [expected]);
    assert.equal(harness.calls.statuses.at(-1).error, false);
    if (subject === 'reading') assert.deepEqual(harness.radios.map(radio => radio.checked), [false, true, false]);
  }
});

test('repeat preset prefers an available original legacy option', async () => {
  for (const subject of ['listening', 'reading']) {
    const id = 'legacy_resource';
    const hot = subject === 'listening' ? `sprint:${id}` : `${id}@1`;
    const harness = repeatHarness(subject, [hot, id]);
    await harness.apply('Synthetic student', { title: 'Synthetic task', repeat: {
      source: subject, listening_exercise_id: id, reading_test_id: id, reading_passage_number: 1
    } });
    assert.equal(harness.nodes[harness.selectId].value, id);
    assert.deepEqual(harness.calls.changes, [id]);
  }
});

test('repeat preset refuses another version or passage without changing the form', async () => {
  const original = 'ninefen_1201_aaaaaaaaaaaa';
  for (const [subject, available, passage] of [
    ['listening', 'sprint:ninefen_1201_bbbbbbbbbbbb', 1],
    ['reading', 'ninefen_1201_bbbbbbbbbbbb@1', 1],
    ['reading', `${original}@2`, 1],
    ['reading', `${original}@1`, null]
  ]) {
    const harness = repeatHarness(subject, [available]);
    await harness.apply('Synthetic student', { title: 'Synthetic task', repeat: {
      source: subject, listening_exercise_id: original,
      reading_test_id: original, reading_passage_number: passage
    } });
    assert.equal(harness.calls.statuses.at(-1).error, true);
    assert.equal(harness.calls.toggles, 0);
    assert.deepEqual(harness.calls.changes, []);
    assert.equal(harness.nodes[harness.selectId].value, 'unchanged-selection');
    assert.equal(harness.nodes.taskStudent.value, '');
  }
});
