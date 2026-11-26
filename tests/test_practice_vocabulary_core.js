const assert = require('node:assert/strict');
const test = require('node:test');
const fs = require('node:fs');
const vm = require('node:vm');
const C = require('../static/js/practice_vocabulary_core.js');

function key(key, extra = {}) {
  return { key, ...extra };
}
function ctx(extra = {}) {
  return { enterArmed: true, canAudio: true, ...extra };
}
function question(mode = 'zh_to_en', extra = {}) {
  return {
    mode,
    learning_question_id: 17,
    queue_item_id: 17,
    question_id: 'q17',
    word_id: 3,
    sense_id: 8,
    dimension: 'form_recall',
    answer_length: 100,
    question: {
      mode,
      prompt: {},
      options: [
        { id: 'a', label: '含义甲' },
        { id: 'b', label: '含义乙' },
      ],
    },
    ...extra,
  };
}
test('IME, composition-end guard, held Enter and in-flight writes cannot submit', () => {
  for (const event of [
    key('Enter', { isComposing: true }),
    key('Enter', { keyCode: 229 }),
    key('Enter', { repeat: true }),
  ])
    assert.equal(C.routeKey('question', event, ctx()), null);
  for (const extra of [
    { composing: true },
    { compositionGuard: true },
    { enterArmed: false },
    { inFlight: true },
    { dialogOpen: true },
  ])
    assert.equal(C.routeKey('question', key('Enter'), ctx(extra)), null);
  assert.equal(C.routeKey('question', key('Escape'), ctx({ inFlight: true })), 'escape');
  assert.equal(C.routeKey('feedback', key('Enter'), ctx({ feedbackWait: true })), 'wait');
  assert.equal(C.routeKey('feedback', key('Enter'), ctx()), 'primary');
});
test('text input keeps digits, arrow keys and R; option selection uses 1–4 and arrows', () => {
  for (const value of ['1', '2', '3', '4', 'ArrowLeft', 'ArrowRight', 'ArrowUp', 'r'])
    assert.equal(C.routeKey('question', key(value), ctx({ inInput: true })), null);
  assert.equal(C.routeKey('question', key('3'), ctx({ isChoice: true })), 'select:2');
  assert.equal(
    C.routeKey('review_question', key('ArrowDown'), ctx({ isChoice: true })),
    'option:next',
  );
  assert.equal(C.routeKey('question', key('ArrowUp'), ctx({ isChoice: true })), 'option:previous');
  assert.equal(C.routeKey('familiarity', key('ArrowLeft'), ctx()), 'previous');
});
test('audio shortcuts respect disclosure rules and native controls keep native Enter', () => {
  assert.equal(C.routeKey('question', key('r', { altKey: true }), ctx({ inInput: true })), 'audio');
  assert.equal(C.routeKey('question', key('r', { altKey: true }), ctx({ canAudio: false })), null);
  assert.equal(C.routeKey('question', key('f'), ctx()), null);
  assert.equal(C.routeKey('feedback', key('Enter'), ctx({ nativeControl: true })), null);
  assert.equal(C.routeKey('result', key('Enter'), ctx()), null);
});
test('six modes submit the correct representation without normalizing student text', () => {
  assert.equal(C.answerValue(question('audio_to_zh'), '', 1), '含义乙');
  assert.equal(C.answerValue(question('context_choice'), '', 1), 'b');
  assert.equal(C.answerValue(question('context_choice'), '', -1), '');
  for (const mode of ['en_to_zh', 'zh_to_en', 'audio_to_en', 'context_fill'])
    assert.equal(
      C.answerValue(question(mode), "  12 May / don't-guess 中 文  ", -1),
      "12 May / don't-guess 中 文",
    );
});
test('attempt IDs share the mobile first/retry slots and isolate correction attempts', () => {
  const q = question();
  assert.equal(C.attemptId(10, q), 'vocabulary-group:10:first:17');
  assert.equal(C.attemptId(10, { ...q, retry: true }), 'vocabulary-group:10:retry:17');
  assert.equal(
    C.attemptId(10, { ...q, retry: true, correction_count: 1 }, null, true),
    'vocabulary-group:10:correction:17:retry:2',
  );
  assert.equal(
    C.attemptId(10, { ...q, review_item_id: 20 }, { session_id: 11 }),
    'web-vocabulary-review:11:20',
  );
  assert.equal(
    C.attemptId(10, { ...q, review_item_id: 20 }, { session_id: 11 }, true),
    'web-vocabulary-review-correction:11:20:1',
  );
});
test('copying a revealed context choice label submits its option id for correction', () => {
  const q = question('context_choice');
  assert.equal(C.correctionValue(q, '  含义乙  '), 'b');
  assert.equal(C.correctionValue(q, '写错的答案'), '写错的答案');
  assert.equal(C.correctionValue(question('audio_to_zh'), '含义乙'), '含义乙');
  assert.equal(C.correctionValue(question('zh_to_en'), ' New York '), 'New York');
});
test('question identity includes retry and correction slots for safe drafts', () => {
  const q = question();
  assert.notEqual(C.questionKey(q), C.questionKey({ ...q, retry: true }));
  assert.notEqual(
    C.questionKey({ ...q, correction_required: true, correction_count: 0 }),
    C.questionKey({ ...q, correction_required: true, correction_count: 1 }),
  );
  assert.notEqual(
    C.position({ queue_token: 'a', phase: 'retry', current_question: q }),
    C.position({ queue_token: 'b', phase: 'retry', current_question: q }),
  );
});
test('hidden audio is unavailable in spelling/context prompts and safe URLs resolve', () => {
  for (const mode of ['zh_to_en', 'context_fill', 'context_choice']) {
    const q = question(mode);
    q.question.prompt.audio_tts_url = '/dictation/words/3/tts';
    assert.equal(C.audioUrl(q, 'question'), '');
  }
  for (const mode of ['en_to_zh', 'audio_to_en', 'audio_to_zh']) {
    const q = question(mode);
    q.question.prompt.audio_tts_url = '/dictation/words/3/tts';
    assert.equal(C.audioUrl(q, 'question'), '/api/dictation/words/3/tts');
  }
  assert.equal(C.resolveAudioUrl('uploads/audio.mp3'), '/uploads/audio.mp3');
  assert.equal(C.resolveAudioUrl('static/audio.mp3'), '/static/audio.mp3');
  assert.equal(C.resolveAudioUrl('javascript:alert(1)'), '');
  assert.equal(C.resolveAudioUrl('//foreign.test/audio'), '');
});
test('spelling diff exposes text operations whose accepted reading is exactly expected', () => {
  for (const [actual, expected] of [
    ['acomodate', 'accommodate'],
    ['definately', 'definitely'],
    ['abc<svg>', '<script>'],
    ['', 'word'],
    ['more', ''],
    ['中文', '中英'],
  ]) {
    const diff = C.spellingDiff(actual, expected);
    assert.equal(
      diff
        .filter((p) => p.kind !== 'del')
        .map((p) => p.text)
        .join(''),
      expected,
    );
    assert.equal(
      diff
        .filter((p) => p.kind !== 'ins')
        .map((p) => p.text)
        .join(''),
      actual,
    );
  }
});
test('service facts govern the state machine including empty completed review and read-only', () => {
  assert.equal(
    C.decideView({ access: { task_date_state: 'future', read_only: true } }),
    'locked_future',
  );
  assert.equal(
    C.decideView({ access: { read_only: true }, settlement: { accuracy: 80 } }),
    'result',
  );
  assert.equal(C.decideView({ stage: 'learning', flow: { completed: true } }), 'settling');
  assert.equal(
    C.decideView({
      stage: 'learning',
      flow: { phase: 'context_discrimination', current_question: question('context_fill') },
    }),
    'question',
  );
  assert.equal(
    C.decideView({
      stage: 'review',
      review: { items: [{ answered: true, correction_required: true }] },
    }),
    'review_correction',
  );
  assert.equal(
    C.decideView({ stage: 'review', review: { items: [{ answered: true }] } }),
    'review_settling',
  );
});

function loadTransport(fetchImpl) {
  const win = {},
    timers = new Map();
  let id = 0;
  vm.runInNewContext(
    fs.readFileSync(require.resolve('../static/js/practice_vocabulary_transport.js'), 'utf8'),
    {
      window: win,
      fetch: fetchImpl,
      AbortController,
      setTimeout(fn, ms) {
        const key = ++id;
        timers.set(key, fn);
        if (ms === 1000) queueMicrotask(fn);
        return key;
      },
      clearTimeout(key) {
        timers.delete(key);
      },
    },
  );
  return win.PracticeVocabularyTransport;
}
function memoryStorage() {
  const map = new Map();
  return {
    getItem: (k) => map.get(k) || null,
    setItem: (k, v) => map.set(k, v),
    removeItem: (k) => map.delete(k),
  };
}
test('blocked sessionStorage does not prevent learning', () => {
  const T = loadTransport(),
    storage = new T.Storage(1, 'identity', {
      getItem() {
        throw Error();
      },
      setItem() {
        throw Error();
      },
      removeItem() {
        throw Error();
      },
    });
  assert.doesNotThrow(() => storage.put('pending', { attempt_id: 'a' }));
  assert.equal(storage.get('pending'), null);
  assert.doesNotThrow(() => storage.remove('pending'));
});
test('network retries reuse identical payload, send identity and clear journal only after ok', async () => {
  const calls = [];
  const T = loadTransport(async (url, init) => {
    calls.push({ url, init });
    if (calls.length === 1) throw Error('offline');
    return {
      ok: true,
      status: 200,
      json: async () => ({ ok: true, feedback: { is_correct: true } }),
    };
  });
  const storage = new T.Storage(1, 'id', memoryStorage()),
    client = new T.Client(
      { api_base: '/api/task/1', csrf_token: 'csrf', identity_key: 'id' },
      storage,
    );
  await client.send('answers', { attempt_id: 'a', answer: 'same' }, 'position');
  assert.equal(calls.length, 2);
  assert.equal(calls[0].init.body, calls[1].init.body);
  assert.equal(calls[0].init.headers['X-Practice-Identity'], 'id');
  assert.equal(calls[0].init.headers['X-CSRF-Token'], 'csrf');
  assert.equal(storage.get('pending'), null);
});
test('failed or malformed success preserves the pending answer, including during recovery sync', async () => {
  const T = loadTransport(async () => ({
    ok: true,
    status: 200,
    json: async () => ({ ok: false, error: 'save_failed' }),
  }));
  const storage = new T.Storage(1, 'id', memoryStorage()),
    client = new T.Client({ api_base: '/api/task/1' }, storage);
  await assert.rejects(client.send('answers', { attempt_id: 'immutable', answer: 'a' }, 'p'));
  assert.equal(storage.get('pending').attempt_id, 'immutable');
  client.fetchOnce = async () => ({ ok: true, stage: 'learning' });
  await client.send('sync', { attempt_id: 'immutable' }, 'p');
  assert.equal(storage.get('pending').attempt_id, 'immutable');
});
test('single-flight and sequence guard reject duplicate writes and obsolete callbacks', async () => {
  let resolve;
  const T = loadTransport(
      () =>
        new Promise((done) => {
          resolve = done;
        }),
    ),
    storage = new T.Storage(1, 'id', memoryStorage()),
    client = new T.Client({ api_base: '/api/task/1' }, storage);
  const first = client.send('answers', { attempt_id: 'a' }, 'p');
  await assert.rejects(
    client.send('answers', { attempt_id: 'b' }, 'p'),
    (error) => error.code === 'request_busy',
  );
  client.seq++;
  resolve({ ok: true, status: 200, json: async () => ({ ok: true }) });
  await assert.rejects(first, (error) => error.code === 'stale_response');
  assert.equal(storage.get('pending').attempt_id, 'a');
});

function pageHarness(clock = Date) {
  const calls = [],
    output = [],
    storage = memoryStorage(),
    node = { textContent: '' };
  const document = {
    getElementById: () => null,
    querySelector: () => node,
    querySelectorAll: () => [],
  };
  class View {
    show(model) {
      output.push(model.state);
    }
    busy() {}
    status() {}
    audio() {}
    toast() {}
    message(text) {
      this.lastMessage = text;
    }
  }
  class Player {
    stop() {}
    play() {}
  }
  const T = loadTransport();
  const win = {
    PracticeVocabularyCore: C,
    PracticeVocabularyTransport: { ...T, Player },
    PracticeVocabularyView: View,
    PracticeVocabularyEvents: { install: () => ({ transition() {} }) },
  };
  vm.runInNewContext(
    fs.readFileSync(require.resolve('../static/js/practice_vocabulary_recovery.js'), 'utf8'),
    { window: win, Date: clock },
  );
  vm.runInNewContext(
    fs.readFileSync(require.resolve('../static/js/practice_vocabulary_page.js'), 'utf8'),
    {
      window: win,
      document,
      sessionStorage: storage,
      queueMicrotask,
      Date: clock,
      location: { assign() {} },
    },
  );
  const page = new win.PracticeVocabularyPage({
    task_id: 10,
    identity_key: 'id',
    task: { title: 'Test' },
  });
  page.request = async (kind, payload) => {
    calls.push({ kind, payload });
    return page.reply;
  };
  return { page, calls, output };
}
test('actual submit includes domain identity tuple and audio choice submits label', async () => {
  const { page, calls } = pageHarness(),
    q = question('audio_to_zh');
  page.model = {
    state: 'question',
    data: { stage: 'learning', flow: { queue_token: 'q' } },
    q,
    selected: 1,
    draft: '',
    busy: false,
  };
  page.reply = { ok: true, feedback: { is_correct: true, student_answer: '含义乙' } };
  await page.submit('answer');
  const sent = calls[0].payload;
  assert.equal(sent.answer, '含义乙');
  assert.equal(sent.sense_id, 8);
  assert.equal(sent.dimension, 'form_recall');
  assert.equal(sent.retry, false);
  assert.equal(page.model.state, 'feedback');
});
test('empty answers stay local; forgotten response is explicit and distinct', async () => {
  const { page, calls } = pageHarness();
  page.model = {
    state: 'question',
    data: { stage: 'learning', flow: { queue_token: 'q' } },
    q: question(),
    selected: -1,
    draft: '',
    busy: false,
  };
  await page.submit('answer');
  assert.equal(calls.length, 0);
  page.reply = { feedback: { is_correct: false, response_kind: 'forgot' } };
  await page.submit('forgot');
  assert.equal(calls[0].payload.response_kind, 'forgot');
  assert.equal(page.model.state, 'feedback');
  assert.ok(page.feedbackUntil > Date.now());
});
test('review answer forwards session ownership and correct item fields', async () => {
  const { page, calls } = pageHarness(),
    q = question('context_choice', { review_item_id: 23 });
  page.model = {
    state: 'review_question',
    data: {
      stage: 'review',
      review: { session_id: 4, session_token: 'secret', queue_token: 'queue', items: [q] },
    },
    q,
    selected: 1,
    draft: '',
    busy: false,
  };
  page.reply = {
    stage: 'review_feedback',
    feedback: { is_correct: true },
    review: { session_id: 4, items: [{ ...q, answered: true }] },
  };
  await page.submit('answer');
  assert.equal(calls[0].kind, 'review/answers');
  assert.equal(calls[0].payload.answer, 'b');
  assert.equal(calls[0].payload.session_token, 'secret');
  assert.equal(calls[0].payload.sense_id, 8);
  assert.equal(page.model.data.stage, 'review');
  assert.equal(page.model.state, 'review_feedback');
});
test('recovery displays saved feedback without auto-settling behind it', async () => {
  const { page, calls } = pageHarness(),
    q = question();
  page.reply = {
    stage: 'learning',
    flow: {
      completed: true,
      saved_response: { is_correct: true, student_answer: 'word', revealed_answer: 'word' },
    },
  };
  await page.recover({
    kind: 'answers',
    attempt_id: 'a',
    payload: { answer: 'word' },
    position: 'old',
    context: { q },
  });
  assert.equal(page.model.state, 'feedback');
  assert.deepEqual(
    calls.map((c) => c.kind),
    ['sync'],
  );
});
test('review recovery reads answered item instead of falsely advancing past missing feedback', async () => {
  const { page, calls } = pageHarness(),
    q = question('zh_to_en', { review_item_id: 23 });
  page.reply = {
    stage: 'review',
    review: {
      session_id: 4,
      items: [
        {
          ...q,
          answered: true,
          first_is_correct: false,
          first_answer: 'wrong',
          revealed_answer: 'word',
        },
      ],
    },
  };
  await page.recover({
    kind: 'review/answers',
    attempt_id: 'a',
    payload: { review_item_id: 23 },
    position: 'old',
    context: { q },
  });
  assert.equal(page.model.state, 'review_feedback');
  assert.equal(page.model.feedback.student_answer, 'wrong');
  assert.deepEqual(
    calls.map((c) => c.kind),
    ['review/claim'],
  );
});

test('same-session focus refresh preserves review elapsed time and a new session resets it', async () => {
  let now = 1000;
  const { page, calls } = pageHarness({ now: () => now });
  const review = {
    session_id: 4,
    session_token: 'token',
    queue_token: 'queue',
    items: [question('zh_to_en', { review_item_id: 23, answered: false })],
  };
  page.reply = { stage: 'review', review };
  await page.claimReview();
  assert.equal(page.reviewStarted, 1000);
  now = 61000;
  await page.refresh();
  assert.equal(page.reviewStarted, 1000);
  now = 62000;
  page.reply = null;
  await page.settle(true);
  assert.equal(calls.find((call) => call.kind === 'review/settle').payload.duration_seconds, 61);
  now = 121000;
  page.reply = { stage: 'review', review: { ...review, session_id: 5 } };
  await page.claimReview();
  assert.equal(page.reviewStarted, 121000);
});

test('correction audio uses the current revealed question rather than stale feedback', () => {
  const old = {
    learning_question_id: 7,
    review_item_id: 7,
    answer_feedback: { audio_tts_url: '/dictation/words/7/tts' },
  };
  const current = question('zh_to_en', {
    learning_question_id: 8,
    word_id: 8,
    correction_required: true,
    revealed_answer: 'current',
  });
  assert.equal(C.audioUrl(current, 'correction', old), '/api/dictation/words/8/tts');
  assert.equal(
    C.audioUrl(
      {
        ...current,
        review_item_id: 8,
        answer_feedback: { audio_tts_url: '/dictation/words/8/tts?current=1' },
      },
      'review_correction',
      old,
    ),
    '/api/dictation/words/8/tts?current=1',
  );
  assert.equal(C.audioUrl({ ...current, revealed_answer: undefined }, 'correction', old), '');
  assert.equal(C.audioUrl(current, 'question', old), '');
});

test('cross-device advancement clears unmatched feedback before rendering a different correction', () => {
  const { page } = pageHarness();
  page.model.q = question('zh_to_en', { learning_question_id: 7, word_id: 7 });
  page.model.feedback = {
    learning_question_id: 7,
    revealed_answer: 'previous',
    answer_feedback: { audio_tts_url: '/dictation/words/7/tts' },
  };
  page.apply(
    {
      stage: 'learning',
      flow: {
        phase: 'active_recall',
        correction_required: true,
        current_question: question('zh_to_en', {
          learning_question_id: 8,
          word_id: 8,
          correction_required: true,
          revealed_answer: 'current',
        }),
      },
    },
    true,
  );
  assert.equal(page.model.feedback, null);
  assert.equal(page.model.state, 'correction');
  assert.equal(page.model.audioUrl, '/api/dictation/words/8/tts');
});

test('review gate displays the bounded batch rather than the entire backlog', () => {
  assert.equal(C.reviewCount({ due_count: 6000, batch_limit: 20 }), 20);
  assert.equal(C.reviewCount({ due_count: 7, batch_limit: 20 }), 7);
  assert.equal(C.reviewCount({ total_count: 0, due_count: 6000 }), 0);
});

function renderHarness() {
  class Element {
    constructor(tag) {
      this.tagName = tag.toUpperCase();
      this.children = [];
      this.dataset = {};
      this.style = {};
      this.attrs = {};
      this._text = '';
    }
    set textContent(value) {
      this._text = String(value);
      this.children = [];
    }
    get textContent() {
      return this._text + this.children.map((child) => child.textContent).join('');
    }
    get childNodes() {
      return this.children;
    }
    append(...children) {
      this.children.push(...children);
    }
    replaceChildren(...children) {
      this._text = '';
      this.children = children;
    }
    setAttribute(key, value) {
      this.attrs[key] = String(value);
    }
    focus() {}
    closest() {
      return null;
    }
    walk() {
      return [this, ...this.children.flatMap((child) => child.walk())];
    }
    querySelectorAll(selector) {
      return this.walk()
        .slice(1)
        .filter((node) => {
          if (selector === 'button') return node.tagName === 'BUTTON';
          if (selector.startsWith('#')) return node.id === selector.slice(1);
          if (selector.startsWith('.'))
            return String(node.className || '')
              .split(' ')
              .includes(selector.slice(1));
          return false;
        });
    }
    querySelector(selector) {
      return this.querySelectorAll(selector)[0] || null;
    }
  }
  const ids = {};
  for (const id of ['pv-stage', 'pv-bar', 'pv-chips', 'pv-title', 'pv-rail', 'pv-save', 'pv-toast'])
    ids[id] = new Element('div');
  const document = {
    activeElement: null,
    createElement: (tag) => new Element(tag),
    createTextNode(value) {
      const node = new Element('#text');
      node.textContent = value;
      return node;
    },
    getElementById: (id) => ids[id] || ids['pv-stage'].walk().find((n) => n.id === id) || null,
    querySelectorAll: (selector) => ids['pv-stage'].querySelectorAll(selector),
  };
  const win = { PracticeVocabularyCore: C };
  const env = { window: win, document, clearTimeout, setTimeout };
  for (const name of ['render_details', 'render'])
    vm.runInNewContext(
      fs.readFileSync(require.resolve(`../static/js/practice_vocabulary_${name}.js`), 'utf8'),
      env,
    );
  return { view: new win.PracticeVocabularyView(), ids };
}
test('all six prompt renderers reject hidden answer fields and treat strings as text', () => {
  for (const mode of Object.keys(C.MODE_LABELS)) {
    const { view, ids } = renderHarness(),
      q = question(mode);
    q.question.prompt = {
      word: 'VISIBLE_WORD',
      phonetic: 'SECRET_PHONETIC',
      meaning: 'VISIBLE_MEANING',
      instruction: 'INSTRUCTION <img src=x onerror=attack()>',
      sentence: 'Safe ____ sentence',
      translation: 'TRANSLATION',
      target_word: 'SECRET_TARGET',
      audio_tts_url: '/dictation/words/3/tts',
    };
    q.revealed_answer = 'SECRET_ANSWER';
    q.first_answer = 'SECRET_FIRST';
    q.answer_feedback = { word: 'SECRET_FEEDBACK' };
    view.show({
      state: 'question',
      data: { task: { title: 'Test' }, flow: {} },
      q,
      draft: '',
      selected: -1,
      busy: false,
      audioUrl: C.audioUrl(q, 'question'),
    });
    const stage = ids['pv-stage'],
      text = stage.textContent;
    for (const hidden of ['SECRET_ANSWER', 'SECRET_FIRST', 'SECRET_FEEDBACK'])
      assert.equal(text.includes(hidden), false, mode + ' hides ' + hidden);
    if (mode !== 'en_to_zh') assert.equal(text.includes('SECRET_PHONETIC'), false);
    if (mode !== 'en_to_zh') assert.equal(text.includes('VISIBLE_WORD'), false);
    if (mode !== 'zh_to_en') assert.equal(text.includes('VISIBLE_MEANING'), false);
    assert.ok(text.includes('<img src=x onerror=attack()>'));
    assert.equal(
      stage.walk().some((n) => n.tagName === 'IMG'),
      false,
    );
    if (!C.choice(q)) {
      const field = stage.walk().find((n) => n.tagName === 'INPUT');
      assert.equal(field.maxLength, mode === 'en_to_zh' ? 200 : 100);
      assert.equal(field.spellcheck, false);
      assert.equal(field.autocomplete, 'off');
    }
  }
});
test('feedback safely reveals answer only after submission, and correction labels unscored copying', () => {
  const { view, ids } = renderHarness(),
    q = question();
  const model = {
    state: 'feedback',
    data: { task: { title: 'Test' }, flow: {} },
    q,
    draft: '',
    selected: -1,
    busy: false,
    feedback: {
      is_correct: false,
      student_answer: 'accomodate',
      revealed_answer: 'accommodate',
      answer_feedback: { word: '<script>literal</script>' },
    },
  };
  view.show(model);
  assert.ok(ids['pv-stage'].textContent.includes('accommodate'));
  assert.equal(
    ids['pv-stage'].walk().some((n) => n.tagName === 'SCRIPT'),
    false,
  );
  view.show({
    ...model,
    state: 'correction',
    q: { ...q, revealed_answer: 'accommodate', correction_count: 1 },
  });
  assert.ok(ids['pv-stage'].textContent.includes('不计分'));
  assert.ok(ids['pv-stage'].textContent.includes('第 2 / 2 次'));
});

test('task and review choice feedback render saved labels instead of internal option ids', () => {
  for (const state of ['feedback', 'review_feedback']) {
    const { view, ids } = renderHarness();
    const q = question('context_choice');
    q.question.options = [
      { id: 'option_right_123', label: '正确选项的文字' },
      { id: 'option_wrong_456', label: '学生选过的文字 <img src=x>' },
    ];
    view.show({
      state,
      data: { task: { title: 'Test' }, flow: {} },
      q,
      draft: '',
      selected: -1,
      busy: false,
      feedback: {
        is_correct: false,
        student_answer: 'option_wrong_456',
        revealed_answer: '正确选项的文字',
      },
    });
    const stage = ids['pv-stage'];
    assert.ok(stage.textContent.includes('学生选过的文字 <img src=x>'));
    assert.ok(stage.textContent.includes('正确选项的文字'));
    assert.equal(stage.textContent.includes('option_wrong_456'), false);
    assert.equal(
      stage.walk().some((node) => node.tagName === 'IMG'),
      false,
    );
  }
});

test('unknown saved option ids use a readable fallback without guessing the answer', () => {
  const { view, ids } = renderHarness();
  view.show({
    state: 'feedback',
    data: { task: { title: 'Test' }, flow: {} },
    q: question('context_choice'),
    draft: '',
    selected: -1,
    busy: false,
    feedback: {
      is_correct: false,
      student_answer: 'option_missing_private',
      revealed_answer: '含义甲',
    },
  });
  const definitions = ids['pv-stage'].walk().filter((node) => node.tagName === 'DD');
  assert.equal(definitions[0].textContent, '含义甲');
  assert.equal(definitions[1].textContent, '已保存的选项（当前选项不可用）');
  assert.equal(ids['pv-stage'].textContent.includes('option_missing_private'), false);
});

test('settled task marks stages complete while retaining the pending review count', () => {
  const { view, ids } = renderHarness();
  view.show({
    state: 'result',
    busy: false,
    data: {
      task: { title: 'Test' },
      flow: {
        phase: 'complete',
        completed: true,
        phase_counts: { familiarity: 2, active_recall: 2, context_discrimination: 2 },
      },
      settlement: { accuracy: 50, correct_count: 2, total_count: 4, deferred_review_count: 2 },
    },
  });
  const rail = ids['pv-rail'];
  const steps = rail.walk().filter((node) =>
    String(node.className || '')
      .split(' ')
      .includes('pv-step'),
  );
  assert.equal(steps.length, 3);
  for (const step of steps) {
    assert.ok(step.className.includes('pv-step--done'));
    assert.equal(step.children[0].textContent, '✓');
  }
  assert.equal(
    rail.walk().find((node) => node.attrs.role === 'progressbar').attrs['aria-valuenow'],
    '100',
  );
  assert.ok(ids['pv-stage'].textContent.includes('2仍待复习'));
  assert.equal(ids['pv-stage'].textContent.includes('已掌握'), false);
});

function eventHarness() {
  const listeners = {},
    timers = [],
    actions = [];
  const dialog = {
    open: false,
    showModal() {
      this.open = true;
    },
    close() {
      this.open = false;
    },
    querySelector: () => ({ addEventListener() {} }),
  };
  const document = {
    visibilityState: 'visible',
    addEventListener(name, fn) {
      listeners[name] = fn;
    },
    getElementById: (id) => (id === 'pv-help-dialog' ? dialog : { addEventListener() {} }),
  };
  const win = {
    PracticeVocabularyCore: C,
    addEventListener(name, fn) {
      listeners['window:' + name] = fn;
    },
  };
  vm.runInNewContext(
    fs.readFileSync(require.resolve('../static/js/practice_vocabulary_events.js'), 'utf8'),
    {
      window: win,
      document,
      Date,
      setTimeout(fn) {
        timers.push(fn);
      },
    },
  );
  const app = {
    boot: { task_id: 10 },
    model: { state: 'question', q: question(), audioUrl: '', busy: false },
    player: { stop() {} },
    view: { status() {} },
    saveDraft() {},
    refresh() {},
    action(value) {
      actions.push(value);
      controller.transition();
    },
  };
  const controller = win.PracticeVocabularyEvents.install(app);
  const inputTarget = { closest: (selector) => (selector.includes('input') ? {} : null) };
  function dispatch(name, keyValue, extra = {}) {
    const event = {
      key: keyValue,
      target: inputTarget,
      ...extra,
      prevented: false,
      preventDefault() {
        this.prevented = true;
      },
    };
    listeners[name](event);
    return event;
  }
  return { app, actions, controller, listeners, timers, dispatch };
}
test('real keyboard wiring requires Enter release across state changes', () => {
  const h = eventHarness();
  h.dispatch('keydown', 'Enter');
  assert.deepEqual(h.actions, ['primary']);
  h.app.model.state = 'feedback';
  h.app.feedbackUntil = 0;
  h.dispatch('keydown', 'Enter', { repeat: true });
  h.dispatch('keydown', 'Enter');
  assert.deepEqual(h.actions, ['primary']);
  h.dispatch('keyup', 'Enter');
  h.dispatch('keydown', 'Enter');
  assert.deepEqual(h.actions, ['primary', 'primary']);
});
test('composition-end same-turn Enter stays local, then the next deliberate Enter submits', () => {
  const h = eventHarness();
  h.listeners.compositionstart();
  h.dispatch('keydown', 'Enter');
  h.listeners.compositionend();
  h.dispatch('keydown', 'Enter');
  assert.deepEqual(h.actions, []);
  h.timers.forEach((fn) => fn());
  h.dispatch('keyup', 'Enter');
  h.dispatch('keydown', 'Enter');
  assert.deepEqual(h.actions, ['primary']);
});
test('native button repeat is prevented and mouse transitions do not swallow the next Enter', () => {
  const h = eventHarness(),
    buttonTarget = { closest: (selector) => (selector.includes('button') ? {} : null) };
  assert.equal(
    h.dispatch('keydown', 'Enter', { repeat: true, target: buttonTarget }).prevented,
    true,
  );
  h.controller.transition();
  assert.equal(h.controller.state.enterArmed, true);
  h.dispatch('keydown', 'Enter');
  assert.deepEqual(h.actions, ['primary']);
});
