const test = require('node:test');
const assert = require('node:assert/strict');
const recovery = require('../static/js/task_planner_recovery.js');
const planner = require('../static/js/task_planner.js');
const series = require('../static/js/task_planner_series.js');

const item = { id: '21:2026-11-01', series_id: 21, student_id: 7, student_name: '合成学生', series_name: '听阅轮换', source_date: '2026-11-01', tasks: [{ id: 101, title: '听力 P1', status_label: '未完成' }], status: 'pending', decision: null };
function preview(action = 'makeup', changes = {}) {
  return { preview_hash: 'hash-first', action, today: '2026-11-02', tasks: item.tasks, changes: [{ entry_id: 201, title: '阅读 P1', from: '2026-11-02', to: '2026-11-03' }], warnings: [], blockers: [], can_apply: true, summary: '今天补做1项，后续2项整体顺延1天。', ...changes };
}
function deferred() { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no; }); return { promise, resolve, reject }; }
class Element {
  constructor(tag = 'div') { this.tagName = tag; this.children = []; this.listeners = {}; this.attributes = {}; this.hidden = false; this.disabled = false; this.value = ''; this.open = false; this._text = ''; this.classList = { toggle() {} }; }
  set textContent(text) { this._text = String(text); this.children = []; }
  get textContent() { return this._text + this.children.map(child => child.textContent).join(''); }
  set innerHTML(_value) { throw new Error('Recovery content must use text nodes, not HTML'); }
  appendChild(child) { this.children.push(child); return child; }
  replaceChildren(...children) { this.children = children; this._text = ''; }
  setAttribute(key, value) { this.attributes[key] = value; }
  removeAttribute(key) { delete this.attributes[key]; }
  addEventListener(name, handler) { (this.listeners[name] ||= []).push(handler); }
  async emit(name) { await Promise.all((this.listeners[name] || []).map(handler => handler({ preventDefault() {} }))); }
  showModal() { this.open = true; }
  close() { this.open = false; }
}
function harness(request) {
  const ids = ['plannerRecovery', 'plannerRecoveryDialog', 'plannerStudent', 'recoveryDialogMessage', 'recoveryDialogClose', 'recoveryDialogCancel', 'recoveryRepreview', 'recoveryApply', 'recoveryInboxList', 'recoveryInboxSummary', 'recoveryInboxError', 'recoveryInboxRefresh', 'recoveryDialogTitle', 'recoveryDialogContext', 'recoveryDialogScope', 'recoveryPreviewSummary', 'recoveryTaskHeading', 'recoveryPreviewTasks', 'recoveryPreviewChanges', 'recoveryChangesSection', 'recoveryPreviewSkipped', 'recoverySkippedSection', 'recoveryPreviewWarnings', 'recoveryPreviewBlockers', 'recoveryPreviewContent', 'recoveryViewPending', 'recoveryViewResolved'];
  const elements = Object.fromEntries(ids.map(id => [id, new Element()]));
  const doc = { getElementById(id) { return elements[id] || null; }, createElement(tag) { return new Element(tag); } };
  const notices = [], errors = []; let keys = 0, refreshes = 0;
  const context = { request, state: { today: '2026-11-02' }, createGate: planner.createGate, createDraftSession: series.createDraftSession, refreshEntries: async () => { refreshes++; }, showMessage: message => notices.push(message), report: error => errors.push(error) };
  const client = recovery.mount(doc, { crypto: { randomUUID: () => 'recovery-request-' + (++keys) } }, context);
  return { client, context, elements, notices, errors, get refreshes() { return refreshes; } };
}

test('inbox filtering only carries selected student and pending/resolved view', () => {
  assert.equal(recovery.inboxQuery('', 'pending'), 'view=pending');
  assert.equal(recovery.inboxQuery('7', 'resolved'), 'view=resolved&student_id=7');
  assert.throws(() => recovery.inboxQuery(-1, 'pending'), /学生筛选/);
  assert.throws(() => recovery.inboxQuery('7&view=resolved', 'pending'), /学生筛选/);
  assert.throws(() => recovery.inboxQuery('7', 'everything'), /待处理/);
});

test('action request identifies the exact original learning day without client-supplied tasks or changes', () => {
  assert.deepEqual(recovery.actionPayload({ ...item, tasks: [{ id: 999 }], changes: [{ to: '2026-11-09' }] }, 'makeup'), { series_id: 21, source_date: '2026-11-01', action: 'makeup' });
  assert.equal(recovery.actionPayload(item, 'continue').action, 'continue');
  assert.throws(() => recovery.actionPayload(item, 'complete'), /补做或忽略/);
  assert.throws(() => recovery.actionPayload({ ...item, source_date: '2026-02-30' }, 'makeup'), /原任务日期/);
  assert.throws(() => recovery.actionPayload({ ...item, series_id: 0 }, 'makeup'), /学习线/);
});

test('summary counts students, learning lines and tasks without double counting repeated records', () => {
  const rows = [item, { ...item, source_date: '2026-10-31' }, { ...item, series_id: 22, tasks: [{ id: 102 }] }, { ...item, student_id: 8, series_id: 23, student_name: '合成学生乙', tasks: [{ id: 103 }] }];
  assert.deepEqual(recovery.counts(rows), { students: 2, lines: 3, tasks: 3, cases: 4 });
  const groups = recovery.groupByStudent(rows);
  assert.equal(groups.length, 2);
  assert.equal(groups[0].items.length, 3);
  assert.equal(groups[1].student_name, '合成学生乙');
});

test('confirmation requires a complete current preview and zero blockers', () => {
  assert.equal(recovery.canApply(preview()), true);
  for (const changes of [{ can_apply: false }, { can_apply: 'true' }, { preview_hash: '' }, { blockers: ['今天已有新任务'] }, { blockers: undefined }]) assert.equal(recovery.canApply(preview('makeup', changes)), false);
  assert.equal(recovery.canApply(null), false);
});

test('resolved labels distinguish makeup from ignoring without claiming completion', () => {
  assert.match(recovery.decisionLabel({ decision: { action: 'makeup', makeup_date: '2026-11-02', decided_at: '2026-11-02 10:20' } }), /已安排补做并顺延 · 补做日期 2026-11-02/);
  assert.equal(recovery.decisionLabel({ decision: { action: 'continue' } }), '已忽略本次');
  assert.throws(() => recovery.resultMessage({ ok: true }, 'makeup'), /未确认/);
  assert.throws(() => recovery.resultMessage({ ok: false, result: {} }, 'makeup'), /未确认/);
  assert.equal(recovery.resultMessage({ ok: true, result: {}, message: '已经处理，不重复创建。' }, 'makeup'), '已经处理，不重复创建。');
});

test('missing recovery markup leaves older page initialization intact', () => {
  assert.equal(recovery.mount({ getElementById() { return null; } }, {}, {}), null);
});

test('opening preview never applies changes and displays server dates and blockers literally', async () => {
  const calls = [];
  const h = harness(async (url, options) => { calls.push([url, options]); return { ok: true, preview: preview('makeup', { blockers: ['今天已有新任务，不能撤回'], can_apply: false, tasks: [{ id: 101, title: '<img src=x onerror=alert(1)>', status_label: '未完成' }] }) }; });
  await h.client.openPreview(item, 'makeup');
  assert.equal(calls.length, 1);
  assert.equal(calls[0][0], '/api/task-planner/inbox/preview');
  assert.equal(h.elements.recoveryApply.disabled, true);
  assert.match(h.elements.recoveryPreviewTasks.textContent, /<img src=x onerror=alert\(1\)>/);
  assert.match(h.elements.recoveryPreviewChanges.textContent, /2026-11-02→2026-11-03/);
  assert.match(h.elements.recoveryPreviewBlockers.textContent, /不能撤回/);
  assert.match(h.elements.recoveryDialogScope.textContent, /星期可能变化/);
  assert.match(h.elements.recoveryDialogScope.textContent, /其他学习线/);
  await h.client.apply();
  assert.equal(calls.length, 1);
});

test('network failure retries the identical accepted hash and request key, then refreshes all lists once', async () => {
  const applies = []; let failed = false;
  const h = harness(async (url, options) => {
    if (url.endsWith('/preview')) return { ok: true, preview: preview() };
    applies.push(options.body);
    if (!failed) { failed = true; throw new TypeError('连接中断'); }
    return { ok: true, result: { decision_id: 1 }, message: '补做已安排。' };
  });
  await h.client.openPreview(item, 'makeup');
  await h.client.apply();
  assert.equal(h.elements.plannerRecoveryDialog.open, true);
  assert.equal(h.elements.recoveryApply.disabled, false);
  assert.match(h.elements.recoveryDialogMessage.textContent, /同一请求标识/);
  await h.client.apply();
  assert.deepEqual(applies[1], applies[0]);
  assert.equal(applies[0].preview_hash, 'hash-first');
  assert.match(applies[0].request_key, /^recovery-request-/);
  assert.equal(h.refreshes, 1);
  assert.deepEqual(h.notices, ['补做已安排。']);
  assert.equal(h.elements.plannerRecoveryDialog.open, false);
});

test('double confirmation creates one apply request and blocks closing until its result arrives', async () => {
  const writing = deferred(); let count = 0;
  const h = harness(async url => {
    if (url.endsWith('/preview')) return { ok: true, preview: preview() };
    count++; return writing.promise;
  });
  await h.client.openPreview(item, 'makeup');
  const first = h.client.apply();
  await h.client.apply();
  await h.elements.recoveryDialogCancel.emit('click');
  assert.equal(count, 1);
  assert.equal(h.elements.recoveryApply.disabled, true);
  assert.equal(h.elements.plannerRecoveryDialog.open, true);
  writing.resolve({ ok: true, result: { decision_id: 2 } }); await first;
  assert.equal(h.refreshes, 1);
});

test('409 invalidates confirmation and a fresh preview receives a fresh idempotency key', async () => {
  const writes = []; let previews = 0;
  const h = harness(async (url, options) => {
    if (url.endsWith('/preview')) return { ok: true, preview: preview('makeup', { preview_hash: ++previews === 1 ? 'old-hash' : 'new-hash' }) };
    writes.push(options.body);
    if (writes.length === 1) throw Object.assign(new Error('预览已变化'), { status: 409, code: 'preview_changed' });
    return { ok: true, result: { decision_id: 3 } };
  });
  await h.client.openPreview(item, 'makeup'); await h.client.apply();
  assert.equal(h.elements.recoveryApply.disabled, true);
  assert.match(h.elements.recoveryDialogMessage.textContent, /重新预览/);
  await h.client.apply(); assert.equal(writes.length, 1);
  await h.elements.recoveryRepreview.emit('click');
  assert.equal(h.elements.recoveryApply.disabled, false);
  await h.client.apply();
  assert.equal(writes[1].preview_hash, 'new-hash');
  assert.notEqual(writes[1].request_key, writes[0].request_key);
});

test('late preview for a different case cannot replace the currently selected action', async () => {
  const first = deferred(), second = deferred(), writes = []; let calls = 0;
  const h = harness(async (url, options) => {
    if (url.endsWith('/preview')) return ++calls === 1 ? first.promise : second.promise;
    writes.push(options.body); return { ok: true, result: { decision_id: 4 } };
  });
  const a = h.client.openPreview(item, 'makeup');
  const b = h.client.openPreview({ ...item, series_id: 22, series_name: '词汇线' }, 'continue');
  second.resolve({ ok: true, preview: preview('continue', { preview_hash: 'continue-hash', changes: [] }) }); await b;
  first.resolve({ ok: true, preview: preview() }); await a;
  assert.match(h.elements.recoveryDialogContext.textContent, /词汇线/);
  assert.equal(h.elements.recoveryDialogTitle.textContent, '忽略本次，继续原计划');
  await h.client.apply();
  assert.deepEqual({ series_id: writes[0].series_id, action: writes[0].action, hash: writes[0].preview_hash }, { series_id: 22, action: 'continue', hash: 'continue-hash' });
});

test('student filtering rejects an earlier slower inbox response', async () => {
  const first = deferred(), second = deferred(), urls = [];
  const h = harness(async url => { urls.push(url); return urls.length === 1 ? first.promise : second.promise; });
  h.elements.plannerStudent.value = '7'; const a = h.client.refresh();
  h.elements.plannerStudent.value = '8'; const b = h.client.refresh();
  second.resolve({ ok: true, items: [{ ...item, student_id: 8, student_name: '合成学生乙' }] }); await b;
  first.resolve({ ok: true, items: [item] }); await a;
  assert.equal(urls[0], '/api/task-planner/inbox?view=pending&student_id=7');
  assert.equal(urls[1], '/api/task-planner/inbox?view=pending&student_id=8');
  assert.match(h.elements.recoveryInboxList.textContent, /合成学生乙/);
  assert.doesNotMatch(h.elements.recoveryInboxList.textContent, /合成学生听阅/);
});

test('changing students clears actionable old cards while the new inbox is loading', async () => {
  const next = deferred(); let reads = 0;
  const h = harness(async () => ++reads === 1 ? { ok: true, items: [item] } : next.promise);
  h.elements.plannerStudent.value = '7'; await h.client.refresh();
  assert.match(h.elements.recoveryInboxList.textContent, /合成学生/);
  assert.match(h.elements.recoveryInboxList.textContent, /补做并顺延/);
  h.elements.plannerStudent.value = '8'; const loading = h.client.refresh();
  assert.match(h.elements.recoveryInboxList.textContent, /正在读取/);
  assert.doesNotMatch(h.elements.recoveryInboxList.textContent, /合成学生|补做并顺延|忽略本次/);
  next.resolve({ ok: true, items: [{ ...item, student_id: 8, student_name: '新筛选学生' }] }); await loading;
  assert.match(h.elements.recoveryInboxList.textContent, /新筛选学生/);
});

test('a late preview after closing the dialog cannot restore confirmation or perform a write', async () => {
  const delayed = deferred(); let writes = 0;
  const h = harness(async url => {
    if (url.endsWith('/preview')) return delayed.promise;
    writes++; return { ok: true, result: { decision_id: 5 } };
  });
  const loading = h.client.openPreview(item, 'makeup');
  await h.elements.recoveryDialogCancel.emit('click');
  assert.equal(h.elements.plannerRecoveryDialog.open, false);
  delayed.resolve({ ok: true, preview: preview() }); await loading;
  assert.equal(h.elements.plannerRecoveryDialog.open, false);
  assert.equal(h.elements.recoveryApply.disabled, true);
  await h.client.apply();
  assert.equal(writes, 0);
});

test('resolved inbox is read-only and displays the recorded decision', async () => {
  const urls = [];
  const h = harness(async url => { urls.push(url); return { ok: true, items: [{ ...item, status: 'resolved', decision: { action: 'continue' } }] }; });
  await h.elements.recoveryViewResolved.emit('click');
  await new Promise(resolve => setImmediate(resolve));
  assert.equal(urls[0], '/api/task-planner/inbox?view=resolved');
  assert.match(h.elements.recoveryInboxList.textContent, /已忽略本次/);
  assert.doesNotMatch(h.elements.recoveryInboxList.textContent, /补做并顺延/);
  assert.equal(h.elements.recoveryViewResolved.attributes['aria-pressed'], 'true');
});

test('successful mutation followed by a list refresh failure is never offered for retry', async () => {
  const h = harness(async url => url.endsWith('/preview') ? { ok: true, preview: preview() } : { ok: true, result: { decision_id: 6 } });
  h.context.refreshEntries = async () => { throw new Error('列表读取失败'); };
  await h.client.openPreview(item, 'makeup'); await h.client.apply();
  assert.equal(h.errors[0].message, '列表读取失败');
  assert.equal(h.notices.length, 1);
  assert.equal(h.elements.plannerRecoveryDialog.open, false);
  assert.equal(h.elements.recoveryApply.disabled, true);
});
