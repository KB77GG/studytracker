const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const SOURCE = fs.readFileSync(path.join(__dirname, '../static/js/mock_exam_review.js'), 'utf8');
const ORIGIN = 'https://practice.example';

function setup({ checked = false, complete = false, checkbox = true } = {}) {
  const listeners = {};
  const control = { checked, addEventListener(type, callback) { this[type] = callback; } };
  const frames = ['listening', 'reading'].map((subject) => {
    const status = { hidden: false, textContent: 'Loading' };
    const sent = [];
    const frame = {
      subject, sent, status, style: { height: '360px' }, listeners: {},
      contentWindow: { postMessage(data, origin) { sent.push({ data, origin }); } },
      contentDocument: {
        readyState: complete ? 'complete' : 'loading',
        querySelector(selector) {
          assert.equal(selector, '[data-review-paper-embed="true"]');
          return this.embedded === false ? null : {};
        },
      },
      parentElement: { querySelector() { return status; } },
      addEventListener(type, callback) { this.listeners[type] = callback; },
    };
    return frame;
  });
  vm.runInNewContext(SOURCE, {
    document: {
      querySelectorAll(selector) {
        assert.equal(selector, 'iframe[data-review-paper]');
        return frames;
      },
      getElementById(id) { assert.equal(id, 'wrongOnly'); return checkbox ? control : null; },
    },
    window: {
      location: { origin: ORIGIN },
      addEventListener(type, callback) { listeners[type] = callback; },
    },
  });
  const message = (frame, data, extra = {}) => listeners.message({
    origin: ORIGIN, source: frame.contentWindow, data, ...extra,
  });
  return { frames, control, message };
}

function assertFilter(frame, wrongOnly) {
  assert.equal(frame.sent.at(-1).origin, ORIGIN);
  assert.equal(frame.sent.at(-1).data.type, 'mock-review-filter');
  assert.equal(frame.sent.at(-1).data.wrongOnly, wrongOnly);
}

test('only the exact same-origin child may mark ready or resize its own frame', () => {
  const { frames, message } = setup();
  const [listening, reading] = frames;
  message(listening, { type: 'mock-review-ready' }, { origin: 'https://unrelated.example' });
  message(listening, { type: 'mock-review-ready' }, { source: {} });
  message(listening, { type: 'mock-review-height', height: 900 }, { source: {} });
  message(listening, null);
  assert.equal(listening.status.hidden, false);
  assert.equal(listening.sent.length, 0);
  assert.equal(listening.style.height, '360px');
  message(listening, { type: 'mock-review-ready' });
  message(listening, { type: 'mock-review-height', height: 901.1 });
  assert.equal(listening.status.hidden, true);
  assert.equal(listening.style.height, '902px');
  assert.equal(reading.style.height, '360px');
  assert.equal(reading.status.hidden, false);
  assertFilter(listening, false);
});

test('invalid heights cannot collapse or expand the review page without bounds', () => {
  const { frames: [frame], message } = setup();
  for (const height of ['700', NaN, Infinity, -Infinity, 0, -1, 100001, null, {}]) {
    message(frame, { type: 'mock-review-height', height });
    assert.equal(frame.style.height, '360px');
  }
  message(frame, { type: 'mock-review-height', height: 30 });
  assert.equal(frame.style.height, '200px');
  message(frame, { type: 'mock-review-height', height: 100000 });
  assert.equal(frame.style.height, '100000px');
});

test('current wrong-only state reaches both children on ready, load and later toggles', () => {
  const { frames, control, message } = setup({ checked: true });
  frames.forEach((frame) => {
    message(frame, { type: 'mock-review-ready' });
    assertFilter(frame, true);
    frame.listeners.load();
    assertFilter(frame, true);
  });
  control.checked = false;
  control.change();
  frames.forEach((frame) => assertFilter(frame, false));
  control.checked = true;
  control.change();
  frames.forEach((frame) => assertFilter(frame, true));
});

test('already loaded child frames recover when their ready event preceded the parent script', () => {
  const { frames } = setup({ checked: true, complete: true });
  frames.forEach((frame) => {
    assertFilter(frame, true);
    assert.equal(frame.status.hidden, true);
  });
});

test('a redirected or failed child shows a retry message and receives no filter', () => {
  const { frames: [frame], message } = setup();
  frame.contentDocument.embedded = false;
  frame.listeners.load();
  assert.equal(frame.status.hidden, false);
  assert.match(frame.status.textContent, /加载失败/);
  assert.equal(frame.sent.length, 0);
  frame.listeners.error();
  assert.match(frame.status.textContent, /刷新/);
  frame.contentDocument.embedded = true;
  message(frame, { type: 'mock-review-ready' });
  assert.equal(frame.status.hidden, true);
  assertFilter(frame, false);
});

test('pages with no wrong-only control default to the complete review', () => {
  const { frames: [frame], message } = setup({ checkbox: false });
  message(frame, { type: 'mock-review-ready' });
  assertFilter(frame, false);
});
