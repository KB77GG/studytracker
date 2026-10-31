const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')
const vm = require('node:vm')
const ROOT = process.env.PRACTICE_REDO_TEST_ROOT || path.resolve(__dirname, '..')
const { create } = require(path.join(ROOT, 'static/js/practice_redo.js'))

function memoryStorage(entries = {}) {
  const values = new Map(Object.entries(entries))
  return { values, getItem: key => values.has(key) ? values.get(key) : null,
    setItem: (key, value) => values.set(key, String(value)), removeItem: key => values.delete(key) }
}
function fixture(overrides = {}) {
  const storage = overrides.storage || memoryStorage({ answers: '{"1":"old answer"}', flags: '["1"]', notes: 'keep note', highlights: 'keep highlight' })
  const navigations = [], alerts = []
  let confirmations = 0
  const button = { hidden: true, disabled: false, addEventListener(name, handler) { this[name] = handler } }
  const options = { storage, storageKey: 'answers', flagStorageKey: 'flags', button,
    location: { href: 'https://practice.test/listening/test/sample?section=2&task_id=7&token=fixture&practice_return=%2Ftasks#q3', replace: url => navigations.push(url) },
    confirm: () => { confirmations++; return true }, alert: message => alerts.push(message), ...overrides }
  return { storage, options, controller: create(options), button, navigations, alerts, confirmations: () => confirmations }
}
test('cancel leaves answers, notes, flags and navigation unchanged', () => {
  const f = fixture({ confirm: () => false }), before = [...f.storage.values]
  assert.equal(f.controller.restart(), false)
  assert.deepEqual([...f.storage.values], before)
  assert.deepEqual(f.navigations, [])
  assert.equal(f.controller.suppressDraftWrites(), false)
  assert.equal(f.controller.skipRestore(), false)
  assert.equal(f.button.disabled, false)
})
for (const [label, options] of [
  ['exam', { examContext: { exam_id: 1 } }],
  ['expired task', { practiceContext: { task_type: 'assigned_task', read_only: true } }],
  ['submitted specialty', { practiceContext: { task_type: 'question_type_practice', read_only: true } }],
  ['write denial', { practiceContext: { can_write: false } }]
]) test(`${label} cannot clear answers through direct handler calls`, () => {
  const f = fixture(options), before = [...f.storage.values]
  assert.equal(f.button.hidden, true)
  assert.equal(f.button.disabled, true)
  assert.equal(f.controller.restart(), false)
  assert.equal(f.confirmations(), 0)
  assert.deepEqual([...f.storage.values], before)
  assert.deepEqual(f.navigations, [])
})
for (const context of [null, { task_type: 'assigned_task', can_write: true }, { task_type: 'question_type_practice', can_write: true }]) {
  test(`${context?.task_type || 'free practice'} clears only current draft and keeps navigation context`, () => {
    const f = fixture({ practiceContext: context, taskId: context ? '7' : '' })
    assert.equal(f.button.hidden, false)
    assert.equal(f.controller.restart(), true)
    assert.equal(f.storage.getItem('answers'), '{}')
    assert.equal(f.storage.getItem('flags'), '[]')
    assert.equal(f.storage.getItem('notes'), 'keep note')
    assert.equal(f.storage.getItem('highlights'), 'keep highlight')
    assert.equal(f.controller.suppressDraftWrites(), true)
    assert.equal(f.controller.skipRestore(), true)
    const url = new URL(f.navigations[0])
    for (const [key, value] of [['section', '2'], ['task_id', '7'], ['token', 'fixture'], ['practice_return', '/tasks']]) assert.equal(url.searchParams.get(key), value)
    assert.equal(url.hash, '')
    assert.equal(f.controller.restart(), false)
    assert.equal(f.navigations.length, 1)
  })
}
test('reload retains redo marker, permits new draft saves and isolates task/exercise scope', () => {
  const f = fixture({ taskId: '7' })
  f.controller.restart()
  const resumed = create(f.options)
  assert.equal(resumed.skipRestore(), true)
  assert.equal(resumed.suppressDraftWrites(), false)
  assert.equal(create({ ...f.options, taskId: '8' }).skipRestore(), false)
  assert.equal(create({ ...f.options, taskId: '' }).skipRestore(), false)
  assert.equal(create({ ...f.options, storageKey: 'different-section' }).skipRestore(), false)
  resumed.submitted()
  assert.equal(create(f.options).skipRestore(), false)
})
test('marker does not hide submitted result after task becomes read-only', () => {
  const f = fixture({ taskId: '7' })
  f.controller.restart()
  const readOnly = create({ ...f.options, practiceContext: { read_only: true } })
  assert.equal(readOnly.skipRestore(), false)
  assert.equal(readOnly.restart(), false)
})
test('explicit history remains readable without draft writes; redo exits history mode', () => {
  const f = fixture()
  f.controller.restart()
  f.storage.setItem('answers', '{"1":"new draft"}')
  const history = create({ ...f.options, historyAttemptId: '17', location: {
    href: 'https://practice.test/reading/test/sample?passage=2&history_attempt=17&practice_return=%2Fpractice#q2',
    replace: url => f.navigations.push(url) } })
  assert.equal(history.skipRestore(), false)
  assert.equal(history.suppressDraftWrites(), true)
  assert.equal(f.storage.getItem('answers'), '{"1":"new draft"}')
  history.restart()
  const url = new URL(f.navigations.at(-1))
  assert.equal(url.searchParams.has('history_attempt'), false)
  assert.equal(url.searchParams.get('passage'), '2')
  assert.equal(url.searchParams.get('practice_return'), '/practice')
  assert.equal(create(f.options).skipRestore(), true)
})
for (const failedWrite of [1, 2, 3]) test(`storage failure on write ${failedWrite} rolls back and permits retry`, () => {
  const f = fixture(), before = [...f.storage.values], write = f.storage.setItem
  let writes = 0
  f.storage.setItem = (key, value) => { if (++writes === failedWrite) throw new Error('quota unavailable'); return write(key, value) }
  assert.equal(f.controller.restart(), false)
  assert.deepEqual([...f.storage.values].sort(), before.sort())
  assert.equal(f.navigations.length, 0)
  assert.equal(f.alerts.length, 1)
  assert.equal(f.controller.suppressDraftWrites(), false)
  assert.equal(f.controller.skipRestore(), false)
  assert.equal(f.button.disabled, false)
  assert.equal(f.controller.restart(), true)
})
test('pending submission blocks redo until it settles', () => {
  const f = fixture()
  f.controller.setBusy(true)
  assert.equal(f.button.disabled, true)
  assert.equal(f.controller.restart(), false)
  assert.equal(f.confirmations(), 0)
  assert.equal(f.storage.getItem('answers'), '{"1":"old answer"}')
  f.controller.setBusy(false)
  assert.equal(f.button.disabled, false)
  assert.equal(f.controller.restart(), true)
})
function templateFunction(kind, name) {
  const source = fs.readFileSync(path.join(ROOT, `templates/${kind}/test_practice.html`), 'utf8')
  const declaration = new RegExp(`^(?:async )?function ${name}\\(`, 'm').exec(source)
  assert.ok(declaration, `${kind}.${name} exists`)
  const rest = source.slice(declaration.index)
  const next = /\n(?:async )?function \w+\(/.exec(rest)
  assert.ok(next, `${kind}.${name} has a following function`)
  return rest.slice(0, next.index)
}
function pageHarness(kind, options = {}) {
  const f = fixture(options), elements = new Map(), applied = [], requests = [], answers = {}
  const submission = { answers: { '1': 'historical' }, results: [{ q: 1, status: 'correct' }], correct_count: 1, total_count: 1 }
  const noop = () => {}
  const context = vm.createContext({ URLSearchParams, practiceRedo: f.controller,
    practiceContext: options.practiceContext || null, persistenceContext: options.persistenceContext || null,
    examContext: null, historyAttemptId: options.historyAttemptId || '',
    listeningTaskId: '', listeningTaskToken: '', readingTaskId: '', readingTaskToken: '', assignedSectionNumber: 0, assignedPassageNumber: 0,
    storageKey: 'answers', examDraftStorageKey: 'answers', localStorage: f.storage, answers,
    test: { id: 'sample' }, testData: { id: 'sample', passages: [{ id: 'p1' }] },
    currentPassageId: 'p1', currentQuestionId: '1', latestResults: null, startedAt: Date.now(), practiceStartedAt: Date.now(),
    document: { body: { classList: { add: noop, remove: noop } }, getElementById(id) {
      if (!elements.has(id)) elements.set(id, { textContent: '', innerHTML: '', disabled: false }); return elements.get(id)
    }, querySelectorAll: () => [] },
    fetch: async (url, settings) => { requests.push({ url, settings }); return { ok: true, json: async () => ({ ok: true, submission }) } },
    applyAnswerRows: rows => { applied.push(rows); Object.assign(answers, rows) }, answerSnapshot: () => answers,
    applyServerResults: noop, setExperienceMode: noop, resultHtml: () => 'result', openReviewCard: noop, markUnit: noop, allQuestions: () => [],
    renderPassage: () => applied.push({ ...answers }), paintResults: noop, updateSummary: noop, setSyncStatus: noop,
    syncQuestionNav: noop, refreshAnsweredCount: noop, updateExamSavedIndicator: noop,
    practiceShellController: { markSaved: noop, setStatus: noop }, window: { location: { replace: noop } } })
  return { ...f, context, applied, requests, answers, elements, submission }
}
for (const kind of ['listening', 'reading']) {
  const persistName = kind === 'listening' ? 'persistAnswers' : 'persistExamDraft'
  const draftRestoreName = kind === 'listening' ? 'restoreServerAnswers' : 'restoreServerExamDraft'
  test(`${kind}: pagehide after redo cannot write old displayed answers back`, async () => {
    const f = pageHarness(kind)
    f.answers['1'] = 'stale displayed answer'
    f.controller.restart()
    vm.runInContext(templateFunction(kind, persistName), f.context)
    assert.equal(await f.context[persistName]('pagehide'), true)
    assert.equal(f.storage.getItem('answers'), '{}')
    assert.equal(f.requests.length, 0)
  })
  test(`${kind}: history load and pagehide preserve active redo draft`, async () => {
    const f = pageHarness(kind, { historyAttemptId: '17' })
    f.storage.setItem('answers', '{"1":"new draft"}')
    vm.runInContext(templateFunction(kind, 'loadExistingSubmission'), f.context)
    vm.runInContext(templateFunction(kind, persistName), f.context)
    await f.context.loadExistingSubmission()
    assert.equal(f.requests[0].url, '/api/practice/history/attempt/17')
    assert.equal(f.answers['1'], 'historical')
    assert.ok(f.applied.length > 0)
    await f.context[persistName]('pagehide')
    assert.equal(f.storage.getItem('answers'), '{"1":"new draft"}')
    assert.equal(f.requests.length, 1)
  })
  test(`${kind}: refreshed redo skips server draft and submission reads`, async () => {
    const f = pageHarness(kind, { persistenceContext: { draft_url: '/draft' } })
    f.controller.restart()
    f.context.practiceRedo = create(f.options)
    vm.runInContext(templateFunction(kind, 'loadExistingSubmission'), f.context)
    vm.runInContext(templateFunction(kind, draftRestoreName), f.context)
    await f.context.loadExistingSubmission()
    await f.context[draftRestoreName]()
    assert.equal(f.requests.length, 0)
    assert.equal(f.applied.length, 0)
  })
  for (const name of ['loadExistingSubmission', draftRestoreName]) test(`${kind}: late ${name} cannot overwrite redo`, async () => {
    const f = pageHarness(kind, { persistenceContext: { draft_url: '/draft' } })
    let resolve, reads = 0
    const pending = new Promise(done => { resolve = done })
    f.context.fetch = async () => ({ ok: true, json: () => { reads++; return pending } })
    vm.runInContext(templateFunction(kind, name), f.context)
    const load = f.context[name]()
    await new Promise(resolve => setImmediate(resolve))
    assert.equal(reads, 1)
    f.controller.restart()
    resolve({ ok: true, submission: f.submission, answers: { '1': 'late old answer' } })
    await load
    assert.equal(f.applied.length, 0)
    assert.deepEqual(f.answers, {})
    assert.equal(f.storage.getItem('answers'), '{}')
  })
  for (const state of ['synced', 'local-only', 'failed']) test(`${kind}: ${state} submission has correct marker lifecycle`, async () => {
    const f = pageHarness(kind)
    f.controller.restart()
    const resumed = create(f.options)
    f.context.practiceRedo = resumed
    let resolve
    const pending = new Promise(done => { resolve = done })
    f.context.fetch = async () => ({ ok: state !== 'failed', json: () => pending })
    const name = kind === 'listening' ? 'syncListeningTestSubmission' : 'submitAnswers'
    vm.runInContext(templateFunction(kind, name), f.context)
    const submitting = f.context[name]('initial result')
    await new Promise(resolve => setImmediate(resolve))
    assert.equal(f.button.disabled, true)
    assert.equal(resumed.restart(), false)
    assert.equal(resumed.skipRestore(), true)
    resolve({ ok: state !== 'failed', synced: state === 'synced', result: { correct: 1, total: 1, results: [] } })
    await submitting
    assert.equal(resumed.skipRestore(), state !== 'synced')
    assert.equal(f.button.disabled, false)
  })
}
for (const kind of ['listening', 'reading']) {
  const persistName = kind === 'listening' ? 'persistAnswers' : 'persistExamDraft'
  test(`${kind}: new answers after reload save normally and remain protected from old history`, async () => {
    const f = pageHarness(kind)
    f.controller.restart()
    f.context.practiceRedo = create(f.options)
    f.answers['1'] = 'new attempt'
    vm.runInContext(templateFunction(kind, persistName), f.context)
    assert.equal(await f.context[persistName]('local'), true)
    assert.deepEqual(JSON.parse(f.storage.getItem('answers')), { '1': 'new attempt' })
    assert.equal(f.context.practiceRedo.skipRestore(), true)
    assert.equal(f.requests.length, 0)
  })
  test(`${kind}: writable specialty saves the new redo draft to its server endpoint`, async () => {
    const f = pageHarness(kind, {
      practiceContext: { task_type: 'question_type_practice', can_write: true },
      persistenceContext: { draft_url: '/specialty/draft' }
    })
    f.controller.restart()
    f.context.practiceRedo = create(f.options)
    f.answers['1'] = 'new specialty attempt'
    vm.runInContext(templateFunction(kind, persistName), f.context)
    assert.equal(await f.context[persistName]('pagehide'), true)
    assert.equal(f.requests.length, 1)
    assert.equal(f.requests[0].url, '/specialty/draft')
    assert.equal(f.requests[0].settings.method, 'PUT')
    assert.deepEqual(JSON.parse(f.requests[0].settings.body).answers, { '1': 'new specialty attempt' })
    assert.equal(f.context.practiceRedo.skipRestore(), true)
  })
}
