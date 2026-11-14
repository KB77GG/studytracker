const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const test = require('node:test')
const {
    groupHomeworkData,
    requiresRecipientCheck,
    groupResultMessage,
    createGroupHomeworkMethods
} = require('../miniprogram/utils/teacher-group-homework.js')

const members = ['学生甲', '学生乙', '学生丙'].map((student_name, index) => ({
    student_name, profile_id: index + 1, status: 'ready', has_wechat_binding: index !== 1
}))
const schedule = {
    schedule_id: '17', schedule_uid: 'id:17', student_id: '88',
    student_name: '学生甲/学生乙/学生丙', schedule_date: '2026-11-14', teacher_id: '4'
}
const preview = { ok: true, is_group: true, can_assign: true, members, roster_token: 'roster-a' }
const items = [
    { source_type: 'custom', detail: '练习一', planned_minutes: 20 },
    { source_type: 'custom', detail: '练习二', planned_minutes: 30 }
]
const result = {
    ok: true, member_count: 3, task_count: 6, push_sent: 4,
    tasks: members.flatMap(member => items.map((item, index) => ({
        id: member.profile_id * 10 + index,
        student_name: member.student_name,
        detail: item.detail
    }))),
    recipients: members.map(member => ({
        ...member,
        push_errors: member.has_wechat_binding ? [] : ['no_student_openid', 'no_student_openid']
    }))
}

function setupUi(confirm = true, storage = new Map()) {
    const modals = []
    const toasts = []
    global.wx = {
        showModal(options) { modals.push(options); if (options.success) options.success({ confirm }) },
        showToast(options) { toasts.push(options) },
        showLoading() {}, hideLoading() {},
        getStorageSync(key) { return storage.get(key) },
        setStorageSync(key, value) { storage.set(key, value) },
        removeStorageSync(key) { storage.delete(key) }
    }
    return { modals, toasts }
}

function pageFor(request) {
    const page = {
        ...createGroupHomeworkMethods(request),
        data: {
            ...structuredClone(groupHomeworkData),
            schedule: { ...schedule }, form: { date: '2026-11-15', category: '英语', note: '独立完成' },
            recipientMembers: structuredClone(members), isGroupHomework: true, rosterToken: 'roster-a',
            existingTasks: [], saving: false
        },
        setData(values) { Object.assign(this.data, values) },
        normalizeExistingTask(task) { return task },
        buildQuickPracticePayload() { return {} },
        async fetchExistingHomework() { this.existingFetches = (this.existingFetches || 0) + 1 }
    }
    return page
}

test('check scheduled entries and scheduler slash separators without splitting personal comma names', () => {
    assert.equal(requiresRecipientCheck({ student_name: '个人学生' }), false)
    assert.equal(requiresRecipientCheck({ schedule_id: '1' }), true)
    assert.equal(requiresRecipientCheck({ schedule_uid: 'hash:a' }), true)
    assert.equal(requiresRecipientCheck({ student_name: 'Smith, John' }), false)
    for (const separator of ['/', '／']) {
        assert.equal(requiresRecipientCheck({ student_name: `甲${separator}乙` }), true)
    }
})

test('complete roster allows all three, even one without a reminder binding', async () => {
    const calls = []
    const page = pageFor(async url => { calls.push(url); return preview })
    assert.equal(await page.loadHomeworkRecipients(), true)
    assert.equal(page.data.recipientsBlocked, false)
    assert.equal(page.data.recipientMembers.length, 3)
    assert.match(page.data.recipientMembers[1].statusLabel, /未绑定微信提醒/)
    assert.match(calls[0], /schedule_date=2026-11-14/)
    assert.equal(page.existingFetches, 1)
})

test('missing member blocks whole class without silently filtering anyone', async () => {
    const page = pageFor(async () => ({
        ...preview, can_assign: false, roster_token: '',
        members: members.map((member, index) => index === 1 ? { ...member, profile_id: null, status: 'missing' } : member)
    }))
    assert.equal(await page.loadHomeworkRecipients(), false)
    assert.equal(page.data.recipientsBlocked, true)
    assert.equal(page.data.recipientMembers.length, 3)
    assert.equal(page.existingFetches, undefined)
    assert.equal(page.data.recipientMembers[1].statusLabel, '缺少个人档案')
})

test('ambiguous member is explicit and blocks class submission', async () => {
    const page = pageFor(async () => ({ ...preview, can_assign: false, members: [{ ...members[0], status: 'ambiguous', profile_id: null }] }))
    await page.loadHomeworkRecipients()
    assert.equal(page.data.recipientsBlocked, true)
    assert.equal(page.data.recipientMembers[0].statusLabel, '同名档案待核实')
})

test('preview transport or API failure never falls back to ordinary single-person list', async () => {
    for (const handler of [async () => { throw Error('offline') }, async () => ({ ok: false, error: 'forbidden_schedule' })]) {
        const page = pageFor(handler)
        assert.equal(await page.loadHomeworkRecipients(), false)
        assert.equal(page.data.recipientsBlocked, true)
        assert.ok(page.data.recipientError)
        assert.equal(page.existingFetches, undefined)
    }
})

test('single personal entry without a schedule preserves legacy path', async () => {
    const page = pageFor(async () => { throw Error('must not request roster') })
    page.data.schedule = { student_name: '个人学生', student_id: 12 }
    await page.loadHomeworkRecipients()
    assert.equal(page.data.recipientsRequired, false)
    assert.equal(page.data.recipientsBlocked, false)
    assert.equal(page.existingFetches, 1)
})

test('server-confirmed singleton is not submitted through group endpoint', async () => {
    const page = pageFor(async () => ({ ...preview, is_group: false, members: [members[0]] }))
    await page.loadHomeworkRecipients()
    assert.equal(page.data.isGroupHomework, false)
    assert.equal(page.data.recipientsBlocked, false)
})

test('whole class and multiple items are one request with explicit recipients and confirmation', async () => {
    const ui = setupUi()
    const calls = []
    const page = pageFor(async (url, options) => { calls.push({ url, options }); return result })
    await page.submitGroupHomework(items)
    assert.equal(calls.length, 1)
    assert.equal(calls[0].url, '/miniprogram/teacher/homework/group')
    assert.deepEqual(calls[0].options.data.recipient_profile_ids, [1, 2, 3])
    assert.equal(calls[0].options.data.items.length, 2)
    assert.equal(calls[0].options.data.items[1].date, '2026-11-15')
    assert.equal(calls[0].options.data.items[1].note, '独立完成')
    assert.match(ui.modals[0].content, /3 位学生分别布置 2 项/)
    assert.match(ui.modals[1].content, /6 项作业已保存/)
    assert.match(ui.modals[1].content, /4\/6 条/)
    assert.match(ui.modals[1].content, /学生乙：未绑定微信/)
    assert.equal(page.data.createdTasks.length, 6)
    assert.equal(page.data.saving, false)
})

test('confirmation cancellation, roster blockers, and saving guards send nothing', async () => {
    setupUi(false)
    const page = pageFor(async () => { throw Error('must not submit') })
    await page.submitGroupHomework(items)
    assert.equal(page._groupSubmission, undefined)
    for (const key of ['saving', 'recipientsBlocked', 'recipientsLoading']) {
        page.data[key] = true
        await page.submitGroupHomework(items)
        page.data[key] = false
    }
})

test('network retry with refreshed token uses same idempotency key and same complete payload', async () => {
    setupUi()
    const keys = []
    const page = pageFor(async (url, options) => {
        keys.push(options.data.idempotency_key)
        if (keys.length === 1) throw Error('response lost after save')
        return { ...result, replayed: true, push_sent: 0 }
    })
    await page.submitGroupHomework(items)
    page.data.rosterToken = 'refreshed-token'
    await page.submitGroupHomework(items)
    assert.equal(keys.length, 2)
    assert.equal(keys[0], keys[1])
})

test('changed assignment content receives a new idempotency key', async () => {
    setupUi()
    const keys = []
    const page = pageFor(async (url, options) => { keys.push(options.data.idempotency_key); return result })
    await page.submitGroupHomework(items)
    page.data.form.date = '2026-11-16'
    await page.submitGroupHomework(items)
    assert.notEqual(keys[0], keys[1])
})

test('pending network retry survives closing and reopening page, then clears confirmed receipt', async () => {
    const storage = new Map([['userInfo', { id: 91 }]])
    setupUi(true, storage)
    const keys = []
    const first = pageFor(async (url, options) => { keys.push(options.data.idempotency_key); throw Error('offline') })
    await first.submitGroupHomework(items)
    const pending = storage.get('teacherGroupHomeworkPending:91:17')
    assert.equal(pending.key, keys[0])
    assert.doesNotMatch(pending.fingerprint, /roster_token|practice_context_token/)
    const reopened = pageFor(async (url, options) => { keys.push(options.data.idempotency_key); return { ...result, replayed: true } })
    reopened.data.rosterToken = 'new-roster-after-reopen'
    await reopened.submitGroupHomework(items)
    assert.equal(keys[0], keys[1])
    assert.equal(storage.has('teacherGroupHomeworkPending:91:17'), false)
})

test('pending submissions are isolated between teacher accounts', async () => {
    const storage = new Map([['userInfo', { id: 91 }]])
    setupUi(true, storage)
    const keys = []
    const request = async (url, options) => { keys.push(options.data.idempotency_key); throw Error('offline') }
    await pageFor(request).submitGroupHomework(items)
    storage.set('userInfo', { id: 92 })
    await pageFor(request).submitGroupHomework(items)
    assert.notEqual(keys[0], keys[1])
    assert.ok(storage.has('teacherGroupHomeworkPending:91:17'))
    assert.ok(storage.has('teacherGroupHomeworkPending:92:17'))
})

test('replayed save never claims reminders were resent', () => {
    const message = groupResultMessage({ ...result, replayed: true, push_sent: 0 })
    assert.match(message, /没有重复布置或再次发送提醒/)
    assert.doesNotMatch(message, /微信提醒已发送/)
})

test('expired roster blocks another submission until refreshed, without needing members in error', async () => {
    setupUi()
    let calls = 0
    const page = pageFor(async () => { calls += 1; return { ok: false, error: 'roster_expired' } })
    await page.submitGroupHomework(items)
    assert.equal(page.data.recipientsBlocked, true)
    assert.match(page.data.recipientError, /刷新名单/)
    await page.submitGroupHomework(items)
    assert.equal(calls, 1)
})

test('group history uses checked schedule, token and existing recent scope', async () => {
    const calls = []
    const page = pageFor(async url => { calls.push(url); return { ok: true, tasks: result.tasks } })
    await page.fetchGroupHomework()
    assert.match(calls[0], /\/homework\/group\?/)
    assert.match(calls[0], /roster_token=roster-a/)
    assert.match(calls[0], /scope=recent/)
    assert.equal(page.data.existingTasks[2].student_name, '学生乙')
})

function loadRealPage(request) {
    let definition
    const filename = path.join(__dirname, '../miniprogram/pages/teacher/homework/index.js')
    vm.runInNewContext(fs.readFileSync(filename, 'utf8'), {
        Page(value) { definition = value },
        require(moduleName) {
            if (moduleName.endsWith('/request.js')) return { request }
            return require(path.resolve(path.dirname(filename), moduleName))
        },
        wx: global.wx,
        console
    }, { filename })
    const page = { ...definition, data: structuredClone(definition.data) }
    page.setData = values => Object.assign(page.data, values)
    return page
}

test('real page blocks unresolved roster before any ordinary POST', async () => {
    setupUi()
    let calls = 0
    const page = loadRealPage(async () => { calls += 1 })
    page.data.recipientsBlocked = true
    await page.submitHomework()
    assert.equal(calls, 0)
})

test('real page hands all selected items to one group submission rather than legacy per-item POST', async () => {
    setupUi()
    const page = loadRealPage(async () => { throw Error('legacy POST must not be reached') })
    page.data.isGroupHomework = true
    page.buildSubmitItems = () => items
    page.hasPracticeSelection = () => true
    let received
    page.submitGroupHomework = async values => { received = values }
    await page.submitHomework()
    assert.equal(received, items)
})

test('real page sends group edit through group PATCH and names the individual target', async () => {
    setupUi()
    const calls = []
    const page = loadRealPage(async (url, options) => { calls.push({ url, options }); return { ok: true, task: { id: 9 } } })
    Object.assign(page.data, {
        isGroupHomework: true, recipientMembers: members, rosterToken: 'roster-a',
        schedule, editingTaskId: 9, editingStudentName: '学生乙',
        form: { date: '2026-11-15', category: '英语', note: '' }
    })
    page.buildEditSubmitItem = () => items[0]
    page.fetchExistingHomework = async () => {}
    await page.updateExistingHomework()
    assert.equal(calls[0].url, '/miniprogram/teacher/homework/group/9')
    assert.equal(calls[0].options.method, 'PATCH')
    assert.deepEqual(calls[0].options.data.recipient_profile_ids, [1, 2, 3])
    assert.equal(calls[0].options.data.roster_token, 'roster-a')
})

test('real page group delete confirmation names recipient, preserving individual delete', () => {
    const ui = setupUi(false)
    const page = loadRealPage(async () => { throw Error('cancelled') })
    page.data.isGroupHomework = true
    page.data.existingTasks = [{ id: 9, student_name: '学生乙', detail: '练习' }]
    page.deleteExistingTask({ currentTarget: { dataset: { id: 9 } } })
    assert.match(ui.modals[0].content, /学生乙的/)
})
