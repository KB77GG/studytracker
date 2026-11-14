// Small-class recipient checks and atomic group submission for the homework page.
const GROUP_NAME_SEPARATOR = /[/／]/
const ROOT = '/miniprogram/teacher/homework'

const groupHomeworkData = {
    recipientsRequired: false,
    recipientsLoading: false,
    recipientsBlocked: false,
    recipientError: '',
    recipientMembers: [],
    isGroupHomework: false,
    rosterToken: '',
    editingStudentName: ''
}

const requiresRecipientCheck = (schedule = {}) => !!(
    schedule.schedule_id || schedule.schedule_uid
    || GROUP_NAME_SEPARATOR.test(schedule.student_name || '')
)

const queryString = (params) => Object.keys(params)
    .filter(key => params[key] !== undefined && params[key] !== null && params[key] !== '')
    .map(key => `${key}=${encodeURIComponent(params[key])}`)
    .join('&')

const memberView = (member) => ({
    ...member,
    statusLabel: member.status === 'ready'
        ? (member.has_wechat_binding ? '可接收作业' : '可接收作业 · 未绑定微信提醒')
        : member.status === 'ambiguous' ? '同名档案待核实' : '缺少个人档案'
})

const groupErrorMessage = (response = {}) => response.message || ({
    roster_changed: '小班名单已变化，请刷新名单后再布置。',
    invalid_roster_token: '名单确认已失效，请刷新名单后再布置。',
    roster_expired: '名单确认已失效，请刷新名单后再布置。',
    incomplete_roster: '请先让管理员补齐个人档案，再刷新名单。',
    roster_incomplete: '请先让管理员补齐个人档案，再刷新名单。',
    recipient_mismatch: '接收名单不一致，请刷新名单后再布置。',
    scheduler_verification_failed: '课表暂时无法核验，请稍后刷新名单。',
    forbidden_schedule: '无法核实这节课属于当前老师，请返回课表重新进入。',
    idempotency_conflict: '这次提交内容有变化，请核对已布置作业后重新操作。'
}[response.error] || '名单或作业核验失败，请刷新后重试。')

const notificationLabel = (code) => ({
    no_student_openid: '未绑定微信',
    user_refused: '暂无可用提醒订阅',
    missing_template_id: '提醒模板未配置',
    send_failed: '提醒发送失败'
}[code] || '提醒未发送')

const groupResultMessage = (response) => {
    const saved = `${response.member_count} 位学生，共 ${response.task_count} 项作业已保存。`
    if (response.replayed) return `${saved}\n已确认上次提交成功，没有重复布置或再次发送提醒。`
    const reminders = `微信提醒已发送 ${Number(response.push_sent) || 0}/${response.task_count} 条。`
    const warnings = (response.recipients || []).filter(row => (row.push_errors || []).length)
        .map(row => `${row.student_name}：${[...new Set(row.push_errors.map(notificationLabel))].join('、')}`)
    return [saved, reminders, ...warnings, '学生可进入小程序查看各自的作业。'].join('\n')
}

const submissionFingerprint = (payload) => {
    const { roster_token, practice_context_token, ...stable } = payload
    return JSON.stringify(stable)
}

const pendingStorageKey = (schedule) => {
    try {
        const current = typeof getApp === 'function' && getApp().globalData
        const user = (current && current.userInfo) || wx.getStorageSync('userInfo')
        const scheduleId = schedule.schedule_id || schedule.schedule_uid
        return user && user.id && scheduleId
            ? `teacherGroupHomeworkPending:${user.id}:${scheduleId}` : ''
    } catch (error) {
        return ''
    }
}

const restorePendingSubmission = (storageKey, fingerprint) => {
    try {
        const stored = storageKey && wx.getStorageSync(storageKey)
        return stored && stored.fingerprint === fingerprint
            && typeof stored.key === 'string' ? stored : null
    } catch (error) {
        return null
    }
}

const savePendingSubmission = (storageKey, submission) => {
    try {
        if (storageKey) wx.setStorageSync(storageKey, submission)
    } catch (error) {
        // In-memory retries still retain the same key if local storage is full.
    }
}

const clearPendingSubmission = (storageKey, submission) => {
    try {
        const stored = storageKey && wx.getStorageSync(storageKey)
        if (stored && stored.key === submission.key) wx.removeStorageSync(storageKey)
    } catch (error) {
        // A retained successful key will safely replay rather than duplicate.
    }
}

const createGroupHomeworkMethods = (request) => ({
    applyGroupHomeworkError(response = {}) {
        const message = groupErrorMessage(response)
        const needsRefresh = response.members || /roster|recipient|schedule/.test(response.error || '')
        if (needsRefresh) {
            this.setData({
                ...(response.members ? { recipientMembers: response.members.map(memberView) } : {}),
                recipientsBlocked: true,
                recipientError: message
            })
        }
        return message
    },

    async loadHomeworkRecipients() {
        if (this.data.saving) return false
        const schedule = this.data.schedule || {}
        const required = requiresRecipientCheck(schedule)
        if (!required) {
            this.setData({ recipientsRequired: false, recipientsBlocked: false })
            await this.fetchExistingHomework()
            return true
        }
        const run = (this._recipientLoadRun || 0) + 1
        this._recipientLoadRun = run
        this.setData({
            recipientsRequired: true,
            recipientsLoading: true,
            recipientsBlocked: true,
            recipientError: '',
            rosterToken: ''
        })
        try {
            const response = await request(`${ROOT}/recipients?${queryString(schedule)}`)
            if (this._recipientLoadRun !== run) return false
            if (!response || !response.ok) {
                this.setData({ recipientError: groupErrorMessage(response || {}), existingTasks: [] })
                return false
            }
            const members = (response.members || []).map(memberView)
            const isGroup = !!response.is_group || members.length > 1
            const ready = !!response.can_assign && members.length > 0
                && members.every(member => member.status === 'ready' && member.profile_id)
                && (!isGroup || !!response.roster_token)
            this.setData({
                recipientMembers: members,
                isGroupHomework: isGroup,
                rosterToken: response.roster_token || '',
                recipientsBlocked: !ready,
                recipientError: ready ? '' : (response.message || '请先让管理员补齐或核实个人档案，再刷新名单。')
            })
            if (ready) await this.fetchExistingHomework()
            else this.setData({ existingTasks: [] })
            return ready
        } catch (error) {
            if (this._recipientLoadRun === run) {
                this.setData({ recipientError: '名单加载失败，请检查网络后刷新。', existingTasks: [] })
            }
            return false
        } finally {
            if (this._recipientLoadRun === run) this.setData({ recipientsLoading: false })
        }
    },

    groupHomeworkContext() {
        return {
            roster_token: this.data.rosterToken,
            recipient_profile_ids: this.data.recipientMembers.map(member => member.profile_id)
        }
    },

    async fetchGroupHomework() {
        if (this.data.recipientsBlocked || !this.data.rosterToken) return
        this.setData({ existingLoading: true })
        try {
            const params = {
                ...this.data.schedule,
                roster_token: this.data.rosterToken,
                date: this.data.form.date,
                scope: 'recent'
            }
            const response = await request(`${ROOT}/group?${queryString(params)}`)
            if (response && response.ok) {
                this.setData({ existingTasks: (response.tasks || []).map(task => this.normalizeExistingTask(task)) })
            } else {
                this.setData({
                    recipientError: groupErrorMessage(response || {}),
                    recipientsBlocked: true,
                    existingTasks: []
                })
            }
        } catch (error) {
            this.setData({ recipientError: '已布置作业加载失败，请刷新名单后重试。', recipientsBlocked: true })
        } finally {
            this.setData({ existingLoading: false })
        }
    },

    async submitGroupHomework(submitItems) {
        if (this.data.saving || this.data.recipientsBlocked || this.data.recipientsLoading) return
        const { form, schedule, recipientMembers } = this.data
        const payload = {
            ...schedule,
            ...this.buildQuickPracticePayload(),
            ...this.groupHomeworkContext(),
            items: submitItems.map(item => ({
                ...item,
                date: form.date,
                category: (item.category || form.category || '').trim(),
                detail: (item.detail || '').trim(),
                planned_minutes: Number(item.planned_minutes) || 0,
                note: (form.note || '').trim()
            }))
        }
        this.setData({ saving: true })
        try {
            const confirmed = await new Promise(resolve => wx.showModal({
                title: '确认布置小班作业',
                content: `向 ${recipientMembers.length} 位学生分别布置 ${submitItems.length} 项作业，共 ${recipientMembers.length * submitItems.length} 项。\n${recipientMembers.map(member => member.student_name).join('、')}`,
                confirmText: '确认布置',
                success: result => resolve(!!result.confirm),
                fail: () => resolve(false)
            }))
            if (!confirmed) return
            const fingerprint = submissionFingerprint(payload)
            const storageKey = pendingStorageKey(schedule)
            if (!this._groupSubmission || this._groupSubmission.fingerprint !== fingerprint) {
                this._groupSubmission = restorePendingSubmission(storageKey, fingerprint) || {
                    fingerprint,
                    key: `group-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 14)}`
                }
            }
            savePendingSubmission(storageKey, this._groupSubmission)
            wx.showLoading({ title: '布置小班作业...' })
            const response = await request(`${ROOT}/group`, {
                method: 'POST',
                data: { ...payload, idempotency_key: this._groupSubmission.key }
            })
            if (!response || !response.ok) {
                const message = this.applyGroupHomeworkError(response || {})
                wx.showModal({ title: '未能布置作业', content: message, showCancel: false })
                return
            }
            clearPendingSubmission(storageKey, this._groupSubmission)
            this.setData({ createdTasks: response.tasks || [], selectedPracticeList: [] })
            await this.fetchExistingHomework()
            wx.showModal({ title: '小班作业已保存', content: groupResultMessage(response), showCancel: false })
        } catch (error) {
            wx.showModal({
                title: '暂未确认保存结果',
                content: '网络中断，请保持作业内容不变后重试。相同提交会核对上次结果，避免重复布置。',
                showCancel: false
            })
        } finally {
            wx.hideLoading()
            this.setData({ saving: false })
        }
    }
})

module.exports = {
    groupHomeworkData,
    requiresRecipientCheck,
    queryString,
    groupErrorMessage,
    groupResultMessage,
    submissionFingerprint,
    createGroupHomeworkMethods
}
