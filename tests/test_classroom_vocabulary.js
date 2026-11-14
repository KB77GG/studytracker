const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const mount = require('../static/js/classroom_vocabulary');

// Small DOM port, without an extra runtime dependency. Setting innerHTML is
// deliberately forbidden: imported teacher content must remain literal text.
function node(tag = 'div') {
  const listeners = new Map();
  const classes = new Set();
  const item = {
    tagName: tag.toUpperCase(), children: [], dataset: {}, value: '', files: [],
    checked: false, hidden: false, disabled: false, href: '', focused: false,
    classList: {
      toggle(name, enabled) { enabled ? classes.add(name) : classes.delete(name); },
      contains(name) { return classes.has(name); }
    },
    addEventListener(event, callback) {
      if (!listeners.has(event)) listeners.set(event, []);
      listeners.get(event).push(callback);
    },
    async fire(event) { await Promise.all((listeners.get(event) || []).map(callback => callback())); },
    appendChild(child) { item.children.push(child); return child; },
    replaceChildren(...children) { item.children = children; item._text = ''; },
    focus() { item.focused = true; }
  };
  Object.defineProperties(item, {
    textContent: {
      get() { return (item._text || '') + item.children.map(child => child.textContent).join(''); },
      set(value) { item._text = String(value); item.children = []; }
    },
    innerHTML: { set() { assert.fail('Imported vocabulary must not be rendered as HTML'); } }
  });
  return item;
}

const template = fs.readFileSync(path.join(__dirname, '../templates/classroom_vocabulary.html'), 'utf8');
function fixture(responses = []) {
  const elements = new Map(Array.from(template.matchAll(/id="([^"]+)"/g), match => [match[1], node()]));
  elements.get('classroomVocabulary').dataset.csrfToken = 'synthetic-csrf';
  const radios = [node('input'), node('input')];
  radios[0].value = 'text'; radios[0].checked = true;
  radios[1].value = 'file';
  class FormData {
    constructor() { this.entries = new Map(); }
    append(key, value) { this.entries.set(key, value); }
    get(key) { return this.entries.get(key); }
  }
  const document = {
    getElementById(id) { return elements.get(id) || null; },
    querySelectorAll(selector) { return selector === 'input[name="cvSource"]' ? radios : []; },
    createElement: node
  };
  const calls = [];
  const fetcher = async (url, options) => {
    calls.push({ url, options });
    assert.ok(responses.length, `Unexpected request: ${url}`);
    const result = responses.shift();
    if (result instanceof Error) throw result;
    return typeof result === 'function' ? result(url, options) : result;
  };
  const controller = mount(document, fetcher, FormData);
  const el = id => elements.get(id);
  el('cvTitle').value = '阅读课堂 · 环境';
  el('cvText').value = 'habitat\tn.\t栖息地';
  return { controller, el, radios, calls, responses, elements };
}

function response(data, ok = true) { return { ok, json: async () => data }; }
function preview(overrides = {}) {
  return response(Object.assign({
    ok: true, valid: true, word_count: 1, errors: [], warnings: [],
    rows: [{ line: 2, word: 'habitat', part_of_speech: 'n.', meaning: '栖息地' }]
  }, overrides));
}
function saved(overrides = {}) {
  return response(Object.assign({
    ok: true, reused: false,
    book: { id: 211, title: '阅读课堂 · 环境', word_count: 1 },
    assignment_url: '/tasks?preset_dictation_book=211'
  }, overrides));
}
function deferred() {
  let resolve;
  const promise = new Promise(done => { resolve = done; });
  return { promise, resolve };
}

test('previews three literal columns with the session CSRF token', async () => {
  const f = fixture([preview()]);
  await f.controller.preview();
  const request = f.calls[0];
  assert.equal(request.url, '/api/classroom-vocabulary/preview');
  assert.equal(request.options.credentials, 'same-origin');
  assert.equal(request.options.headers['X-CSRF-Token'], 'synthetic-csrf');
  assert.equal(request.options.body.get('text'), 'habitat\tn.\t栖息地');
  assert.equal(request.options.body.get('file'), undefined);
  assert.deepEqual(f.el('cvRows').children[0].children.map(cell => cell.textContent), ['2', 'habitat', 'n.', '栖息地']);
  assert.equal(f.el('cvWordCount').textContent, '1 条');
  assert.equal(f.el('cvPreviewPanel').hidden, false);
  assert.equal(f.el('cvSave').disabled, false);
  assert.equal(f.calls.length, 1, 'preview itself must not create books or assignments');
});

test('mixed vocabulary and synonym rows preserve complete phrases through preview and save', async () => {
  const rows = [
    { line: 1, word: 'habitat', part_of_speech: 'n.', meaning: '栖息地' },
    { line: 2, word: 'participate', part_of_speech: '=', meaning: 'take part in' },
    { line: 3, word: 'because of', part_of_speech: '=', meaning: 'due to' }
  ];
  const f = fixture([
    preview({ rows, word_count: 3 }),
    saved({ book: { id: 211, title: '课堂生词与同义替换', word_count: 3 } })
  ]);
  const input = 'habitat\tn.\t栖息地\nparticipate\t=\ttake part in\nbecause of\t＝\tdue to';
  f.el('cvText').value = input;
  f.el('cvTitle').value = '课堂生词与同义替换';
  await f.controller.preview();
  assert.equal(f.calls[0].options.body.get('text'), input, 'only the server normalizes the equals sign');
  assert.deepEqual(f.el('cvRows').children.map(row => row.children.map(cell => cell.textContent)), [
    ['1', 'habitat', 'n.', '栖息地'],
    ['2', 'participate', '=', 'take part in'],
    ['3', 'because of', '=', 'due to']
  ]);
  assert.equal(f.el('cvWordCount').textContent, '3 条');
  assert.match(f.el('cvStatus').textContent, /同义替换/);
  assert.equal(f.el('cvSave').disabled, false);
  await f.controller.save();
  assert.deepEqual(JSON.parse(f.calls[1].options.body), { title: '课堂生词与同义替换', rows });
  assert.equal(f.el('cvSavedSummary').textContent, '课堂生词与同义替换 · 3 条');
  assert.equal(f.el('cvAssign').href, '/tasks?preset_dictation_book=211');
  assert.equal(f.calls.length, 2, 'saving a mixed list must not publish a task');
});

test('an invalid synonym row remains visible and blocks saving the whole mixed list', async () => {
  const f = fixture([preview({
    valid: false,
    word_count: 2,
    rows: [
      { line: 1, word: 'habitat', part_of_speech: 'n.', meaning: '栖息地' },
      { line: 2, word: 'participate', part_of_speech: '=', meaning: '' }
    ],
    errors: [{ line: 2, message: '同义替换不能为空' }]
  })]);
  await f.controller.preview();
  assert.equal(f.el('cvRows').children.length, 2);
  assert.deepEqual(f.el('cvRows').children[1].children.map(cell => cell.textContent), ['2', 'participate', '=', '']);
  assert.match(f.el('cvIssues').textContent, /第 2 行：同义替换不能为空/);
  assert.equal(f.el('cvSave').disabled, true);
  await f.controller.save();
  assert.equal(f.calls.length, 1);
});

test('invalid rows show their source line and cannot be saved', async () => {
  const f = fixture([preview({ valid: false, errors: [{ line: 2, message: '中文释义不能为空' }] })]);
  await f.controller.preview();
  assert.match(f.el('cvIssues').textContent, /第 2 行：中文释义不能为空/);
  assert.equal(f.el('cvIssues').hidden, false);
  assert.equal(f.el('cvSave').disabled, true);
  await f.controller.save();
  assert.equal(f.calls.length, 1);
});

test('normalization and workbook warnings are visible but do not prevent a valid save', async () => {
  const f = fixture([
    preview({ warnings: [
      { line: 0, message: '仅导入第一个工作表，其他工作表未导入' },
      { line: 2, message: '词性已统一为 n.' }
    ] }),
    saved()
  ]);
  await f.controller.preview();
  assert.equal(f.el('cvWarnings').hidden, false);
  assert.match(f.el('cvWarnings').textContent, /其他工作表未导入/);
  assert.match(f.el('cvWarnings').textContent, /第 2 行：词性已统一为 n\./);
  assert.equal(f.el('cvSave').disabled, false);
  await f.controller.save();
  assert.equal(f.controller.state.saved, true);
});

test('fresh preview clears warnings from a previous input', async () => {
  const f = fixture([
    preview({ warnings: [{ line: 2, message: '词性已统一为 n.' }] }),
    preview()
  ]);
  await f.controller.preview();
  await f.el('cvText').fire('input');
  await f.controller.preview();
  assert.equal(f.el('cvWarnings').hidden, true);
  assert.equal(f.el('cvWarnings').textContent, '');
  assert.equal(f.el('cvSave').disabled, false);
});

test('editing the pasted source discards the preview and requires a fresh check', async () => {
  const f = fixture([preview()]);
  await f.controller.preview();
  f.el('cvText').value = 'conserve\tv.\t保护';
  await f.el('cvText').fire('input');
  assert.equal(f.controller.state.valid, false);
  assert.equal(f.el('cvPreviewPanel').hidden, true);
  assert.equal(f.el('cvSave').disabled, true);
  await f.controller.save();
  assert.equal(f.calls.length, 1);
  assert.equal(f.el('cvText').value, 'conserve\tv.\t保护');
});

test('changing the title keeps the checked rows but an empty title blocks saving', async () => {
  const f = fixture([preview()]);
  await f.controller.preview();
  f.el('cvTitle').value = '  ';
  await f.el('cvTitle').fire('input');
  assert.equal(f.controller.state.valid, true);
  assert.equal(f.el('cvSave').disabled, true);
  await f.controller.save();
  assert.equal(f.calls.length, 1);
  assert.match(f.el('cvStatus').textContent, /填写词表名称/);
});

test('rapid preview and save clicks each send only one request', async () => {
  const previewGate = deferred();
  const saveGate = deferred();
  const f = fixture([() => previewGate.promise, () => saveGate.promise]);
  const firstPreview = f.controller.preview();
  await f.controller.preview();
  assert.equal(f.calls.length, 1);
  assert.equal(f.el('cvText').disabled, true);
  previewGate.resolve(preview());
  await firstPreview;
  const firstSave = f.controller.save();
  await f.controller.save();
  assert.equal(f.calls.length, 2);
  assert.equal(f.el('cvSave').disabled, true);
  saveGate.resolve(saved());
  await firstSave;
  await f.controller.save();
  assert.equal(f.calls.length, 2);
  assert.equal(f.controller.state.saved, true);
});

test('failed saving preserves the list and retry can reuse a book without publishing tasks', async () => {
  const f = fixture([preview(), new Error('Network disconnected'), saved({ reused: true })]);
  await f.controller.preview();
  await f.controller.save();
  assert.equal(f.el('cvText').value, 'habitat\tn.\t栖息地');
  assert.equal(f.el('cvTitle').value, '阅读课堂 · 环境');
  assert.equal(f.el('cvSave').disabled, false);
  assert.equal(f.controller.state.valid, true);
  await f.controller.save();
  assert.equal(f.el('cvSuccess').hidden, false);
  assert.match(f.el('cvSavedSummary').textContent, /已保存过/);
  assert.equal(f.el('cvAssign').href, '/tasks?preset_dictation_book=211');
  assert.match(f.el('cvStatus').textContent, /尚未布置给学生/);
  assert.ok(f.calls.every(call => call.url.startsWith('/api/classroom-vocabulary/')));
  assert.deepEqual(JSON.parse(f.calls[1].options.body), JSON.parse(f.calls[2].options.body));
  assert.equal(f.calls[2].options.headers['Content-Type'], 'application/json');
});

test('imports and saved titles render as text, and supplied redirect URLs are not used', async () => {
  const malicious = '<img src=x onerror=alert(1)>';
  const f = fixture([
    preview({ rows: [{ line: 2, word: 'example', part_of_speech: 'n.', meaning: malicious }] }),
    saved({ book: { id: 211, title: malicious, word_count: 1 }, assignment_url: 'javascript:alert(1)' })
  ]);
  await f.controller.preview();
  assert.equal(f.el('cvRows').children[0].children[3].textContent, malicious);
  assert.equal(f.el('cvRows').children[0].children[3].children.length, 0);
  await f.controller.save();
  assert.match(f.el('cvSavedSummary').textContent, /<img src=x onerror=alert\(1\)>/);
  assert.equal(f.el('cvSavedSummary').children.length, 0);
  assert.equal(f.el('cvAssign').href, '/tasks?preset_dictation_book=211');
});

test('source switching invalidates a pasted preview and uploads only the selected file', async () => {
  const f = fixture([preview(), preview()]);
  await f.controller.preview();
  f.radios[0].checked = false;
  f.radios[1].checked = true;
  await f.radios[1].fire('change');
  assert.equal(f.el('cvTextArea').hidden, true);
  assert.equal(f.el('cvFileArea').hidden, false);
  assert.equal(f.el('cvSave').disabled, true);
  await f.controller.preview();
  assert.equal(f.calls.length, 1, 'missing file cannot trigger a request');
  const file = { name: '课堂生词.xlsx' };
  f.el('cvFile').files = [file];
  await f.controller.preview();
  assert.equal(f.calls[1].options.body.get('file'), file);
  assert.equal(f.calls[1].options.body.get('text'), undefined);
});

test('login expiry or rejected CSRF keeps teacher input recoverable', async () => {
  for (const failure of [
    { ok: false, json: async () => { throw new Error('HTML login page'); } },
    response({ ok: false, message: '页面已过期，请刷新后重试' }, false)
  ]) {
    const f = fixture([failure]);
    await f.controller.preview();
    assert.equal(f.el('cvText').value, 'habitat\tn.\t栖息地');
    assert.equal(f.el('cvPreview').disabled, false);
    assert.equal(f.el('cvSave').disabled, true);
    assert.equal(f.el('cvStatus').classList.contains('is-error'), true);
    assert.match(f.el('cvStatus').textContent, /过期/);
  }
});

test('continuing to another list clears the saved state without new network actions', async () => {
  const f = fixture([preview(), saved()]);
  await f.controller.preview();
  await f.controller.save();
  await f.el('cvNew').fire('click');
  assert.equal(f.controller.state.saved, false);
  assert.equal(f.el('cvTitle').value, '');
  assert.equal(f.el('cvText').value, '');
  assert.equal(f.el('cvSuccess').hidden, true);
  assert.equal(f.el('cvPreview').disabled, false);
  assert.equal(f.el('cvSave').disabled, true);
  assert.equal(f.calls.length, 2);
});

test('a stale preview cannot re-enable save after its source has been invalidated', async () => {
  const gate = deferred();
  const f = fixture([() => gate.promise]);
  const request = f.controller.preview();
  f.controller.invalidate();
  gate.resolve(preview());
  await request;
  assert.equal(f.controller.state.valid, false);
  assert.equal(f.el('cvSave').disabled, true);
  assert.equal(f.el('cvPreviewPanel').hidden, true);
});
