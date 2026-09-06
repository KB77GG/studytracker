const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')
const vm = require('node:vm')

const ROOT = path.resolve(__dirname, '..')
const template = fs.readFileSync(path.join(ROOT, 'templates/reading/test_practice.html'), 'utf8')

function extractFunction(name, nextName) {
  const start = template.indexOf(`function ${name}(`)
  const end = template.indexOf(`\n\nfunction ${nextName}(`, start)
  assert.notEqual(start, -1, `missing ${name}`)
  assert.notEqual(end, -1, `missing boundary ${nextName}`)
  return template.slice(start, end)
}

test('filtered reading practice keeps the source Passage number in bottom navigation', () => {
  const navigation = { innerHTML: '' }
  const context = {
    document: {
      getElementById(id) {
        assert.equal(id, 'questionNav')
        return navigation
      },
      querySelectorAll() { return [] }
    },
    escapeHtml: value => String(value),
    goToQuestion() {},
    syncQuestionNav() {},
    testData: {
      passages: [{ passage: 3, groups: [{ questions: [{ id: 27, number: 27 }] }] }]
    }
  }

  vm.runInNewContext(
    `${extractFunction('renderQuestionNav', 'syncQuestionNav')}\nrenderQuestionNav();`,
    context
  )

  assert.match(navigation.innerHTML, /aria-label="Passage 3"/)
  assert.match(navigation.innerHTML, />P3<\/span>/)
  assert.doesNotMatch(navigation.innerHTML, />P1<\/span>/)
})

test('manual focus cancels a queued question-navigation focus', () => {
  const frames = []
  const listeners = new Map()
  const focused = []
  const anchor = { scrollIntoView() {} }

  function control(id) {
    return {
      dataset: { qid: id },
      disabled: false,
      addEventListener(name, handler) { listeners.set(`${id}:${name}`, handler) },
      closest() { return this },
      matches() { return true },
      querySelector() { return null },
      focus() {
        focused.push(id)
        listeners.get(`${id}:focusin`)?.()
      }
    }
  }

  const controlA = control('A')
  const controlB = control('B')
  const context = {
    CSS: { escape: value => String(value) },
    PracticeScoring: {},
    currentPassageId: 'p1',
    currentQuestionId: '',
    document: {
      body: { dataset: {} },
      getElementById() { return null },
      querySelector(selector) {
        if (selector === '[data-qid="A"]') return controlA
        if (selector.includes('[data-question-id="A"]')) return anchor
        return null
      },
      querySelectorAll(selector) {
        if (selector === '[data-qid]') return [controlA, controlB]
        return []
      }
    },
    handleAnswerChange() {},
    openReviewCard() {},
    passageForQuestion() { return { id: 'p1' } },
    practiceContext: null,
    requestAnimationFrame(callback) { frames.push(callback) },
    resultMode: false,
    syncQuestionNav() {}
  }

  const source = [
    'let questionNavigationRevision = 0;',
    extractFunction('bindInputs', 'handleAnswerChange'),
    extractFunction('focusQuestionControl', 'goToQuestion'),
    extractFunction('goToQuestion', 'goToAdjacentQuestion'),
    'bindInputs();',
    'goToQuestion("A");'
  ].join('\n')
  vm.runInNewContext(source, context)

  assert.equal(frames.length, 1)
  frames.shift()()
  assert.equal(frames.length, 1)

  focused.push('B')
  listeners.get('B:focusin')()
  frames.shift()()

  assert.deepEqual(focused, ['B'])
})
