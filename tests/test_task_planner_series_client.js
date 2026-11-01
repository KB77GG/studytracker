const test = require('node:test');
const assert = require('node:assert/strict');
const series = require('../static/js/task_planner_series.js');

function fields(changes = {}) {
  return Object.assign({ name: ' 阅读练习 ', student_id: '7', kind: 'question_type', start_date: '2026-11-02', end_date: '2026-11-08', weekday_counts: ['1', '1', '1', '1', '1', '2', '2'], planned_minutes: '20', subject: 'reading', standard_type: 'all', pace: 'training', source_scope: 'cambridge:10', start_group_id: 'first-group', wait_for_previous: false, note: '' }, changes);
}

test('7-day and 30-day presets include the start day across month/year/leap boundaries', () => {
  assert.equal(series.periodEnd('2026-10-31', 7), '2026-11-06');
  assert.equal(series.periodEnd('2026-12-20', 30), '2027-01-18');
  assert.equal(series.periodEnd('2024-02-28', 3), '2024-03-01');
  assert.equal(series.periodEnd('2026-11-01', 1), '2026-11-01');
  assert.throws(() => series.periodEnd('2026-02-30', 7), /有效日期/);
  assert.throws(() => series.periodEnd('2026-11-01', 32), /1–31天/);
});

test('date controls allow starts up to today plus 90 and clamp the end to both limits', () => {
  assert.deepEqual(series.dateBounds('2026-10-31', '2026-12-01'), { start_min: '2026-10-31', start_max: '2027-01-29', end_min: '2026-12-01', end_max: '2026-12-31' });
  assert.deepEqual(series.dateBounds('2026-10-31', '2027-01-20'), { start_min: '2026-10-31', start_max: '2027-01-29', end_min: '2027-01-20', end_max: '2027-01-29' });
  assert.equal(series.dateBounds('2024-01-01', '2024-03-30').start_max, '2024-03-31');
  assert.equal(series.dateBounds('2026-10-31', '2027-01-29').end_max, '2027-01-29');
});

test('7-day and 30-day presets cannot silently run past the 90-day scheduling window', () => {
  const today = '2026-10-31';
  assert.doesNotThrow(() => series.validateDateWindow(today, '2027-01-23', series.periodEnd('2027-01-23', 7)));
  assert.throws(() => series.validateDateWindow(today, '2027-01-24', series.periodEnd('2027-01-24', 7)), /未来90天/);
  assert.doesNotThrow(() => series.validateDateWindow(today, '2026-12-31', series.periodEnd('2026-12-31', 30)));
  assert.throws(() => series.validateDateWindow(today, '2027-01-01', series.periodEnd('2027-01-01', 30)), /缩短安排时间/);
  assert.throws(() => series.validateDateWindow(today, '2026-10-30', '2026-11-05'), /未来90天/);
});

test('preview and save payload validation checks the same inclusive 90-day bounds', () => {
  const finalDay = fields({ today: '2026-10-31', start_date: '2027-01-29', end_date: '2027-01-29' });
  assert.equal(series.buildPayload(finalDay).start_date, '2027-01-29');
  assert.equal(series.buildPayload(finalDay).today, undefined);
  assert.throws(() => series.buildPayload(Object.assign({}, finalDay, { end_date: '2027-01-30' })), /未来90天/);
  assert.throws(() => series.buildPayload(Object.assign({}, finalDay, { start_date: '2027-01-30', end_date: '2027-01-30' })), /未来90天/);
});

test('Monday-first quotas follow calendar dates and share one finite queue', () => {
  const rows = series.scheduleDays('2026-10-31', '2026-11-06', [1, 0, 1, 0, 1, 2, 3], 'question_type');
  assert.deepEqual(rows, [
    { target_date: '2026-10-31', unit_count: 2 },
    { target_date: '2026-11-01', unit_count: 3 },
    { target_date: '2026-11-02', unit_count: 1 },
    { target_date: '2026-11-04', unit_count: 1 },
    { target_date: '2026-11-06', unit_count: 1 }
  ]);
});

test('rest-only ranges, incomplete quotas, fractions and out-of-bounds volumes cannot preview', () => {
  const run = (start, end, quotas, kind = 'question_type') => series.scheduleDays(start, end, quotas, kind);
  assert.throws(() => run('2026-11-07', '2026-11-08', [1, 1, 1, 1, 1, 0, 0]), /至少安排一天/);
  for (const bad of [-1, 1.5, 21, '', 'x']) assert.throws(() => run('2026-11-02', '2026-11-08', [bad, 1, 1, 1, 1, 1, 1]), /整数配额/);
  assert.throws(() => run('2026-11-02', '2026-11-08', [1]), /整数配额/);
  assert.throws(() => run('2026-11-02', '2026-12-03', [1, 1, 1, 1, 1, 1, 1]), /最多31天/);
  assert.throws(() => run('2026-11-02', '2026-11-01', [1, 1, 1, 1, 1, 1, 1]), /结束日期/);
  assert.equal(run('2026-11-02', '2026-11-02', [1200, 0, 0, 0, 0, 0, 0], 'dictation')[0].unit_count, 1200);
  assert.throws(() => run('2026-11-02', '2026-11-02', [1201, 0, 0, 0, 0, 0, 0], 'dictation'), /1200/);
});

test('question practice preview requires an exact source and first group without guessed IDs', () => {
  const payload = series.buildPayload(fields());
  assert.deepEqual(payload.selection, { subject: 'reading', standard_type: 'all', pace: 'training' });
  assert.equal(payload.name, '阅读练习');
  assert.equal(payload.student_id, 7);
  assert.equal(payload.source_scope, 'cambridge:10');
  assert.equal(payload.start_group_id, 'first-group');
  assert.deepEqual(payload.weekday_counts, [1, 1, 1, 1, 1, 2, 2]);
  assert.equal(payload.wait_for_previous, false);
  assert.throws(() => series.buildPayload(fields({ source_scope: '' })), /教材/);
  assert.throws(() => series.buildPayload(fields({ start_group_id: '' })), /起始题组/);
  assert.throws(() => series.buildPayload(fields({ kind: 'unknown' })), /支持连续安排/);
});

function sequenceFields(kind, changes = {}) {
  return fields(Object.assign({ kind, source_scopes: ['cambridge:11', 'cambridge:10'], start_resource_id: 'first-resource', section_number: '', passage_number: '', training_mode: 'system' }, changes));
}

test('whole listening and fixed Parts retain exact filters and explicit multiple sources', () => {
  const original = sequenceFields('listening_test');
  const whole = series.buildPayload(original);
  assert.deepEqual(whole.selection, { section_number: null });
  assert.deepEqual(whole.source_scopes, ['cambridge:10', 'cambridge:11']);
  assert.equal(whole.start_resource_id, 'first-resource');
  assert.equal(whole.source_scope, undefined);
  assert.equal(whole.start_group_id, undefined);
  assert.deepEqual(original.source_scopes, ['cambridge:11', 'cambridge:10']);
  for (const section_number of ['1', 4]) assert.deepEqual(series.buildPayload(sequenceFields('listening_test', { section_number })).selection, { section_number: Number(section_number) });
  for (const section_number of [0, 5, 1.5, 'invalid']) assert.throws(() => series.buildPayload(sequenceFields('listening_test', { section_number })), /Part 1–4/);
});

test('reading can advance through all passages or remain on a chosen Passage number', () => {
  assert.deepEqual(series.buildPayload(sequenceFields('reading_passage')).selection, { passage_number: null });
  for (const passage_number of ['1', 3]) assert.deepEqual(series.buildPayload(sequenceFields('reading_passage', { passage_number })).selection, { passage_number: Number(passage_number) });
  for (const passage_number of [0, 4, 1.5, 'invalid']) assert.throws(() => series.buildPayload(sequenceFields('reading_passage', { passage_number })), /Passage 1–3/);
});

test('intensive listening preserves the training mode for all Parts and fixed Parts', () => {
  assert.deepEqual(series.buildPayload(sequenceFields('intensive', { training_mode: '' })).selection, { section_number: null, training_mode: 'system' });
  assert.deepEqual(series.buildPayload(sequenceFields('intensive', { section_number: '2', training_mode: 'challenge' })).selection, { section_number: 2, training_mode: 'challenge' });
});

test('resource sequences cannot preview without explicit sources and an exact starting resource', () => {
  for (const kind of ['listening_test', 'reading_passage', 'intensive']) {
    assert.throws(() => series.buildPayload(sequenceFields(kind, { source_scopes: [] })), /教材和起始内容/);
    assert.throws(() => series.buildPayload(sequenceFields(kind, { start_resource_id: '' })), /教材和起始内容/);
    assert.throws(() => series.buildPayload(sequenceFields(kind, { source_scopes: [''] })), /明确选择教材/);
    assert.throws(() => series.buildPayload(sequenceFields(kind, { source_scopes: 'cambridge:10' })), /明确选择教材/);
    assert.throws(() => series.buildPayload(sequenceFields(kind, { weekday_counts: [21, 1, 1, 1, 1, 1, 1] })), /0–20/);
    const payload = series.buildPayload(sequenceFields(kind, { source_scopes: ['cambridge:10', 'cambridge:10'], weekday_counts: [20, 0, 0, 0, 0, 0, 0] }));
    assert.deepEqual(payload.source_scopes, ['cambridge:10']);
  }
});

test('sequence discovery uses repeated source_scope keys and empty filters for all content', () => {
  const listening = new URLSearchParams(series.sequenceQuery(sequenceFields('listening_test')));
  assert.deepEqual(listening.getAll('source_scope'), ['cambridge:10', 'cambridge:11']);
  assert.equal(listening.get('section_number'), '');
  assert.equal(listening.get('kind'), 'listening_test');
  const reading = new URLSearchParams(series.sequenceQuery(sequenceFields('reading_passage', { passage_number: '3', source_scopes: [] })));
  assert.equal(reading.get('passage_number'), '3');
  assert.equal(reading.has('section_number'), false);
  assert.deepEqual(reading.getAll('source_scope'), []);
  const intensive = new URLSearchParams(series.sequenceQuery(sequenceFields('intensive', { section_number: '1', training_mode: 'review' })));
  assert.equal(intensive.get('section_number'), '1');
  assert.equal(intensive.get('training_mode'), 'review');
  assert.throws(() => series.sequenceQuery(fields()), /听力、阅读整篇或精听/);
});

test('quota units match words, groups, whole tests and individual passages', () => {
  assert.equal(series.kindUnit('dictation'), '词');
  assert.equal(series.kindUnit('question_type'), '组');
  assert.equal(series.kindUnit('listening_test', { section_number: null }), '套');
  assert.equal(series.kindUnit('listening_test', { section_number: 1 }), '篇');
  assert.equal(series.kindUnit('reading_passage'), '篇');
  assert.equal(series.kindUnit('intensive'), '篇');
  assert.match(series.quotaSummary([1, 1, 1, 1, 1, 2, 0], 'listening_test', '篇'), /周六 2篇 · 周日 休息/);
});

test('daily preview summaries distinguish multiple same-day tasks from learning days', () => {
  const preview = { start_date: '2026-11-02', end_date: '2026-11-03', kind: 'reading_passage', quota_unit: '篇', totals: { days: 2, units: 3 }, rows: [{ target_date: '2026-11-02', unit_count: 1 }, { target_date: '2026-11-02', unit_count: 1 }, { target_date: '2026-11-03', unit_count: 1 }] };
  assert.match(series.previewSummary(preview), /2个学习日 · 3次任务 · 共3篇/);
  assert.match(series.previewSummary(Object.assign({}, preview, { kind: 'listening_test', quota_unit: '套' })), /共3套/);
});

test('changing selected books, fixed Part or intensive mode makes the accepted preview unusable', () => {
  const session = series.createDraftSession(() => 'test-key');
  const base = series.buildPayload(sequenceFields('intensive'));
  session.accept(session.begin(base), { preview_hash: 'prepared' });
  for (const change of [{ source_scopes: ['cambridge:12'] }, { section_number: '2' }, { training_mode: 'review' }, { start_resource_id: 'next-resource' }]) {
    assert.throws(() => session.writePayload(series.buildPayload(sequenceFields('intensive', change))), /重新预览/);
  }
  assert.equal(session.writePayload(series.buildPayload(sequenceFields('intensive', { source_scopes: ['cambridge:10', 'cambridge:11'] }))).preview_hash, 'prepared');
});

test('vocabulary payload uses a first word and lets the preview determine every end word', () => {
  const original = fields({ kind: 'dictation', book_id: '12', word_start: '21', vocabulary_goal: 'listening', weekday_counts: [20, 20, 20, 20, 20, 40, 40], wait_for_previous: true });
  const payload = series.buildPayload(original);
  assert.deepEqual(payload.selection, { book_id: 12, word_start: 21, vocabulary_goal: 'listening', dictation_mode: 'audio_to_en', dictation_order: 'sequence' });
  assert.equal(payload.wait_for_previous, true);
  assert.equal(payload.source_scope, undefined);
  assert.equal(payload.start_group_id, undefined);
  assert.equal(original.word_start, '21');
  assert.throws(() => series.buildPayload(Object.assign({}, original, { word_start: 0 })), /正整数/);
  assert.throws(() => series.buildPayload(Object.assign({}, original, { book_id: '' })), /请选择词书/);
});

test('the preview submission must have a student, a name and a bounded whole-number duration', () => {
  assert.throws(() => series.buildPayload(fields({ student_id: '' })), /学生/);
  assert.throws(() => series.buildPayload(fields({ name: '   ' })), /命名/);
  for (const value of [0, 181, 1.5, '']) assert.throws(() => series.buildPayload(fields({ planned_minutes: value })), /1–180分钟/);
});

test('failed saves keep one idempotency key and a retry carries the accepted preview hash', () => {
  let keys = 0;
  const session = series.createDraftSession(() => 'request-' + ++keys);
  const payload = series.buildPayload(fields());
  assert.throws(() => session.writePayload(payload), /重新预览/);
  assert.equal(session.accept(session.begin(payload), { preview_hash: 'hash-one' }), true);
  const first = session.writePayload(payload);
  const retry = session.writePayload(payload);
  assert.deepEqual(retry, first);
  assert.equal(retry.request_key, 'request-1');
  assert.equal(retry.preview_hash, 'hash-one');
  assert.equal(keys, 1);
  assert.equal(payload.request_key, undefined);
});

test('editing inputs rejects stale preview responses and prevents saving the previous contents', () => {
  let keys = 0;
  const session = series.createDraftSession(() => 'request-' + ++keys);
  const payload = series.buildPayload(fields());
  const stale = session.begin(payload);
  session.invalidate();
  assert.equal(session.accept(stale, { preview_hash: 'stale' }), false);
  assert.throws(() => session.writePayload(payload), /重新预览/);
  const changed = Object.assign({}, payload, { name: 'Changed' });
  const fresh = session.begin(changed);
  assert.equal(session.accept(fresh, { preview_hash: 'fresh' }), true);
  assert.equal(session.writePayload(changed).request_key, 'request-2');
  assert.throws(() => session.writePayload(payload), /重新预览/);
  session.reset();
  assert.throws(() => session.writePayload(changed), /重新预览/);
});

test('re-previewing identical content keeps a retry key; a changed resource hash gets a fresh key', () => {
  let keys = 0;
  const session = series.createDraftSession(() => 'request-' + ++keys);
  const payload = series.buildPayload(fields());
  session.accept(session.begin(payload), { preview_hash: 'one' });
  session.invalidate();
  session.accept(session.begin(payload), { preview_hash: 'one' });
  assert.equal(session.writePayload(payload).request_key, 'request-1');
  assert.equal(keys, 1);
  session.invalidate();
  session.accept(session.begin(payload), { preview_hash: 'two' });
  const retry = session.writePayload(payload);
  assert.equal(keys, 2);
  assert.equal(retry.request_key, 'request-2');
  assert.equal(retry.preview_hash, 'two');
});

test('weekly summary explicitly distinguishes rests, groups and words', () => {
  assert.equal(series.quotaSummary([1, 1, 1, 1, 1, 2, 0], 'question_type'), '周一 1组 · 周二 1组 · 周三 1组 · 周四 1组 · 周五 1组 · 周六 2组 · 周日 休息');
  assert.match(series.quotaSummary([10, 10, 10, 10, 10, 20, 20], 'dictation'), /周六 20词/);
});

test('split vocabulary books sort by numeric Day and chapter while preserving a stable ID tie', () => {
  const books = [
    { id: 10, label: '四级单词 Day10' }, { id: 2, label: '四级单词 Day2' },
    { id: 1, label: '四级单词 Day1' }, { id: 8, label: 'WL库 1-10' },
    { id: 9, label: 'wl库 1-2' }, { id: 7, label: 'WL库 1-2' },
    { id: 21, label: 'Upper Intermediate 10' }, { id: 20, label: 'Upper Intermediate 2' }
  ];
  const before = JSON.stringify(books);
  assert.deepEqual(series.orderedBooks(books).map(book => book.id), [20, 21, 7, 9, 8, 1, 2, 10]);
  assert.equal(JSON.stringify(books), before);
});

test('search only filters available vocabulary choices and never adds hidden or same-prefix books', () => {
  const books = [
    { id: 10, label: '四级单词 Day10' }, { id: 2, label: '四级单词 Day2' },
    { id: 1, label: '四级单词 Day1' }, { id: 9, label: 'WL库 1-2' }
  ];
  const result = series.vocabularyChoices(books, ['10', '1', '9'], '1', '四级');
  assert.deepEqual(result.visible.map(book => book.id), [1, 2, 10]);
  assert.deepEqual(result.selected.map(book => book.id), [9, 1, 10]);
  assert.equal(result.start_id, '1');
  assert.deepEqual(series.vocabularyChoices(books, [], '', '四级').selected, []);
  assert.equal(series.vocabularyChoices(books, ['1'], '1', ' WL ').visible[0].id, 9);
});

test('removing a selected or unavailable starting book clears the start without silently changing it', () => {
  const books = [{ id: 2, label: 'Day2' }, { id: 10, label: 'Day10' }];
  assert.equal(series.vocabularyChoices(books, ['2', '10'], '2').start_id, '2');
  assert.equal(series.vocabularyChoices(books, ['10'], '2').start_id, '');
  const unavailable = series.vocabularyChoices(books, ['1', '10'], '1');
  assert.equal(unavailable.start_id, '');
  assert.deepEqual(unavailable.selected.map(book => book.id), [10]);
  assert.deepEqual(series.vocabularyChoices(books, [], '10').selected, []);
});

function vocabularyFields(changes = {}) {
  return fields(Object.assign({ kind: 'dictation', book_id: '2', book_ids: ['2', '10'], word_start: '41', vocabulary_goal: 'reading' }, changes));
}

test('multiple vocabulary books carry explicit IDs and a per-book starting sequence; legacy requests stay unchanged', () => {
  const payload = series.buildPayload(vocabularyFields());
  assert.deepEqual(payload.selection, { book_id: 2, word_start: 41, vocabulary_goal: 'reading', dictation_mode: 'audio_to_en', dictation_order: 'sequence', book_ids: [2, 10] });
  assert.equal(payload.selection.word_end, undefined);
  const legacy = series.buildPayload(vocabularyFields({ book_ids: undefined }));
  assert.equal(Object.hasOwn(legacy.selection, 'book_ids'), false);
  assert.equal(legacy.selection.book_id, 2);
  assert.deepEqual(series.buildPayload(vocabularyFields({ book_ids: ['2'] })).selection.book_ids, [2]);
});

test('invalid, duplicate or missing vocabulary scope cannot be previewed', () => {
  for (const book_ids of [[], null, '2', [2, '02'], [true], [-2], [2.5], ['bad'], Array.from({ length: 101 }, (_, i) => i + 1)]) {
    assert.throws(() => series.buildPayload(vocabularyFields({ book_ids })), /分册/);
  }
  assert.throws(() => series.buildPayload(vocabularyFields({ book_ids: [10] })), /起始分册/);
});

test('changed vocabulary selections or starting position cannot save an earlier preview', () => {
  let keys = 0;
  const session = series.createDraftSession(() => 'request-' + ++keys);
  const payload = series.buildPayload(vocabularyFields());
  session.accept(session.begin(payload), { preview_hash: 'multi-book-preview' });
  for (const changes of [{ book_ids: [2] }, { book_id: 10 }, { word_start: 42 }]) {
    assert.throws(() => session.writePayload(series.buildPayload(vocabularyFields(changes))), /重新预览/);
  }
  session.invalidate();
  const oldTicket = session.begin(payload);
  session.invalidate();
  assert.equal(session.accept(oldTicket, { preview_hash: 'stale-response' }), false);
});

test('cross-book days count the combined word quota while showing separate tasks', () => {
  assert.equal(series.previewSummary({ kind: 'dictation', start_date: '2026-11-02', end_date: '2026-11-03', totals: { days: 2, units: 60 }, rows: [{ unit_count: 10 }, { unit_count: 20 }, { unit_count: 30 }] }), '2026-11-02 至 2026-11-03 · 2个学习日 · 3次任务 · 共60词；休息日不生成任务。');
});
