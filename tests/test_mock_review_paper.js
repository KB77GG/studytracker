const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');
const ROOT = path.resolve(__dirname, '..');
const source = fs.readFileSync(path.join(ROOT, 'static/js/mock_review_paper.js'), 'utf8');

function element(cards = []) {
  const attrs = new Map();
  return {
    hidden: false, querySelectorAll: () => cards,
    setAttribute: (key, value) => attrs.set(key, value),
    getAttribute: key => attrs.get(key),
    hasAttribute: key => attrs.has(key), removeAttribute: key => attrs.delete(key)
  };
}
function card(status, active = true) {
  return { ...element(), querySelector: () => ({ dataset: { status } }),
    closest: () => ({ classList: { contains: () => active } }) };
}
function fixture() {
  const listeners = {}, frames = [], messages = [], observers = [];
  const correct = card('correct'), wrong = card('incorrect'), partial = card('partial'), unanswered = card('unanswered');
  const correctRow = element([correct]), mixedRow = element([correct, wrong]);
  const sourceOnlyRow = element([]), group = element([correct, wrong, partial, unanswered]);
  const state = { height: 1500, cards: [correct, wrong, partial, unanswered], rows: [correctRow, mixedRow, sourceOnlyRow, group] };
  const empty = element();
  const parent = { postMessage: (message, origin) => messages.push({ ...message, origin }) };
  const window = { parent, location: { origin: 'https://study.example' },
    requestAnimationFrame: callback => frames.push(callback), addEventListener: (type, callback) => { listeners[type] = callback; } };
  const document = {
    body: { dataset: { reviewPaperEmbed: 'true' }, getBoundingClientRect: () => ({ height: state.height }) },
    querySelector: () => null, getElementById: () => null, createElement: () => empty,
    querySelectorAll: selector => selector.startsWith('.review-card') ? state.cards : state.rows,
    addEventListener() {}
  };
  vm.runInNewContext(source, { window, document, Number,
    MutationObserver: function (callback) { observers.push(callback); this.observe = () => {}; } });
  const flush = () => { while (frames.length) frames.shift()(); };
  const send = (data, origin = window.location.origin, sender = parent) => listeners.message({ data, origin, source: sender });
  flush();
  return { state, correct, wrong, partial, unanswered, correctRow, mixedRow, sourceOnlyRow, group, empty, messages, observers, flush, send, parent };
}

test('embedded review filters correctly and restores all rows without dropping shared wrong context', () => {
  const f = fixture();
  f.send({ type: 'mock-review-filter', wrongOnly: true }); f.flush();
  assert.equal(f.correct.getAttribute('data-review-hidden'), 'true');
  assert.equal(f.correctRow.getAttribute('data-review-hidden'), 'true');
  for (const node of [f.wrong, f.partial, f.unanswered, f.mixedRow, f.sourceOnlyRow, f.group]) assert.equal(node.hasAttribute('data-review-hidden'), false);
  f.send({ type: 'mock-review-filter', wrongOnly: false }); f.flush();
  for (const node of [...f.state.cards, ...f.state.rows]) assert.equal(node.hasAttribute('data-review-hidden'), false);
});

test('embedded review ignores messages from another origin/window and malformed filters', () => {
  const f = fixture(); const before = f.messages.length;
  f.send({ type: 'mock-review-filter', wrongOnly: true }, 'https://other.example');
  f.send({ type: 'mock-review-filter', wrongOnly: true }, 'https://study.example', {});
  f.send({ type: 'mock-review-filter', wrongOnly: 'true' });
  f.send({ type: 'unrelated', wrongOnly: true }); f.flush();
  assert.equal(f.messages.length, before);
  assert.equal(f.correct.hasAttribute('data-review-hidden'), false);
});

test('filter survives passage redraw and empty notice only considers the active Section', () => {
  const f = fixture();
  f.send({ type: 'mock-review-filter', wrongOnly: true }); f.flush();
  const replacement = card('correct');
  f.state.cards = [replacement, card('incorrect', false)];
  f.state.rows = [element([replacement])];
  f.observers[0](); f.flush();
  assert.equal(replacement.getAttribute('data-review-hidden'), 'true');
  assert.equal(f.empty.hidden, false);
  f.state.cards = [card('incorrect')]; f.state.rows = [element(f.state.cards)];
  f.observers[0](); f.flush();
  assert.equal(f.empty.hidden, true);
});

test('content height shrinks, rejects invalid measurements and replies to a late parent handshake', () => {
  const f = fixture();
  assert.equal(f.messages[0].type, 'mock-review-ready');
  assert.equal(f.messages.at(-1).height, 1500);
  const before = f.messages.length;
  f.send({ type: 'mock-review-filter', wrongOnly: false }); f.flush();
  assert.equal(f.messages.length, before + 1);
  assert.equal(f.messages.at(-1).height, 1500);
  f.state.height = 325.2; f.observers[0](); f.flush();
  assert.equal(f.messages.at(-1).height, 326);
  for (const height of [NaN, Infinity, 0, -10]) { f.state.height = height; f.observers[0](); f.flush(); }
  assert.equal(f.messages.at(-1).height, 326);
});

function highlighter(readOnly) {
  const events = [], callbacks = [], observers = [], reads = [];
  let refreshes = 0;
  const root = { querySelectorAll: () => [], normalize: () => { refreshes += 1; }, getAttribute: () => 'reading-passage' };
  const document = { getElementById: () => null, createElement: () => ({}), head: { appendChild() {} },
    querySelectorAll: () => [root], createTreeWalker: () => ({ nextNode: () => null }),
    addEventListener: name => events.push(name) };
  const window = { __SELECTION_HIGHLIGHT_READ_ONLY__: readOnly, location: { pathname: '/mock' },
    localStorage: { length: 0, getItem: key => { reads.push(key); return null; } },
    clearTimeout() {}, setTimeout: callback => callbacks.push(callback) };
  vm.runInNewContext(fs.readFileSync(path.join(ROOT, 'static/js/selection-highlight.js'), 'utf8'), {
    window, document, NodeFilter: { SHOW_TEXT: 4 },
    MutationObserver: function (callback) { observers.push(callback); this.observe = () => {}; this.takeRecords = () => {}; }
  });
  return { events, observers, reads, get refreshes() { return refreshes; }, redraw() { observers[0](); callbacks.shift()(); } };
}

test('read-only highlighter still restores and observes redraws without editing handlers', () => {
  const f = highlighter(true);
  assert.deepEqual(f.events, []);
  assert.equal(f.observers.length, 1);
  assert.equal(f.refreshes, 1);
  assert.ok(f.reads.includes('exhl:v1:/mock'));
  f.redraw(); assert.equal(f.refreshes, 2);
});

test('ordinary highlighter retains desktop, touch and keyboard-selection handlers', () => {
  const f = highlighter(false);
  for (const name of ['mouseup', 'touchend', 'selectionchange', 'contextmenu', 'click', 'keyup']) assert.ok(f.events.includes(name), name);
  assert.equal(f.refreshes, 1);
});

for (const subject of ['listening', 'reading']) {
  test(`${subject} embedded review skips the history-owning shell while standalone review keeps it`, () => {
    const template = fs.readFileSync(path.join(ROOT, `templates/${subject}/test_practice.html`), 'utf8');
    const start = template.lastIndexOf('practiceShellController = ');
    const end = template.indexOf('\n});', start) + '\n});'.length;
    assert.ok(start >= 0 && end > start);
    assert.doesNotMatch(template, /PracticeShell\.installListContext\(/);
    for (const embedded of [true, false]) {
      const historyCalls = [];
      const controller = {};
      const context = {
        practiceContext: { embed_review: embedded, read_only: true },
        persistenceContext: { exit_url: '/exam/1/session/test/review' },
        isMockExamReview: true, practiceShellController: null,
        persistAnswers() {}, persistExamDraft() {},
        PracticeShell: { init() { historyCalls.push('replaceState', 'pushState', 'popstate'); return controller; } }
      };
      vm.runInNewContext(template.slice(start, end), context);
      assert.deepEqual(historyCalls, embedded ? [] : ['replaceState', 'pushState', 'popstate']);
      assert.equal(context.practiceShellController, embedded ? null : controller);
    }
  });
}
