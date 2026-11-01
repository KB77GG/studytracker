const test = require('node:test');
const assert = require('node:assert/strict');
const weekly = require('../static/js/task_planner_weekly.js');
const series = require('../static/js/task_planner_series.js');

const common = { today: '2026-11-01', name: '听阅周安排', student_id: '7', start_date: '2026-11-02', end_date: '2026-12-01', skip_assigned: true, wait_for_previous: false };
function activity(id, kind, selection = {}) {
  return { id, name: id, kind, selection, source_scopes: ['cambridge:10'], start_resource_id: kind === 'reading_test' ? 'ielts10_test1_reading:all' : 'ielts10_test1:1', planned_minutes: 20, note: '' };
}
const activities = [activity('听力P1', 'listening_test', { section_number: 1 }), activity('阅读P1', 'reading_passage', { passage_number: 1 }), activity('整套听力', 'listening_test', { section_number: null }), activity('整套阅读', 'reading_test')];
function rules() {
  const result = weekly.emptyWeeks();
  result[0][0] = [{ activity_id: '听力P1', quantity: 1 }];
  result[0][3] = [{ activity_id: '阅读P1', quantity: 1 }];
  result[0][5] = [{ activity_id: '整套听力', quantity: 1 }];
  result[0][6] = [{ activity_id: '整套阅读', quantity: 1 }];
  result[1][0] = [{ activity_id: '阅读P1', quantity: 1 }];
  result[1][3] = [{ activity_id: '听力P1', quantity: 1 }];
  result[1][5] = [{ activity_id: '整套阅读', quantity: 1 }];
  result[1][6] = [{ activity_id: '整套听力', quantity: 1 }];
  return result;
}

test('weekly mode carries four distinct content queues and exactly one or two rule weeks', () => {
  const fixed = weekly.buildPayload(common, activities, rules(), 1, series);
  const alternating = weekly.buildPayload(common, activities, rules(), 2, series);
  assert.equal(fixed.kind, 'weekly');
  assert.equal(fixed.week_rules.length, 1);
  assert.equal(alternating.week_rules.length, 2);
  assert.equal(alternating.skip_assigned, true);
  assert.equal(alternating.student_id, 7);
  assert.equal(alternating.activities[3].kind, 'reading_test');
  assert.deepEqual(alternating.activities[3].selection, {});
  assert.equal(alternating.weekday_counts, undefined);
});

test('weekly repeat keeps Monday listening and Thursday reading while weekend full tests alternate', () => {
  const rows = weekly.schedule(common.start_date, '2026-11-15', weekly.normalizedRules(activities, rules(), 1));
  assert.deepEqual(rows.map(row => [row.target_date, row.activity_id]), [
    ['2026-11-02', '听力P1'], ['2026-11-05', '阅读P1'], ['2026-11-07', '整套听力'], ['2026-11-08', '整套阅读'],
    ['2026-11-09', '听力P1'], ['2026-11-12', '阅读P1'], ['2026-11-14', '整套听力'], ['2026-11-15', '整套阅读'],
  ]);
});

test('two-week rotation changes the same weekdays and repeats A after B', () => {
  const rows = weekly.schedule(common.start_date, '2026-11-22', weekly.normalizedRules(activities, rules(), 2));
  assert.equal(rows.find(row => row.target_date === '2026-11-09').activity_id, '阅读P1');
  assert.equal(rows.find(row => row.target_date === '2026-11-14').activity_id, '整套阅读');
  assert.equal(rows.find(row => row.target_date === '2026-11-15').activity_id, '整套听力');
  assert.equal(rows.find(row => row.target_date === '2026-11-16').activity_id, '听力P1');
});

test('midweek starts anchor A to the calendar Monday and never backfill earlier dates', () => {
  assert.equal(weekly.anchor('2026-11-05'), '2026-11-02');
  assert.equal(weekly.anchor('2027-01-01'), '2026-12-28');
  const rows = weekly.schedule('2026-11-05', '2026-11-12', weekly.normalizedRules(activities, rules(), 2));
  assert.equal(rows[0].target_date, '2026-11-05');
  assert.equal(rows.find(row => row.target_date === '2026-11-09').activity_id, '阅读P1');
  assert.throws(() => weekly.anchor('2026-02-30'), /有效开始日期/);
});

test('same-day multiple activities retain deliberate order and independent quantities', () => {
  const configured = rules();
  configured[0][0] = [{ activity_id: '阅读P1', quantity: '2' }, { activity_id: '听力P1', quantity: '1' }];
  const normalized = weekly.normalizedRules(activities, configured, 1);
  assert.deepEqual(weekly.schedule('2026-11-02', '2026-11-02', normalized), [
    { target_date: '2026-11-02', activity_id: '阅读P1', quantity: 2 },
    { target_date: '2026-11-02', activity_id: '听力P1', quantity: 1 },
  ]);
});

test('missing, duplicate and removed activity references cannot be previewed', () => {
  assert.throws(() => weekly.normalizedRules([], rules(), 1), /先加入/);
  assert.throws(() => weekly.normalizedRules([...activities, activities[0]], rules(), 1), /标识重复/);
  const duplicate = rules(); duplicate[0][0].push({ activity_id: '听力P1', quantity: 2 });
  assert.throws(() => weekly.normalizedRules(activities, duplicate, 1), /同一天/);
  const missing = rules(); missing[0][0][0].activity_id = '已删除';
  assert.throws(() => weekly.normalizedRules(activities, missing, 1), /已移除/);
  assert.throws(() => weekly.normalizedRules(activities, rules(), 3), /两周轮换/);
  const unfinished = rules(); unfinished[0][1] = [{ activity_id: '', quantity: 1 }];
  assert.throws(() => weekly.normalizedRules(activities, unfinished, 1), /未选择练习项/);
  const unused = rules(); unused[0][0] = [];
  assert.throws(() => weekly.normalizedRules(activities, unused, 1), /尚未安排到任何星期/);
});

test('rest dates, malformed dates and overlong periods cannot produce an empty or invalid batch', () => {
  const normalized = weekly.normalizedRules(activities, rules(), 1);
  assert.throws(() => weekly.schedule('2026-11-03', '2026-11-04', normalized), /没有练习/);
  assert.throws(() => weekly.schedule('2026-11-02', '2026-12-03', normalized), /1–31天/);
  assert.throws(() => weekly.schedule('2026-11-02', '2026-11-01', normalized), /1–31天/);
  assert.throws(() => weekly.schedule('2026-11-02', '2026-11-32', normalized), /有效结束日期/);
  assert.throws(() => weekly.buildPayload({ ...common, start_date: '2027-02-01', end_date: '2027-02-07' }, activities, rules(), 1, series), /未来90天/);
});

test('word quantities and whole-test quantities have separate bounds', () => {
  const items = [activity('词汇', 'dictation'), activities[0]], configured = weekly.emptyWeeks();
  configured[0][0] = [{ activity_id: '词汇', quantity: 1200 }, { activity_id: '听力P1', quantity: 20 }];
  assert.equal(weekly.normalizedRules(items, configured, 1)[0][0][0].quantity, 1200);
  for (const invalid of [0, -1, 1.5, 'x', 1201]) { configured[0][0][0].quantity = invalid; assert.throws(() => weekly.normalizedRules(items, configured, 1), /1–1200/); }
  configured[0][0][0].quantity = 30; configured[0][0][1].quantity = 21;
  assert.throws(() => weekly.normalizedRules(items, configured, 1), /1–20/);
});

test('removing an activity removes its A/B assignments and preserves unrelated choices without mutating input', () => {
  const before = rules(), removed = weekly.removeActivity(activities, before, '听力P1');
  assert.equal(removed.activities.length, 3);
  assert.deepEqual(removed.week_rules[0][0], []);
  assert.deepEqual(removed.week_rules[1][3], []);
  assert.equal(removed.week_rules[1][0][0].activity_id, '阅读P1');
  assert.equal(before[0][0][0].activity_id, '听力P1');
});

test('explicit listening/reading example only uses the four configured activities without guessing sources', () => {
  assert.deepEqual(weekly.exampleRules(activities), rules());
  assert.equal(weekly.exampleRules(activities.slice(0, 3)), null);
  assert.equal(weekly.exampleRules([...activities, activity('另一听力P1', 'listening_test', { section_number: 1 })]), null);
  assert.equal(weekly.exampleRules(activities.map(item => item.id === '阅读P1' ? { ...item, selection: { passage_number: 2 } } : item)), null);
});

test('empty week creation does not share day arrays across dates or A/B weeks', () => {
  const independent = weekly.emptyWeeks();
  independent[0][0].push({ activity_id: '听力P1', quantity: 1 });
  assert.deepEqual(independent[0][1], []);
  assert.deepEqual(independent[1][0], []);
});

test('stored activity payloads are snapshots and omit editor-only data', () => {
  const original = { ...activities[0], _summary: '教材标签', student_id: 99, weekday_counts: [9] };
  const item = weekly.activityFromPayload('a1', ' 听力 ', original);
  original.selection.section_number = 3;
  assert.equal(item.selection.section_number, 1);
  assert.equal(item.name, '听力');
  assert.equal(item._summary, undefined);
  assert.equal(item.student_id, undefined);
  assert.equal(item.weekday_counts, undefined);
  assert.throws(() => weekly.activityFromPayload('a2', '', original), /练习项名称/);
  original.selection.section_number = 1;
});

test('strict reading Test selection sends no Passage filter and keeps an exact suite starting ID', () => {
  const payload = series.buildPayload({ ...common, kind: 'reading_test', weekday_counts: [0, 0, 0, 0, 0, 0, 1], planned_minutes: 20, source_scopes: ['cambridge:10'], start_resource_id: 'ielts10_test1_reading:all', passage_number: 2 });
  assert.deepEqual(payload.selection, {});
  assert.equal(series.kindUnit('reading_test'), '套');
  const query = new URLSearchParams(series.sequenceQuery({ kind: 'reading_test', source_scopes: ['cambridge:10'], passage_number: 2 }));
  assert.equal(query.has('passage_number'), false);
  assert.equal(query.get('kind'), 'reading_test');
  assert.equal(payload.skip_assigned, true);
});

test('new automatic-skip flag is explicit and absent legacy input stays absent', () => {
  const fields = { ...common, kind: 'listening_test', section_number: 1, weekday_counts: [1, 0, 0, 0, 0, 0, 0], source_scopes: ['cambridge:10'], start_resource_id: 'ielts10_test1:1', planned_minutes: 20 };
  assert.equal(series.buildPayload(fields).skip_assigned, true);
  assert.equal(series.buildPayload({ ...fields, skip_assigned: false }).skip_assigned, false);
  const legacy = { ...fields }; delete legacy.skip_assigned;
  assert.equal(Object.hasOwn(series.buildPayload(legacy), 'skip_assigned'), false);
  assert.throws(() => series.buildPayload({ ...fields, skip_assigned: 'false' }), /自动跳过/);
});

test('weekly summaries show activity-specific quantities while preview avoids summing unlike units', () => {
  const payload = weekly.buildPayload(common, activities, rules(), 2, series);
  const description = weekly.summary(payload, series.kindUnit);
  assert.match(description, /A周：周一 听力P1 × 1篇/);
  assert.match(description, /B周：周一 阅读P1 × 1篇/);
  assert.match(description, /整套阅读 × 1套/);
  const preview = { ...payload, totals: { days: 4, units: 33 }, rows: Array(8).fill({}) };
  assert.match(series.previewSummary(preview), /4个学习日 · 8次任务/);
  assert.doesNotMatch(series.previewSummary(preview), /共33/);
});

test('changing weekly rules invalidates saved-preview payload just like changing a single sequence', () => {
  const first = weekly.buildPayload(common, activities, rules(), 1, series);
  const draft = series.createDraftSession(() => 'weekly-request-123456');
  const ticket = draft.begin(first); draft.accept(ticket, { preview_hash: 'hash-1' });
  const modifiedRules = rules(); modifiedRules[0][0][0].quantity = 2;
  const second = weekly.buildPayload(common, activities, modifiedRules, 1, series);
  assert.throws(() => draft.writePayload(second), /重新预览/);
  assert.equal(draft.writePayload(first).preview_hash, 'hash-1');
});
