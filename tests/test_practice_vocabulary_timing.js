'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');

function storage() {
  const values = new Map();
  return {
    values, writes: 0,
    get length() { return values.size; },
    key(i) { return [...values.keys()][i] || null; },
    getItem(k) { return values.get(k) || null; },
    setItem(k, v) { this.writes++; values.set(k, v); },
    removeItem(k) { values.delete(k); },
  };
}
function fixture(local = storage()) {
  let now = 1000;
  const root = { localStorage: local };
  const context = vm.createContext({ window: root, Date, Math });
  for (const file of ['transport', 'timing']) vm.runInContext(
    fs.readFileSync(require.resolve(`../static/js/practice_vocabulary_${file}.js`), 'utf8'), context);
  return {
    local, root, now: () => now,
    at: value => { now = value; },
    timer(task = 1, identity = 'student') { return new root.PracticeVocabularyTransport.Timing(task, identity, () => now); },
  };
}
function start(timer, sessionId) {
  timer.observe(sessionId == null ? { stage: 'learning' } : { stage: 'review', review: { session_id: sessionId } });
  timer.setState(sessionId == null ? 'question' : 'review_question');
}

test('visible recent activity accumulates, inactivity stops at exactly five minutes', () => {
  const f = fixture(), timer = f.timer(); start(timer);
  f.at(20 * 60 * 1000 + 1000);
  assert.equal(timer.snapshot(null), 300);
});
test('deliberate activity resumes after idle without filling the idle gap', () => {
  const f = fixture(), timer = f.timer(); start(timer);
  f.at(601000); timer.activity();
  f.at(661000);
  assert.equal(timer.snapshot(null), 360);
});
test('17:00 ten minutes, hidden until 22:00, then fifteen minutes totals 25 minutes', () => {
  const f = fixture(), timer = f.timer(); start(timer);
  for (let i = 1; i <= 10; i++) { f.at(1000 + i * 60000); timer.activity(); }
  timer.visibility(false);
  f.at(1000 + 5 * 60 * 60000); timer.visibility(true);
  for (let i = 1; i <= 15; i++) { f.at(1000 + 5 * 60 * 60000 + i * 60000); timer.activity(); }
  assert.equal(timer.snapshot(null), 25 * 60);
});
test('reload persists only saved intervals and never credits closed-page time', () => {
  const f = fixture(), first = f.timer(); start(first);
  f.at(31000); first.visibility(false);
  f.at(301000); const reloaded = f.timer(); start(reloaded);
  f.at(331000);
  assert.equal(reloaded.snapshot(null), 60);
});
test('a page opened hidden earns zero until it becomes visible', () => {
  const f = fixture(), timer = f.timer(); timer.visibility(false); start(timer);
  f.at(901000); timer.activity(); timer.tick();
  timer.visibility(true); f.at(916000);
  assert.equal(timer.snapshot(null), 15);
});
test('automatic sync and render do not renew the inactivity window', () => {
  const f = fixture(), timer = f.timer(); start(timer);
  for (let i = 1; i <= 20; i++) { f.at(1000 + i * 60000); start(timer); }
  assert.equal(timer.snapshot(null), 300);
});
test('network error, blocked, result and unavailable states do not accrue waiting time', () => {
  for (const state of ['save_failed', 'settle_failed', 'blocked', 'read_only', 'locked_future', 'result', 'settling']) {
    const f = fixture(), timer = f.timer(); start(timer);
    f.at(11000); timer.setState(state);
    f.at(101000); timer.activity();
    assert.equal(timer.snapshot(null), 10, state);
  }
  const f = fixture();
  for (const data of [{ stage: 'blocked' }, { stage: 'result', settlement: {} }, { stage: 'learning', access: { read_only: true } }, { stage: 'learning', access: { state: 'future' } }]) {
    f.timer().observe(data);
  }
  assert.equal(f.local.length, 0);
});
test('overlapping pages count the union once, including partially overlapping intervals', () => {
  const f = fixture(), first = f.timer(); start(first);
  f.at(21000); const second = f.timer(); start(second);
  f.at(61000); first.visibility(false);
  f.at(81000);
  assert.equal(second.snapshot(null), 80);
  assert.equal(first.snapshot(null), 80);
  assert.equal([...f.local.values.keys()].filter(k => k.includes(':page:')).length, 2);
});
test('task, student and review-session namespaces are isolated', () => {
  const f = fixture(), first = f.timer(); start(first, 7);
  f.at(21000); first.tick(true); const otherTask = f.timer(2); start(otherTask);
  f.at(41000); const otherStudent = f.timer(1, 'other'); start(otherStudent, 7);
  f.at(61000); first.tick(true);
  assert.equal(first.snapshot(7), 60);
  assert.equal(otherTask.snapshot(null), 40);
  assert.equal(otherStudent.snapshot(7), 20);
  start(first, 8); f.at(62000);
  assert.equal(first.snapshot(8), 1);
});
test('leaving a review session stops its timer while the task can continue', () => {
  const f = fixture(), timer = f.timer(); start(timer, 7);
  f.at(21000); start(timer);
  f.at(51000);
  assert.equal(timer.snapshot(7), 20);
  assert.equal(timer.snapshot(null), 50);
});
test('settlement snapshot survives delay and reload; completion cannot be overwritten', () => {
  const f = fixture(), timer = f.timer(); start(timer);
  f.at(21000); assert.equal(timer.snapshot(null), 20);
  f.at(181000); const reloaded = f.timer(); start(reloaded);
  assert.equal(reloaded.snapshot(null), 20);
  reloaded.finish(null, 20); timer.finish(null, 999);
  assert.equal(timer.snapshot(null), 20);
  timer.resume(null); f.at(240000); timer.activity();
  assert.equal(timer.snapshot(null), 20);
});
test('incomplete settlement resumes from response time, excluding frozen waiting', () => {
  const f = fixture(), timer = f.timer(); start(timer);
  f.at(11000); assert.equal(timer.snapshot(null), 10);
  f.at(101000); timer.resume(null);
  f.at(121000);
  assert.equal(timer.snapshot(null), 30);
});
test('a late tab sees resumed generation without adding another tab frozen interval', () => {
  for (const session of [null, 7]) {
    const f = fixture(), first = f.timer(), late = f.timer(); start(first, session); start(late, session);
    f.at(61000); first.tick(true); assert.equal(first.snapshot(session), 60);
    f.at(121000); first.resume(session);
    f.at(181000);
    assert.equal(late.snapshot(session), 120);
    assert.equal(first.snapshot(session), 120);
  }
});
test('storage restored after denied writes keeps memory intervals and filters freeze wait', () => {
  const shared = storage(); let denied = false;
  const unstable = {
    get length() { return shared.length; }, key: i => shared.key(i), getItem: k => shared.getItem(k),
    setItem(k, v) { if (denied) throw Error('quota'); shared.setItem(k, v); },
  };
  const a = fixture(shared), b = fixture(unstable), first = a.timer(), late = b.timer(); start(first); start(late);
  a.at(61000); b.at(61000); first.tick(true); assert.equal(first.snapshot(null), 60);
  denied = true;
  a.at(121000); first.resume(null);
  b.at(181000); late.tick(true); // Reads the newer epoch, but cannot persist its range.
  denied = false;
  assert.equal(late.snapshot(null), 120);
});
test('disabled or throwing storage enumeration falls back to this page only', () => {
  const broken = { getItem() { throw Error(); }, setItem() { throw Error(); }, get length() { throw Error(); } };
  const f = fixture(broken), timer = f.timer(); start(timer);
  f.at(61000); assert.equal(timer.snapshot(null), 60);
  const reloaded = f.timer(); start(reloaded); f.at(62000);
  assert.equal(reloaded.snapshot(null), 1);
});
test('unsettled v1 wall-clock records are not converted to active time', () => {
  const f = fixture();
  f.local.setItem('pv:1:student:timer:task', JSON.stringify({ version: 1, startedAt: 0, seconds: null, complete: false }));
  f.at(18001000); const timer = f.timer(); start(timer); f.at(18061000);
  assert.equal(timer.snapshot(null), 60);
  assert.equal(JSON.parse(f.local.getItem('pv:1:student:timer:task')).version, 1);
});
test('damaged metadata and future intervals cannot inflate elapsed time', () => {
  const f = fixture();
  f.local.setItem('pv:1:student:active:v2:task', '{');
  f.local.setItem('pv:1:student:active:v2:task:page:bad', JSON.stringify({ version: 2, ranges: [[0, 999999999]] }));
  const timer = f.timer(); start(timer); f.at(6000);
  assert.equal(timer.snapshot(null), 5);
});
test('oversized frozen values are rejected and legacy submitted seconds never replace active time', () => {
  const f = fixture();
  f.local.setItem('pv:1:student:active:v2:task', JSON.stringify({
    version: 2, generation: 0, windows: [[0, 1000]], seconds: Number.MAX_SAFE_INTEGER, complete: true,
  }));
  const timer = f.timer(); start(timer); f.at(6000);
  timer.finish(null, 5 * 60 * 60);
  assert.equal(timer.snapshot(null), 5);
});
test('clock rollback and large forward jump do not yield negative or hours of credit', () => {
  const f = fixture(), timer = f.timer(); start(timer);
  f.at(11000); timer.tick(true); f.at(5000); timer.tick(true);
  f.at(20 * 60 * 60000); assert.ok(timer.snapshot(null) <= 300);
  assert.ok(timer.snapshot(null) >= 0);
});
test('frequent input avoids per-keystroke writes and continuous samples compact to one span', () => {
  const f = fixture(), timer = f.timer(); start(timer);
  const initialWrites = f.local.writes;
  for (let i = 1; i <= 100; i++) { f.at(1000 + i * 10); timer.activity(); }
  assert.equal(f.local.writes, initialWrites);
  for (let i = 1; i <= 10; i++) { f.at(1000 + i * 5000); timer.tick(); }
  const own = [...f.local.values.entries()].filter(([k]) => k.includes(':page:'));
  assert.equal(own.length, 1);
  assert.equal(JSON.parse(own[0][1]).ranges.length, 1);
  assert.equal(timer.snapshot(null), 50);
});

test('real event wiring uses trusted input/IME/wheel, ignores script and key-repeat, and flushes lifecycle', () => {
  const listeners = {}, calls = [], intervals = [];
  const add = (target, type, fn) => { (listeners[target + type] ||= []).push(fn); };
  const dialog = { open: false, querySelector: () => ({ addEventListener() {} }) };
  const document = { visibilityState: 'visible', addEventListener: (type, fn) => add('doc:', type, fn),
    getElementById: id => id === 'pv-help-dialog' ? dialog : { addEventListener() {} } };
  const root = { PracticeVocabularyCore: { routeKey: () => null, choice: () => false },
    addEventListener: (type, fn) => add('win:', type, fn), setInterval: fn => intervals.push(fn) };
  vm.runInNewContext(fs.readFileSync(require.resolve('../static/js/practice_vocabulary_events.js'), 'utf8'),
    { window: root, document, Date, setTimeout() {} });
  const timing = { activity: () => calls.push('activity'), visibility: v => calls.push(['visible', v]), tick: () => calls.push('tick') };
  const app = { timing, boot: {}, model: {}, player: { stop() {} }, view: { status() {} }, saveDraft() {}, refresh() { calls.push('refresh'); } };
  root.PracticeVocabularyEvents.install(app);
  const target = { id: 'pv-answer', value: '中文', closest: () => null };
  const dispatch = (name, extra = {}) => (listeners[name] || []).forEach(fn => fn({ target, isTrusted: true, ...extra }));
  for (const type of ['keydown', 'input', 'compositionstart', 'compositionend', 'pointerdown', 'wheel']) dispatch('doc:' + type);
  assert.equal(calls.filter(x => x === 'activity').length, 6);
  dispatch('doc:keydown', { repeat: true }); dispatch('doc:pointermove', { isTrusted: false }); dispatch('doc:scroll');
  assert.equal(calls.filter(x => x === 'activity').length, 6);
  dispatch('win:focus'); assert.equal(calls.filter(x => x === 'activity').length, 6);
  document.visibilityState = 'hidden'; dispatch('doc:visibilitychange');
  dispatch('win:pagehide'); document.visibilityState = 'visible'; dispatch('win:pageshow'); intervals[0]();
  assert.deepEqual(calls.filter(Array.isArray), [['visible', true], ['visible', false], ['visible', false], ['visible', true]]);
  assert.equal(calls.at(-1), 'tick');
});
