const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const test = require('node:test');
const applyPreset = require('../static/js/task_dictation_preset');

// Execute the actual page handlers as well as the preset module, so this
// verifies the integration with defaults/ranges rather than a copied handler.
const template = fs.readFileSync(path.join(__dirname, '../templates/tasks.html'), 'utf8');
const sourceHandler = template.slice(
  template.indexOf('function toggleTaskSource('),
  template.indexOf('function setQuestionSelectionMeta(')
);
const detailHandler = template.slice(
  template.indexOf('async function toggleDetailInput('),
  template.indexOf('const listeningSegmentCache')
);

function fixture(search, defaultGoal = 'reading') {
  const elements = new Map();
  const events = [];
  const pending = [];
  const notices = [];
  let opened = 0;
  let rangeUpdates = 0;

  function element(id) {
    const attributes = {};
    const node = {
      id, value: '', checked: false, disabled: false, hidden: false,
      textContent: '', innerHTML: '', style: {}, dataset: {}, options: [],
      setAttribute(name, value) { attributes[name] = value; },
      removeAttribute(name) { delete attributes[name]; },
      getAttribute(name) { return attributes[name] ?? null; },
      querySelector() { return element('child'); },
      dispatchEvent(event) {
        events.push([id, event.type, event.bubbles]);
        if (node.onchange) pending.push(node.onchange());
      },
      before(notice) { notices.push(notice); elements.set(notice.id, notice); },
      scrollIntoView() {},
      click() { opened += 1; },
      submit() { assert.fail('preset must never submit a task'); }
    };
    return node;
  }

  const ids = new Set([
    ...Array.from((sourceHandler + detailHandler).matchAll(/getElementById\(['"]([^'"]+)['"]\)/g), match => match[1]),
    'taskForm', 'openTaskAssignment'
  ]);
  for (const id of ids) elements.set(id, element(id));
  const radio = element('material-radio');
  const select = elements.get('material_id');
  const option = element('option');
  option.value = 'dictation-210';
  option.setAttribute('data-title', '阅读课堂生词');
  option.setAttribute('data-type', '听写词库');
  option.setAttribute('data-count', '3词');
  option.setAttribute('data-book-type', 'translation');
  option.setAttribute('data-vocabulary-goal', defaultGoal);
  select.options = [option];
  Object.defineProperty(select, 'selectedIndex', {
    get() { return select.options.findIndex(item => item.value === select.value); }
  });
  const ranges = { dictation_word_start: element('start'), dictation_word_end: element('end') };
  const document = {
    getElementById(id) { return elements.get(id) || null; },
    getElementsByName(name) { return [ranges[name]]; },
    querySelector(query) {
      return query === 'input[name="task_source"][value="material"]' ? radio : null;
    },
    createElement() { return element('new'); },
    body: { prepend(notice) { notices.push(notice); } }
  };
  const window = {
    document, location: { search },
    Event: class Event { constructor(type, options) { this.type = type; Object.assign(this, options); } }
  };
  const context = vm.createContext({
    document, window,
    resetListeningSectionSelection() {}, resetReadingPassageSelection() {},
    setSentenceRangeControlsVisible() {}, setQuestionSelectionMeta() {},
    updateDictationRangeSuggestion() { rangeUpdates += 1; },
    fetch() { assert.fail('word book preset must not fetch material questions'); }
  });
  vm.runInContext(sourceHandler + detailHandler, context);
  radio.onchange = () => context.toggleTaskSource('material');
  select.onchange = () => context.toggleDetailInput();
  return {
    window, elements, select, option, radio, ranges, notices, events, pending,
    get opened() { return opened; },
    get rangeUpdates() { return rangeUpdates; }
  };
}

test('preselects a word book via real handlers, fills reading default and opens the drawer', async () => {
  const state = fixture('?preset_dictation_book=210');
  assert.equal(applyPreset(state.window), true);
  await Promise.all(state.pending);
  assert.equal(state.radio.checked, true);
  assert.equal(state.select.value, 'dictation-210');
  assert.equal(state.elements.get('materialSelectRow').style.display, 'flex');
  assert.equal(state.elements.get('taskDetail').value, '阅读课堂生词');
  assert.equal(state.elements.get('vocabularyGoalSelect').value, 'reading');
  assert.equal(state.elements.get('vocabularyGoalSelect').disabled, false);
  assert.equal(state.elements.get('dictation-range-group').style.display, 'block');
  assert.equal(state.ranges.dictation_word_end.placeholder, '共 3');
  assert.equal(state.rangeUpdates, 1);
  assert.equal(state.opened, 1);
  assert.deepEqual(state.events, [['material-radio', 'change', true], ['material_id', 'change', true]]);
  assert.equal(state.elements.get('taskStudent').value, '');
  assert.equal(state.notices.length, 0);
});

test('respects each existing book default and resets a stale selection', async () => {
  for (const goal of ['reading', 'writing', 'listening', 'comprehensive', '']) {
    const state = fixture('?preset_dictation_book=210', goal);
    state.elements.get('vocabularyGoalSelect').value = 'comprehensive';
    state.elements.get('vocabularyGoalSelect').dataset.autofill = '0';
    state.elements.get('listeningExerciseSelect').value = 'existing-listening';
    assert.equal(applyPreset(state.window), true);
    await Promise.all(state.pending);
    assert.equal(state.elements.get('vocabularyGoalSelect').value, goal);
    assert.equal(state.elements.get('listeningExerciseSelect').value, '');
  }
});

test('does not alter other task routes including the existing listening preset', () => {
  for (const search of ['', '?preset_exercise=sample', '?source=question_type', '?dictation_book_id=210']) {
    const state = fixture(search);
    state.select.value = 'original';
    assert.equal(applyPreset(state.window), false);
    assert.equal(state.select.value, 'original');
    assert.equal(state.opened, 0);
    assert.equal(state.events.length, 0);
    assert.equal(state.notices.length, 0);
  }
});

test('rejects invalid, empty and repeated IDs visibly without changing the form', () => {
  for (const query of ['', '0', '-2', '2.1', '2e2', '210%20', '210&preset_dictation_book=211', '<script>']) {
    const state = fixture(`?preset_dictation_book=${query}`);
    state.select.value = 'original';
    assert.equal(applyPreset(state.window), false);
    assert.match(state.notices[0].textContent, /词表链接无效/);
    assert.equal(state.notices[0].getAttribute('role'), 'alert');
    assert.equal(state.notices[0].innerHTML, '');
    assert.equal(state.select.value, 'original');
    assert.equal(state.opened, 0);
    assert.equal(state.events.length, 0);
  }
});

test('unknown or disabled books show an error without selecting another book', () => {
  for (const disabled of [false, true]) {
    const state = fixture(`?preset_dictation_book=${disabled ? '210' : '999'}`);
    state.option.disabled = disabled;
    assert.equal(applyPreset(state.window), false);
    assert.match(state.notices[0].textContent, /不存在或已停用/);
    assert.equal(state.select.value, '');
    assert.equal(state.opened, 0);
  }
});

test('missing page controls fail visibly before mutating the form', () => {
  const state = fixture('?preset_dictation_book=210');
  state.elements.delete('openTaskAssignment');
  assert.equal(applyPreset(state.window), false);
  assert.match(state.notices[0].textContent, /预选失败/);
  assert.equal(state.events.length, 0);
});
