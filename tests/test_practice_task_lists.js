const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const MODULE_PATH = path.join(__dirname, '..', 'static', 'js', 'practice_task_lists.js');
const lists = require(MODULE_PATH);
const ids = tasks => tasks.map(task => task.id);

function current(id, overrides = {}) {
  return {
    id,
    date: '2026-11-03',
    status: 'pending',
    task_status: 'pending',
    task_date_state: 'today',
    availability_status: 'today',
    can_start: true,
    can_write: true,
    read_only: false,
    url: `/listening/example?task_id=${id}`,
    ...overrides,
  };
}

function expired(id, overrides = {}) {
  return current(id, {
    date: '2026-10-02',
    status: 'in_progress',
    task_status: 'in_progress',
    task_date_state: 'expired',
    availability_status: 'expired',
    can_start: false,
    can_write: false,
    read_only: true,
    completion_rate: 4.5,
    ...overrides,
  });
}

test('forty unfinished expired assignments cannot displace the current task preview or count', () => {
  const backlog = Array.from({ length: 40 }, (_, index) => expired(index + 1));
  const actionable = [current(101), current(102, { status: 'in_progress', task_status: 'in_progress' })];
  const result = lists.partition([...backlog, ...actionable]);

  assert.deepEqual(ids(result.current.slice(0, 4)), [102, 101]);
  assert.equal(result.current.length, 2);
  assert.equal(result.expired.length, 40);
  assert.equal(result.history.length, 0);
  assert.equal(result.upcoming.length, 0);
});

test('server-authorized grace-period and undated assignments remain current without local date math', () => {
  const grace = current(1, {
    date: '1999-01-01',
    task_date: '1999-01-01',
    is_grace_period: true,
    task_cutoff_at: '1999-01-02T03:00:00+08:00',
  });
  const legacy = current(2, { date: '', task_date: null });
  const result = lists.partition([grace, legacy]);

  assert.deepEqual(ids(result.current), [1, 2]);
  assert.equal(lists.isLocked(grace), false);
  assert.equal(lists.isLocked(legacy), false);
  assert.equal(grace.date, '1999-01-01');
});

test('submitted work is history even when its withdrawal window is still writable or already expired', () => {
  const submitted = current(1, { status: 'submitted', task_status: 'submitted' });
  const oldSubmitted = expired(2, { status: 'submitted', task_status: 'submitted' });
  const result = lists.partition([submitted, oldSubmitted]);

  assert.deepEqual(ids(result.history), [1, 2]);
  assert.equal(result.current.length, 0);
  assert.equal(result.expired.length, 0);
  assert.equal(lists.isLocked(submitted), false);
  assert.equal(lists.isLocked(oldSubmitted), true);
});

test('completed results stay in history and retain usable review links despite read-only flags', () => {
  const done = current(1, {
    status: 'done', task_status: 'completed', task_date_state: 'completed',
    availability_status: 'completed', can_start: false, can_write: false, read_only: true,
  });
  const completeAlias = { ...done, id: 2, status: 'completed' };
  const result = lists.partition([done, completeAlias]);

  assert.deepEqual(new Set(ids(result.history)), new Set([1, 2]));
  assert.equal(result.current.length, 0);
  assert.equal(lists.isLocked(done), false);
  assert.equal(lists.isLocked(completeAlias), false);
  assert.equal(result.history.find(task => task.id === 1).url, done.url);
});

test('future and expired assignments remain unavailable even if stale writable flags say true', () => {
  const future = current(1, { task_date_state: 'future', availability_status: 'future' });
  const old = current(2, { task_date_state: 'expired', availability_status: 'expired' });
  const result = lists.partition([future, old]);

  assert.deepEqual(ids(result.upcoming), [1]);
  assert.deepEqual(ids(result.expired), [2]);
  assert.equal(result.current.length, 0);
  assert.equal(lists.isLocked(future), true);
  assert.equal(lists.isLocked(old), true);
});

test('task_date_state takes precedence over the compatibility availability alias', () => {
  const open = current(1, { availability_status: 'expired' });
  const closed = expired(2, { availability_status: 'today' });
  const result = lists.partition([open, closed]);

  assert.deepEqual(ids(result.current), [1]);
  assert.deepEqual(ids(result.expired), [2]);
});

test('availability_status alone is sufficient for older payload shapes', () => {
  const result = lists.partition([
    { id: 1, status: 'pending', availability_status: 'today' },
    { id: 2, status: 'pending', availability_status: 'future' },
    { id: 3, status: 'in_progress', availability_status: 'expired' },
  ]);

  assert.deepEqual(ids(result.current), [1]);
  assert.deepEqual(ids(result.upcoming), [2]);
  assert.deepEqual(ids(result.expired), [3]);
});

test('each explicit permission denial prevents classification as current', () => {
  const blocked = [
    current(1, { read_only: true }),
    current(2, { can_start: false }),
    current(3, { can_write: false }),
  ];
  const result = lists.partition(blocked);

  assert.equal(result.current.length, 0);
  assert.deepEqual(new Set(ids(result.history)), new Set([1, 2, 3]));
  for (const task of blocked) assert.equal(lists.isLocked(task), true);
});

test('unknown availability requires an affirmative server permission, never just pending status', () => {
  const result = lists.partition([
    { id: 1, status: 'pending' },
    { id: 2, status: 'in_progress', read_only: false },
    { id: 3, status: 'pending', can_start: true },
    { id: 4, status: 'pending', can_write: true },
  ]);

  assert.deepEqual(new Set(ids(result.current)), new Set([3, 4]));
  assert.deepEqual(new Set(ids(result.history)), new Set([1, 2]));
});

test('current work prioritizes progress and uses authoritative task_date before legacy date', () => {
  const result = lists.partition([
    current(1, { date: '2026-11-20', task_date: '2026-11-01' }),
    current(2, { date: '2026-10-01', task_date: '2026-11-03' }),
    current(3, { date: '2026-11-02', status: 'in_progress', task_status: 'in_progress' }),
    current(4, { date: '2026-11-03', status: 'in_progress', task_status: 'in_progress' }),
  ]);

  assert.deepEqual(ids(result.current), [4, 3, 2, 1]);
});

test('upcoming work runs earliest first while closed work runs most recent first', () => {
  const future = date => current(date, {
    date, task_date_state: 'future', availability_status: 'future',
    read_only: true, can_start: false, can_write: false,
  });
  const done = date => current(`done-${date}`, {
    date, status: 'done', task_status: 'completed',
    task_date_state: 'completed', availability_status: 'completed',
  });
  const result = lists.partition([
    future('2026-11-10'), future('2026-11-04'),
    expired(1, { date: '2026-10-01' }), expired(2, { date: '2026-11-02' }),
    done('2026-10-01'), done('2026-11-02'),
  ]);

  assert.deepEqual(ids(result.upcoming), ['2026-11-04', '2026-11-10']);
  assert.deepEqual(ids(result.expired), [2, 1]);
  assert.deepEqual(ids(result.history), ['done-2026-11-02', 'done-2026-10-01']);
});

test('both assignment roles contribute current tasks independently of their historical backlog', () => {
  const groups = {
    assistant: [expired(1), current(2)],
    teacher: [expired(3), current(4)],
  };
  const result = lists.fromGroups(groups);

  assert.deepEqual(new Set(ids(result.current)), new Set([2, 4]));
  assert.deepEqual(new Set(ids(result.expired)), new Set([1, 3]));
});

test('missing or malformed arrays safely yield empty collections', () => {
  for (const value of [undefined, null, {}, 'tasks']) {
    const result = lists.partition(value);
    assert.deepEqual(result, { current: [], upcoming: [], history: [], expired: [] });
  }
  for (const groups of [undefined, null, {}, { assistant: {}, teacher: null }]) {
    assert.deepEqual(lists.fromGroups(groups), { current: [], upcoming: [], history: [], expired: [] });
  }
  const task = current(1);
  assert.deepEqual(lists.fromGroups({ assistant: null, teacher: [task] }).current, [task]);
});

test('partitioning does not mutate source arrays or records and equal sort keys remain stable', () => {
  const first = Object.freeze(current(1));
  const second = Object.freeze(current(1));
  const old = Object.freeze(expired(2));
  const source = Object.freeze([old, first, second]);
  const before = JSON.stringify(source);
  const result = lists.partition(source);

  assert.equal(JSON.stringify(source), before);
  assert.notEqual(result.current, source);
  assert.equal(result.current[0], first);
  assert.equal(result.current[1], second);
  assert.equal(result.expired[0], old);
});

test('browser loading exposes the same public API without CommonJS globals', () => {
  const sandbox = { window: {} };
  vm.runInNewContext(fs.readFileSync(MODULE_PATH, 'utf8'), sandbox, { filename: MODULE_PATH });
  const browserLists = sandbox.window.PracticeTaskLists || sandbox.PracticeTaskLists;

  assert.ok(browserLists);
  for (const method of ['partition', 'fromGroups', 'isLocked']) {
    assert.equal(typeof browserLists[method], 'function');
  }
  assert.equal(browserLists.partition([expired(1), current(2)]).current[0].id, 2);
});

function templatePage(templateName, response) {
  const filename = path.join(__dirname, '..', 'templates', templateName);
  const html = fs.readFileSync(filename, 'utf8');
  const elements = new Map();
  for (const match of html.matchAll(/<[^>]+\bid="([^"]+)"[^>]*>/g)) {
    elements.set(match[1], {
      innerHTML: '', textContent: '', value: '', style: {}, dataset: {},
      hidden: /\shidden(?:[\s>])/.test(match[0]),
      open: /\sopen(?:[\s>])/.test(match[0]),
      addEventListener() {}, focus() {},
    });
  }
  const identity = { dataset: { practiceStaffMode: '0' } };
  const storage = { getItem: () => null, setItem() {}, removeItem() {} };
  const sandbox = {
    PracticeTaskLists: lists,
    document: {
      getElementById: id => elements.get(id) || null,
      querySelector: selector => selector === '.practice-identity' ? identity : null,
      querySelectorAll: () => [],
      addEventListener() {},
    },
    window: { addEventListener() {} },
    localStorage: storage, sessionStorage: storage,
    fetch: async () => ({ ok: true, json: async () => response }),
    console, Date, Intl,
  };
  let script = [...html.matchAll(/<script>([\s\S]*?)<\/script>/g)]
    .map(match => match[1])
    .find(source => source.includes('function renderNewTasks(') || source.includes('async function loadAssignedTasks('));
  assert.ok(script, 'the real task-rendering script must exist');
  if (templateName === 'practice/index_content.html') {
    script = script.replace(/\}\)\(\);\s*$/, 'globalThis.taskPage = { loadAssignedTasks, hideAssignedTasks };\n})();');
  }
  vm.runInNewContext(script, sandbox, { filename });
  return { sandbox, elements, html };
}

test('the actual listening homepage shows one current assignment, not forty expired cards', () => {
  const { sandbox, elements } = templatePage('listening/index.html');
  const backlog = Array.from({ length: 40 }, (_, index) => expired(index + 1, { title: `Closed assignment ${index}` }));
  const available = current(101, { title: 'Current assignment', category: '精听', status_label: '待完成' });
  sandbox.renderNewTasks({ groups: { assistant: backlog, teacher: [available] } });

  assert.equal(elements.get('newTasksMeta').textContent, '1 项待完成');
  assert.match(elements.get('newTasksList').innerHTML, /Current assignment/);
  assert.doesNotMatch(elements.get('newTasksList').innerHTML, /Closed assignment/);
  assert.equal((elements.get('newTasksList').innerHTML.match(/<a class="today-task[" ]/g) || []).length, 1);
  assert.equal(elements.get('newTasksMore').hidden, false);
});

test('the actual listening homepage keeps the history entry when all assignments are closed', () => {
  const { sandbox, elements } = templatePage('listening/index.html');
  sandbox.renderNewTasks({ groups: { assistant: [expired(1)] } });

  assert.equal(elements.get('newTasksMeta').textContent, '0 项待完成');
  assert.match(elements.get('newTasksList').innerHTML, /当前没有待完成任务/);
  assert.equal(elements.get('newTasksMore').hidden, false);
});

test('the actual practice center counts current work and defaults every historical section to collapsed', async () => {
  const complete = current(103, {
    title: 'Completed result', status: 'done', task_status: 'completed',
    task_date_state: 'completed', availability_status: 'completed',
    can_start: false, can_write: false, read_only: true,
  });
  const future = current(104, {
    task_date_state: 'future', availability_status: 'future',
    read_only: true, can_start: false, can_write: false,
  });
  const response = { ok: true, groups: {
    assistant: [...Array.from({ length: 40 }, (_, index) => expired(index + 1)), current(101, { title: 'Current assistant' })],
    teacher: [current(102, { title: 'Current teacher' }), complete, future],
  } };
  const { sandbox, elements } = templatePage('practice/index_content.html', response);
  await sandbox.taskPage.loadAssignedTasks();

  assert.equal(elements.get('practiceAssignedMeta').textContent, '2 个可做任务');
  assert.equal(elements.get('practiceAssistantCount').textContent, '1');
  assert.equal(elements.get('practiceTeacherCount').textContent, '1');
  assert.match(elements.get('practiceAssistantTasks').innerHTML, /Current assistant/);
  assert.match(elements.get('practiceTeacherTasks').innerHTML, /Current teacher/);
  assert.equal(elements.get('practiceCurrentEmpty').hidden, true);
  assert.equal(elements.get('practiceCurrentGroups').hidden, false);
  for (const [name, count] of [['Expired', '40'], ['History', '1'], ['Upcoming', '1']]) {
    assert.equal(elements.get(`practice${name}Count`).textContent, count);
    assert.equal(elements.get(`practice${name}`).hidden, false);
    assert.equal(elements.get(`practice${name}`).open, false);
  }
  assert.match(elements.get('practiceHistoryTasks').innerHTML, /href="\/listening\/example\?task_id=103"/);
  assert.doesNotMatch(elements.get('practiceHistoryTasks').innerHTML, /aria-disabled/);
  assert.match(elements.get('practiceExpiredTasks').innerHTML, /aria-disabled="true"/);
  assert.match(elements.get('practiceUpcomingTasks').innerHTML, /aria-disabled="true"/);
});

test('the actual practice center handles all-history accounts and clears old records on identity reset', async () => {
  const { sandbox, elements } = templatePage('practice/index_content.html', {
    ok: true, groups: { assistant: [expired(1)], teacher: [] },
  });
  await sandbox.taskPage.loadAssignedTasks();

  assert.equal(elements.get('practiceAssignedMeta').textContent, '暂无可做任务');
  assert.equal(elements.get('practiceCurrentEmpty').hidden, false);
  assert.equal(elements.get('practiceCurrentGroups').hidden, true);
  assert.equal(elements.get('practiceExpiredCount').textContent, '1');
  elements.get('practiceExpired').open = true;
  sandbox.taskPage.hideAssignedTasks();

  assert.equal(elements.get('practiceAssignedTasks').style.display, 'none');
  for (const name of ['Expired', 'History', 'Upcoming']) {
    assert.equal(elements.get(`practice${name}`).hidden, true);
    assert.equal(elements.get(`practice${name}`).open, false);
    assert.equal(elements.get(`practice${name}Count`).textContent, '0');
    assert.equal(elements.get(`practice${name}Tasks`).innerHTML, '');
  }
});
