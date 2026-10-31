const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const ROOT = process.env.STUDYTRACKER_ROOT || path.resolve(__dirname, '..');
const source = fs.readFileSync(process.env.PLAYER_REDO_TEMPLATE || path.join(ROOT, 'templates/listening/player.html'), 'utf8');
const ListeningCloze = require(path.join(ROOT, 'static/js/listening-cloze.js'));
function extract(start, end) {
  const a = source.indexOf(`  function ${start}`);
  const b = source.indexOf(`  function ${end}`, a);
  assert.ok(a >= 0 && b > a);
  return source.slice(a, b);
}
function runtime(options = {}) {
  const rows = { '4': { is_completed: true, answers_json: ['original'], accuracy: 50 } };
  const store = new Map();
  const events = [];
  const context = {
    taskId: options.taskId || '', taskReadOnly: !!options.readOnly,
    taskTrainingPolicy: { review_only: !!options.reviewOnly },
    data: { parts: [] }, practiceRedoState: null, mode: 'sentence',
    firstAttemptGates: new Map(), pendingFirstAttempts: new Map(),
    dictationStartedSegments: new Set(['9']), correctionSegments: new Set(),
    dictationDrafts: new Map([['9:standard', ['draft']]]), dictationLevelsBySegment: new Map(),
    reviewListenedSegments: new Set([4]), showOriginal: true, showTranslation: true,
    currentDictationContext: null, dictationLevel: 'standard', errorSummaryDirty: true,
    getFreeProgressStorageKey: () => 'free:exercise:owner',
    getActiveProgressMap: () => rows,
    getSegmentLocations: () => [{ globalIndex: 4, partIndex: 0, segmentIndex: 0, seg: { text: 'original text' } }, { globalIndex: 9, partIndex: 1, segmentIndex: 0, seg: { text: 'new text' } }],
    getPracticeText: seg => seg.text,
    getEffectiveProgress: (progress, key) => progress[key] || null,
    dictationStateKey: id => String(id), dictationDraftKey: (id, level) => `${id}:${level}`,
    getFirstAttemptGate(id, saved) {
      if (!context.firstAttemptGates.has(String(id))) context.firstAttemptGates.set(String(id), ListeningCloze.createFirstAttemptGate(saved));
      return context.firstAttemptGates.get(String(id));
    },
    clearFreeDictationTransientState() {
      ListeningCloze.clearFreePracticeTransientState(context, !!context.taskId);
    },
    localStorage: {
      getItem: key => store.get(key) || null,
      setItem(key, value) { if (options.storageFailure) throw Error('unavailable'); store.set(key, value); }
    },
    practiceShellController: { setStatus: value => events.push(value), markSaved: () => events.push('saved') },
    audio: { pause: () => events.push('pause') },
    stopAutoRepeat: () => events.push('stop-repeat'), stopSegmentBoundaryMonitor: () => events.push('stop-monitor'),
    updatePlayBtn: value => events.push(['playing', value]),
    document: { getElementById: () => ({ value: options.value || 'new draft', classList: { remove() {} } }), querySelectorAll: () => [{ value: options.value || 'new draft' }] },
    confirm: () => options.confirm !== false, alert: value => events.push(value),
    persistCurrentErrorSummary: () => events.push('notes-saved'),
    selectSegmentLocation: location => events.push(['select', location.globalIndex]),
    freezeDictationLevel() {},
    rows, events, store, ListeningCloze,
  };
  vm.createContext(context);
  vm.runInContext(extract('getPracticeRedoStorageKey()', 'getSegmentSourceIndex('), context);
  vm.runInContext(extract('saveCurrentDictationDraft()', 'startCurrentDictation()'), context);
  return context;
}
for (const taskId of ['', 'task-7']) {
  test(`redo retains historical answers, closes saved gates, permits untouched first attempt: ${taskId || 'free'}`, () => {
    const r = runtime({ taskId });
    const history = JSON.stringify(r.rows);
    vm.runInContext('redoPractice()', r);
    assert.equal(JSON.stringify(r.rows), history);
    assert.equal(r.firstAttemptGates.get('4').beginFirstAttempt(), false);
    assert.equal(r.firstAttemptGates.get('4').canPost(), false);
    assert.equal(r.correctionSegments.has('4'), true);
    assert.equal(r.correctionSegments.has('9'), false);
    assert.equal(r.getFirstAttemptGate(9, false).beginFirstAttempt(), true);
    assert.equal(r.dictationDrafts.size, 0);
    assert.equal(r.showOriginal, false);
    assert.equal(r.showTranslation, false);
    assert.equal(r.mode, 'dictation');
    assert.deepEqual(r.events.find(e => Array.isArray(e) && e[0] === 'select'), ['select', 4]);
    assert.ok(r.events.includes('pause'));
    assert.ok(r.events.includes('notes-saved'));
  });
}
test('new round correction drafts survive reload without restoring original answers', () => {
  const r = runtime({ taskId: 'task-7', value: 'new draft' });
  vm.runInContext('redoPractice()', r);
  r.currentDictationContext = { segGlobalIdx: 4, level: 'standard', savedProgress: r.rows['4'], correction: true };
  vm.runInContext('saveCurrentDictationDraft()', r);
  r.dictationDrafts.clear(); r.correctionSegments.clear(); r.practiceRedoState = null;
  vm.runInContext('restorePracticeRedoState()', r);
  assert.equal(r.correctionSegments.has('4'), true);
  assert.deepEqual(Array.from(r.dictationDrafts.get('4:standard')), ['new draft']);
  assert.deepEqual(r.rows['4'].answers_json, ['original']);
});
test('read-only and cancellation preserve every input and stored record', () => {
  for (const options of [{ readOnly: true }, { confirm: false }]) {
    const r = runtime(options);
    vm.runInContext('redoPractice()', r);
    assert.equal(r.store.size, 0);
    assert.deepEqual(Array.from(r.dictationDrafts.get('9:standard')), ['draft']);
    assert.equal(r.events.length, 0);
  }
});
test('in-flight or uncertain first attempt cannot be cleared', () => {
  for (const uncertain of [false, true]) {
    const r = runtime({ taskId: 'task-7' });
    if (uncertain) r.pendingFirstAttempts.set('9', {});
    else r.getFirstAttemptGate(9, false).beginFirstAttempt();
    vm.runInContext('redoPractice()', r);
    assert.equal(r.store.size, 0);
    assert.deepEqual(Array.from(r.dictationDrafts.get('9:standard')), ['draft']);
    assert.match(r.events[0], /首答正在保存/);
  }
});
test('storage failure preserves current answers rather than silently resetting', () => {
  const r = runtime({ storageFailure: true });
  vm.runInContext('redoPractice()', r);
  assert.equal(r.store.size, 0);
  assert.deepEqual(Array.from(r.dictationDrafts.get('9:standard')), ['draft']);
  assert.ok(!r.events.includes('pause'));
});
test('listening-only review remains listening-only after redo', () => {
  const r = runtime({ taskId: 'task-7', reviewOnly: true });
  vm.runInContext('redoPractice()', r);
  assert.equal(r.mode, 'sentence');
  assert.equal(r.correctionSegments.size, 0);
  assert.equal(r.reviewListenedSegments.size, 0);
  assert.deepEqual(r.rows['4'].answers_json, ['original']);
});
test('selected redo difficulty and its draft survive refresh together', () => {
  const r = runtime({ taskId: 'task-7', value: 'challenge draft' });
  vm.runInContext('redoPractice()', r);
  r.currentDictationContext = { segGlobalIdx: 4, level: 'challenge', savedProgress: r.rows['4'], correction: true };
  r.dictationLevelsBySegment.set('4', 'challenge');
  vm.runInContext('saveCurrentDictationDraft()', r);
  r.dictationLevelsBySegment.clear(); r.dictationDrafts.clear(); r.practiceRedoState = null;
  vm.runInContext('restorePracticeRedoState()', r);
  assert.equal(r.dictationLevelsBySegment.get('4'), 'challenge');
  assert.deepEqual(Array.from(r.dictationDrafts.get('4:challenge')), ['challenge draft']);
});
test('submitting redo correction grades locally without posting or changing first answer', () => {
  const r = runtime({ taskId: 'task-7', value: 'original' });
  vm.runInContext('redoPractice()', r);
  const history = JSON.stringify(r.rows);
  r.currentDictationContext = {
    segGlobalIdx: 4, level: 'standard', savedProgress: r.rows['4'], correction: true,
    expected: ['original'], sourceText: 'original', hiddenIndices: [0],
  };
  r.applyDictationGrade = (_context, grade, options) => r.events.push({ grade, options });
  r.fetch = () => { throw Error('Redo must not POST a first attempt'); };
  vm.runInContext(extract('checkDictation()', 'updateAudioProgressDisplay()'), r);
  vm.runInContext('checkDictation()', r);
  assert.equal(JSON.stringify(r.rows), history);
  const graded = r.events.find(event => event && event.grade);
  assert.equal(graded.grade.accuracy, 100);
  assert.equal(graded.options.correction, true);
});
test('inline player scripts remain valid JavaScript', () => {
  const blocks = [...source.matchAll(/<script>([\s\S]*?)<\/script>/g)].map(match => match[1]);
  assert.ok(blocks.length > 0);
  blocks.forEach(block => new vm.Script(block));
});
