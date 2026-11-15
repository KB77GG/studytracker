const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const guard = require('../static/js/exam_guard.js');

class Node {
  constructor(tag = 'div', doc = null) {
    this.tagName = tag.toUpperCase();
    this.doc = doc;
    this.children = [];
    this.attributes = new Map();
    this.events = new Map();
    this.hidden = false;
    this.isConnected = true;
    this.className = '';
    this.textContent = '';
    this.classes = new Set();
    this.classList = {
      add: name => this.classes.add(name),
      remove: name => this.classes.delete(name),
      toggle: (name, on) => on ? this.classes.add(name) : this.classes.delete(name),
      contains: name => this.classes.has(name),
    };
  }
  appendChild(node) { this.children.push(node); node.parent = this; return node; }
  remove() { this.isConnected = false; if (this.parent) this.parent.children = this.parent.children.filter(node => node !== this); }
  setAttribute(key, value) { this.attributes.set(key, String(value)); }
  getAttribute(key) { return this.attributes.has(key) ? this.attributes.get(key) : null; }
  removeAttribute(key) { this.attributes.delete(key); }
  addEventListener(type, fn, options) {
    if (!this.events.has(type)) this.events.set(type, []);
    this.events.get(type).push({ fn, options });
  }
  removeEventListener(type, fn) { this.events.set(type, (this.events.get(type) || []).filter(item => item.fn !== fn)); }
  emit(type, extra = {}) {
    const event = { type, target: this, defaultPrevented: false, preventDefault() { this.defaultPrevented = true; }, ...extra };
    (this.events.get(type) || []).forEach(item => item.fn(event));
    return event;
  }
  focus() { if (this.doc) this.doc.activeElement = this; }
  contains(node) { return node === this || this.children.some(child => child.contains(node)); }
  matches(selector) { return selector === 'textarea[id^="essayTask"]' && this.tagName === 'TEXTAREA' && this.id.startsWith('essayTask'); }
  closest(selector) {
    if (selector.includes('input, textarea') && ['INPUT', 'TEXTAREA'].includes(this.tagName)) return this;
    if (selector.includes('[data-task]') && this.getAttribute('data-task')) return this;
    return this.parent ? this.parent.closest(selector) : null;
  }
}

function find(node, className) {
  if (!node) return null;
  if (node.className === className) return node;
  for (const child of node.children) {
    const match = find(child, className);
    if (match) return match;
  }
  return null;
}

function harness(section = 'reading', mode = 'enforce') {
  const doc = new Node('document');
  doc.body = new Node('body', doc);
  doc.createElement = tag => new Node(tag, doc);
  doc.visibilityState = 'visible';
  doc.activeElement = doc.body;
  const start = new Node('a', doc);
  start.setAttribute('href', '/exam/1/session/example/listening?practice_source=test');
  start.setAttribute('data-practice-entry', '');
  start.setAttribute('data-disabled', 'true');
  doc.querySelectorAll = () => [start];
  const win = new Node('window');
  const values = new Map();
  const requests = [];
  const intervals = new Map();
  let nextInterval = 0;
  let response = { ok: true, mode, acked: true, is_locked: false, exempt: false, device_bound: true, leave_count: 0, hidden_seconds: 0 };
  let failure = null;
  win.document = doc;
  win.getComputedStyle = () => ({ getPropertyValue: () => '1' });
  win.navigator = { sendBeacon: () => false };
  win.localStorage = { getItem: key => values.get(key) || null, setItem: (key, value) => values.set(key, value) };
  win.crypto = { randomUUID: (() => { let i = 0; return () => `device-uuid-000${++i}`; })() };
  win.setTimeout = setTimeout;
  win.clearTimeout = clearTimeout;
  win.setInterval = (fn, ms) => { intervals.set(++nextInterval, { fn, ms }); return nextInterval; };
  win.clearInterval = id => intervals.delete(id);
  win.URLSearchParams = URLSearchParams;
  win.AbortController = AbortController;
  win.Blob = Blob;
  win.innerWidth = 1024;
  win.screen = { width: 1024 };
  win.fetch = async (url, options) => {
    requests.push({ url, options, payload: options.body ? JSON.parse(options.body) : null });
    if (failure) throw failure;
    return { ok: true, json: async () => ({ ...response }) };
  };
  const config = { mode, section, event_url: '/event', state_url: '/state', max_leaves: 3, max_hidden_seconds: 60, student_name: 'Synthetic Student' };
  return {
    win, doc, config, start, requests, intervals,
    setState: patch => { response = { ...response, ...patch }; },
    fail: () => { failure = new Error('offline'); },
    recover: () => { failure = null; },
    root: () => doc.body.children.find(node => node.id === 'exam-integrity-root'),
    box() { const ta = new Node('textarea', doc); ta.id = 'essayTask1'; ta.setAttribute('data-task', '1'); ta.value = 'My own essay'; ta.selectionStart = 0; ta.selectionEnd = ta.value.length; return ta; },
  };
}
const flush = () => new Promise(resolve => setImmediate(resolve));

async function installed(section, mode, patch) {
  const h = harness(section, mode);
  if (patch) h.setState(patch);
  h.instance = guard.install(h.win, h.config);
  await flush();
  return h;
}

test('off and unknown modes have no DOM, network, listeners or timer side effects', () => {
  for (const mode of ['off', 'bad', undefined]) {
    const h = harness('reading', mode);
    h.config.mode = mode;
    assert.equal(guard.install(h.win, h.config), null);
    assert.equal(h.requests.length, 0);
    assert.equal(h.doc.body.children.length, 0);
    assert.equal(h.intervals.size, 0);
  }
});

test('listening never covers the paper even for stored lock or device conflict', () => {
  const view = guard.viewState({ mode: 'enforce', is_locked: true, device_conflict: true, leave_count: 3 }, 'listening');
  assert.equal(view.locked, false);
  assert.equal(view.conflict, false);
  assert.equal(view.warning, true);
});

test('monitor and exempt sessions cannot be locked or device blocked', () => {
  for (const state of [{ mode: 'monitor' }, { mode: 'enforce', exempt: true }]) {
    const view = guard.viewState({ ...state, is_locked: true, device_conflict: true, leave_count: 8 }, 'reading');
    assert.equal(view.locked, false);
    assert.equal(view.conflict, false);
    assert.equal(view.warning, false);
  }
});

test('unhealthy guard has no enforcement or acknowledgement gate', () => {
  assert.deepEqual(guard.viewState({ mode: 'enforce', is_locked: true }, 'process', false), {
    enabled: false, enforce: false, locked: false, conflict: false, ackRequired: false, warning: false,
  });
});

test('visibility state machine ignores duplicates and includes only elapsed hidden milliseconds', () => {
  const transition = guard.visibilityTracker('page-1');
  assert.equal(transition('visible', 1), null);
  assert.deepEqual(transition('hidden', 1000), { type: 'hidden', page_id: 'page-1', client_ts: 1000 });
  assert.equal(transition('hidden', 1800), null);
  assert.deepEqual(transition('visible', 3000), { type: 'visible', page_id: 'page-1', client_ts: 3000, client_hidden_ms: 2000 });
  assert.equal(transition('visible', 5000), null);
});

test('narrow viewport is a soft signal with finite fallback', () => {
  assert.deepEqual(guard.viewportSignal(500, 1000), { ratio: 0.5, narrow: true });
  assert.equal(guard.viewportSignal(700, 1000).narrow, false);
  assert.equal(guard.viewportSignal(0, 1000).narrow, false);
  assert.equal(guard.viewportSignal(500, 0).narrow, false);
  assert.equal(guard.viewportSignal(NaN, 1000).narrow, false);
});

test('internal paste comparison is exact, nonempty and type checked', () => {
  assert.equal(guard.allowsInternalPaste('own text', 'own text'), true);
  assert.equal(guard.allowsInternalPaste('external', 'own text'), false);
  assert.equal(guard.allowsInternalPaste('own text ', 'own text'), false);
  assert.equal(guard.allowsInternalPaste('', ''), false);
  assert.equal(guard.allowsInternalPaste(null, null), false);
});

test('startup failure leaves the original Start link intact and starts no requests', () => {
  const h = harness('process');
  h.win.localStorage.getItem = () => { throw new Error('storage unavailable'); };
  guard.install(h.win, h.config);
  assert.equal(h.start.getAttribute('href'), '/exam/1/session/example/listening?practice_source=test');
  assert.equal(h.requests.length, 0);
  assert.equal(h.intervals.size, 0);
});

test('only enforce acknowledgements disable Start, preserving existing progression gates', async () => {
  const h = await installed('process', 'enforce', { acked: false });
  assert.equal(h.start.getAttribute('href'), null);
  assert.equal(h.start.getAttribute('data-practice-entry'), null);
  assert.equal(h.start.getAttribute('data-disabled'), 'true');
  h.setState({ acked: true });
  await h.instance.poll();
  assert.equal(h.start.getAttribute('href'), '/exam/1/session/example/listening?practice_source=test');
  assert.equal(h.start.getAttribute('data-practice-entry'), '');
  assert.equal(h.start.getAttribute('data-disabled'), 'true');
  h.instance.stop();
  const monitor = await installed('process', 'monitor', { acked: false });
  assert.equal(monitor.start.getAttribute('href'), '/exam/1/session/example/listening?practice_source=test');
  assert.equal(find(monitor.root(), 'exam-integrity-rules').hidden, false);
  monitor.instance.stop();
});

test('server lock focuses its own overlay; unlock restores the paper without touching timers', async () => {
  const h = await installed('reading', 'enforce', { is_locked: true, locked_reason: '累计离开 3 次' });
  const overlay = find(h.root(), 'exam-integrity-overlay');
  assert.equal(overlay.hidden, false);
  assert.equal(h.doc.activeElement, overlay);
  const unrelatedTimer = h.win.setInterval(() => {}, 1000);
  h.setState({ is_locked: false });
  await h.instance.poll();
  assert.equal(overlay.hidden, true);
  assert.equal(h.doc.activeElement, h.doc.body);
  h.instance.stop();
  assert.equal(h.intervals.has(unrelatedTimer), true);
});

test('blur is manually dismissible and creates no visibility strike', async () => {
  const h = await installed('reading', 'enforce');
  h.win.emit('blur');
  await flush();
  const overlay = find(h.root(), 'exam-integrity-overlay');
  assert.equal(overlay.hidden, false);
  find(overlay, 'exam-integrity-button').emit('click');
  assert.equal(overlay.hidden, true);
  assert.equal(h.requests.filter(r => r.payload && r.payload.type === 'hidden').length, 0);
  assert.equal(h.requests.filter(r => r.payload && r.payload.type === 'blur').length, 1);
  h.instance.stop();
});

test('listening blur and narrow viewport remain nonblocking', async () => {
  const h = await installed('listening', 'enforce', { is_locked: true, leave_count: 3 });
  h.win.emit('blur');
  h.win.innerWidth = 500;
  h.win.emit('resize');
  await flush();
  assert.equal(find(h.root(), 'exam-integrity-overlay').hidden, true);
  assert.equal(find(h.root(), 'exam-integrity-warning').hidden, false);
  assert.equal(h.requests.some(r => r.payload && r.payload.type === 'viewport' && r.payload.detail.ratio < 0.7), true);
  h.instance.stop();
});

test('failed state request removes lock and clipboard enforcement; recovered state can restore it', async () => {
  const h = await installed('writing', 'enforce', { is_locked: true });
  h.fail();
  await h.instance.poll();
  assert.equal(h.root().hidden, true);
  assert.equal(h.doc.body.classList.contains('exam-integrity-enforce'), false);
  const event = h.doc.emit('paste', { target: h.box(), clipboardData: { getData: () => 'External text' } });
  assert.equal(event.defaultPrevented, false);
  h.recover();
  await h.instance.poll();
  assert.equal(h.root().hidden, false);
  assert.equal(find(h.root(), 'exam-integrity-overlay').hidden, false);
  h.instance.stop();
});

test('emergency off restores Start and stops all guard requests and timers', async () => {
  const h = await installed('process', 'enforce', { acked: false });
  h.setState({ mode: 'off' });
  await h.instance.poll();
  const count = h.requests.length;
  assert.equal(h.root(), undefined);
  assert.equal(h.start.getAttribute('href'), '/exam/1/session/example/listening?practice_source=test');
  assert.equal(h.intervals.size, 0);
  h.win.emit('blur');
  h.doc.emit('visibilitychange');
  await h.instance.poll();
  assert.equal(h.requests.length, count);
});

test('state poll includes device identity and section, and a new conflicted device claims after reset', async () => {
  const h = await installed('reading', 'enforce', { device_conflict: true });
  h.setState({ device_bound: false });
  await h.instance.poll();
  const get = h.requests.find(r => r.options.method === 'GET');
  const url = new URL(get.url, 'https://example.test');
  assert.equal(url.searchParams.get('section'), 'reading');
  assert.equal(url.searchParams.has('device_id'), false);
  assert.ok(get.options.headers['X-Exam-Integrity-Device'].length >= 8);
  assert.equal(get.url.includes(get.options.headers['X-Exam-Integrity-Device']), false);
  assert.ok(url.searchParams.get('page_id'));
  assert.equal(h.requests.filter(r => r.payload && r.payload.type === 'hello').length, 2);
  h.instance.stop();
});

test('external writing paste/drop/beforeinput are blocked and send length only', async () => {
  for (const type of ['paste', 'drop', 'beforeinput']) {
    const h = await installed('writing', 'enforce');
    const target = h.box();
    const extra = type === 'paste' ? { clipboardData: { getData: () => 'private external essay' } }
      : { dataTransfer: { getData: () => 'private external essay' }, inputType: 'insertFromPaste' };
    const event = h.doc.emit(type, { target, ...extra });
    assert.equal(event.defaultPrevented, true);
    const blocked = h.requests.find(r => r.payload && r.payload.type === 'paste_blocked').payload;
    assert.equal(blocked.detail.length, 22);
    assert.equal(blocked.detail.blocked, true);
    assert.equal(JSON.stringify(h.requests).includes('private external essay'), false);
    h.instance.stop();
  }
});

test('internal writing copy and subsequent paste/beforeinput remain native', async () => {
  const h = await installed('writing', 'enforce');
  const target = h.box();
  const copy = h.doc.emit('cut', { target });
  const paste = h.doc.emit('paste', { target, clipboardData: { getData: () => target.value } });
  const before = h.doc.emit('beforeinput', { target, inputType: 'insertFromPaste', data: null });
  assert.equal(copy.defaultPrevented, false);
  assert.equal(paste.defaultPrevented, false);
  assert.equal(before.defaultPrevented, false);
  assert.equal(h.requests.some(r => r.payload && r.payload.type === 'paste_blocked'), false);
  h.instance.stop();
});

test('monitor records external paste/copy without preventing default', async () => {
  const h = await installed('writing', 'monitor');
  const paste = h.doc.emit('paste', { target: h.box(), clipboardData: { getData: () => 'outside' } });
  const copy = h.doc.emit('copy', { target: new Node('p') });
  assert.equal(paste.defaultPrevented, false);
  assert.equal(copy.defaultPrevented, false);
  assert.equal(h.requests.filter(r => r.payload && /_blocked$/.test(r.payload.type)).length, 2);
  assert.equal(h.requests.filter(r => r.payload && r.payload.detail).every(r => r.payload.detail.blocked !== true), true);
  h.instance.stop();
});

test('ordinary input copy is never blocked and selection/context menu are untouched', async () => {
  const h = await installed('reading', 'enforce');
  assert.equal(h.doc.emit('copy', { target: new Node('input') }).defaultPrevented, false);
  assert.equal(h.doc.events.has('contextmenu'), false);
  assert.equal(h.doc.events.has('selectstart'), false);
  h.instance.stop();
});

test('only clipboard/drop/beforeinput listeners are nonpassive', async () => {
  const h = await installed('reading', 'enforce');
  for (const node of [h.doc, h.win, find(h.root(), 'exam-integrity-button')]) {
    for (const [type, entries] of node.events) {
      for (const entry of entries) assert.equal(entry.options.passive, !['copy', 'cut', 'paste', 'drop', 'beforeinput'].includes(type));
    }
  }
  const source = fs.readFileSync(require.resolve('../static/js/exam_guard.js'), 'utf8');
  assert.equal(source.includes('stopPropagation'), false);
  assert.equal(source.includes('inert'), false);
  h.instance.stop();
});

test('watermark is outside the paper and CSS cannot intercept clicks or change highlight geometry', async () => {
  const h = await installed('reading', 'enforce');
  assert.equal(h.root().parent, h.doc.body);
  const watermark = find(h.root(), 'exam-integrity-watermark');
  assert.equal(watermark.getAttribute('aria-hidden'), 'true');
  assert.equal(watermark.children.length, 20);
  const css = fs.readFileSync(require.resolve('../static/css/exam_guard.css'), 'utf8');
  assert.match(css, /\.exam-integrity-watermark \{[^}]*position: fixed;[^}]*pointer-events: none;/);
  assert.equal(css.includes('data-hl-root'), false);
  h.instance.stop();
});

test('request timeout releases the acknowledgement gate even if fetch never settles', async () => {
  const h = await installed('process', 'enforce', { acked: false });
  let timeout;
  h.win.setTimeout = fn => { timeout = fn; return 101; };
  h.win.clearTimeout = () => {};
  h.win.fetch = () => new Promise(() => {});
  const pending = h.instance.poll();
  timeout();
  await pending;
  assert.equal(h.root().hidden, true);
  assert.equal(h.start.getAttribute('href'), '/exam/1/session/example/listening?practice_source=test');
  h.instance.stop();
});

test('off response permanently wins over an older enforce response still in flight', async () => {
  const h = await installed('reading', 'enforce');
  const pending = [];
  h.win.fetch = () => new Promise(resolve => pending.push(resolve));
  h.win.emit('blur');
  const polling = h.instance.poll();
  assert.equal(pending.length, 2);
  pending[1]({ ok: true, json: async () => ({ mode: 'off' }) });
  await polling;
  pending[0]({ ok: true, json: async () => ({ mode: 'enforce', is_locked: true }) });
  await flush();
  assert.equal(h.root(), undefined);
  assert.equal(h.intervals.size, 0);
});

test('an older but valid off response also releases a newer locked state', async () => {
  const h = await installed('reading', 'enforce');
  const pending = [];
  h.win.fetch = () => new Promise(resolve => pending.push(resolve));
  h.win.emit('blur');
  const polling = h.instance.poll();
  pending[1]({ ok: true, json: async () => ({ mode: 'enforce', is_locked: true, device_bound: true }) });
  await polling;
  assert.equal(find(h.root(), 'exam-integrity-overlay').hidden, false);
  pending[0]({ ok: true, json: async () => ({ mode: 'off' }) });
  await flush();
  assert.equal(h.root(), undefined);
});

test('hidden uses sendBeacon and visible contains the same page id and finite fallback duration', async () => {
  const h = await installed('reading', 'enforce');
  const beacons = [];
  h.win.navigator.sendBeacon = (url, body) => { beacons.push({ url, body }); return true; };
  h.doc.visibilityState = 'hidden';
  h.doc.emit('visibilitychange');
  h.doc.emit('visibilitychange');
  h.doc.visibilityState = 'visible';
  h.doc.emit('visibilitychange');
  await flush();
  assert.equal(beacons.length, 1);
  const hidden = JSON.parse(await beacons[0].body.text());
  const visible = h.requests.find(r => r.payload && r.payload.type === 'visible').payload;
  assert.equal(hidden.type, 'hidden');
  assert.equal(hidden.page_id, visible.page_id);
  assert.equal(typeof visible.client_hidden_ms, 'number');
  assert.ok(visible.client_hidden_ms >= 0);
  h.instance.stop();
});

test('a listener exception fails open before it can prevent a paste', async () => {
  const h = await installed('writing', 'enforce');
  const event = h.doc.emit('paste', { target: h.box(), clipboardData: { getData: () => { throw new Error('unsupported clipboard'); } } });
  assert.equal(event.defaultPrevented, false);
  assert.equal(h.root().hidden, true);
  h.instance.stop();
});

test('rejected or late Wake Lock cannot break the exam or remain held after off', async () => {
  const h = harness('reading', 'enforce');
  let releaseWake;
  let released = false;
  h.win.navigator.wakeLock = { request: () => new Promise(resolve => { releaseWake = resolve; }) };
  h.instance = guard.install(h.win, h.config);
  await flush();
  assert.equal(h.root().hidden, false);
  h.setState({ mode: 'off' });
  await h.instance.poll();
  releaseWake({ release: async () => { released = true; } });
  await flush();
  assert.equal(released, true);
  assert.equal(h.root(), undefined);
});


test('a missing guard stylesheet fails open and can recover when the stylesheet arrives', async () => {
  const h = harness('process', 'enforce');
  h.setState({ acked: false });
  h.win.getComputedStyle = () => ({ getPropertyValue: () => '' });
  h.instance = guard.install(h.win, h.config);
  await flush();
  assert.equal(h.root().hidden, true);
  assert.ok(h.start.getAttribute('href'));
  h.win.getComputedStyle = () => ({ getPropertyValue: () => '1' });
  await h.instance.poll();
  assert.equal(h.root().hidden, false);
  assert.equal(h.start.getAttribute('href'), null);
  h.instance.stop();
});


test('normal pages avoid five-second requests while a locked page polls for unlock', async () => {
  const normal = await installed('reading', 'enforce');
  const normalCount = normal.requests.length;
  const refreshNormal = Array.from(normal.intervals.values())[0];
  assert.equal(refreshNormal.ms, 5000);
  await refreshNormal.fn();
  assert.equal(normal.requests.length, normalCount);
  normal.instance.stop();
  const locked = await installed('reading', 'enforce', { is_locked: true });
  const lockedCount = locked.requests.length;
  await Array.from(locked.intervals.values())[0].fn();
  assert.equal(locked.requests.length, lockedCount + 1);
  locked.instance.stop();
});

test('normal visible pages refresh at fifteen seconds to leave four seconds for fail-open', async () => {
  const h = harness('reading', 'enforce');
  let now = 0;
  h.win.performance = { now: () => now };
  h.instance = guard.install(h.win, h.config);
  await flush();
  const refresh = Array.from(h.intervals.values())[0].fn;
  const count = h.requests.length;
  now = 10000;
  await refresh();
  assert.equal(h.requests.length, count);
  h.setState({ mode: 'off' });
  now = 15000;
  await refresh();
  assert.equal(h.requests.at(-1).payload.type, 'heartbeat');
  assert.equal(h.root(), undefined);
});


test('the old successfully bound page cannot claim again after the teacher clears the binding', async () => {
  const h = await installed('reading', 'enforce');
  assert.equal(h.requests.filter(r => r.payload && r.payload.type === 'hello').length, 1);
  h.setState({ device_bound: false });
  await h.instance.poll();
  assert.equal(h.requests.filter(r => r.payload && r.payload.type === 'hello').length, 1);
  let now = 0;
  h.win.performance = { now: () => now };
  h.setState({ device_bound: true, device_conflict: true });
  await h.instance.poll();
  h.setState({ device_bound: false, device_conflict: false });
  await h.instance.poll();
  assert.equal(h.requests.filter(r => r.payload && r.payload.type === 'hello').length, 1);
  h.instance.stop();
});

test('a failed initial hello may retry its first device claim after service recovery', async () => {
  const h = harness('reading', 'enforce');
  h.fail();
  h.instance = guard.install(h.win, h.config);
  await flush();
  h.recover();
  h.setState({ device_bound: false });
  await h.instance.poll();
  assert.equal(h.requests.filter(r => r.payload && r.payload.type === 'hello').length, 2);
  h.instance.stop();
});


test('a state response confirming ownership also prevents reclaim after a lost hello response', async () => {
  const h = harness('reading', 'enforce');
  h.fail();
  h.instance = guard.install(h.win, h.config);
  await flush();
  h.recover();
  h.setState({ device_bound: true, device_conflict: false });
  await h.instance.poll();
  h.setState({ device_bound: false });
  await h.instance.poll();
  assert.equal(h.requests.filter(r => r.payload && r.payload.type === 'hello').length, 1);
  h.instance.stop();
});
