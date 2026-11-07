'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const { templateRuntime, controls } = require('./helpers/practice_template_runtime.js');
const renderers = require('../static/js/practice_renderers.js');
const root = path.resolve(__dirname, '..');
const fixture = (subject, name) => JSON.parse(fs.readFileSync(path.join(root, 'static', `${subject}_tests`, `${name}.json`)));
const units = (subject, payload) => payload[subject === 'listening' ? 'sections' : 'passages'];
const find = (subject, payload, number) => units(subject, payload).flatMap(unit => unit.groups).find(group => group.questions.some(q => q.number === number));

test('all 144 Cambridge papers render every logical answer exactly once with its displayed number and no raw markers', () => {
  for (const subject of ['reading', 'listening']) {
    let questions = 0;
    for (const filename of fs.readdirSync(path.join(root, 'static', `${subject}_tests`)).filter(name => /^ielts\d+_test\d+(?:_reading)?\.json$/.test(name))) {
      const payload = fixture(subject, filename.replace('.json', ''));
      const context = templateRuntime(subject, payload);
      for (const unit of units(subject, payload)) for (const group of unit.groups) {
        const html = context.renderGroup(group, 0);
        const actual = controls(html, subject);
        assert.deepEqual(actual.flatMap(control => control.id.split(',')).sort(), group.questions.map(q => String(q.id)).sort(), filename);
        for (const control of actual) if (control.number) assert.deepEqual(control.number.split(','), control.id.split(',').map(id => String(group.questions.find(q => String(q.id) === id).number)), filename);
        assert.doesNotMatch(html, /\$\d+\$|【\s*\d+\s*】/, filename);
        const words = text => renderers.plainText(String(text || '').replace(/>\s*</g, '> <')).replace(/\$\d+\$/g, ' ').toLowerCase().match(/[a-z]{3,}/g) || [];
        const visible = new Set(words(html));
        // The reviewed C6 T2 Q40 title corrects these OCR errors in legacy collect.
        const collect = filename === 'ielts6_test2.json' ? String(group.collect || '').replace('The Lighis ofNew York', 'The Lights of New York') : group.collect;
        const missingWords = [...new Set(words(collect))].filter(word => !visible.has(word) && !['nbsp', 'label', 'example', 'answer'].includes(word));
        assert.deepEqual(missingWords, [], `${filename}: source collect words remain visible`);
        questions += group.questions.length;
      }
    }
    assert.equal(questions, 2880);
  }
});

const compoundFixtures = [
  ['listening', 'ielts4_test1', 11, 'and', 'coal', 'firewood'],
  ['listening', 'ielts6_test1', 7, 'to', '10', '4.30'],
  ['listening', 'ielts6_test1', 19, 'and', 'Monday', 'Thursday'],
  ['listening', 'ielts6_test1', 32, 'and', 'metal', 'leather'],
  ['listening', 'ielts6_test3', 36, 'and', 'water', 'sand'],
  ['listening', 'ielts9_test1', 33, 'or', 'plants', 'fish'],
  ['listening', 'ielts9_test2', 12, 'and', 'Friday', 'Sunday'],
  ['reading', 'ielts4_test1_reading', 21, 'whales and', 'bowhead', 'humpback'],
  ['reading', 'ielts7_test2_reading', 26, 'and', 'farmers', 'consumers'],
  ['reading', 'ielts9_test3_reading', 33, 'and', 'Jupiter', 'Saturn'],
  ['reading', 'ielts9_test3_reading', 35, 'and', 'sensors', 'circuits'],
  ['reading', 'ielts10_test2_reading', 23, 'and', 'books', 'activities']
];

for (const [subject, name, number, separator, left, right] of compoundFixtures) test(`${name} Q${number}: two physical blanks remain one saved answer and one mark`, () => {
  const payload = fixture(subject, name);
  const group = find(subject, payload, number);
  const question = group.questions.find(q => q.number === number);
  const context = templateRuntime(subject, payload);
  const html = context.renderGroup(group, 0);
  const control = controls(html, subject).find(control => control.id === String(question.id));
  assert.equal(control.kind, 'text-parts');
  assert.equal(control.attrs['data-separator'], separator);
  assert.equal(control.attrs['data-marks'] || '1', '1');
  assert.equal((html.match(new RegExp(`aria-label="Question ${number} answer [12] of 2"`, 'g')) || []).length, 2);
  const inputs = [{ value: left }, { value: right }];
  const unit = { dataset: { kind: 'text-parts', separator }, querySelectorAll: () => inputs };
  const joiner = separator.split(' ').at(-1);
  const saved = `${left} ${joiner} ${right}`;
  assert.equal(renderers.multiBlankValue(unit), saved);
  renderers.restoreMultiBlankValue(unit, saved);
  assert.deepEqual(inputs.map(input => input.value), [left, right]);
  assert.equal(renderers.multiBlankValue(unit), saved);
  // Legacy single-box attempts are displayed without rewriting their value or score.
  renderers.restoreMultiBlankValue(unit, left);
  assert.equal(renderers.multiBlankValue(unit), left);
  inputs[1].value = right;
  assert.equal(renderers.multiBlankValue(unit), saved);
  renderers.restoreMultiBlankValue(unit, '');
  assert.deepEqual(inputs.map(input => input.value), ['', '']);
  assert.equal(renderers.multiBlankValue(unit), '');
});

test('compound form stems preserve the complete text after the second blank', () => {
  for (const [name, number, suffix] of [
    ['ielts6_test3', 36, 'were necessary for grinding and polishing.'],
    ['ielts9_test1', 33, 'are commonly consumed by whales']
  ]) {
    const payload = fixture('listening', name);
    const html = templateRuntime('listening', payload).renderGroup(find('listening', payload, number), 0);
    assert.ok(html.includes(suffix), name);
    assert.equal((html.match(new RegExp(`Question ${number} answer [12] of 2`, 'g')) || []).length, 2);
  }
});

test('empty titles with two distinct source IDs render one complete sentence in source order', () => {
  for (const [name, numbers, prefix, suffix] of [
    ['ielts19_test4', [37, 38], '- increasing the', 'were soon attracted to the area.'],
    ['ielts20_test1', [39, 40], '· Instead of road transport, goods could be transported', '.']
  ]) {
    const payload = fixture('listening', name);
    const html = templateRuntime('listening', payload).renderGroup(find('listening', payload, numbers[0]), 0);
    assert.equal(html.split(prefix).length - 1, 1, name);
    const first = html.indexOf(`aria-label="Question ${numbers[0]} answer"`);
    const second = html.indexOf(`aria-label="Question ${numbers[1]} answer"`);
    assert.ok(first >= 0 && second > first);
    assert.ok(html.slice(second).includes(suffix));
  }
});

test('numbered brackets place the control within its stem, including renumbered historical source questions', () => {
  const payload = fixture('listening', 'ielts18_test3');
  const group = payload.sections[0].groups[0];
  const html = templateRuntime('listening', payload).renderGroup(group, 0);
  assert.match(html, /Home address:.*52[\s\S]*Question 1 answer[\s\S]*Street, Peacetown/);
  for (const question of group.questions) { question.source_number = question.number; question.number += 11; }
  const renumbered = templateRuntime('listening', payload).renderGroup(group, 0);
  assert.match(renumbered, /Home address:.*52[\s\S]*Question 12 answer[\s\S]*Street, Peacetown/);
  assert.doesNotMatch(renumbered, /【[1-4]】/);
  const source = fixture('listening', 'ielts20_test1');
  const notes = find('listening', source, 36);
  for (const question of notes.questions) { question.source_number = question.number; question.number -= 30; }
  const notesHtml = templateRuntime('listening', source).renderGroup(notes, 0);
  assert.doesNotMatch(notesHtml, /display 36/);
  assert.match(notesHtml, /display[\s\S]*Question 6 answer/);
});

test('actual listening answerSnapshot/applyAnswerRows preserve compound values and reset both inputs', () => {
  const inputs = [{ value: 'water' }, { value: 'sand' }];
  const unit = { dataset: { id: '1672', kind: 'text-parts', separator: 'and' }, querySelectorAll: () => inputs };
  const context = templateRuntime('listening', {}, { document: { querySelectorAll: () => [unit] }, refreshAnsweredCount() {}, syncQuestionNav() {} });
  assert.equal(context.answerSnapshot()['1672'], 'water and sand');
  context.applyAnswerRows({ 1672: 'sand and water' });
  assert.deepEqual(inputs.map(input => input.value), ['sand', 'water']);
  assert.equal(context.answerSnapshot()['1672'], 'sand and water');
  context.applyAnswerRows({});
  assert.deepEqual(inputs.map(input => input.value), ['', '']);
});

test('actual reading input handler saves both blanks under one qid and respects read-only review', () => {
  const inputs = [{ value: 'books' }, { value: 'activities' }];
  const unit = { dataset: { qid: '1325', separator: 'and' }, querySelectorAll: () => inputs };
  const context = templateRuntime('reading', {}, { practiceContext: {}, persistExamDraft: () => true, practiceShellController: null, resultMode: false, updateSummary() {}, syncQuestionNav() {} });
  context.handleAnswerChange({ target: { closest: () => unit } });
  assert.equal(context.answers['1325'], 'books and activities');
  context.practiceContext.read_only = true;
  inputs[0].value = 'changed';
  context.handleAnswerChange({ target: { closest: () => unit } });
  assert.equal(context.answers['1325'], 'books and activities');
});

test('source-only form labels and fixed facts keep their question ownership', () => {
  const cases = [
    ['ielts18_test1', 6, 'Complaints about bus service:'],
    ['ielts14_test1', 4, 'Items stolen:'],
    ['ielts14_test1', 8, 'Details of suspect:'],
    ['ielts6_test3', 5, 'Telephone:'],
    ['ielts6_test3', 8, 'Opening sum:'],
    ['ielts6_test4', 1, 'Three day cost:'],
    ['ielts9_test2', 33, 'Disadvantage:']
  ];
  for (const [name, number, label] of cases) {
    const payload = fixture('listening', name);
    const group = find('listening', payload, number);
    const html = templateRuntime('listening', payload).renderGroup(group, 0);
    const labelAt = html.indexOf(label);
    const inputAt = html.indexOf(`aria-label="Question ${number} answer"`);
    assert.ok(labelAt >= 0 && labelAt < inputAt, `${name} ${label}`);
    if (number > group.questions[0].number) assert.ok(labelAt > html.indexOf(`aria-label="Question ${number - 1} answer"`), `${name} label belongs to Q${number}`);
  }
  for (const [name, number, text] of [
    ['ielts6_test2', 40, 'The Lights of New York'],
    ['ielts7_test4', 2, 'Age: 28 years'],
    ['ielts9_test1', 40, 'Marine Mammals Ashore'],
    ['ielts17_test4', 31, 'made from the sap of the maple tree']
  ]) {
    const payload = fixture('listening', name);
    const html = templateRuntime('listening', payload).renderGroup(find('listening', payload, number), 0);
    assert.ok(html.includes(text), `${name} retains the complete source cell`);
  }
});

test('renumbered specialty instructions display current question range without changing word limits or frozen text', () => {
  for (const [subject, name, number] of [['listening', 'ielts18_test1', 31], ['reading', 'ielts6_test1_reading', 27]]) {
    const payload = fixture(subject, name);
    const group = find(subject, payload, number);
    const original = group.desc;
    const sourceTail = original.replace(/^[^\n]*/, '');
    group.questions.forEach((question, index) => { question.source_number = question.number; question.number = index + 1; });
    const rendered = renderers.groupDescription(group);
    assert.ok(rendered.startsWith(`Questions 1–${group.questions.length}`));
    assert.equal(rendered.replace(/^[^\n]*/, ''), sourceTail);
    assert.equal(group.desc, original);
    const html = templateRuntime(subject, payload).renderGroup(group, 0);
    assert.ok(html.includes(`Questions 1–${group.questions.length}`));
  }
  const group = { desc: 'Questions 14–15\nWrite NO MORE THAN TWO WORDS. In 1998, 31 people applied.', questions: [{ number: 1 }, { number: 2 }] };
  assert.equal(renderers.groupDescription(group), 'Questions 1–2\nWrite NO MORE THAN TWO WORDS. In 1998, 31 people applied.');
  assert.equal(renderers.groupDescription({ ...group, desc: 'Discuss Questions 14–15 in Chapter 2.' }), 'Discuss Questions 14–15 in Chapter 2.');
});
