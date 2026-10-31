const test = require('node:test');
const assert = require('node:assert/strict');
const planner = require('../static/js/task_planner.js');

test('execution records label every current action in Chinese and retain useful details', () => {
  const actions = { save_draft: '保存草稿', confirm: '确认安排', cancel: '取消安排', enable: '启用自动布置', disable: '暂停自动布置', blocked: '进入待处理', auto_publish: '自动布置完成', publish: '立即布置完成', failed: '布置失败' };
  for (const [action, label] of Object.entries(actions)) assert.equal(planner.eventLabel({ action }), label);
  assert.equal(planner.eventLabel({ action: 'blocked', detail: '前置任务未完成' }), '进入待处理 · 前置任务未完成');
  assert.equal(planner.eventLabel({ action: 'future_action' }), 'future_action');
});

test('date arithmetic uses calendar days across months and leap years', () => {
  assert.equal(planner.addDays('2026-10-31', 1), '2026-11-01');
  assert.equal(planner.addDays('2024-02-28', 1), '2024-02-29');
  assert.equal(planner.addDays('2026-01-01', -1), '2025-12-31');
  assert.throws(() => planner.addDays('2026-02-30', 1));
  assert.throws(() => planner.addDays('', 1));
});

test('immediate publication is offered only for today and a publishable state', () => {
  for (const status of ['draft', 'blocked', 'published', 'cancelled']) {
    assert.equal(planner.canPublish({ status, target_date: '2026-10-31' }, '2026-10-31'), false);
  }
  for (const status of ['ready', 'failed']) {
    assert.equal(planner.canPublish({ status, target_date: '2026-10-31' }, '2026-10-31'), true);
    assert.equal(planner.canPublish({ status, target_date: '2026-10-30' }, '2026-10-31'), false);
    assert.equal(planner.canPublish({ status, target_date: '2026-11-01' }, '2026-10-31'), false);
  }
});

test('expired drafts must be rescheduled rather than confirmed', () => {
  assert.equal(planner.canConfirm({ status: 'draft', target_date: '2026-10-30' }, '2026-10-31'), false);
  assert.equal(planner.canConfirm({ status: 'draft', target_date: '2026-11-01' }, '2026-10-31'), true);
  assert.equal(planner.canConfirm({ status: 'published', target_date: '2026-11-01' }, '2026-10-31'), false);
});

test('summary counts tomorrow specifically and distinguishes unpublished expired entries', () => {
  const result = planner.summary([
    { status: 'ready', target_date: '2026-11-01' },
    { status: 'ready', target_date: '2026-11-02' },
    { status: 'ready', target_date: '2026-10-30' },
    { status: 'draft', target_date: '2026-10-30' },
    { status: 'published', target_date: '2026-10-30' },
    { status: 'failed', target_date: '2026-10-31' },
    { status: 'cancelled', target_date: '2026-10-30' }
  ], '2026-10-31');
  assert.deepEqual(result, { tomorrow: 1, draft: 1, attention: 3, published: 1 });
});

test('double-clicked mutations share an in-flight lock until completion', async () => {
  const gate = planner.createGate();
  let release;
  let writes = 0;
  const first = gate.run('entry-1', async () => { writes++; await new Promise(resolve => { release = resolve; }); return 'saved'; });
  assert.equal(gate.busy('entry-1'), true);
  const second = await gate.run('entry-1', async () => { writes++; });
  assert.deepEqual(second, { skipped: true });
  assert.equal(writes, 1);
  release();
  assert.equal(await first, 'saved');
  assert.equal(gate.busy('entry-1'), false);
});

test('failed mutations release their lock and can be explicitly retried', async () => {
  const gate = planner.createGate();
  await assert.rejects(gate.run('entry-3', async () => { throw new Error('conflict'); }), /conflict/);
  assert.equal(gate.busy('entry-3'), false);
  assert.equal(await gate.run('entry-3', async () => 'retry'), 'retry');
});

test('JSON writes send same-origin credentials, current CSRF token and exact version', async () => {
  let captured;
  let csrf = 'first';
  const request = planner.createRequest(async (path, init) => {
    captured = { path, init };
    return { ok: true, status: 200, json: async () => ({ ok: true, entry: { version: 5 } }) };
  }, () => csrf);
  csrf = 'refreshed';
  const result = await request('/api/task-planner/entries/12/confirm', { method: 'POST', body: { version: 4 } });
  assert.equal(captured.init.credentials, 'same-origin');
  assert.equal(captured.init.headers['X-CSRF-Token'], 'refreshed');
  assert.equal(captured.init.headers['Content-Type'], 'application/json');
  assert.deepEqual(JSON.parse(captured.init.body), { version: 4 });
  assert.equal(result.entry.version, 5);
});

test('read-only requests never add a body or mutation header', async () => {
  const request = planner.createRequest(async (_path, init) => {
    assert.equal(init.method, 'GET');
    assert.equal(init.body, undefined);
    assert.equal(init.headers['X-CSRF-Token'], undefined);
    return { ok: true, json: async () => ({ ok: true, entries: [] }) };
  }, () => 'csrf');
  await request('/api/task-planner/entries');
});

test('server conflicts retain status so the UI can reload the latest version', async () => {
  const request = planner.createRequest(async () => ({
    ok: false, status: 409,
    json: async () => ({ ok: false, error: 'version_conflict', message: '安排已被修改' })
  }), () => 'csrf');
  await assert.rejects(request('/api/task-planner/entries/1'), error => error.status === 409 && error.code === 'version_conflict' && error.message === '安排已被修改');
});

test('expired login HTML and network errors do not appear as successful saves', async () => {
  const html = planner.createRequest(async () => ({ ok: true, json: async () => { throw new Error('not json'); } }), () => 'csrf');
  await assert.rejects(html('/api/task-planner/bootstrap'), /重新登录/);
  const offline = planner.createRequest(async () => { throw new Error('offline'); }, () => 'csrf');
  await assert.rejects(offline('/api/task-planner/entries'), /网络连接失败/);
});

test('question-type selection submits only explicit selected groups', () => {
  const selection = new Map([['gA', { label: 'A' }], ['gC', { label: 'C' }]]);
  assert.deepEqual(planner.buildSelection('question_type', selection, { subject: 'reading', standard_type: 'judgment', pace: 'training' }), {
    subject: 'reading', standard_type: 'judgment', group_ids: ['gA', 'gC'], pace: 'training'
  });
  assert.throws(() => planner.buildSelection('question_type', new Map(), {}), /选择具体/);
});

test('vocabulary saves the edited range without mutating the catalog selection', () => {
  const book = { id: 8, selection: { book_id: 8, word_start: 1, word_end: 80, dictation_order: 'random' } };
  const result = planner.buildSelection('dictation', new Map([['8', book]]), { word_start: '21', word_end: '40', vocabulary_goal: 'reading' });
  assert.equal(result.word_start, 21);
  assert.equal(result.word_end, 40);
  assert.equal(result.dictation_order, 'random');
  assert.equal(book.selection.word_start, 1);
  assert.throws(() => planner.buildSelection('dictation', new Map([['8', book]]), { word_start: '40', word_end: '21' }), /有效/);
});

test('whole-passage and intensive selections preserve the exact chosen resource', () => {
  assert.deepEqual(planner.buildSelection('reading_passage', new Map([['test:2', { test_id: 'test', passage_number: 2 }]]), {}), { test_id: 'test', passage_number: 2 });
  assert.deepEqual(planner.buildSelection('intensive', new Map([['exercise-A', { id: 'exercise-A' }]]), { training_mode: 'review' }), { exercise_id: 'exercise-A', training_mode: 'review' });
});

test('HTTP success with blocked or failed publication never reports a published task', async () => {
  for (const status of ['blocked', 'failed']) {
    const request = planner.createRequest(async () => ({ ok: true, status: 200, json: async () => ({ ok: true, entry: { status, error: '前置任务尚未完成' } }) }), () => 'csrf');
    const result = await request('/api/task-planner/entries/4/publish', { method: 'POST', body: { version: 1 } });
    const feedback = planner.mutationFeedback('publish', result.entry);
    assert.equal(feedback.error, true);
    assert.match(feedback.message, /前置任务尚未完成/);
    assert.doesNotMatch(feedback.message, /已布置到学生任务列表/);
  }
  assert.deepEqual(planner.mutationFeedback('publish', { status: 'published' }), { message: '已布置到学生任务列表。', error: false });
  assert.equal(planner.mutationFeedback('publish', undefined).error, true);
});

test('missing old prerequisite remains selected instead of being silently removed', () => {
  const historical = planner.prerequisiteOptions([{ id: 103, title: '最近任务', date: '2026-10-31', status_label: '已完成' }], 7);
  assert.equal(historical.selected, '7');
  assert.equal(historical.options[0].id, '7');
  assert.equal(historical.missing, true);
  assert.match(historical.options[0].label, /保留当前前置/);
  const whileLoadingOrFailed = planner.prerequisiteOptions([], 7);
  assert.equal(whileLoadingOrFailed.selected, '7');
  assert.equal(whileLoadingOrFailed.options.length, 1);
});

test('explicitly cleared prerequisite stays clear when late task options arrive', () => {
  const result = planner.prerequisiteOptions([{ id: 7, title: '原前置', date: '2026-10-30', status_label: '已完成' }], '');
  assert.equal(result.selected, '');
  assert.equal(result.missing, false);
  const restored = planner.prerequisiteOptions([{ id: 7, title: '原前置', date: '2026-10-30', status_label: '已完成' }], 7);
  assert.equal(restored.selected, '7');
  assert.equal(restored.options.length, 1);
  assert.equal(restored.missing, false);
});
