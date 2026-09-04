const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')
const vm = require('node:vm')

const ROOT = path.resolve(__dirname, '..')

function loadPage(subject, response) {
  const pagePath = path.join(
    ROOT,
    'miniprogram',
    'pages',
    'student',
    subject,
    'cambridge',
    'index.js'
  )
  let definition = null
  const calls = {
    modal: null,
    refreshes: 0,
    requests: []
  }
  const sandbox = {
    console,
    Date,
    getApp: () => ({ globalData: { baseUrl: 'https://example.test/api' } }),
    Page: value => { definition = value },
    require: requestPath => {
      if (requestPath.endsWith('utils/request.js')) {
        return {
          request: async (url, options) => {
            calls.requests.push({ url, options })
            return response
          },
          isTaskDateGateError: payload => Boolean(payload && payload.taskDateBlocked)
        }
      }
      if (requestPath.endsWith('utils/practice-table.js')) {
        return { tableLayout: () => ({}) }
      }
      throw new Error(`Unexpected require: ${requestPath}`)
    },
    wx: {
      hideLoading() {},
      pageScrollTo() {},
      showLoading() {},
      showToast() {},
      showModal(options) {
        calls.modal = options
        if (options.complete) options.complete()
      }
    }
  }
  vm.runInNewContext(fs.readFileSync(pagePath, 'utf8'), sandbox, {
    filename: pagePath
  })
  assert.ok(definition, `Page definition missing for ${subject}`)

  const page = Object.assign({}, definition)
  page.data = JSON.parse(JSON.stringify(definition.data))
  Object.assign(page.data, {
    taskId: 4259,
    token: 'test-token',
    test: { id: subject === 'listening' ? 'ielts11_test2' : 'ielts11_test2_reading' },
    progress: { answeredCount: 1, totalCount: 1, percent: 100 },
    answers: { 1: 'answer' },
    startedAt: Date.now() - 1000
  })
  page.setData = function setData(next, callback) {
    Object.assign(this.data, next)
    if (callback) callback()
  }
  page.normalizeAnswerMap = answers => answers || {}
  page.buildReviewState = () => ({ resultMap: {}, wrongKeys: [] })
  page.buildResultDisplay = () => ({ correct: 1, total: 1, accuracy: 100 })
  page.buildProgress = () => ({ answeredCount: 1, totalCount: 1, percent: 100 })
  page.fetchCambridgeTask = async () => { calls.refreshes += 1 }
  return { page, calls }
}

for (const subject of ['listening', 'reading']) {
  test(`${subject} keeps same-day retry available after a successful submit`, async () => {
    const { page } = loadPage(subject, {
      ok: true,
      task: {
        id: 4259,
        status: 'done',
        status_label: '已完成',
        read_only: false,
        can_write: true
      },
      result: { correct: 1, total: 1, accuracy: 100 },
      submission: { answers: { 1: 'answer' } }
    })

    await page.submitAnswers()

    assert.equal(page.data.submitting, false)
    assert.equal(page.data.submitted, true)
    assert.equal(page.data.readOnly, false)
    assert.notEqual(page.data.task.read_only, true)
    assert.equal(page.data.task.can_write, true)
    assert.equal(page.data.dateStatusText, '已完成')
  })

  test(`${subject} explains a date-gate rejection and restores saved results`, async () => {
    const { page, calls } = loadPage(subject, {
      ok: false,
      error: 'task_completed_read_only',
      taskDateBlocked: true,
      message: '该任务已完成，当前仅可查看结果。',
      taskStatusLabel: '已完成'
    })

    await page.submitAnswers()

    assert.equal(page.data.submitting, false)
    assert.equal(page.data.readOnly, true)
    assert.equal(page.data.task.read_only, true)
    assert.equal(page.data.dateStatusText, '已完成')
    assert.equal(calls.modal.title, '当前不可提交')
    assert.equal(calls.modal.content, '该任务已完成，当前仅可查看结果。')
    assert.equal(calls.refreshes, 1)
  })
}
