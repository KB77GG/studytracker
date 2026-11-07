'use strict';

const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const test = require('node:test');
const renderers = require('../static/js/practice_renderers.js');
const root = path.resolve(__dirname, '..');
const bank = name => JSON.parse(fs.readFileSync(path.join(root, 'static/listening_tests', `${name}.json`)));
const groupAt = (name, section, number) => bank(name).sections[section - 1].groups.find(group => group.questions.some(q => q.number === number));
const render = group => renderers.renderForm(group, q => `[Q${q.number}]`);
const normalize = value => renderers.plainText(value).replace(/[^\p{L}\p{N}]+/gu, ' ').trim().toLowerCase();
const questionRows = html => [...html.matchAll(/<div class="practice-form__(?:shared-source|content)">([\s\S]*?)<\/div>/g)].map(match => match[1]);
const rowFor = (html, number) => questionRows(html).find(row => row.includes(`[Q${number}]`));
const plain = html => renderers.plainText(html.replace(/<\/div>/g, '</div>\n'));

test('all 165 listening forms retain each nonempty source suffix on its own question row', () => {
  let groups = 0, suffixes = 0, questions = 0;
  for (const file of fs.readdirSync(path.join(root, 'static/listening_tests')).filter(name => /^ielts\d+_test\d+\.json$/.test(name))) {
    for (const section of bank(file.replace('.json', '')).sections) for (const group of section.groups) {
      if (!renderers.isFormGroup(group)) continue;
      groups += 1;
      questions += group.questions.length;
      const html = render(group);
      assert.match(html, /data-layout="flow"/);
      for (const field of renderers.formFields(group)) {
        assert.equal(html.split(`[Q${field.question.number}]`).length - 1, 1, `${file} Q${field.question.number}`);
        if (!field.target) continue;
        const source = renderers.targetSource(field);
        const last = [...source.matchAll(/\$(\d+)\$/g)].at(-1);
        if (!last || last[1] !== String(field.question.id)) continue;
        const suffix = normalize(source.slice(last.index + last[0].length));
        if (!suffix) continue;
        suffixes += 1;
        assert.ok(normalize(rowFor(html, field.question.number)).includes(suffix), `${file} Q${field.question.number} must retain '${suffix}' on its row`);
      }
    }
  }
  assert.deepEqual({ groups, questions, suffixes }, { groups: 165, questions: 1252, suffixes: 677 });
});

test('all 39 shared clusters keep the complete original target cells with their controls', () => {
  let clusters = 0, questions = 0;
  for (const file of fs.readdirSync(path.join(root, 'static/listening_tests')).filter(name => /^ielts\d+_test\d+\.json$/.test(name))) {
    for (const section of bank(file.replace('.json', '')).sections) for (const group of section.groups) {
      if (!renderers.isFormGroup(group)) continue;
      const fields = renderers.formFields(group);
      const html = render(group);
      for (const cluster of renderers.sharedFormClusters(fields)) {
        clusters += 1;
        questions += cluster.fields.length;
        for (const field of cluster.fields) {
          let source = renderers.targetSource(field);
          for (const q of group.questions) {
            source = source.replace(new RegExp(`\\s+${q.source_number || q.number}\\s*(?=\\$${q.id}\\$)`, 'g'), '');
            source = source.replaceAll(`$${q.id}$`, `[Q${q.number}]`);
          }
          assert.ok(normalize(rowFor(html, field.question.number)).includes(normalize(source)), `${file} Q${field.question.number}: ${source}`);
        }
      }
    }
  }
  assert.deepEqual({ clusters, questions }, { clusters: 39, questions: 102 });
});

test('C13 T1 research notes keep tails and intervening scientist introductions in source order', () => {
  const html = render(groupAt('ielts13_test1', 4, 35));
  assert.match(plain(rowFor(html, 35)), /\[Q35\] and to deal with new dangers\./);
  assert.match(plain(rowFor(html, 36)), /Catarina Miranda.*\[Q36\] of urban and rural blackbirds\./);
  assert.match(plain(rowFor(html, 37)), /\[Q37\] \./);
  assert.match(plain(rowFor(html, 38)), /\[Q38\] by producing lower levels of hormones\./);
  assert.equal(html.split('Emilie Snell-Rood studied').length - 1, 1);
  assert.ok(html.indexOf('Emilie Snell-Rood studied') < html.indexOf('[Q34]'));
  assert.ok(html.indexOf('[Q37]') < html.indexOf('Jonathan Atwell studies'));
  assert.ok(html.indexOf('Jonathan Atwell studies') < html.indexOf('[Q38]'));
});

test('C12 T5 restores static packing notes between Q7 and Q8 without duplicating them', () => {
  const html = render(groupAt('ielts12_test5', 1, 6));
  for (const phrase of ['Cyclists need:', 'a repair kit', 'food and drink']) {
    assert.equal(html.split(phrase).length - 1, 1);
    assert.ok(html.indexOf('[Q7]') < html.indexOf(phrase));
    assert.ok(html.indexOf(phrase) < html.indexOf('[Q8]'));
  }
  assert.match(plain(rowFor(html, 8)), /\[Q8\] \(can be hired\)/);
  assert.doesNotMatch(plain(rowFor(html, 9)), /can be hired/);
});

test('C12 T6 and C14 T2 short suffixes do not move into the next question', () => {
  const event = render(groupAt('ielts12_test6', 1, 7));
  assert.match(plain(rowFor(event, 7)), /\[Q7\] House/);
  assert.match(plain(rowFor(event, 8)), /\[Q8\] dances/);
  assert.doesNotMatch(plain(rowFor(event, 9)), /dances/);
  const medical = render(groupAt('ielts14_test2', 1, 7));
  assert.match(plain(rowFor(medical, 7)), /\[Q7\] club/);
  assert.match(plain(rowFor(medical, 8)), /\[Q8\] regularly/);
  assert.doesNotMatch(plain(rowFor(medical, 9)), /regularly/);
});

test('shared source rows do not repeat headings inferred from the concatenated title', () => {
  const html = render(groupAt('ielts12_test7', 4, 32));
  assert.equal(html.split('Claire Varian-Ramos is investigating').length - 1, 1);
  assert.ok(html.indexOf('Claire Varian-Ramos is investigating') < html.indexOf('[Q32]'));
  assert.ok(html.indexOf('[Q33]') < html.indexOf('Findings:'));
  assert.ok(html.indexOf('Findings:') < html.indexOf('[Q34]'));
  assert.ok(html.indexOf('[Q35]') < html.indexOf('Lab-based studies:'));
  assert.ok(html.indexOf('Lab-based studies:') < html.indexOf('[Q36]'));
});

test('fixed name/value cells on one source line stay on one displayed line', () => {
  const html = render(groupAt('ielts18_test1', 1, 1));
  const facts = [...html.matchAll(/<div class="practice-form__(?:line|subheading)">([^<]*)<\/div>/g)].map(match => renderers.plainText(match[1]));
  assert.ok(facts.includes('Name: Sadie Jones'));
  assert.ok(facts.includes('Year of birth: 1991'));
  assert.equal(facts.filter(text => text.includes('Sadie Jones')).length, 1);
});

test('C7 T2 independent paper columns become complete blocks in question reading order', () => {
  const html = render(groupAt('ielts7_test2', 1, 6));
  assert.match(html, /data-layout="flow"/);
  for (const [before, after] of [
    ['Name(s) of other driver(s)', '[Q6]'], ['[Q6]', 'Relationship to main driver'],
    ['Relationship to main driver', '[Q7]'], ['[Q7]', 'Uses of car'],
    ['Uses of car', '- social'], ['- social', '[Q8]']
  ]) assert.ok(html.indexOf(before) < html.indexOf(after), `${before} precedes ${after}`);
  assert.equal(html.split('Uses of car').length - 1, 1);
});

test('C18 T1 joins the reviewed anti-poaching erratum and keeps genuine minus bullets', () => {
  const html = render(groupAt('ielts18_test1', 4, 31));
  assert.match(html, /practice-form__line">• strict enforcement of anti-poaching laws<\/div>/);
  assert.equal(html.split('poaching laws').length - 1, 1);
  assert.doesNotMatch(html, />− poaching laws/);
  assert.match(html, /practice-form__line">− tracking devices were fitted/);
  assert.doesNotMatch(html, /practice-form__subheading">− /);
});

test('similar or separated static lines are not guessed to be anti-prefix compounds', () => {
  for (const source of [
    '• strict enforcement of anti\n− poaching regulations',
    '• enforcement of anti\n− poaching laws',
    '• strict enforcement of anti\n- poaching laws',
    '• strict enforcement of anti\n• An intervening note\n− poaching laws'
  ]) {
    const html = render({ type: 5, collect: `${source}\n• prompt $1$`, questions: [{ id: 1, number: 1, title: '• prompt 【 】' }] });
    assert.doesNotMatch(html, /anti-poaching/);
    for (const line of source.split('\n')) assert.ok(plain(html).includes(line), line);
  }
});

test('incomplete, reversed or foreign-ID source spans retain the reviewed title fallback', () => {
  for (const collect of ['Raw first $1$\nNo second marker', 'Raw second $2$\nRaw first $1$', 'Raw first $1$\nForeign $99$\nRaw second $2$']) {
    const title = 'Reviewed first 【 】 tail; reviewed second 【 】 final.';
    const group = { type: 5, collect, questions: [{ id: 1, number: 1, title }, { id: 2, number: 2, title }] };
    const html = render(group);
    assert.ok(html.includes('Reviewed first'));
    assert.ok(html.includes('reviewed second'));
    assert.ok(html.includes('final.'));
    assert.equal(html.split('[Q1]').length - 1, 1);
    assert.equal(html.split('[Q2]').length - 1, 1);
    assert.equal(html.split('class="practice-form__shared-source"').length - 1, 1);
    assert.match(plain(rowFor(html, 1)), /\[Q1\] tail; reviewed second \[Q2\] final\./);
  }
});

test('shared source rows keep current numbers after specialty renumbering', () => {
  const group = groupAt('ielts13_test1', 4, 35);
  group.questions.forEach(q => { q.source_number = q.number; q.number -= 30; });
  const html = render(group);
  assert.match(plain(rowFor(html, 5)), /\[Q5\] and to deal with new dangers\./);
  assert.match(plain(rowFor(html, 6)), /Catarina Miranda.*\[Q6\] of urban and rural blackbirds\./);
  assert.doesNotMatch(html, /\[Q3[5-9]\]/);
});
