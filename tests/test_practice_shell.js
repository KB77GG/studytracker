const assert = require('node:assert/strict')
const test = require('node:test')

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
  assert.equal(shell.contextUrl({
    sourcePath: '/listening/tests',
    sourceSearchParams: '?status=todo',
    activeTab: 'cambridge-7'
  }, 'http://practice.test'), '/listening/tests?status=todo#cambridge-7')
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
