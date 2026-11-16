// What does the student home page (repository miniprogram/ source) show when
// tasks/today or task-history answers 500 with Werkzeug's HTML error page?
// Same VM harness idea as tests/test_student_home_grace_client.js; nothing is sent anywhere.
const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')

const ROOT = path.resolve(__dirname, '..', '..', '..')
const PAGE_PATH = path.join(ROOT, 'miniprogram', 'pages', 'student', 'home', 'index.js')
const HTML_500 = '<!doctype html>\n<html lang=en>\n<title>500 Internal Server Error</title>\n' +
  '<h1>Internal Server Error</h1>\n<p>The server encountered an internal error and was unable to ' +
  'complete your request. Either the server is overloaded or there is an error in the application.</p>\n'
// utils/request.js resolves non-2xx like this (it does not reject):
const asRequestJsResolves = () => Object.assign({ ok: false, statusCode: 500 }, HTML_500 || {})

function loadPage(responder) {
  let definition = null
  const app = { globalData: { guestMode: false, activeTimer: null, userInfo: null } }
  const toasts = []
  const sandbox = {
    console: { log() {}, warn() {}, error() {} },
    Date, clearInterval, setInterval,
    getApp: () => app,
    Page: value => { definition = value },
    require: requestPath => {
      if (requestPath.endsWith('utils/request.js')) return { request: async url => responder(url) }
      if (requestPath.endsWith('utils/subscribe.js')) {
        return { getSubscribeSummary: async () => ({ state: 'unknown' }), requestTemplateSubscribe: async () => ({}) }
      }
      if (requestPath.endsWith('utils/demo-data.js')) return { buildStudentTasks: () => [] }
      throw new Error(`Unexpected require: ${requestPath}`)
    },
    wx: {
      getStorageSync: () => null, removeStorageSync() {}, setStorageSync() {},
      showModal(options) { toasts.push(options) }, showToast(options) { toasts.push(options) }
    }
  }
  vm.runInNewContext(fs.readFileSync(PAGE_PATH, 'utf8'), sandbox, { filename: PAGE_PATH })
  const page = Object.assign({}, definition)
  page.data = JSON.parse(JSON.stringify(definition.data))
  Object.assign(page.data, { currentDate: '2026-09-05', todayStr: '2026-09-05', isGuest: false })
  page.setData = function setData(next, callback) { Object.assign(this.data, next); if (callback) callback() }
  return { page, toasts }
}

const task = {
  id: 1, date: '2026-09-05', task_name: '合成任务', module: '课后作业', planned_minutes: 20,
  status: 'pending', status_label: '待完成'
}

async function main() {
  let fail = false
  const { page, toasts } = loadPage(url => {
    if (url.includes('/task-history')) {
      return fail ? asRequestJsResolves() : { ok: true, items: [], summary: { wrong_tasks: 3 } }
    }
    return fail ? asRequestJsResolves() : { ok: true, tasks: [task, Object.assign({}, task, { id: 2 })] }
  })
  await page.fetchTasks()
  page.loadReviewTaskCount()
  await new Promise(resolve => setImmediate(resolve))
  const before = { tasks: page.data.tasks.length, reviewTaskCount: page.data.reviewTaskCount }

  fail = true
  await page.fetchTasks()
  page.loadReviewTaskCount()
  await new Promise(resolve => setImmediate(resolve))
  const after = {
    tasks: page.data.tasks.length,
    progressTotal: page.data.progress.total,
    reviewTaskCount: page.data.reviewTaskCount,
    loading: page.data.loading,
    errorOrRetryStateFields: Object.keys(page.data).filter(key => /error|retry|fail/i.test(key)),
    toastsOrModalsShown: toasts.length
  }
  assert.equal(before.tasks, 2)
  console.log(JSON.stringify({ source: 'repository miniprogram/ (not the released package)', before, after_500: after }, null, 2))
}

main()
