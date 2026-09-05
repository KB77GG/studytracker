const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')
const vm = require('node:vm')

const ROOT = path.resolve(__dirname, '..')
const PAGE_PATH = path.join(
  ROOT,
  'miniprogram',
  'pages',
  'student',
  'home',
  'index.js'
)

function loadPage(response) {
  let definition = null
  const app = { globalData: { guestMode: false, activeTimer: null, userInfo: null } }
  const calls = { requests: [] }
  const sandbox = {
    console,
    Date,
    clearInterval,
    setInterval,
    getApp: () => app,
    Page: value => { definition = value },
    require: requestPath => {
      if (requestPath.endsWith('utils/request.js')) {
        return {
          request: async url => {
            calls.requests.push(url)
            return response
          }
        }
      }
      if (requestPath.endsWith('utils/subscribe.js')) {
        return {
          getSubscribeSummary: async () => ({ state: 'unknown' }),
          requestTemplateSubscribe: async () => ({})
        }
      }
      if (requestPath.endsWith('utils/demo-data.js')) {
        return { buildStudentTasks: () => [] }
      }
      throw new Error(`Unexpected require: ${requestPath}`)
    },
    wx: {
      getStorageSync: () => null,
      removeStorageSync() {},
      setStorageSync() {},
      showModal() {},
      showToast() {}
    }
  }
  vm.runInNewContext(fs.readFileSync(PAGE_PATH, 'utf8'), sandbox, {
    filename: PAGE_PATH
  })
  assert.ok(definition, 'student home Page definition missing')

  const page = Object.assign({}, definition)
  page.data = JSON.parse(JSON.stringify(definition.data))
  Object.assign(page.data, {
    currentDate: '2026-09-05',
    todayStr: '2026-09-05',
    isGuest: false
  })
  page.setData = function setData(next, callback) {
    Object.assign(this.data, next)
    if (callback) callback()
  }
  return { page, calls }
}

test('home keeps yesterday attribution and exposes its grace-period entry', async () => {
  const response = {
    ok: true,
    tasks: [],
    grace_period: {
      active: true,
      task_date: '2026-09-04',
      pending_count: 2,
      cutoff_time: '03:00'
    }
  }
  const { page } = loadPage(response)

  await page.fetchTasks()

  assert.deepEqual(
    JSON.parse(JSON.stringify(page.data.gracePeriod)),
    {
      active: true,
      taskDate: '2026-09-04',
      pendingCount: 2,
      cutoffTime: '03:00'
    }
  )
  let selectedDate = null
  page.applyDate = date => { selectedDate = date }
  page.openGraceTasks()
  assert.equal(selectedDate, '2026-09-04')
})

test('home labels an open after-midnight task without changing its date', () => {
  const { page } = loadPage({ ok: true, tasks: [] })
  const gracePeriod = page.normalizeGracePeriod({
    active: true,
    task_date: '2026-09-04',
    pending_count: 1,
    cutoff_time: '03:00'
  })
  page.data.currentDate = '2026-09-04'

  page.applyTaskData([
    {
      id: 94,
      date: '2026-09-04',
      task_name: '词汇 - 第 4 组',
      module: '词汇',
      planned_minutes: 20,
      actual_seconds: 0,
      status: 'pending',
      status_label: '待完成',
      can_write: true,
      read_only: false,
      is_grace_period: true,
      task_cutoff_at: '2026-09-05T03:00:00+08:00'
    }
  ], gracePeriod)

  assert.equal(page.data.tasks[0].date, '2026-09-04')
  assert.equal(page.data.tasks[0].isGracePeriod, true)
  assert.equal(page.data.tasks[0].readOnly, false)
  assert.equal(page.data.taskGroupTitle, '昨日任务 · 宽限至 03:00')
  assert.equal(page.data.progressLabel, '昨日任务完成度')
})

test('home template always explains the next-day three-am cutoff', () => {
  const template = fs.readFileSync(
    path.join(
      ROOT,
      'miniprogram',
      'pages',
      'student',
      'home',
      'index.wxml'
    ),
    'utf8'
  )
  assert.match(template, /温馨提示/)
  assert.match(template, /次日凌晨 3:00 前完成/)
  assert.match(template, /无法重做或补做/)
  assert.match(template, /bindtap="openGraceTasks"/)
})
