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
  assert.throws(() => series.buildPayload(fields({ kind: 'listening_test' })), /目前支持题型和词汇/);
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
