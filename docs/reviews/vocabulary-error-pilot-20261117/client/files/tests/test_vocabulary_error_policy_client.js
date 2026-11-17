const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')
const vm = require('node:vm')
const ROOT = path.resolve(__dirname, '..')

function loadPage(name, response = { ok: true, items: [] }) {
    let definition
    const calls = { requests: [], navigations: [] }
    const app = { globalData: { guestMode: false } }
    const filename = path.join(ROOT, 'miniprogram/pages/student', name, 'index.js')
    const sandbox = {
        console, Date, setTimeout, clearTimeout, setInterval, clearInterval,
        Page: value => { definition = value }, getApp: () => app,
        wx: {
            getStorageSync: () => null, setStorageSync() {}, removeStorageSync() {},
            showToast() {}, navigateTo: value => calls.navigations.push(value.url)
        },
        require: source => {
            if (source.endsWith('/request.js')) return { request: async (url, options) => {
                calls.requests.push({ url, options })
                if (response instanceof Error) throw response
                return response
            } }
            if (source.endsWith('/dictation-audio.js')) return { createReliableAudioPlayer: () => ({ destroy() {} }) }
            if (source.endsWith('/subscribe.js')) return { getSubscribeSummary: async () => ({}), requestTemplateSubscribe: async () => ({}) }
            if (source.endsWith('/demo-data.js')) return { buildStudentTasks: () => [] }
            return require(path.resolve(path.dirname(filename), source))
        }
    }
    vm.runInNewContext(fs.readFileSync(filename, 'utf8'), sandbox, { filename })
    const page = Object.assign({}, definition)
    page.data = JSON.parse(JSON.stringify(definition.data))
    page.setData = function (values, done) { Object.assign(this.data, values); if (done) done() }
    page._reviewPageActive = true
    return { page, calls }
}

test('OFF summary retains legacy exact count and hides optional entry', async () => {
    const { page, calls } = loadPage('home', { ok: true, review_due_count: 2406 })
    await page.loadReviewDueCount()
    assert.equal(page.data.reviewDueCount, 2406)
    assert.equal(page.data.reviewPolicyEnabled, false)
    page.goOptionalReview()
    assert.equal(calls.navigations.length, 0)
})

test('optional practice remains accessible after mandatory count reaches zero', async () => {
    const { page, calls } = loadPage('home', { ok: true, policy_enabled: true, review_due_count: 0, optional_available: true, maintenance_remaining: 7 })
    await page.loadReviewDueCount()
    assert.equal(page.data.reviewDueCount, 0)
    assert.equal(page.data.optionalReviewRemaining, 7)
    page.goOptionalReview()
    assert.equal(calls.navigations[0], '/pages/student/vocabulary-review/index?mode=maintenance')
})

test('failed summary clears stale pilot availability and guest cannot open it', async () => {
    const { page, calls } = loadPage('home', new Error('synthetic network failure'))
    page.applyReviewSummary({ ok: true, policy_enabled: true, optional_available: true, maintenance_remaining: 10 })
    page.data.isGuest = true
    page.goOptionalReview()
    assert.equal(calls.navigations.length, 0)
    page.data.isGuest = false
    await page.loadReviewDueCount()
    assert.equal(page.data.reviewPolicyEnabled, false)
    assert.equal(page.data.optionalReviewAvailable, false)
})

test('only explicit maintenance mode ignores task redirect', () => {
    for (const mode of ['maintenance', 'mandatory', 'untrusted-mode']) {
        const { page } = loadPage('vocabulary-review')
        page.fetchSession = () => {}
        page.readPendingSettlement = () => null
        page.onLoad({ mode, returnTaskId: '123' })
        assert.equal(page.returnTaskId, mode === 'maintenance' ? '' : '123')
        assert.equal(page.sessionQuery(), mode === 'maintenance' ? '?mode=maintenance' : '?origin_task_id=123')
    }
})

test('server snapshot controls mode and old payload restores legacy presentation', () => {
    const { page } = loadPage('vocabulary-review')
    page.returnTaskId = '123'
    page.data.returningToTask = true
    page.applyPolicyPresentation({ policy_enabled: true, session_mode: 'maintenance' })
    assert.equal(page.data.reviewMode, 'maintenance')
    assert.equal(page.returnTaskId, '')
    assert.equal(page.data.returningToTask, false)
    assert.equal(page.sessionQuery(), '?mode=maintenance')
    page.applyPolicyPresentation({ ok: true })
    assert.equal(page.data.reviewPolicyEnabled, false)
    assert.equal(page.data.reviewMode, 'mandatory')
    assert.equal(page.sessionQuery(), '')
})

test('empty optional claim keeps optional labels and does not settle or redirect', async () => {
    const { page, calls } = loadPage('vocabulary-review', { ok: true, policy_enabled: true, session_mode: 'maintenance', items: [], status: 'empty' })
    page._requestedReviewMode = 'maintenance'
    await page.fetchSession()
    assert.equal(page.data.empty, true)
    assert.equal(page.data.reviewMode, 'maintenance')
    assert.equal(calls.requests.length, 1)
    assert.equal(calls.requests[0].options.method, undefined)
    assert.equal(calls.navigations.length, 0)
})

test('conflicting active mode waits for a user action and resumes the server mode', async () => {
    const { page, calls } = loadPage('vocabulary-review', { ok: false, error: 'review_other_mode_active', session_mode: 'maintenance' })
    page.returnTaskId = '123'
    await page.fetchSession()
    assert.equal(calls.requests.length, 1)
    assert.equal(page.data.conflictingReviewMode, 'maintenance')
    assert.match(page.data.loadError, /未完成的自选巩固/)
    page.fetchSession = function () { calls.requests.push({ url: this.sessionQuery() }) }
    page.resumeOtherReview()
    assert.equal(calls.requests[1].url, '?mode=maintenance')
    assert.equal(page.returnTaskId, '')
})

test('invalid conflict payload is a normal retryable error, never a mode redirect', async () => {
    const { page, calls } = loadPage('vocabulary-review', { ok: false, error: 'review_other_mode_active', session_mode: '../../evil' })
    await page.fetchSession()
    assert.equal(page.data.conflictingReviewMode, '')
    assert.match(page.data.loadError, /加载失败/)
    page.resumeOtherReview()
    assert.equal(calls.requests.length, 1)
})

test('same word different ability questions survive queue normalization', () => {
    const { page } = loadPage('vocabulary-review')
    const result = page.setReviewQueue([
        { review_item_id: 1, word_id: 7, sense_id: 7, dimension: 'meaning_recall', mode: 'en_to_zh', question_id: 'q1', question: { prompt: { word: 'sample' } } },
        { review_item_id: 2, word_id: 7, sense_id: 7, dimension: 'form_recall', mode: 'zh_to_en', question_id: 'q2', question: { prompt: { meaning: '样本' } } }
    ])
    assert.equal(result.items.length, 2)
})

test('empty continuation clears stale count and session and keeps server policy mode', async () => {
    const { page, calls } = loadPage('vocabulary-review', { ok: true, policy_enabled: true, session_mode: 'mandatory', items: [], remaining_due_count: 0 })
    Object.assign(page.data, { sessionId: 12, sessionToken: 'synthetic', queueToken: 'old', remainingDueCount: 5 })
    await page.continueReview()
    assert.equal(page.data.empty, true)
    assert.equal(page.data.remainingDueCount, 0)
    assert.equal(page.data.sessionId, null)
    assert.equal(page.data.sessionToken, '')
    assert.equal(page.data.queueToken, '')
    assert.equal(page.data.reviewPolicyEnabled, true)
    assert.equal(calls.requests.length, 1)
})

test('new failed fetch clears an earlier cross-mode action', async () => {
    const { page } = loadPage('vocabulary-review', new Error('synthetic failure'))
    page.data.conflictingReviewMode = 'maintenance'
    await page.fetchSession()
    assert.equal(page.data.conflictingReviewMode, '')
    assert.match(page.data.loadError, /加载失败/)
})

test('home displays configured capacities without imposing a second client cap', async () => {
    const { page } = loadPage('home', { ok: true, policy_enabled: true, mandatory_limit: 30, maintenance_limit: 12, maintenance_remaining: 11 })
    await page.loadReviewDueCount()
    assert.equal(page.data.mandatoryReviewLimit, 30)
    assert.equal(page.data.optionalReviewLimit, 12)
    assert.equal(page.data.optionalReviewRemaining, 11)
})
