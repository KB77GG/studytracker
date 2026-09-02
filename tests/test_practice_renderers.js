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

test('complete paper-form titles are not repeated as trailing or misplaced facts', () => {
  const listening18 = JSON.parse(fs.readFileSync(
    path.join(__dirname, '..', 'static', 'listening_tests', 'ielts18_test1.json'),
    'utf8'
  ))
  const group = listening18.sections[0].groups[0]
  const html = renderers.renderForm(group, question => `<input data-test-q="${question.number}">`)
  const escaped = value => String(value).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const standalone = value => new RegExp(
    `<div class="practice-form__(?:line|subheading)">${escaped(value)}</div>`,
    'g'
  )

  for (const stem of ['Travelled by bus because cost of', 'Got on bus at', 'Goes to the']) {
    assert.equal((html.match(new RegExp(escaped(stem), 'g')) || []).length, 1, `${stem} should remain in Q${stem === 'Goes to the' ? 8 : stem === 'Got on bus at' ? 5 : 4}`)
    assert.equal((html.match(standalone(stem)) || []).length, 0, `${stem} should not render as a standalone fact`)
  }
  assert.ok(html.includes('Goes to the <input data-test-q="8"> by car'))
  assert.equal((html.match(/Travelling by car/g) || []).length, 1)

  const carHeading = '<div class="practice-form__subheading">Travelling by car</div>'
  const bicycleHeading = '<div class="practice-form__section">Travelling by bicycle</div>'
  assert.ok(html.indexOf(carHeading) < html.indexOf('data-test-q="8"'))
  assert.ok(html.indexOf('data-test-q="8"') < html.indexOf(bicycleHeading))
  assert.ok(html.indexOf(bicycleHeading) < html.indexOf('data-test-q="9"'))
  assert.ok(html.indexOf('data-test-q="9"') < html.indexOf('data-test-q="10"'))
  assert.match(html, /<div class="practice-form__subheading">Travelling by car<\/div>\s*<div class="practice-form__field[^>]*data-question-number="8"/)
  assert.match(html, /<div class="practice-form__section">Travelling by bicycle<\/div>\s*<div class="practice-form__field[^>]*data-question-number="9"/)
})

test('same text in a different source cell remains visible', () => {
  const group = {
    type: 5,
    collect: 'Status        $1$\nStatus\nDetails:        $2$',
    questions: [
      { id: 1, number: 1, title: 'Status 【   】' },
      { id: 2, number: 2, title: 'Details: 【   】' }
    ]
  }
  const fields = renderers.formFields(group)
  const html = renderers.renderForm(group, question => `<input data-test-q="${question.number}">`)

  assert.deepEqual(fields[1].beforeFactIndexes, [2])
  assert.equal((html.match(/<div class="practice-form__subheading">Status<\/div>/g) || []).length, 1)
  assert.ok(html.includes('Status <input data-test-q="1">'))
  assert.ok(html.includes('Details: <input data-test-q="2">'))
})

test('context keeps legal items in source order when another cell is suppressed', () => {
  const group = {
    type: 5,
    collect: 'Status        $1$\n<b>Current section</b>\nImportant note\nQuestion        $2$',
    questions: [
      { id: 1, number: 1, title: 'Status 【   】' },
      { id: 2, number: 2, title: 'Question 【   】' }
    ]
  }
  const fields = renderers.formFields(group)
  const html = renderers.renderForm(group, question => `<input data-test-q="${question.number}">`)

  assert.deepEqual(fields[1].contextIndexes, [3])
  assert.deepEqual(fields[1].context, ['Important note'])
  assert.match(html, /<div class="practice-form__section">Current section<\/div><div class="practice-form__subheading">Important note<\/div>\s*<div class="practice-form__field[^>]*data-question-number="2"/)
  assert.equal((html.match(/<div class="practice-form__(?:line|subheading)">Question<\/div>/g) || []).length, 0)
  assert.ok(html.includes('Question <input data-test-q="2">'))
})

test('repeated context indexes emit once while equal text in another cell remains visible', () => {
  const group = {
    type: 5,
    collect: '<b>Section</b>\nRepeated note\nQuestion one        $1$\nQuestion two        $2$',
    questions: [
      { id: 1, number: 1, title: 'Question one 【   】' },
      { id: 2, number: 2, title: 'Question two 【   】' }
    ]
  }
  const fields = renderers.formFields(group)
  const html = renderers.renderForm(group, question => `<input data-test-q="${question.number}">`)

  assert.deepEqual(fields[0].contextIndexes, [1])
  assert.deepEqual(fields[1].contextIndexes, [1])
  assert.equal((html.match(/Repeated note/g) || []).length, 1)
  assert.equal((html.match(/<div class="practice-form__section">Section<\/div>/g) || []).length, 1)
  assert.equal((html.match(/data-test-q="1"/g) || []).length, 1)
  assert.equal((html.match(/data-test-q="2"/g) || []).length, 1)
})

test('label candidates with trailing values keep the complete source fact', () => {
  const samples = [
    {
      filename: 'ielts10_test1.json',
      sectionIndex: 0,
      groupIndex: 0,
      values: ['Andrea Brown'],
      wrongPrefixes: ['Andrea: Address']
    },
    {
      filename: 'ielts6_test3.json',
      sectionIndex: 0,
      groupIndex: 0,
      values: ['home 796431'],
      wrongPrefixes: ['home: Occupation']
    },
    {
      filename: 'ielts7_test1.json',
      sectionIndex: 0,
      groupIndex: 1,
      values: ['No. of passengers: One', 'Type of ticket: Single', 'From: London Heathrow'],
      wrongPrefixes: ['No. of passengers: Bus Time', 'Type of ticket: Name', 'From: Credit Card No']
    }
  ]

  for (const sample of samples) {
    const book = JSON.parse(fs.readFileSync(
      path.join(__dirname, '..', 'static', 'listening_tests', sample.filename),
      'utf8'
    ))
    const group = book.sections[sample.sectionIndex].groups[sample.groupIndex]
    const html = renderers.renderForm(group, question => `<input data-test-q="${question.number}">`)
    for (const value of sample.values) {
      assert.equal((html.match(new RegExp(value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g')) || []).length, 1, `${sample.filename}: ${value}`)
    }
    for (const prefix of sample.wrongPrefixes) assert.ok(!html.includes(prefix), `${sample.filename}: ${prefix}`)
  }
})

test('decorated pure labels keep JFDR6 section ownership and order', () => {
  const book = JSON.parse(fs.readFileSync(
    path.join(__dirname, '..', 'static', 'listening_tests', 'jfdr6_test2.json'),
    'utf8'
  ))
  const group = book.sections[3].groups[0]
  const fields = renderers.formFields(group)
  const html = renderers.renderForm(group, question => `<input data-test-q="${question.number}">`)
  const q31 = html.indexOf('data-question-number="31"')
  const q32 = html.indexOf('data-question-number="32"')
  const studyHeading = html.indexOf('<div class="practice-form__section">The study by Cunningham in 1995</div>')
  const methodologyHeading = html.indexOf('<div class="practice-form__section">Methodology</div>')

  assert.equal(fields[0].label, 'The study by Cunningham in 1995')
  assert.equal(fields[1].label, 'Methodology')
  assert.ok(studyHeading >= 0 && studyHeading < q31)
  assert.ok(q31 < methodologyHeading && methodologyHeading < q32)
  assert.equal((html.match(/<div class="practice-form__section">The study by Cunningham in 1995<\/div>/g) || []).length, 1)
  assert.equal((html.match(/<div class="practice-form__section">Methodology<\/div>/g) || []).length, 1)
  assert.equal((html.match(/practice-form__prompt">The study by Cunningham in 1995/g) || []).length, 0)
  assert.equal((html.match(/practice-form__prompt">Methodology/g) || []).length, 0)
})

test('legitimate adjacent-column facts remain visible', () => {
  const maple = JSON.parse(fs.readFileSync(
    path.join(__dirname, '..', 'static', 'listening_tests', 'ielts17_test4.json'),
    'utf8'
  ))
  const telecom = JSON.parse(fs.readFileSync(
    path.join(__dirname, '..', 'static', 'listening_tests', 'ielts5_test4.json'),
    'utf8'
  ))
  const mapleGroup = maple.sections[3].groups.find(group => group.title === 'Maple syrup')
  const telecomGroup = telecom.sections[2].groups.find(group => group.collect.includes('Problems: been affected by'))
  const mapleHtml = renderers.renderForm(mapleGroup, question => `<input data-test-q="${question.number}">`)
  const telecomHtml = renderers.renderForm(telecomGroup, question => `<input data-test-q="${question.number}">`)

  for (const fact of ['• added to food or used in cooking', '• needs sunny days and cool nights']) {
    assert.equal((mapleHtml.match(new RegExp(fact.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'), 'g')) || []).length, 1, fact)
  }
  assert.equal((telecomHtml.match(/Problems: been affected by/g) || []).length, 1)
  assert.ok(telecomHtml.includes('<div class="practice-form__line">Problems: been affected by</div>'))
})

test('all form fixtures omit same-row title prefixes from standalone facts', () => {
  const normalize = value => String(value || '')
    .replace(/【\s*】|\[\s*\]/g, '')
    .replace(/^[\s·•\-–—]+/, '')
    .replace(/[:：?？\s]+$/g, '')
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase()
  const escapeRegex = value => String(value).replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
  const candidates = []
  const renderedDuplicates = []

  for (const directory of ['listening_tests', 'reading_tests']) {
    const fixtureDirectory = path.join(__dirname, '..', 'static', directory)
    for (const filename of fs.readdirSync(fixtureDirectory).filter(name => name.endsWith('.json'))) {
      let book
      try {
        book = JSON.parse(fs.readFileSync(path.join(fixtureDirectory, filename), 'utf8'))
      } catch {
        continue
      }
      for (const [sectionIndex, section] of (book.sections || []).entries()) {
        for (const [groupIndex, group] of (section.groups || []).entries()) {
          if (!renderers.isFormGroup(group)) continue
          const fields = renderers.formFields(group)
          const html = renderers.renderForm(group, question => `<input data-test-q="${question.number}">`)
          for (const field of fields) {
            const prompt = normalize(field.question.title)
            if (!prompt || !field.target) continue
            for (const cell of field.cells.filter((candidate, index) => (
              index < field.targetIndex &&
              candidate.line === field.target.line &&
              !/\$\d+\$/.test(candidate.raw) &&
              !/^[·•\-–—]/.test(candidate.text.trim())
            ))) {
              const fact = normalize(cell.text)
              if (!fact || !(prompt === fact || prompt.startsWith(`${fact} `) || prompt.startsWith(`${fact}:`))) continue
              const location = `${directory}/${filename} S${sectionIndex + 1} G${groupIndex + 1} Q${field.question.number}: ${cell.text}`
              candidates.push(location)
              const standalone = new RegExp(
                `<div class="practice-form__(?:line|subheading)">${escapeRegex(cell.text)}</div>`
              )
              if (standalone.test(html)) renderedDuplicates.push(location)
            }
          }
        }
      }
    }
  }

  assert.equal(candidates.length, 68)
  assert.deepEqual(renderedDuplicates, [])
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

test('shared multi-blank form stems render once with controls in placeholder order', () => {
  const samples = [
    ['ielts13_test3.json', 3, 38, [38, 39, 40]],
    ['ielts5_test1.json', 3, 36, [36, 37, 38, 39, 40]],
    ['ielts8_test1.json', 3, 38, [38, 39, 40]],
    ['ielts18_test1.json', 3, 33, [33, 34]]
  ]

  for (const [filename, sectionIndex, firstNumber, expectedNumbers] of samples) {
    const book = JSON.parse(fs.readFileSync(
      path.join(__dirname, '..', 'static', 'listening_tests', filename),
      'utf8'
    ))
    const group = book.sections[sectionIndex].groups.find(item =>
      (item.questions || []).some(question => Number(question.number) === firstNumber)
    )
    const fields = renderers.formFields(group)
    const cluster = renderers.sharedFormClusters(fields).find(item =>
      Number(item.fields[0].question.number) === firstNumber
    )
    assert.ok(cluster, `${filename} Q${firstNumber} should be a shared stem cluster`)
    assert.deepEqual(cluster.fields.map(field => Number(field.question.number)), expectedNumbers)

    const html = renderers.renderForm(
      group,
      question => `<input data-shared-q="${question.number}">`,
      question => `<span data-shared-extra="${question.number}"></span>`
    )
    const wrapper = new RegExp(
      `practice-form__shared-field" data-shared-question-count="${expectedNumbers.length}" data-shared-source-group-count="(\\d+)"`
    ).exec(html)
    assert.ok(wrapper, `${filename} Q${firstNumber} should have one shared wrapper`)

    const sourceGroupCount = cluster.fields.reduce((count, field, index) =>
      index === 0 || field.targetIndex !== cluster.fields[index - 1].targetIndex ? count + 1 : count,
      0
    )
    assert.equal(Number(wrapper[1]), sourceGroupCount)
    for (const question of cluster.fields.map(field => field.question)) {
      const control = `data-shared-q="${question.number}"`
      const anchor = `data-question-id="${question.id}"`
      const extra = `data-shared-extra="${question.number}"`
      assert.equal((html.match(new RegExp(control, 'g')) || []).length, 1, `${filename} Q${question.number} control`)
      assert.equal((html.match(new RegExp(anchor, 'g')) || []).length, 1, `${filename} Q${question.number} anchor`)
      assert.equal((html.match(new RegExp(extra, 'g')) || []).length, 1, `${filename} Q${question.number} extra`)
    }
    for (let index = 1; index < expectedNumbers.length; index += 1) {
      assert.ok(
        html.indexOf(`data-shared-q="${expectedNumbers[index - 1]}"`) < html.indexOf(`data-shared-q="${expectedNumbers[index]}"`),
        `${filename} controls should follow title placeholder order`
      )
    }
  }
})

test('form rows join without array separators around shared stems', () => {
  const group = {
    type: 5,
    collect: 'Intro        $1$\nShared text $2$ and $3$\nTail         $4$',
    questions: [
      { id: 1, number: 1, title: 'Intro 【   】' },
      { id: 2, number: 2, title: 'Shared text 【   】 and 【   】' },
      { id: 3, number: 3, title: 'Shared text 【   】 and 【   】' },
      { id: 4, number: 4, title: 'Tail 【   】' }
    ]
  }
  const html = renderers.renderForm(group, question => `<input data-test-q="${question.number}">`)

  assert.equal((html.match(/practice-form__shared-field/g) || []).length, 1)
  assert.equal((html.match(/,\s*<div class="practice-form__/g) || []).length, 0)
  assert.ok(html.indexOf('data-test-q="1"') < html.indexOf('data-test-q="2"'))
  assert.ok(html.indexOf('data-test-q="2"') < html.indexOf('data-test-q="3"'))
  assert.ok(html.indexOf('data-test-q="3"') < html.indexOf('data-test-q="4"'))
})

test('shared form cluster invariant covers listening data and excludes reading forms', () => {
  const repeatedClusters = []
  const listeningSections = new Set()
  let listeningQuestions = 0
  let readingClusters = 0
  const renderedText = value => String(value || '')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;|&#160;/gi, ' ')
    .replace(/&amp;/gi, '&')
    .replace(/&lt;/gi, '<')
    .replace(/&gt;/gi, '>')
    .replace(/&quot;/gi, '"')
    .replace(/&#39;|&apos;/gi, "'")
    .replace(/\s+/g, ' ')
    .trim()

  const scan = (directory, onGroup) => {
    const fixtureDirectory = path.join(__dirname, '..', 'static', directory)
    for (const filename of fs.readdirSync(fixtureDirectory).filter(name => name.endsWith('.json'))) {
      let book
      try {
        book = JSON.parse(fs.readFileSync(path.join(fixtureDirectory, filename), 'utf8'))
      } catch {
        continue
      }
      for (const [sectionIndex, section] of (book.sections || []).entries()) {
        for (const group of section.groups || []) onGroup(filename, sectionIndex, group)
      }
    }
  }

  scan('listening_tests', (filename, sectionIndex, group) => {
    if (!renderers.isFormGroup(group)) return
    const fields = renderers.formFields(group)
    const clusters = renderers.sharedFormClusters(fields)
    if (!clusters.length) return
    listeningSections.add(`${filename}:${sectionIndex}`)
    const html = renderers.renderForm(
      group,
      question => `<input data-invariant-q="${question.id}">`,
      question => `<span data-invariant-extra="${question.id}"></span>`
    )
    assert.equal(
      (html.match(/practice-form__shared-field/g) || []).length,
      clusters.length,
      `${filename} shared stems should render once`
    )
    for (const cluster of clusters) {
      const blankCount = (cluster.key.match(/【\s*】|\[\s*\]/g) || []).length
      assert.equal(cluster.fields.length, blankCount, `${filename} shared title blank count`)
      assert.ok(cluster.fields.every(field => field.target), `${filename} shared title targets`)
      repeatedClusters.push(`${filename}:Q${cluster.fields[0].question.number}`)
      listeningQuestions += cluster.fields.length
      const outputText = renderedText(html).toLowerCase()
      for (const labelIndex of new Set(cluster.fields.map(field => field.labelIndex).filter(index => index >= 0))) {
        const sourceLabel = cluster.fields.find(field => field.labelIndex === labelIndex).label
          .replace(/^[\s·•\-–—]+/, '')
          .replace(/[:：?？\s]+$/g, '')
          .replace(/\s+/g, ' ')
          .trim()
          .toLowerCase()
        assert.ok(sourceLabel && outputText.includes(sourceLabel), `${filename} shared source label ${sourceLabel} should remain visible`)
      }
      for (const field of cluster.fields) {
        const question = field.question
        assert.equal((html.match(new RegExp(`data-invariant-q="${question.id}"`, 'g')) || []).length, 1)
        assert.equal((html.match(new RegExp(`data-question-id="${question.id}"`, 'g')) || []).length, 1)
        assert.equal((html.match(new RegExp(`data-invariant-extra="${question.id}"`, 'g')) || []).length, 1)
      }
    }
  })

  scan('reading_tests', (_filename, _sectionIndex, group) => {
    if (!renderers.isFormGroup(group)) return
    readingClusters += renderers.sharedFormClusters(renderers.formFields(group)).length
  })

  assert.equal(repeatedClusters.length, 38)
  assert.equal(listeningSections.size, 31)
  assert.equal(listeningQuestions, 100)
  assert.equal(readingClusters, 0)
})

test('adjacent shared clusters retain a shared direct label once in source order', () => {
  const book = JSON.parse(fs.readFileSync(
    path.join(__dirname, '..', 'static', 'listening_tests', 'ielts6_test4.json'),
    'utf8'
  ))
  const group = book.sections[0].groups[0]
  const fields = renderers.formFields(group)
  const clusters = renderers.sharedFormClusters(fields)
  assert.deepEqual(
    clusters.map(cluster => cluster.fields.map(field => Number(field.question.number))),
    [[7, 8], [9, 10]]
  )

  const html = renderers.renderForm(group, question => `<input data-shared-q="${question.number}">`)
  assert.equal((html.match(/Location:/g) || []).length, 1)
  for (let number = 7; number <= 10; number += 1) {
    assert.equal((html.match(new RegExp(`data-shared-q="${number}"`, 'g')) || []).length, 1)
  }
  assert.ok(html.indexOf('Location:') < html.indexOf('data-shared-q="7"'))
  for (let number = 7; number < 10; number += 1) {
    assert.ok(
      html.indexOf(`data-shared-q="${number}"`) < html.indexOf(`data-shared-q="${number + 1}"`),
      `Q${number} should precede Q${number + 1}`
    )
  }
})

test('static facts and contexts never emit one source cell more than once', () => {
  const normalize = value => String(value || '')
    .replace(/&nbsp;|&#160;/gi, ' ')
    .replace(/&amp;/gi, '&')
    .replace(/&lt;/gi, '<')
    .replace(/&gt;/gi, '>')
    .replace(/&quot;/gi, '"')
    .replace(/&#39;|&apos;/gi, "'")
    .replace(/<[^>]+>/g, '')
    .replace(/^[\s·•\-–—]+/, '')
    .replace(/[:：?？\s]+$/g, '')
    .replace(/\s+/g, ' ')
    .trim()
    .toLowerCase()
  const renderedEntries = html => {
    const entries = []
    const pattern = /<div class="practice-form__(section|subheading|line|context)">([\s\S]*?)<\/div>/g
    let match
    while ((match = pattern.exec(html))) {
      const values = match[1] === 'context' ? match[2].split(/\s+·\s+/) : [match[2]]
      values.map(normalize).filter(Boolean).forEach(text => entries.push(text))
    }
    return entries
  }
  const duplicates = []

  for (const directory of ['listening_tests', 'reading_tests']) {
    const fixtureDirectory = path.join(__dirname, '..', 'static', directory)
    for (const filename of fs.readdirSync(fixtureDirectory).filter(name => name.endsWith('.json'))) {
      let book
      try {
        book = JSON.parse(fs.readFileSync(path.join(fixtureDirectory, filename), 'utf8'))
      } catch {
        continue
      }
      for (const [sectionIndex, section] of (book.sections || []).entries()) {
        for (const [groupIndex, group] of (section.groups || []).entries()) {
          if (!renderers.isFormGroup(group)) continue
          const markers = new Set((group.questions || []).map(question => `$${question.id}$`))
          const sourceCounts = new Map()
          for (const cell of renderers.visualCells(group.collect || '')) {
            if (Array.from(markers).some(marker => cell.raw.includes(marker))) continue
            const text = normalize(cell.text)
            if (text) sourceCounts.set(text, (sourceCounts.get(text) || 0) + 1)
          }
          const renderedCounts = new Map()
          for (const text of renderedEntries(renderers.renderForm(group, question => `<input data-test-q="${question.number}">`))) {
            renderedCounts.set(text, (renderedCounts.get(text) || 0) + 1)
          }
          for (const [text, renderedCount] of renderedCounts) {
            const sourceCount = sourceCounts.get(text) || 0
            if (sourceCount > 0 && renderedCount > sourceCount) {
              duplicates.push(`${directory}/${filename} S${sectionIndex + 1} G${groupIndex + 1}: ${text} source=${sourceCount} rendered=${renderedCount}`)
            }
          }
        }
      }
    }
  }

  assert.deepEqual(duplicates, [])
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
