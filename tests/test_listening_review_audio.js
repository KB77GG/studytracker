const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const vm = require('node:vm');

const TEMPLATE = fs.readFileSync(
  path.resolve(__dirname, '../templates/listening/test_practice.html'),
  'utf8'
);

function between(startMarker, endMarker) {
  const start = TEMPLATE.indexOf(startMarker);
  const end = TEMPLATE.indexOf(endMarker, start);
  assert.notEqual(start, -1, `missing ${startMarker}`);
  assert.notEqual(end, -1, `missing ${endMarker}`);
  return TEMPLATE.slice(start, end);
}

function reviewRuntime() {
  const audioHelpers = between('function questionAudioWindow(', '\n\nfunction seekTo(');
  const questionHelpers = between('function questionForId(', '\n\nfunction updateReviewCards(');
  const openReview = between('function openReviewCard(', '\n\nfunction answerSnapshot(');
  const calls = { sections: [], plays: [], scrolls: 0, syncs: 0 };
  const cards = [
    { dataset: { reviewQuestion: '22081' }, classList: { toggle(_name, open) { this.open = open; } } },
    { dataset: { reviewQuestion: '22082' }, classList: { toggle(_name, open) { this.open = open; } } }
  ];
  const questions = [
    { id: 22081, number: 7, sectionIndex: 2, audio_review: { available: true, start: 230.25, end: 244.5 } },
    { id: 22082, number: 8, sectionIndex: 3, audio_review: { available: false, reason: '定位不可用' } },
    { id: 22083, number: 9, sectionIndex: 0, audio_review: { available: true, start: 0, end: 8 } }
  ];
  const context = {
    __calls: calls,
    __cards: cards,
    __questions: questions,
    escapeHtml: (value) => String(value),
    formatClock: (seconds) => `${Math.floor(Number(seconds) / 60)}:${String(Math.floor(Number(seconds)) % 60).padStart(2, '0')}`,
    allQuestions: () => questions,
    document: { querySelectorAll: () => cards },
    findUnitByQuestionId: () => ({
      closest: () => ({ scrollIntoView: () => { calls.scrolls += 1; } })
    }),
    switchSection: (index) => { calls.sections.push(index); },
    playQuestionAudio: (questionId, sectionIndex) => { calls.plays.push([String(questionId), sectionIndex]); },
    syncQuestionNav: () => { calls.syncs += 1; },
    Number,
    String
  };
  vm.createContext(context);
  vm.runInContext(`
    let activeSectionIndex = 0;
    let currentQuestionId = '';
    let latestResults = [];
    ${audioHelpers}
    ${questionHelpers}
    ${openReview}
  `, context);
  return context;
}

test('review focus resolves a question id and plays its verified clip', () => {
  const runtime = reviewRuntime();
  vm.runInContext(`openReviewCard('22081', true, true)`, runtime);

  assert.deepEqual(runtime.__calls.sections, [2]);
  assert.deepEqual(runtime.__calls.plays, [['22081', 2]]);
  assert.equal(runtime.__calls.scrolls, 1);
  assert.equal(runtime.__cards[0].classList.open, true);
  assert.equal(runtime.__cards[1].classList.open, false);
});

test('review focus still delegates an unavailable window to the Section fallback', () => {
  const runtime = reviewRuntime();
  vm.runInContext(`openReviewCard('22082', true, true)`, runtime);

  assert.deepEqual(runtime.__calls.sections, [3]);
  assert.deepEqual(runtime.__calls.plays, [['22082', 3]]);
  assert.equal(runtime.__calls.scrolls, 1);
});

test('zero is a valid verified clip start and receives a visible review locator', () => {
  const runtime = reviewRuntime();
  const result = vm.runInContext(`({
    window: questionAudioWindow(__questions[2]),
    locator: reviewAudioLocator(__questions[2], 0)
  })`, runtime);

  assert.equal(result.window.start, 0);
  assert.equal(result.window.end, 8);
  assert.match(result.locator, /播放定位片段 0:00–0:08/);
  assert.match(result.locator, /playQuestionAudio\('22083', 0\)/);
  assert.match(result.locator, /data-capability="canShowCorrectness" hidden/);
});

test('unavailable question locator is explicit about the full Section fallback', () => {
  const runtime = reviewRuntime();
  const locator = vm.runInContext(`reviewAudioLocator(__questions[1], 3)`, runtime);
  assert.match(locator, /定位不可用 · 播放完整 Section/);
  assert.match(locator, /data-audio-fallback="section"/);
});

test('every review entry point is wired to seek while initial review loading remains silent', () => {
  assert.match(TEMPLATE, /openReviewCard\(button\.dataset\.id, true, true\)/);
  assert.match(TEMPLATE, /openReviewCard\(currentQuestionId, true, true\)/);
  assert.match(TEMPLATE, /openReviewCard\(link\.dataset\.reviewJump, true, true\)/);
  assert.match(TEMPLATE, /openReviewCard\(anchor\.dataset\.questionId, false, true\)/);
  assert.match(TEMPLATE, /openReviewCard\(card\.dataset\.reviewQuestion, false, true\)/);
  assert.match(TEMPLATE, /openReviewCard\(currentQuestionId \|\| allQuestions\(\)\[0\]\?\.id \|\| allQuestions\(\)\[0\]\?\.number\);/);
});

test('every listening question renderer keeps a hidden locator ready for review', () => {
  assert.match(TEMPLATE, /function renderQuestion[\s\S]*reviewAudioLocator\(question, sectionIndex\)/);
  assert.match(TEMPLATE, /renderForm\([\s\S]*question => `\$\{reviewAudioLocator\(question, sectionIndex\)\}/);
  assert.match(TEMPLATE, /renderMatching\([\s\S]*\$\{reviewAudioLocator\(question, sectionIndex\)\}/);
  assert.match(TEMPLATE, /\(hasCollect \|\| hasTable \|\| combinedMulti\)[\s\S]*\$\{reviewAudioLocator\(q, sectionIndex\)\}/);
  assert.match(TEMPLATE, /data-review-audio-question="\$\{id\}" data-capability="canShowCorrectness" hidden/);
});

test('transcript seeks share the trusted timeline gate and expected media duration', () => {
  const helpers = between('function sectionAudioTimeline(', '\n\nfunction transcriptIndexAt(');
  const calls = { fallback: [], playFrom: [], sync: [] };
  const context = {
    test: {
      sections: [
        { audio_timeline: { available: false, reason: '版本不匹配' } },
        { audio_timeline: { available: true, expected_duration: 123.5 } }
      ]
    },
    experienceCapabilities: { canSeekAudio: true },
    playCompleteSection: (sectionIndex, fallback) => calls.fallback.push([sectionIndex, fallback]),
    listeningClipPlayer: {
      playFrom: options => calls.playFrom.push(options)
    },
    syncTranscriptAt: (sectionIndex, seconds) => calls.sync.push([sectionIndex, seconds]),
    Number
  };
  vm.createContext(context);
  vm.runInContext(helpers, context);

  vm.runInContext('seekTo(0, 88)', context);
  assert.deepEqual(calls.fallback, [[0, true]]);
  assert.deepEqual(calls.playFrom, []);
  assert.deepEqual(calls.sync, [[0, 0]]);

  vm.runInContext('seekTo(1, 22)', context);
  assert.equal(calls.playFrom.length, 1);
  assert.equal(calls.playFrom[0].sectionIndex, 1);
  assert.equal(calls.playFrom[0].start, 22);
  assert.equal(calls.playFrom[0].expectedDuration, 123.5);
});

test('untrusted transcript text stays readable but all sentence controls are disabled', () => {
  assert.match(TEMPLATE, /transcript-timeline-warning/);
  assert.match(TEMPLATE, /transcript-row\$\{timeline\.available \? '' : ' is-static'\}/);
  assert.match(TEMPLATE, /timeline\.available \? `onclick="seekTo/);
  assert.match(TEMPLATE, /<button class="small-btn" type="button" disabled>定位不可用<\/button>/);
});

const cambridge18 = JSON.parse(fs.readFileSync(
  path.resolve(__dirname, '../static/listening_tests/ielts18_test1.json'), 'utf8'
));
const actualRenderers = require('../static/js/practice_renderers.js');
const cambridgeQuestions = cambridge18.sections.flatMap((section, sectionIndex) =>
  section.groups.flatMap(group => group.questions.map(question => ({
    ...question,
    sectionIndex,
    audio_review: {
      available: true, start: question.start, end: question.end,
      evidence: section.transcript
        .filter(row => Math.max(row.start, question.start) < Math.min(row.end, question.end))
        .map(row => ({ text: row.en }))
    }
  })))
);

function cambridgeReviewRuntime() {
  const replacements = new Map();
  const calls = { plays: [], sections: [] };
  const cards = cambridgeQuestions.map(question => ({
    dataset: { reviewQuestion: String(question.id) },
    classList: { toggle(_name, open) { this.open = open; } },
    replaceWith(value) { replacements.set(String(question.id), value); }
  }));
  const context = {
    allQuestions: () => cambridgeQuestions,
    PracticeRenderers: actualRenderers,
    escapeHtml: actualRenderers.escapeHtml,
    CSS: { escape: String },
    formatClock: seconds => String(seconds),
    unitValue: unit => unit.value,
    syncQuestionNav() {},
    findUnitByQuestionId() { return null; },
    switchSection: section => calls.sections.push(section),
    playQuestionAudio: (id, section) => calls.plays.push([id, section]),
    document: {
      querySelector(selector) {
        const id = /data-review-question="([^"]+)"/.exec(selector)?.[1];
        return cards.find(card => card.dataset.reviewQuestion === id);
      },
      querySelectorAll: () => cards,
      createElement() {
        return {
          set innerHTML(html) {
            this.firstElementChild = {
              html,
              dataset: { reviewQuestion: /data-review-question="([^"]+)"/.exec(html)?.[1] },
              classList: { toggle() {} },
              setAttribute(name, value) { this[name] = value; }
            };
          }
        };
      }
    }
  };
  vm.createContext(context);
  vm.runInContext(`let currentQuestionId = ''; let activeSectionIndex = 0; let latestResults = [];
    ${between('function questionAudioWindow(', '\n\nfunction reviewAudioLocator(')}
    ${between('function questionForId(', '\n\nfunction renderReviewSummary(')}
    ${between('function openReviewCard(', '\n\nfunction answerSnapshot(')}
    ${between('function resultHtml(', '\n\nfunction applyServerResults(')}
  `, context);
  return { context, replacements, calls, cards };
}

test('real Cambridge 18 ids cannot be intercepted by another question displayed number', () => {
  const { context, calls, cards } = cambridgeReviewRuntime();
  assert.equal(cambridgeQuestions.find(question => question.number === 14).id, 11);
  assert.equal(cambridgeQuestions.find(question => question.number === 11).id, 1851);
  for (const question of cambridgeQuestions) {
    assert.equal(context.questionForId(String(question.id)).number, question.number);
    context.openReviewCard(String(question.id), false, true);
    assert.deepEqual(calls.plays.at(-1), [String(question.id), question.sectionIndex]);
    assert.deepEqual(cards.filter(card => card.classList.open).map(card => card.dataset.reviewQuestion), [String(question.id)]);
  }
  assert.equal(context.questionForId('999999'), undefined);
});

test('real Cambridge 18 multi-choice review replacements preserve each source question analysis and evidence', () => {
  const { context, replacements } = cambridgeReviewRuntime();
  for (const numbers of [[14, 15], [29, 30]]) {
    const questions = numbers.map(number => cambridgeQuestions.find(question => question.number === number));
    const answer = questions[0].answer;
    const unit = { dataset: { id: questions.map(question => question.id).join(',') }, value: answer };
    context.updateReviewCards(unit, { answer, status: 'correct' });
    for (const question of questions) {
      const rendered = replacements.get(String(question.id));
      assert.equal(rendered.dataset.reviewQuestion, String(question.id));
      assert.ok(rendered.html.includes(actualRenderers.escapeHtml(question.analysis)));
      for (const evidence of question.audio_review.evidence) {
        assert.ok(rendered.html.includes(actualRenderers.escapeHtml(evidence.text)));
      }
      assert.ok(rendered['aria-label'].includes(`第 ${question.number} 题`));
    }
  }
});

test('displayed-number result links resolve explicitly to ids including combined labels', () => {
  const { context } = cambridgeReviewRuntime();
  const html = context.resultHtml(0, 40, ['11', '14,15', '20', '29,30', '999']);
  assert.match(html, /data-review-jump="1851">Q11</);
  assert.match(html, /data-review-jump="11">Q14,15</);
  assert.match(html, /data-review-jump="17">Q20</);
  assert.match(html, /data-review-jump="20">Q29,30</);
  assert.doesNotMatch(html, /data-review-jump="999"/);
});
