const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')

const renderers = require('../static/js/practice_renderers.js')

const fixture = JSON.parse(fs.readFileSync(
  path.join(__dirname, '..', 'static', 'listening_tests', 'ielts7_test2.json'),
  'utf8'
))
const formGroup = fixture.sections[0].groups.find(group => Number(group.type) === 5)

test('Cambridge 7 Test 2 Q4-Q8 become ordered semantic form fields', () => {
  const fields = renderers.formFields(formGroup)
  const target = fields.filter(field => field.question.number >= 4 && field.question.number <= 8)

  assert.deepEqual(target.map(field => field.question.number), [4, 5, 6, 7, 8])
  assert.deepEqual(target.map(field => field.label), [
    'Previous insurance company',
    'If yes, give brief details',
    'Name(s) of other driver(s)',
    'Relationship to main driver',
    'Uses of car'
  ])
  assert.deepEqual(target[1].context, [
    'Any insurance claims in the last five years?',
    'Yes✔️',
    'No'
  ])
  assert.deepEqual(target[4].context, ['- social'])
  assert.deepEqual(fields.find(field => field.question.number === 9).beforeFacts, [
    'Start date: 31 January',
    'Recommended Insurance arrangement'
  ])
})

test('form renderer keeps one control per question and strips OCR question-number debris', () => {
  const html = renderers.renderForm(formGroup, question => `<input data-test-q="${question.number}">`)
  for (let number = 1; number <= 10; number += 1) {
    assert.equal((html.match(new RegExp(`data-test-q="${number}"`, 'g')) || []).length, 1)
  }
  assert.ok(html.indexOf('Previous insurance company:') < html.indexOf('If yes, give brief details:'))
  assert.ok(html.indexOf('Name(s) of other driver(s):') < html.indexOf('Relationship to main driver:'))
  assert.ok(html.indexOf('Relationship to main driver:') < html.indexOf('Uses of car:'))
  assert.ok(!html.includes('Name of company:  9<input'))
  assert.ok(!html.includes('&nbsp;'))
  assert.ok(!html.includes('Question 7'))
  assert.ok(html.includes('data-layout="columns"'))
})

test('continuous notes keep static lines with their section instead of making question cards', () => {
  const listening17 = JSON.parse(fs.readFileSync(
    path.join(__dirname, '..', 'static', 'listening_tests', 'ielts17_test1.json'),
    'utf8'
  ))
  const group = listening17.sections[0].groups.find(item => Number(item.type) === 5)
  const html = renderers.renderForm(group, question => `<input data-test-q="${question.number}">`)

  assert.ok(html.includes('data-layout="flow"'))
  assert.equal((html.match(/Forthcoming events/g) || []).length, 1)
  assert.ok(!html.includes('Q7 · Question 7'))
  assert.ok(html.indexOf('• take a picnic') < html.indexOf('data-test-q="7"'))
  assert.ok(html.indexOf('• 17th, from 10 a.m. to 3 p.m.') < html.indexOf('data-test-q="10"'))
})

test('empty per-question titles fall back to the complete collect stem', () => {
  const listening20 = JSON.parse(fs.readFileSync(
    path.join(__dirname, '..', 'static', 'listening_tests', 'ielts20_test4.json'),
    'utf8'
  ))
  const group = listening20.sections[0].groups.find(item => item.title === 'Advice on family visit')
  const html = renderers.renderForm(group, question => `<input data-test-q="${question.number}">`)

  for (let number = 1; number <= 10; number += 1) {
    assert.equal((html.match(new RegExp(`data-test-q="${number}"`, 'g')) || []).length, 1)
  }
  assert.ok(html.includes('· a <input data-test-q="3"> tour of the city centre'))
  assert.ok(html.includes('· a trip by <input data-test-q="4"> to the old fort'))
  assert.ok(html.includes('· see the exhibition about <input data-test-q="6">, which opens soon'))
  assert.ok(html.includes('- good for <input data-test-q="7"> food'))
  assert.ok(html.includes('- need to have lunch before <input data-test-q="8"> p.m.'))
  assert.ok(!html.includes('practice-form__content"><input data-test-q="3">'))
})

test('empty titles also recover prompts split into paper-form columns', () => {
  const listening19 = JSON.parse(fs.readFileSync(
    path.join(__dirname, '..', 'static', 'listening_tests', 'ielts19_test4.json'),
    'utf8'
  ))
  const group = listening19.sections[0].groups.find(item => item.title === 'First day at work')
  const html = renderers.renderForm(group, question => `<input data-test-q="${question.number}">`)

  assert.ok(html.includes('• Name of supervisor: <input data-test-q="1">'))
  assert.ok(html.includes('• Where to leave coat and bag: use <input data-test-q="2"> in staffroom'))
  assert.ok(html.includes('• Supervisor’s mobile number: <input data-test-q="6">'))
})

test('trailing source whitespace does not hide a collect stem', () => {
  const listening21 = JSON.parse(fs.readFileSync(
    path.join(__dirname, '..', 'static', 'listening_tests', 'ielts21_test4.json'),
    'utf8'
  ))
  const group = listening21.sections[3].groups.find(item => item.title === 'Music therapy for surgical patients')
  const fields = renderers.formFields(group)
  const html = renderers.renderForm(group, question => `<input data-test-q="${question.number}">`)

  assert.ok(fields.find(field => field.question.number === 32).target)
  assert.ok(html.includes('A study reviewed data from about 100 <input data-test-q="32"> and found that listening to music'))
})

test('all form-completion fixtures map every control to a source stem', () => {
  let groupCount = 0
  let controlCount = 0
  let emptyTitleCount = 0
  const sourceOnlyControls = []

  for (const directory of ['listening_tests', 'reading_tests']) {
    const fixtureDirectory = path.join(__dirname, '..', 'static', directory)
    for (const filename of fs.readdirSync(fixtureDirectory).filter(name => name.endsWith('.json'))) {
      let book
      try {
        book = JSON.parse(fs.readFileSync(path.join(fixtureDirectory, filename), 'utf8'))
      } catch {
        continue
      }
      for (const section of book.sections || []) {
        for (const group of section.groups || []) {
          if (!renderers.isFormGroup(group)) continue
          groupCount += 1
          const fields = renderers.formFields(group)
          const html = renderers.renderForm(group, question => `<input data-test-id="${question.id}">`)
          controlCount += fields.length
          for (const field of fields) {
            if (!String(field.question.title || '').trim()) {
              emptyTitleCount += 1
              assert.ok(field.target, `${filename} Q${field.question.number} has no source target`)
              const marker = `$${field.question.id}$`
              const sourceText = renderers.plainText(renderers.targetSource(field).replace(marker, ''))
                .replace(/[^\p{L}\p{N}]+/gu, '')
              if (!sourceText) sourceOnlyControls.push(`${filename}:Q${field.question.number}`)
            }
            assert.equal(
              (html.match(new RegExp(`data-test-id="${field.question.id}"`, 'g')) || []).length,
              1,
              `${filename} Q${field.question.number} should render once`
            )
          }
        }
      }
    }
  }

  assert.equal(groupCount, 195)
  assert.equal(controlCount, 1476)
  assert.equal(emptyTitleCount, 230)
  assert.deepEqual(sourceOnlyControls.sort(), [
    'ielts21_test1.json:Q31',
    'ielts4_test1.json:Q2',
    'ielts4_test4.json:Q7',
    'ielts4_test4.json:Q8',
    'ielts4_test4.json:Q9'
  ].sort())
})

test('matching and map renderers expose dedicated workspaces without repeated option banks', () => {
  const questions = [16, 17, 18, 19, 20].map(number => ({ id: number, number, title: `Item ${number}` }))
  const matching = renderers.renderMatching(
    { questions },
    () => '<div class="option-bank">A</div>',
    question => `<select data-q="${question.id}"></select>`
  )
  assert.equal((matching.match(/class="option-bank"/g) || []).length, 1)
  assert.equal((matching.match(/<select data-q=/g) || []).length, 5)

  const map = renderers.renderMap(
    { title: 'Plan', questions },
    '/static/listening_tests/images/map.png',
    question => `<input data-q="${question.id}">`
  )
  for (const action of ['zoom-in', 'zoom-out', 'reset', 'fullscreen']) {
    assert.ok(map.includes(`data-map-action="${action}"`))
  }
  assert.ok(map.includes('data-map-canvas'))
  assert.equal((map.match(/<input data-q=/g) || []).length, 5)
})

test('type 8 without a shared option bank remains a completion task', () => {
  assert.equal(renderers.isMatchingGroup({
    type: 8,
    collect: 'The $1$',
    questions: [{ id: 1 }]
  }), false)
  assert.equal(renderers.isMatchingGroup({
    type: 8,
    collect_option: { list: [{ key: 'A' }, { key: 'B' }, { key: 'C' }] },
    questions: [{ id: 1 }, { id: 2 }, { id: 3 }]
  }), true)
})

test('review cards use explicit textual status in addition to color', () => {
  const question = { id: 7, number: 7, answer: 'son', analysis: 'Listen for the relationship.' }
  assert.ok(renderers.renderReviewCard(question, { status: 'correct' }, 'son').includes('✓ 正确'))
  assert.ok(renderers.renderReviewCard(question, { status: 'incorrect' }, 'friend').includes('× 错误'))
  assert.ok(renderers.renderReviewCard(question, null, '').includes('— 未作答'))
})
