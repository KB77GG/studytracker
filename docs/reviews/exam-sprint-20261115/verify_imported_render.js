/* Execute the actual practice renderers on imported JSON, without a browser. */
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');

const root = path.resolve(__dirname, '../../..');
const PracticeTable = require(path.join(root, 'static/js/practice_table.js'));
const PracticeRenderers = require(path.join(root, 'static/js/practice_renderers.js'));
const PracticeScoring = require(path.join(root, 'static/js/practice_scoring.js'));
const documents = JSON.parse(fs.readFileSync(0, 'utf8'));
let questionCount = 0;
let placeholderCount = 0;
let imageCount = 0;
let exactLongIds = 0;
const contexts = {};
for (const subject of ['reading', 'listening']) {
  const name = subject === 'reading' ? 'test_practice.html' : 'jijing_part.html';
  const source = fs.readFileSync(path.join(root, 'templates', subject, name), 'utf8');
  const start = source.indexOf('function escapeHtml(');
  const stop = source.indexOf(subject === 'reading' ? '\nfunction renderPassage(' : '\nfunction unitValue(', start);
  assert.ok(start > 0 && stop > start);
  const context = {
    PracticeTable, PracticeRenderers, PracticeScoring,
    answers: {}, testData: {},
    experienceCapabilities: { simulationMode: false, canShowCorrectness: false },
  };
  vm.createContext(context);
  if (subject === 'listening') {
    const mediaGuard = source.match(/^const isSprintAsset = .+;$/m);
    assert.ok(mediaGuard, 'The actual local asset guard is present');
    vm.runInContext(mediaGuard[0], context);
  }
  vm.runInContext(source.slice(start, stop), context);
  contexts[subject] = context;
}

for (const document of documents) {
  const { subject, payload } = document;
  const runtime = contexts[subject];
  runtime.testData = payload;
  const groups = subject === 'reading'
    ? payload.passages.flatMap(passage => passage.groups || [])
    : payload.groups;
  for (const group of groups) {
    const questions = group[subject === 'reading' ? 'questions' : 'items'];
    for (const question of questions) {
      if (payload.source === 'ninefen') {
        assert.equal(typeof question.id, 'string', 'Source IDs must survive tojson/JSON.parse as strings');
        assert.equal(question.id, question.source_question_id);
        if (question.id.length > 15) exactLongIds += 1;
      }
      questionCount += 1;
    }
    const html = runtime.renderGroup(group);
    const ids = [...new Set([...String(group.collect || '').matchAll(/\$([^$\s]+)\$/g)].map(match => match[1]))];
    if (ids.length) {
      const context = { seenIds: new Set() };
      const replacement = subject === 'reading'
        ? runtime.replacePlaceholders(group.collect, group, context, true)
        : runtime.renderWithPlaceholders(group.collect, group, context, true);
      for (const id of ids) {
        assert.ok(context.seenIds.has(id), `${payload.id}: placeholder ${id} retained exact identity`);
        assert.ok(!replacement.includes(`$${id}$`), `${payload.id}: placeholder was replaced`);
        placeholderCount += 1;
      }
    }
    if (subject === 'reading') {
      for (const question of questions) {
        assert.ok(html.includes(`data-qid="${question.id}"`), `${payload.id}: answer control for ${question.id}`);
      }
    } else if (runtime.isCombinedMulti(group)) {
      assert.ok(html.includes('data-kind="checkbox-set"'));
      assert.ok(html.includes(`data-marks="${questions.length}"`));
      assert.ok(html.includes(`data-q="${runtime.escapeHtml(group.desc)}"`));
    } else {
      for (const question of questions) {
        assert.ok(html.includes(`data-q="${runtime.escapeHtml(question.number)}"`), `${payload.id}: listening answer control ${question.number}`);
      }
    }
    if (group.img_url && group.img_url.startsWith('/practice/sprint/assets/')) {
      assert.ok(html.includes(group.img_url), `${payload.id}: source diagram is visible`);
      imageCount += 1;
    }
  }
}
process.stdout.write(JSON.stringify({ documents: documents.length, questions: questionCount,
  placeholders_replaced: placeholderCount, exact_long_question_ids: exactLongIds,
  diagrams_rendered: imageCount, passed: true }) + '\n');
