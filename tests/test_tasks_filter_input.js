const assert = require('node:assert/strict');
const fs = require('node:fs');
const test = require('node:test');
const vm = require('node:vm');

class Element {
  constructor() {
    this.value = '';
    this.dataset = {};
    this.hidden = true;
    this.children = [];
    this.attributes = {};
    this.listeners = {};
    this.classList = { toggle() {}, remove() {} };
  }
  addEventListener(type, handler) { (this.listeners[type] ||= []).push(handler); }
  fire(type, properties = {}) {
    const event = { target: this, preventDefault() {}, ...properties };
    for (const handler of this.listeners[type] || []) handler(event);
  }
  setAttribute(name, value) { this.attributes[name] = value; }
  removeAttribute(name) { delete this.attributes[name]; }
  append(...children) { this.children.push(...children); }
  appendChild(child) { this.children.push(child); }
  replaceChildren() { this.children = []; }
  querySelectorAll() { return this.children.filter(child => child.attributes.role === 'option'); }
  scrollIntoView() {}
  blur() { this.fire('blur'); }
}

function setup(search = '?period=month&page_size=25&page=4') {
  const fields = Object.fromEntries([
    'filterStudent', 'filterStudentSuggestions', 'taskQuickSearch', 'filterCategory',
    'filterStatus', 'filterDueDate', 'filterApply', 'filterClear'
  ].map(id => [id, new Element()]));
  const navigation = [];
  const timers = new Map();
  let timerId = 0;
  const context = {
    URLSearchParams,
    document: {
      getElementById: id => fields[id] || null,
      createElement: () => new Element(),
      querySelectorAll: () => []
    },
    setTimeout: fn => { timers.set(++timerId, fn); return timerId; },
    clearTimeout: id => timers.delete(id)
  };
  context.window = {
    location: { search, pathname: '/tasks', assign: url => navigation.push(url) },
    taskStudentFilterOptions: [
      { name: '测试学生', search: '测试学生 ceshixuesheng ce shi xue sheng' },
      { name: '测试同学', search: '测试同学 ceshitongxue ce shi tong xue' }
    ],
    setTimeout: context.setTimeout
  };
  vm.createContext(context);
  // Include the original inline controller if it returns: duplicate listeners
  // would otherwise pass isolated module tests while still reloading the page.
  const template = fs.readFileSync('templates/tasks.html', 'utf8');
  const legacy = template.match(/\/\/ === 服务端筛选：[\s\S]*?(?=\/\/ === 计时逻辑)/);
  if (legacy) vm.runInContext(legacy[0], context);
  vm.runInContext(fs.readFileSync('static/js/tasks_workspace.js', 'utf8'), context);
  return {
    fields, navigation, window: context.window,
    flushTimers() {
      const pending = Array.from(timers.values());
      timers.clear();
      pending.forEach(fn => fn());
    },
    params() {
      assert.equal(navigation.length, 1, 'one deliberate action should navigate once');
      return new URL(navigation[0], 'https://example.test').searchParams;
    }
  };
}

test('pauses while typing a name or quick search never reload the page', () => {
  for (const id of ['filterStudent', 'taskQuickSearch']) {
    const view = setup();
    for (const value of ['c', 'ce', '测试', '测试学生']) {
      view.fields[id].value = value;
      view.fields[id].fire('input');
      view.flushTimers();
      assert.equal(view.fields[id].value, value);
      assert.deepEqual(view.navigation, []);
    }
  }
});

test('IME candidate confirmation does not select a suggestion or submit either input', () => {
  for (const id of ['filterStudent', 'taskQuickSearch']) {
    const view = setup();
    const input = view.fields[id];
    input.value = 'ce';
    input.fire('input');
    input.fire('keydown', { key: 'ArrowDown' });
    input.fire('compositionstart');
    input.value = 'ceshi';
    input.fire('input', { isComposing: true });
    input.fire('keydown', { key: 'Enter', isComposing: true });
    // Some browsers emit Enter without isComposing before compositionend.
    input.fire('keydown', { key: 'Enter' });
    input.value = '测试学生';
    input.fire('compositionend');
    input.fire('input');
    input.fire('keydown', { key: 'Enter', keyCode: 229 });
    view.flushTimers();
    assert.deepEqual(view.navigation, []);
    assert.equal(input.value, '测试学生');
    input.fire('keydown', { key: 'Enter' });
    assert.equal(view.params().get(id === 'filterStudent' ? 'student' : 'q'), '测试学生');
  }
});

test('Enter submits a name fragment, pinyin, or unmatched name without requiring a suggestion', () => {
  for (const name of ['测试', 'ceshi', '不存在的学生', '']) {
    const view = setup();
    view.fields.filterStudent.value = name;
    view.fields.filterStudent.fire('input');
    view.fields.filterStudent.fire('keydown', { key: 'Enter' });
    assert.equal(view.params().get('student'), name || null);
  }
});

test('keyboard choice uses the selected full name and navigates only once', () => {
  const view = setup();
  view.fields.filterStudent.value = 'ceshi';
  view.fields.filterStudent.fire('input');
  view.fields.filterStudent.fire('keydown', { key: 'ArrowDown' });
  view.fields.filterStudent.fire('keydown', { key: 'ArrowDown' });
  view.fields.filterStudent.fire('keydown', { key: 'Enter' });
  view.flushTimers();
  assert.equal(view.params().get('student'), '测试同学');
});

test('clicking a suggestion commits its full name without a delayed second navigation', () => {
  const view = setup();
  view.fields.filterStudent.value = 'ceshi';
  view.fields.filterStudent.fire('input');
  view.fields.filterStudentSuggestions.children[0].fire('click');
  view.flushTimers();
  assert.equal(view.params().get('student'), '测试学生');
});

test('query button preserves explicit combined filters and period but resets pagination and legacy targets', () => {
  const view = setup('?period=year&page_size=50&page=8&student_name=old&task_id=42');
  Object.entries({ filterStudent: ' 测试学生 ', taskQuickSearch: ' Day4 ', filterCategory: '词汇',
    filterStatus: 'done', filterDueDate: '2026-10-17' }).forEach(([id, value]) => { view.fields[id].value = value; });
  view.fields.filterApply.fire('click');
  const params = view.params();
  assert.deepEqual(Object.fromEntries(params), {
    period: 'year', page_size: '50', page: '1', q: 'Day4', student: '测试学生',
    category: '词汇', status: 'done', due_date: '2026-10-17'
  });
});

test('reset clears the top search and every filter, preserving the selected time range and page size', () => {
  const view = setup('?period=month&page_size=25&page=4&q=old&student=old&category=old&status=done&due_date=2026-10-17&student_name=old&task_id=42');
  for (const id of ['filterStudent', 'taskQuickSearch', 'filterCategory', 'filterStatus', 'filterDueDate']) {
    view.fields[id].value = 'old';
  }
  view.fields.filterClear.fire('click');
  assert.deepEqual(Object.fromEntries(view.params()), { period: 'month', page_size: '25', page: '1' });
  assert.equal(view.fields.taskQuickSearch.value, '');
  assert.equal(view.window.taskSelectedDate, '');
});

test('category, status and date changes still apply server filters once', () => {
  for (const [id, name, value] of [
    ['filterCategory', 'category', '词汇'], ['filterStatus', 'status', 'submitted'],
    ['filterDueDate', 'due_date', '2026-10-17']
  ]) {
    const view = setup();
    view.fields[id].value = value;
    view.fields[id].fire('change');
    assert.equal(view.params().get(name), value);
  }
});

test('Escape dismisses suggestions without navigating or losing typed text', () => {
  const view = setup();
  view.fields.filterStudent.value = 'ceshi';
  view.fields.filterStudent.fire('input');
  view.fields.filterStudent.fire('keydown', { key: 'Escape' });
  assert.equal(view.fields.filterStudentSuggestions.hidden, true);
  assert.equal(view.fields.filterStudent.value, 'ceshi');
  assert.deepEqual(view.navigation, []);
});
