const assert = require('node:assert/strict')
const test = require('node:test')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')

const shell = require('../static/js/practice_shell.js')

function storage() {
  const values = new Map()
  return {
    getItem: key => values.has(key) ? values.get(key) : null,
    setItem: (key, value) => values.set(key, String(value)),
    removeItem: key => values.delete(key)
  }
}

function fakeWindow(pathname = '/listening/tests', search = '?book=7') {
  return {
    location: { pathname, search, hash: '#cambridge-7', origin: 'http://practice.test' },
    localStorage: storage(),
    sessionStorage: storage(),
    scrollY: 684,
    document: {
      documentElement: { dataset: { page: '3' } },
      querySelectorAll: () => []
    }
  }
}

test('return context persists the complete list state contract', () => {
  const win = fakeWindow()
  win.localStorage.setItem('listening_student', 'Student A')
  const context = shell.captureListState(win, {
    filters: { status: 'unfinished' },
    targetPath: '/listening/test/ielts7_test2?section=1'
  })

  assert.deepEqual({
    sourcePath: context.sourcePath,
    sourceSearchParams: context.sourceSearchParams,
    studentId: context.studentId,
    activeTab: context.activeTab,
    filters: context.filters,
    page: context.page,
    scrollPosition: context.scrollPosition,
    sourceMode: context.sourceMode,
    moduleExitPath: context.moduleExitPath,
    identityMode: context.identityMode
  }, {
    sourcePath: '/listening/tests',
    sourceSearchParams: '?book=7',
    studentId: 'Student A',
    activeTab: 'cambridge-7',
    filters: { status: 'unfinished' },
    page: 3,
    scrollPosition: 684,
    sourceMode: 'listening_tests',
    moduleExitPath: '/login',
    identityMode: 'guest'
  })
  assert.deepEqual(JSON.parse(win.sessionStorage.getItem(shell.CONTEXT_KEY)), context)
})

test('return labels and stable fallbacks are source-aware', () => {
  assert.equal(shell.returnLabel('task_detail'), '返回任务详情')
  assert.equal(shell.returnLabel('listening_tests'), '返回剑雅听力')
  assert.equal(shell.returnLabel('reading_tests'), '返回剑雅阅读')
  assert.equal(shell.returnLabel('intensive_library'), '返回精听列表')
  assert.equal(shell.sourceModeForPath('/tasks'), 'staff_tasks')
  assert.equal(shell.sourceModeForPath('/student/today'), 'student_today')
  assert.equal(shell.sourceModeForPath('/reading/jijing'), 'reading_jijing')
  assert.equal(shell.sourceModeForPath('/exam/1/session/example/review'), 'mock_exam_review')
  assert.equal(shell.sourceModeForPath('/exam/1/session/example/review/reading'), 'mock_exam_review')
  assert.equal(shell.sourceModeForPath('/exam/1/session/example/reading'), 'mock_exam_process')
  assert.equal(shell.contextUrl({
    sourcePath: '/listening/tests',
    sourceSearchParams: '?status=todo',
    activeTab: 'cambridge-7'
  }, 'http://practice.test'), '/listening/tests?status=todo#cambridge-7')
})

test('review reload ignores a stored return pointing back to itself', () => {
  const win = fakeWindow('/exam/1/session/example/review', '')
  win.location.hash = ''
  shell.captureListState(win)
  const context = shell.resolveContext(win, '/exam/1/session/example/result', 'mock_exam_result')
  assert.equal(shell.contextUrl(context, win.location.origin), '/exam/1/session/example/result')
  assert.equal(shell.returnLabel(context.sourceMode), '返回成绩')
})

test('sprint practice returns to its subject and selected part after a new-tab reload', () => {
  assert.equal(shell.returnLabel('exam_sprint'), '返回考前冲刺')
  assert.equal(shell.sourceModeForPath('/practice/sprint/listening'), 'exam_sprint')
  assert.equal(shell.sourceModeForPath('/practice/sprint/reading'), 'exam_sprint')
  const listWindow = fakeWindow('/practice/sprint/reading', '')
  listWindow.location.hash = '#sprint-2'
  const captured = shell.captureListState(listWindow, {
    targetPath: '/reading/jijing/reading_jijing_5_test_59?passage=2'
  })
  assert.equal(captured.sourceMode, 'exam_sprint')
  assert.equal(shell.contextUrl(captured, listWindow.location.origin), '/practice/sprint/reading#sprint-2')
  const practiceWindow = fakeWindow('/reading/jijing/reading_jijing_5_test_59',
    '?passage=2&practice_return=%2Fpractice%2Fsprint%2Freading%23sprint-2&practice_source=exam_sprint')
  practiceWindow.location.hash = ''
  const restored = shell.resolveContext(practiceWindow, '/reading/jijing', 'reading_jijing')
  assert.equal(shell.contextUrl(restored, practiceWindow.location.origin), '/practice/sprint/reading#sprint-2')
  assert.equal(shell.returnLabel(restored.sourceMode), '返回考前冲刺')
})

test('external task and student entry become the module exit without losing the immediate parent', () => {
  const win = fakeWindow('/student/today', '?date=2026-08-29')
  win.location.hash = ''
  const studentEntry = shell.captureListState(win, {
    identityMode: 'student_account',
    moduleExitUrl: '/student/today',
    targetPath: '/practice/question-types/task/9?token=opaque'
  })
  assert.equal(studentEntry.sourceMode, 'student_today')
  assert.equal(studentEntry.moduleExitPath, '/student/today')
  assert.equal(studentEntry.moduleExitSearchParams, '?date=2026-08-29')
  assert.equal(studentEntry.moduleExitLabel, '返回今日计划')

  win.location.pathname = '/practice/question-types/task/9'
  win.location.search = '?token=opaque'
  const inside = shell.captureListState(win, {
    identityMode: 'student_account',
    moduleExitUrl: '/student/today',
    targetPath: '/practice/question-types/task/9/result?token=opaque'
  })
  assert.equal(inside.sourcePath, '/practice/question-types/task/9')
  assert.equal(inside.moduleExitPath, '/student/today')

  const afterScroll = shell.captureListState(win, {
    identityMode: 'student_account',
    moduleExitUrl: '/student/today'
  })
  const afterClick = shell.captureListState(win, {
    identityMode: 'student_account',
    moduleExitUrl: '/student/today',
    targetPath: '/practice/question-types/task/9/result?token=opaque'
  })
  assert.equal(afterScroll.moduleExitPath, '/student/today')
  assert.equal(afterClick.moduleExitPath, '/student/today')
})

test('explicit navigation query survives a new tab and rejects external targets', () => {
  const win = fakeWindow('/listening/test/ielts10_test1', '?section=1&practice_return=%2Ftasks%3Fstudent_name%3DA&practice_exit=%2Ftasks&practice_source=staff_tasks')
  win.location.hash = ''
  const context = shell.resolveContext(win, '/listening/tests', 'listening_tests', {
    moduleExitUrl: '/',
    moduleExitLabel: '返回工作台'
  })
  assert.equal(shell.contextUrl(context, win.location.origin), '/tasks?student_name=A')
  assert.equal(shell.moduleExitUrl(context, win.location.origin), '/tasks')
  assert.equal(context.sourceMode, 'staff_tasks')

  assert.equal(shell.safeLocalUrl('https://evil.test/steal', win.location.origin, '/practice'), '/practice')
  assert.equal(shell.cleanLocalPath('/listening/tests?practice_return=%2Flogin&book=10', win.location.origin), '/listening/tests?book=10')
})

test('explicit identity keeps the correct module exit label in a new tab', () => {
  const classroom = fakeWindow('/reading/test/ielts10_test1_reading', '?practice_return=%2Fpractice&practice_exit=%2Flogin&practice_source=practice_library&practice_identity=classroom')
  classroom.location.hash = ''
  const classroomContext = shell.resolveContext(classroom, '/reading/tests', 'reading_tests')
  assert.equal(classroomContext.identityMode, 'classroom')
  assert.equal(classroomContext.moduleExitLabel, '退出课堂刷题')

  const staff = fakeWindow('/listening/test/ielts10_test1', '?practice_return=%2Ftasks&practice_exit=%2F&practice_source=staff_tasks&practice_identity=staff')
  staff.location.hash = ''
  const staffContext = shell.resolveContext(staff, '/listening/tests', 'listening_tests')
  assert.equal(staffContext.identityMode, 'staff')
  assert.equal(staffContext.moduleExitLabel, '返回工作台')
})

test('a bookmarked web task falls back to the task list, while mini-program and exam sources stay intact', () => {
  const win = fakeWindow('/reading/test/ielts10_test1', '?task_id=3&token=opaque')
  win.location.hash = ''
  // The SDK can exist on a normal WeChat browser page; that alone is not a mini-program.
  win.wx = { miniProgram: {} }
  const context = shell.resolveContext(win, '/tasks', 'task_detail')
  assert.equal(shell.contextUrl(context, win.location.origin), '/practice#practiceAssignedTasks')
  assert.equal(shell.returnLabel(context.sourceMode), '返回练习中心')

  win.__wxjs_environment = 'miniprogram'
  assert.equal(shell.resolveContext(win, '/tasks', 'task_detail').sourceMode, 'task_detail')
  delete win.__wxjs_environment
  win.navigator = { userAgent: 'MicroMessenger miniProgram' }
  assert.equal(shell.resolveContext(win, '/tasks', 'task_detail').sourceMode, 'task_detail')
  delete win.navigator

  const exam = shell.resolveContext(win, '/exam/1/session/token', 'mock_exam_process')
  assert.equal(shell.contextUrl(exam, win.location.origin), '/exam/1/session/token')
  assert.equal(shell.returnLabel(exam.sourceMode), '返回模考流程')
  win.location.search += '&practice_return=%2Fstudent%2Ftoday&practice_source=student_today'
  const explicit = shell.resolveContext(win, '/tasks', 'task_detail')
  assert.equal(shell.contextUrl(explicit, win.location.origin), '/student/today')
  assert.equal(shell.returnLabel(explicit.sourceMode), '返回今日计划')
})

function eventNode() {
  const handlers = {}
  return {
    dataset: {}, textContent: '', hidden: false,
    addEventListener: (name, callback) => { handlers[name] = callback },
    setAttribute: () => {},
    fire: (name, event = {}) => handlers[name]?.({ preventDefault() {}, ...event })
  }
}

function interactiveWindow() {
  const win = fakeWindow('/reading/test/ielts10_test1', '?task_id=3')
  win.location.hash = ''
  win.location.assign = value => { win.assigned = value }
  const back = eventNode(), status = eventNode(), retry = eventNode()
  const confirm = eventNode(), cancel = eventNode()
  const dialog = {
    shown: 0, open: false,
    showModal() { this.shown++; this.open = true },
    close() { this.open = false },
    querySelector: selector => selector.includes('cancel') ? cancel : confirm
  }
  const documentEvents = {}, windowEvents = {}, timers = new Map()
  let timerId = 0
  win.document.addEventListener = (name, callback) => { documentEvents[name] = callback }
  win.document.querySelectorAll = selector => selector === '[data-practice-back]' ? [back] : []
  win.document.querySelector = selector => selector.includes('save-status') ? status : retry
  win.document.getElementById = () => dialog
  win.history = { state: {}, replaceState() {}, pushState() {} }
  win.addEventListener = (name, callback) => { windowEvents[name] = callback }
  win.setTimeout = callback => { timers.set(++timerId, callback); return timerId }
  win.clearTimeout = id => timers.delete(id)
  return { win, back, status, retry, dialog, confirm, cancel, documentEvents, windowEvents, timers }
}

const settled = () => new Promise(resolve => setImmediate(resolve))

test('opening an untouched task neither claims a save nor blocks returning', async () => {
  const ui = interactiveWindow()
  let saves = 0
  shell.init({
    fallbackMode: 'task_detail', fallbackUrl: '/tasks',
    confirmExit: ({ dirty, saving }) => dirty || saving,
    save: () => { saves++; return true }
  }, ui.win)
  assert.equal(ui.status.textContent, '尚未保存')
  ui.back.fire('click')
  await settled()
  assert.equal(ui.dialog.shown, 0)
  assert.equal(ui.win.assigned, '/practice#practiceAssignedTasks')
  assert.equal(saves, 0)
})

test('only an actual save receives a saved time, while restored state starts as synced', async () => {
  const ui = interactiveWindow()
  const controller = shell.init({ initialSaved: true, save: () => true }, ui.win)
  assert.equal(ui.status.textContent, '已同步')
  assert.notEqual(ui.status.dataset.tone, 'saved')
  controller.markDirty()
  assert.equal(await controller.flush(), true)
  assert.match(ui.status.textContent, /^已保存 \d{2}:\d{2}$/)
  assert.equal(ui.status.dataset.tone, 'saved')
})

test('unsaved answers prompt, failed saving keeps the page, and a successful retry permits return', async () => {
  const ui = interactiveWindow()
  let saveWorks = false
  const controller = shell.init({
    fallbackUrl: '/practice#practiceAssignedTasks', fallbackMode: 'practice_library',
    confirmExit: ({ dirty, saving }) => dirty || saving,
    save: () => saveWorks
  }, ui.win)
  controller.markDirty()
  ui.back.fire('click')
  assert.equal(ui.dialog.shown, 1)
  assert.equal(ui.win.assigned, undefined)
  ui.confirm.fire('click')
  await settled()
  assert.equal(ui.win.assigned, undefined)
  assert.equal(ui.status.dataset.tone, 'error')
  assert.equal(ui.retry.hidden, false)
  saveWorks = true
  ui.retry.fire('click')
  await settled()
  assert.match(ui.status.textContent, /^已保存 \d{2}:\d{2}$/)
  ui.back.fire('click')
  await settled()
  assert.equal(ui.dialog.shown, 1)
  assert.equal(ui.win.assigned, '/practice#practiceAssignedTasks')
})

test('exit guard is evaluated at click time and protects active timing or an in-flight save', async () => {
  const ui = interactiveWindow()
  let timerRunning = false, finishSave
  const controller = shell.init({
    confirmExit: ({ dirty, saving }) => dirty || saving || timerRunning,
    save: () => new Promise(resolve => { finishSave = resolve })
  }, ui.win)
  timerRunning = true
  ui.back.fire('click')
  assert.equal(ui.dialog.shown, 1)
  ui.cancel.fire('click')
  assert.equal(ui.win.assigned, undefined)
  timerRunning = false
  controller.markDirty()
  const pending = controller.flush()
  await settled()
  ui.windowEvents.popstate()
  assert.equal(ui.dialog.shown, 2)
  finishSave(true)
  assert.equal(await pending, true)
})

test('navigation uses changed identity after installation, with explicit options still taking precedence', () => {
  function installed(options = {}) {
    const ui = interactiveWindow()
    ui.win.location.pathname = '/practice'
    ui.win.location.search = ''
    ui.win.PRACTICE_NAVIGATION_DEFAULTS = { identityMode: 'guest' }
    const link = { href: 'http://practice.test/listening/tests', dataset: {}, hasAttribute: () => false }
    ui.win.document.querySelectorAll = selector => selector === 'a[href], [data-href]' ? [link] : []
    shell.installListContext(options, ui.win)
    return { ...ui, link }
  }
  const ui = installed()
  for (const identity of ['verified_student', 'guest']) {
    ui.win.PRACTICE_NAVIGATION_DEFAULTS.identityMode = identity
    ui.documentEvents.click({ target: { closest: () => ui.link }, defaultPrevented: false })
    assert.equal(new URL(ui.link.href).searchParams.get('practice_identity'), identity)
    ui.windowEvents.scroll()
    for (const callback of ui.timers.values()) callback()
    assert.equal(JSON.parse(ui.win.sessionStorage.getItem(shell.CONTEXT_KEY)).identityMode, identity)
  }
  const explicit = installed({ identityMode: 'student_account' })
  explicit.win.PRACTICE_NAVIGATION_DEFAULTS.identityMode = 'verified_student'
  explicit.documentEvents.click({ target: { closest: () => explicit.link }, defaultPrevented: false })
  assert.equal(new URL(explicit.link.href).searchParams.get('practice_identity'), 'student_account')
})

for (const subject of ['listening', 'reading']) {
  test(`${subject} page exit wiring protects real exam timing without treating page load as work`, () => {
    const template = fs.readFileSync(path.join(__dirname, `../templates/${subject}/test_practice.html`), 'utf8')
    const expression = template.match(/confirmExit:\s*([\s\S]*?),\n\s*initialSaved:/)?.[1]
    assert.ok(expression, 'page must supply its live exit policy')
    const context = { practiceContext: { task_id: 3 }, examContext: null }
    const guard = vm.runInNewContext(`(${expression})`, context)
    assert.equal(guard({ dirty: false, saving: false }), false)
    assert.equal(guard({ dirty: true, saving: false }), true)
    assert.equal(guard({ dirty: false, saving: true }), true)
    context.examContext = { started_at: null, deadline_at: null }
    assert.equal(guard({ dirty: false, saving: false }), false)
    context.examContext = { started_at: '2026-11-26T12:00:00Z', deadline_at: '2026-11-26T13:00:00Z' }
    assert.equal(guard({ dirty: false, saving: false }), true)
    context.practiceContext = { read_only: true }
    assert.equal(guard({ dirty: true, saving: true }), false)
  })
}

test('intensive page does not prompt on initial load, but does protect a pending note', () => {
  const template = fs.readFileSync(path.join(__dirname, '../templates/listening/player.html'), 'utf8')
  const expression = template.match(/confirmExit:\s*([\s\S]*?),\n\s*initialSaved:/)?.[1]
  const context = {
    taskReadOnly: false, errorSummaryDirty: false,
    hasUnsubmittedDictationDraft: () => false, hasUnconfirmedFirstAttempt: () => false
  }
  const guard = vm.runInNewContext(`(${expression})`, context)
  assert.equal(guard({ dirty: false, saving: false }), false)
  context.errorSummaryDirty = true
  assert.equal(guard({ dirty: false, saving: false }), true)
  context.taskReadOnly = true
  assert.equal(guard({ dirty: true, saving: false }), false)
})

test('restoring records cannot masquerade as a write or clear newer changes and errors', async () => {
  const ui = interactiveWindow()
  let completeSave
  const controller = shell.init({
    confirmExit: ({ dirty, saving }) => dirty || saving,
    save: () => new Promise(resolve => { completeSave = resolve })
  }, ui.win)
  assert.equal(controller.markRestored(), true)
  assert.equal(ui.status.textContent, '已恢复草稿')
  assert.doesNotMatch(ui.status.textContent, /已保存|\d{2}:\d{2}/)
  controller.markDirty()
  assert.equal(controller.markRestored('已加载记录'), false)
  const pending = controller.flush()
  await settled()
  assert.equal(controller.markRestored('已加载记录'), false)
  completeSave(false)
  assert.equal(await pending, false)
  assert.equal(controller.markRestored('已加载记录'), false)
  assert.equal(ui.status.dataset.tone, 'error')
  ui.back.fire('click')
  assert.equal(ui.dialog.shown, 1)
})

test('a pending first-answer gate blocks both confirmed exit and browser back until recovery', async () => {
  const ui = interactiveWindow()
  let pending = true
  shell.init({
    fallbackUrl: '/practice#practiceAssignedTasks', fallbackMode: 'practice_library',
    confirmExit: () => pending,
    beforeLeave: () => !pending
  }, ui.win)
  ui.back.fire('click')
  ui.confirm.fire('click')
  await settled()
  assert.equal(ui.win.assigned, undefined)
  ui.windowEvents.popstate()
  ui.confirm.fire('click')
  await settled()
  assert.equal(ui.win.assigned, undefined)
  pending = false
  ui.back.fire('click')
  await settled()
  assert.equal(ui.win.assigned, '/practice#practiceAssignedTasks')
})

test('actual intensive guard distinguishes untouched, unsubmitted, pending and saved first answers', () => {
  const template = fs.readFileSync(path.join(__dirname, '../templates/listening/player.html'), 'utf8')
  const helpers = template.slice(template.indexOf('  function hasUnconfirmedFirstAttempt()'), template.indexOf('  practiceShellController = PracticeShell.init('))
  const guardExpression = template.match(/confirmExit:\s*([\s\S]*?),\n\s*initialSaved:/)[1]
  const beforeExpression = template.match(/beforeLeave:\s*([\s\S]*?),\n\s*save:/)[1]
  const cloze = require('../static/js/listening-cloze.js')
  const progress = {}, messages = []
  const context = {
    data: {}, taskReadOnly: false, errorSummaryDirty: false,
    pendingFirstAttempts: new Map(), firstAttemptGates: new Map(),
    dictationDrafts: new Map(), correctionSegments: new Set(),
    getActiveProgressMap: () => progress,
    getSegmentLocations: () => [{ globalIndex: 4, seg: { text: 'synthetic' } }],
    getEffectiveProgress: (rows, key) => rows[key], getPracticeText: seg => seg.text,
    dictationStateKey: id => String(id),
    practiceShellController: { setStatus: text => messages.push(text) }
  }
  vm.createContext(context)
  vm.runInContext(helpers, context)
  const guard = vm.runInContext(`(${guardExpression})`, context)
  const before = vm.runInContext(`(${beforeExpression})`, context)
  const clean = { dirty: false, saving: false }
  assert.equal(guard(clean), false)
  assert.equal(before(), true)
  context.dictationDrafts.set('4:standard', ['unfinished'])
  assert.equal(guard(clean), true, 'typed but unsubmitted answer needs an explicit discard choice')
  assert.equal(before(), true)
  const gate = cloze.createFirstAttemptGate(false)
  context.firstAttemptGates.set('4', gate)
  gate.beginFirstAttempt()
  assert.equal(guard(clean), true)
  assert.equal(before(), false, 'in-flight first answer is not a saved result')
  context.pendingFirstAttempts.set('4', { answers: ['unfinished'] })
  assert.equal(before(), false, 'failed/uncertain first answer still cannot leave')
  assert.match(messages.at(-1), /刷新确认/)
  context.pendingFirstAttempts.clear()
  progress[4] = { is_completed: true }
  assert.equal(guard(clean), false, 'confirmed saved progress is not pending')
  assert.equal(before(), true)
})

for (const subject of ['listening', 'reading']) {
  test(`${subject} local/server restoration reports a read and preserves a newer dirty save state`, async () => {
    const template = fs.readFileSync(path.join(__dirname, `../templates/${subject}/test_practice.html`), 'utf8')
    const localName = subject === 'listening' ? 'restoreAnswers' : 'restoreExamDraft'
    const serverName = subject === 'listening' ? 'restoreServerAnswers' : 'restoreServerExamDraft'
    function extract(name) {
      const at = template.indexOf(`function ${name}(`)
      return template.slice(template.slice(at - 6, at) === 'async ' ? at - 6 : at, template.indexOf('\n}', at) + 2)
    }
    const ui = interactiveWindow()
    const controller = shell.init({ confirmExit: ({ dirty, saving }) => dirty || saving }, ui.win)
    const indicator = { textContent: 'Not saved' }
    let resolveFetch
    const context = {
      practiceContext: null, practiceRedo: { skipRestore: () => false }, historyAttemptId: '',
      persistenceContext: { draft_url: '/synthetic-draft' },
      storageKey: 'draft', examDraftStorageKey: 'draft', localStorage: ui.win.localStorage,
      practiceShellController: controller, answers: {}, applyAnswerRows() {},
      document: { getElementById: () => indicator },
      renderPassage() {}, currentPassageId: 'p1', testData: { passages: [{ id: 'p1' }] },
      updateExamSavedIndicator: text => { indicator.textContent = text },
      fetch: () => new Promise(resolve => { resolveFetch = resolve })
    }
    vm.createContext(context)
    vm.runInContext(extract(localName) + '\n' + extract(serverName), context)
    context.localStorage.setItem('draft', JSON.stringify({ q: '' }))
    context[localName]()
    assert.equal(ui.status.textContent, '尚未保存', 'empty draft does not imply prior work')
    context.localStorage.setItem('draft', JSON.stringify({ q: 'previous answer' }))
    context[localName]()
    assert.equal(ui.status.textContent, '已恢复草稿')
    assert.equal(indicator.textContent, 'Restored')
    const pending = context[serverName]()
    controller.markDirty()
    indicator.textContent = 'Saving…'
    resolveFetch({ ok: true, json: async () => ({ ok: true, answers: { q: 'server answer' } }) })
    await pending
    assert.equal(ui.status.textContent, '保存中')
    assert.equal(indicator.textContent, 'Saving…')
    ui.back.fire('click')
    assert.equal(ui.dialog.shown, 1, 'a late restore did not clear the newer dirty flag')
  })
}

test('intensive note storage failure remains unsaved and a later successful retry can save', () => {
  const template = fs.readFileSync(path.join(__dirname, '../templates/listening/player.html'), 'utf8')
  function extract(name) {
    const at = template.indexOf(`  function ${name}(`)
    return template.slice(at, template.indexOf('\n  }', at) + 4)
  }
  let fail = true, saved = 0
  const context = {
    taskReadOnly: false, errorSummaryDirty: true, errorSummaries: { 0: 'old' },
    document: { getElementById: () => ({ value: 'new note' }) },
    getGlobalSegmentIndex: () => 0, getErrorSummaryStorageKey: () => 'notes',
    localStorage: { setItem: () => { if (fail) throw Error('quota') } },
    console: { warn() {} }, setErrorSummaryStatus() {},
    practiceShellController: { setStatus() {}, markSaved: () => saved++ }
  }
  vm.createContext(context)
  vm.runInContext(extract('saveErrorSummaries') + '\n' + extract('persistCurrentErrorSummary'), context)
  assert.equal(context.persistCurrentErrorSummary(true), false)
  assert.equal(context.errorSummaryDirty, true)
  assert.equal(context.errorSummaries[0], 'old')
  assert.equal(saved, 0)
  fail = false
  assert.equal(context.persistCurrentErrorSummary(false), true)
  assert.equal(context.errorSummaryDirty, false)
  assert.equal(context.errorSummaries[0], 'new note')
  assert.equal(saved, 1)
})

function hubWindow(pathname = '/reading/tests', search = '', hash = '') {
  const ui = interactiveWindow()
  Object.assign(ui.win.location, { pathname, search, hash })
  const marker = { dataset: { practiceHub: pathname === '/practice' ? 'root' : 'section' } }
  const back = eventNode(), exit = eventNode(), brand = eventNode()
  back.dataset.practiceModuleBack = ''
  back.href = '/practice'
  exit.dataset.practiceModuleExit = ''
  exit.href = '/login'
  brand.dataset.practiceHome = ''
  brand.href = '/practice'
  brand.textContent = 'Sage Path'
  for (const node of [back, exit, brand]) node.hasAttribute = () => false
  ui.win.document.querySelector = selector => selector === '[data-practice-hub]' ? marker : null
  ui.win.document.querySelectorAll = selector => ({
    '[data-practice-module-back]': [back], '[data-practice-module-exit]': [exit],
    'a[href], [data-href]': [brand, back, exit]
  })[selector] || []
  ui.win.requestAnimationFrame = callback => callback()
  ui.win.scrollTo = (_x, y) => { ui.win.scrollY = y }
  return { ...ui, back, exit, brand, marker }
}

test('catalog back uses the incoming sprint context for its label, href, click and browser back', () => {
  const query = '?practice_return=%2Fpractice%2Fsprint%2Freading%23sprint-2&practice_source=exam_sprint&practice_exit=%2Flogin&practice_identity=verified_student'
  for (const browserBack of [false, true]) {
    const ui = hubWindow('/reading/tests', query)
    const { context } = shell.installHub({}, ui.win)
    assert.equal(ui.brand.textContent, 'Sage Path')
    assert.equal(ui.back.textContent, '← 返回考前冲刺')
    assert.equal(ui.back.href, '/practice/sprint/reading#sprint-2')
    assert.equal(context.identityMode, 'verified_student')
    if (browserBack) ui.windowEvents.popstate()
    else ui.back.fire('click')
    assert.equal(ui.win.assigned, '/practice/sprint/reading#sprint-2')
    assert.equal(JSON.parse(ui.win.sessionStorage.getItem(shell.CONTEXT_KEY)).returning, true)
  }
})

test('catalog return infers a missing source mode and rejects a self-return bookmark', () => {
  const sprint = hubWindow('/reading/tests', '?practice_return=%2Fpractice%2Fsprint%2Freading')
  shell.installHub({}, sprint.win)
  assert.equal(sprint.back.textContent, '← 返回考前冲刺')
  const self = hubWindow('/reading/tests', '?practice_return=%2Freading%2Ftests%23book-10&practice_source=reading_tests')
  shell.installHub({}, self.win)
  assert.equal(self.back.href, '/practice')
  assert.equal(self.back.textContent, '← 返回练习中心')
  const root = hubWindow('/practice')
  shell.installHub({}, root.win)
  assert.equal(root.back.hidden, true)
})

test('return, exit and home links do not overwrite the incoming parent; main navigation to the center stays clean', () => {
  const ui = hubWindow('/reading/tests', '?practice_return=%2Fpractice%2Fsprint%2Freading&practice_source=exam_sprint')
  shell.installListContext({}, ui.win)
  shell.installHub({}, ui.win)
  const center = { href: 'http://practice.test/practice#practiceIdentity', dataset: { practiceNav: '' }, hasAttribute: () => false }
  const samePage = { href: 'http://practice.test/reading/tests#cambridge-10', dataset: {}, hasAttribute: () => false }
  for (const link of [ui.brand, ui.back, ui.exit, center, samePage]) {
    const before = link.href
    ui.documentEvents.click({ target: { closest: () => link }, defaultPrevented: false })
    assert.equal(link.href, before)
    assert.equal(ui.win.sessionStorage.getItem(shell.CONTEXT_KEY), null)
  }
})

test('intensive entry participates in the module and sibling main navigation captures its immediate source', () => {
  assert.equal(shell.isPracticeModulePath('/practices'), true)
  const ui = hubWindow('/practice/sprint/reading', '', '#sprint-3')
  ui.win.PRACTICE_NAVIGATION_DEFAULTS = { identityMode: 'verified_student' }
  shell.installListContext({}, ui.win)
  for (const path of ['/practices', '/reading/tests']) {
    const link = { href: `http://practice.test${path}`, dataset: { practiceNav: '' }, hasAttribute: () => false }
    ui.documentEvents.click({ target: { closest: () => link }, defaultPrevented: false })
    const target = new URL(link.href)
    assert.equal(target.searchParams.get('practice_return'), '/practice/sprint/reading#sprint-3')
    assert.equal(target.searchParams.get('practice_source'), 'exam_sprint')
    assert.equal(target.searchParams.get('practice_identity'), 'verified_student')
    assert.equal(target.searchParams.get('practice_exit'), '/login')
  }
})

test('a catalog opened in a new tab preserves its external module exit on the next navigation', () => {
  const ui = hubWindow('/reading/tests', '?practice_return=%2Fpractice&practice_exit=%2Ftasks%3Ftab%3Dreading&practice_identity=staff')
  ui.win.PRACTICE_NAVIGATION_DEFAULTS = { identityMode: 'staff', moduleExitUrl: '/', moduleExitLabel: '返回工作台' }
  const captured = shell.captureListState(ui.win, { targetPath: '/reading/test/ielts10_test1' })
  assert.equal(shell.moduleExitUrl(captured, ui.win.location.origin), '/tasks?tab=reading')
  assert.equal(captured.moduleExitLabel, '返回任务中心')
  assert.equal(captured.identityMode, 'staff')
})

test('sprint → catalog → detail → catalog retains the catalog parent and list position', async () => {
  const catalog = hubWindow('/reading/tests', '?practice_return=%2Fpractice%2Fsprint%2Freading%23sprint-2&practice_source=exam_sprint', '#cambridge-10')
  shell.installHub({}, catalog.win)
  shell.captureListState(catalog.win, { targetPath: '/reading/test/ielts10_test1', filters: { status: 'todo' } })

  const detail = interactiveWindow()
  detail.win.location.search = ''
  detail.win.sessionStorage = catalog.win.sessionStorage
  const controller = shell.init({ fallbackUrl: '/reading/tests', fallbackMode: 'reading_tests' }, detail.win)
  assert.equal(controller.context.sourceMode, 'reading_tests')
  await controller.leave()
  assert.equal(detail.win.assigned, '/reading/tests#cambridge-10')

  const returned = hubWindow('/reading/tests', '', '#cambridge-10')
  returned.win.sessionStorage = catalog.win.sessionStorage
  shell.installListContext({}, returned.win)
  shell.installHub({}, returned.win)
  assert.equal(returned.win.scrollY, 684)
  assert.equal(returned.back.textContent, '← 返回考前冲刺')
  assert.equal(returned.back.href, '/practice/sprint/reading#sprint-2')
  returned.back.fire('click')
  assert.equal(returned.win.assigned, '/practice/sprint/reading#sprint-2')
})

test('an unrelated fresh catalog visit does not reuse an old parent and modified clicks keep native navigation', () => {
  const first = hubWindow('/reading/tests', '?practice_return=%2Fpractice%2Fsprint%2Freading&practice_source=exam_sprint')
  shell.installHub({}, first.win)
  const fresh = hubWindow('/reading/tests')
  fresh.win.sessionStorage = first.win.sessionStorage
  shell.installHub({}, fresh.win)
  assert.equal(fresh.back.href, '/practice')
  first.back.fire('click', { ctrlKey: true })
  assert.equal(first.win.assigned, undefined)
  assert.equal(first.back.href, '/practice/sprint/reading')
})


function enterHub(previous, path) {
  shell.navigate(path, {}, previous.win)
  const target = new URL(previous.win.assigned)
  const next = hubWindow(target.pathname, target.search, target.hash)
  next.win.sessionStorage = previous.win.sessionStorage
  shell.installHub({}, next.win)
  return next
}

test('listening → reading → listening truncates the revisited parent instead of looping on Back', () => {
  const listening = hubWindow('/listening/tests')
  shell.installHub({}, listening.win)
  const reading = enterHub(listening, '/reading/tests')
  assert.equal(reading.back.href, '/listening/tests')
  const revisited = enterHub(reading, '/listening/tests')
  assert.equal(revisited.back.href, '/practice')
  assert.equal(revisited.back.textContent, '← 返回练习中心')
  revisited.back.fire('click')
  assert.equal(revisited.win.assigned, '/practice')

  // The other directory can still return to listening, whose parent is now stable.
  const readingAgain = enterHub(revisited, '/reading/tests')
  assert.equal(readingAgain.back.href, '/listening/tests')
  readingAgain.back.fire('click')
  const returned = hubWindow('/listening/tests')
  returned.win.sessionStorage = readingAgain.win.sessionStorage
  shell.installHub({}, returned.win)
  returned.windowEvents.popstate()
  assert.equal(returned.win.assigned, '/practice')
})

test('a three-catalog loop keeps the original sprint parent and remains acyclic on return', () => {
  const sprint = hubWindow('/practice/sprint/reading', '', '#sprint-2')
  shell.installHub({}, sprint.win)
  const listening = enterHub(sprint, '/listening/tests')
  const reading = enterHub(listening, '/reading/tests')
  const writing = enterHub(reading, '/writing/')
  const revisited = enterHub(writing, '/listening/tests')
  assert.equal(revisited.back.href, '/practice/sprint/reading#sprint-2')
  assert.equal(revisited.back.textContent, '← 返回考前冲刺')
  revisited.back.fire('click')
  const returned = hubWindow('/practice/sprint/reading', '', '#sprint-2')
  returned.win.sessionStorage = revisited.win.sessionStorage
  shell.installHub({}, returned.win)
  assert.equal(returned.back.href, '/practice')
  returned.back.fire('click')
  assert.equal(returned.win.assigned, '/practice')
})
