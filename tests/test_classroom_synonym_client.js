const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const root = path.resolve(__dirname, '../miniprogram');

// Execute the existing pages and shared request wrapper. Only WeChat's native
// boundary is replaced: no source rewrites, real student accounts or network.
function mount(pageName) {
  const calls = [];
  const toasts = [];
  const responses = [];
  let definition;
  const app = { globalData: { baseUrl: 'https://synthetic.invalid/api', token: 'synthetic-token' } };
  const context = vm.createContext({
    getApp: () => app,
    Page: value => { definition = value; },
    wx: {
      request(options) {
        calls.push(options);
        const response = responses.shift();
        assert.ok(response, `Unexpected network request: ${options.url}`);
        if (response.fail) options.fail(response.fail);
        else options.success({ statusCode: response.statusCode || 200, data: response.data });
      },
      showToast: toast => toasts.push(toast),
      getStorageSync: () => null
    },
    console: { warn() {} },
    setTimeout,
    clearTimeout
  });
  const cache = new Map();
  function load(filename) {
    if (cache.has(filename)) return cache.get(filename).exports;
    assert.ok(filename.startsWith(root + path.sep), 'Only mini-program sources may load');
    const module = { exports: {} };
    cache.set(filename, module);
    const factory = vm.runInContext(
      `(function (require, module, exports) {\n${fs.readFileSync(filename, 'utf8')}\n})`,
      context,
      { filename }
    );
    factory(imported => load(path.resolve(path.dirname(filename), imported)), module, module.exports);
    return module.exports;
  }
  load(path.join(root, 'pages/student', pageName, 'index.js'));
  const page = Object.assign({}, definition, {
    data: JSON.parse(JSON.stringify(definition.data)),
    setData(patch, callback) {
      Object.assign(this.data, patch);
      if (callback) callback.call(this);
    }
  });
  return { page, calls, toasts, responses };
}

const flush = () => new Promise(resolve => setImmediate(resolve));

function synonym(overrides = {}) {
  return Object.assign({
    learning_question_id: 301,
    queue_item_id: 401,
    review_item_id: 501,
    question_id: 'synthetic-synonym-1',
    word_id: 11,
    sense_id: 21,
    dimension: 'meaning_recall',
    mode: 'context_fill',
    question: {
      kind: 'synonym_recall',
      dimension: 'meaning_recall',
      mode: 'context_fill',
      prompt: { instruction: '填写课堂词表中的同义词或词组', sentence: 'participate = ____' }
    }
  }, overrides);
}

function loadQuestion(fixture, pageName, item = synonym()) {
  const page = fixture.page;
  if (pageName === 'vocabulary-learning') {
    page.setData({ taskId: '7', selectedOption: 'old-option', isMeaningChoice: true });
    page.applyQueue({
      ok: true,
      queue_token: 'synthetic-queue',
      group_number: 1,
      group_count: 1,
      group_size: 1,
      total_word_count: 1,
      phase: 'active_recall',
      familiarity: [{ word_id: 11, word: 'participate', meaning: '同义替换：take part in', viewed: true }],
      current_question: item
    });
  } else {
    page.setData({
      sessionId: 17,
      sessionToken: 'synthetic-session',
      items: [item],
      selectedOption: 'old-option',
      isMeaningChoice: true
    });
    page.showItem(0);
  }
}

for (const pageName of ['vocabulary-learning', 'vocabulary-review']) {
  test(`${pageName} keeps synonym recall in the meaning dimension with free-text input`, () => {
    const f = mount(pageName);
    loadQuestion(f, pageName);
    const current = f.page.data.currentQuestion || f.page.data.currentItem;
    assert.equal(current.mode, 'context_fill');
    assert.equal(current.dimension, 'meaning_recall');
    assert.equal(current.question.kind, 'synonym_recall');
    assert.equal(current.question.prompt.instruction, '填写课堂词表中的同义词或词组');
    assert.equal(current.question.prompt.sentence, 'participate = ____');
    assert.equal(current.question.prompt.translation, undefined, 'no invented Chinese hint');
    assert.equal(f.page.data.isMeaningChoice, false);
    assert.equal(f.page.data.meaningOptions.length, 0);
    assert.equal(f.page.data.selectedOption, '');
    if (pageName === 'vocabulary-learning') assert.equal(f.page.data.phase, 'active_recall');
    else assert.equal(f.page.data.currentDimensionLabel, '词义提取');
    assert.equal(f.calls.length, 0);
    assert.equal(f.toasts.length, 0, 'a visual synonym prompt must not try to play audio');
  });

  test(`${pageName} sends the whole phrase through the real authenticated request wrapper`, async () => {
    const f = mount(pageName);
    loadQuestion(f, pageName);
    f.responses.push({ data: {
      ok: true, is_correct: true, attempt_id: 'synthetic-stored-attempt',
      student_answer: 'take   part in', revealed_answer: 'take part in'
    } });
    f.page.onInput({ detail: { value: '  take   part in  ' } });
    assert.equal(f.page.data.inputValue, '  take   part in  ');
    f.page.submitAnswer();
    await flush();
    assert.equal(f.calls.length, 1);
    const request = f.calls[0];
    assert.equal(request.header.Authorization, 'Bearer synthetic-token');
    assert.equal(request.method, 'POST');
    assert.equal(request.data.answer, 'take   part in');
    assert.equal(request.data.dimension, 'meaning_recall');
    assert.equal(request.data.input_mode, 'native');
    assert.equal(request.data.word_id, 11);
    assert.equal(request.data.sense_id, 21);
    if (pageName === 'vocabulary-learning') {
      assert.equal(request.url, 'https://synthetic.invalid/api/dictation/submit');
      assert.equal(request.data.attempt_id, 'vocabulary-group:7:first:301');
      assert.equal(request.data.queue_token, 'synthetic-queue');
    } else {
      assert.equal(request.url, 'https://synthetic.invalid/api/miniprogram/student/vocabulary-review/sessions/17/answers');
      assert.equal(request.data.attempt_id, 'wx-vocabulary-review:17:501');
      assert.equal(request.data.session_token, 'synthetic-session');
    }
    assert.equal(f.page.data.submitting, false);
    assert.equal(f.page.data.showResult, true);
    assert.equal(f.page.data.isCorrect, true);
    assert.equal(f.page.data.submittedAnswer, 'take   part in');
    assert.equal(f.page.data.correctAnswer, 'take part in');
    assert.equal(f.toasts.length, 0);
  });

  test(`${pageName} rejects an empty answer and preserves a failed phrase submission for retry`, async () => {
    const f = mount(pageName);
    loadQuestion(f, pageName);
    f.page.onInput({ detail: { value: '   ' } });
    f.page.submitAnswer();
    assert.equal(f.calls.length, 0);
    assert.equal(f.toasts.at(-1).title, '请输入答案');
    f.responses.push({ fail: { errMsg: 'synthetic network failure' } });
    f.page.onInput({ detail: { value: "one's own" } });
    f.page.submitAnswer();
    await flush();
    assert.equal(f.page.data.showResult, false);
    assert.equal(f.page.data.submitting, false);
    assert.equal(f.page.data.inputValue, "one's own");
    f.responses.push({ data: { ok: true, is_correct: false, revealed_answer: 'take part in' } });
    f.page.submitAnswer();
    await flush();
    assert.equal(f.calls.length, 2);
    assert.equal(f.calls[1].data.attempt_id, f.calls[0].data.attempt_id);
    assert.equal(f.calls[1].data.answer, "one's own");
    assert.equal(f.page.data.showResult, true);
    assert.equal(f.page.data.isCorrect, false);
  });
}

test('existing WXML has the server synonym prompt and a native text input for complete phrases', () => {
  for (const pageName of ['vocabulary-learning', 'vocabulary-review']) {
    const markup = fs.readFileSync(path.join(root, 'pages/student', pageName, 'index.wxml'), 'utf8');
    const branch = markup.match(/<block wx:elif="{{(?:currentQuestion|currentItem)\.mode === 'context_fill'}}">([\s\S]*?)<\/block>/);
    assert.ok(branch, `${pageName}: context_fill display branch`);
    assert.match(branch[1], /question\.prompt\.instruction/);
    assert.match(branch[1], /question\.prompt\.sentence/);
    const input = markup.match(/<input\s[\s\S]*?\/>/)[0];
    assert.match(input, /bindinput="onInput"/);
    assert.match(input, /bindconfirm="submitAnswer"/);
    assert.doesNotMatch(input, /type="(?:number|digit|idcard)"|maxlength="(?:[1-9]|[1-9][0-9])"/);
    assert.match(input, /!isMeaningChoice/);
    assert.doesNotMatch(input, /(?:context_fill|meaning_recall)\s*===|!==\s*'(?:context_fill|meaning_recall)'/);
  }
});
