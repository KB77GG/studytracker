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

test('review focus resolves a displayed question number and plays its verified clip', () => {
  const runtime = reviewRuntime();
  vm.runInContext(`openReviewCard('7', true, true)`, runtime);

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
