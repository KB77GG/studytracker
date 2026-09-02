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
  const audioHelpers = between('function questionAudioStart(', '\n\nfunction seekTo(');
  const questionHelpers = between('function questionForId(', '\n\nfunction updateReviewCards(');
  const openReview = between('function openReviewCard(', '\n\nfunction answerSnapshot(');
  const calls = { sections: [], seeks: [], scrolls: 0, syncs: 0 };
  const cards = [
    { dataset: { reviewQuestion: '22081' }, classList: { toggle(_name, open) { this.open = open; } } },
    { dataset: { reviewQuestion: '22082' }, classList: { toggle(_name, open) { this.open = open; } } }
  ];
  const questions = [
    { id: 22081, number: 7, sectionIndex: 2, start: 240.25 },
    { id: 22082, number: 8, sectionIndex: 3, start: null },
    { id: 22083, number: 9, sectionIndex: 0, start: 0 }
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
    seekTo: (sectionIndex, seconds) => { calls.seeks.push([sectionIndex, seconds]); },
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

test('review focus resolves a displayed question number and seeks its source timestamp', () => {
  const runtime = reviewRuntime();
  vm.runInContext(`openReviewCard('7', true, true)`, runtime);

  assert.deepEqual(runtime.__calls.sections, [2]);
  assert.deepEqual(runtime.__calls.seeks, [[2, 240.25]]);
  assert.equal(runtime.__calls.scrolls, 1);
  assert.equal(runtime.__cards[0].classList.open, true);
  assert.equal(runtime.__cards[1].classList.open, false);
});

test('review focus changes section but does not seek when a question has no timestamp', () => {
  const runtime = reviewRuntime();
  vm.runInContext(`openReviewCard('22082', true, true)`, runtime);

  assert.deepEqual(runtime.__calls.sections, [3]);
  assert.deepEqual(runtime.__calls.seeks, []);
  assert.equal(runtime.__calls.scrolls, 1);
});

test('zero is a valid audio timestamp and receives a visible review locator', () => {
  const runtime = reviewRuntime();
  const result = vm.runInContext(`({
    start: questionAudioStart(__questions[2]),
    locator: reviewAudioLocator(__questions[2], 0)
  })`, runtime);

  assert.equal(result.start, 0);
  assert.match(result.locator, /定位音频 0:00/);
  assert.match(result.locator, /seekTo\(0, 0\)/);
  assert.match(result.locator, /data-capability="canShowCorrectness" hidden/);
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
