const { request } = require('../../../utils/request.js')

const SOURCE_OPTIONS = [
    { key: 'custom', label: '自定义' },
    { key: 'cambridge_listening', label: '剑雅听力' },
    { key: 'cambridge_reading', label: '剑雅阅读' }
]

const decodeParam = (value) => {
    if (value === undefined || value === null) return ''
    return decodeURIComponent(value)
}

const clampIndex = (value, length) => {
    const index = Number(value) || 0
    if (length <= 0) return 0
    return Math.max(0, Math.min(index, length - 1))
}

const pushErrorMessage = (code) => {
    const mapping = {
        missing_template_id: '作业已保存，但服务端没有配置任务提醒模板。',
        no_student_openid: '作业已保存，但学生还没有完成微信绑定。',
        user_refused: '作业已保存，但学生当前没有可用的任务提醒订阅，请让学生在小程序里重新开启提醒。',
        invalid_template_id: '作业已保存，但任务提醒模板 ID 配置错误。',
        invalid_page: '作业已保存，但提醒跳转页面配置错误。',
        template_param_error: '作业已保存，但提醒模板字段与后端参数不匹配。',
        missing_access_token: '作业已保存，但微信服务认证失败，请稍后再试。',
        send_failed: '作业已保存，但提醒发送失败，请稍后重试。'
    }
    return mapping[code] || '作业已保存，但提醒发送失败。'
}

Page({
    data: {
        schedule: {
            schedule_uid: '',
            schedule_id: '',
            student_id: '',
            student_name: '',
            teacher_id: '',
            teacher_name: '',
            course_name: '',
            start_time: '',
            end_time: '',
            schedule_date: ''
        },
        form: {
            date: '',
            category: '',
            detail: '',
            plannedMinutes: 30,
            note: ''
        },
        sourceOptions: SOURCE_OPTIONS,
        sourceLabels: SOURCE_OPTIONS.map(item => item.label),
        sourceIndex: 0,
        sourceKey: 'custom',
        isCustomSource: true,
        isListeningSource: false,
        isReadingSource: false,
        catalogLoading: false,
        catalog: {
            cambridge_listening: [],
            cambridge_reading: []
        },
        listeningBookIndex: 0,
        listeningTestIndex: 0,
        listeningScopeIndex: 0,
        listeningBookLabels: [],
        listeningTestLabels: [],
        listeningScopeLabels: [],
        readingBookIndex: 0,
        readingTestIndex: 0,
        readingScopeIndex: 0,
        readingBookLabels: [],
        readingTestLabels: [],
        readingScopeLabels: [],
        selectedPracticeSummary: '',
        saving: false
    },

    onLoad(options) {
        const schedule = {
            schedule_uid: decodeParam(options.schedule_uid),
            schedule_id: decodeParam(options.schedule_id),
            student_id: decodeParam(options.student_id),
            student_name: decodeParam(options.student_name),
            teacher_id: decodeParam(options.teacher_id),
            teacher_name: decodeParam(options.teacher_name),
            course_name: decodeParam(options.course_name),
            start_time: decodeParam(options.start_time),
            end_time: decodeParam(options.end_time),
            schedule_date: decodeParam(options.schedule_date)
        }
        const courseName = schedule.course_name || '课后作业'
        this.setData({
            schedule,
            form: {
                date: this.getTodayString(),
                category: courseName.slice(0, 32),
                detail: `${courseName}课后练习`,
                plannedMinutes: 30,
                note: ''
            }
        })
        this.fetchPracticeCatalog()
    },

    getTodayString() {
        const now = new Date()
        const year = now.getFullYear()
        const month = String(now.getMonth() + 1).padStart(2, '0')
        const day = String(now.getDate()).padStart(2, '0')
        return `${year}-${month}-${day}`
    },

    async fetchPracticeCatalog() {
        this.setData({ catalogLoading: true })
        try {
            const res = await request('/miniprogram/practice/catalog')
            if (res && res.ok) {
                this.setData({
                    catalog: {
                        cambridge_listening: res.cambridge_listening || [],
                        cambridge_reading: res.cambridge_reading || []
                    }
                }, () => this.refreshPracticeOptions(false))
            }
        } catch (err) {
            console.warn('load practice catalog failed', err)
        } finally {
            this.setData({ catalogLoading: false })
        }
    },

    refreshPracticeOptions(applySelection = true) {
        const source = SOURCE_OPTIONS[this.data.sourceIndex] || SOURCE_OPTIONS[0]
        const listeningBooks = this.data.catalog.cambridge_listening || []
        const readingBooks = this.data.catalog.cambridge_reading || []

        const listeningBookIndex = clampIndex(this.data.listeningBookIndex, listeningBooks.length)
        const listeningBook = listeningBooks[listeningBookIndex] || {}
        const listeningTests = listeningBook.tests || []
        const listeningTestIndex = clampIndex(this.data.listeningTestIndex, listeningTests.length)
        const listeningTest = listeningTests[listeningTestIndex] || {}
        const listeningScopes = [
            { label: '整套 Test', scope: 'test' },
            ...((listeningTest.sections || []).map(section => ({
                label: `${section.title || ('Part ' + section.number)} · ${section.question_name || ''}`,
                scope: 'section',
                sectionNumber: section.number
            })))
        ]
        const listeningScopeIndex = clampIndex(this.data.listeningScopeIndex, listeningScopes.length)

        const readingBookIndex = clampIndex(this.data.readingBookIndex, readingBooks.length)
        const readingBook = readingBooks[readingBookIndex] || {}
        const readingTests = readingBook.tests || []
        const readingTestIndex = clampIndex(this.data.readingTestIndex, readingTests.length)
        const readingTest = readingTests[readingTestIndex] || {}
        const readingScopes = [
            { label: '整套 Test', scope: 'test' },
            ...((readingTest.passages || []).map(passage => ({
                label: `${passage.title || ('Passage ' + passage.number)} · ${passage.question_name || ''}`,
                scope: 'passage',
                passageNumber: passage.number
            })))
        ]
        const readingScopeIndex = clampIndex(this.data.readingScopeIndex, readingScopes.length)

        const selected = this.getSelectedPractice({
            source,
            listeningBook,
            listeningTest,
            listeningScope: listeningScopes[listeningScopeIndex],
            readingBook,
            readingTest,
            readingScope: readingScopes[readingScopeIndex]
        })

        this.setData({
            sourceKey: source.key,
            isCustomSource: source.key === 'custom',
            isListeningSource: source.key === 'cambridge_listening',
            isReadingSource: source.key === 'cambridge_reading',
            listeningBookIndex,
            listeningTestIndex,
            listeningScopeIndex,
            listeningBookLabels: listeningBooks.map(book => `剑雅 ${book.book}`),
            listeningTestLabels: listeningTests.map(test => `Test ${test.test}`),
            listeningScopeLabels: listeningScopes.map(item => item.label),
            readingBookIndex,
            readingTestIndex,
            readingScopeIndex,
            readingBookLabels: readingBooks.map(book => `剑雅 ${book.book}`),
            readingTestLabels: readingTests.map(test => `Test ${test.test}`),
            readingScopeLabels: readingScopes.map(item => item.label),
            selectedPracticeSummary: selected ? selected.summary : ''
        }, () => {
            if (applySelection) this.applySelectedPractice()
        })
    },

    getSelectedPractice(context) {
        const source = context.source || SOURCE_OPTIONS[this.data.sourceIndex] || SOURCE_OPTIONS[0]
        if (source.key === 'cambridge_listening') {
            const test = context.listeningTest
            const scope = context.listeningScope
            if (!test || !test.id || !scope) return null
            const suffix = scope.scope === 'section' ? ` ${scope.label.split(' · ')[0]}` : ' 整套'
            return {
                source_type: source.key,
                practice_test_id: test.id,
                practice_scope: scope.scope,
                practice_section_number: scope.sectionNumber || null,
                category: '雅思-听力',
                detail: `${test.title || ('Cambridge IELTS ' + test.book + ' Test ' + test.test + ' Listening')}${suffix}`,
                plannedMinutes: scope.scope === 'section' ? 30 : 40,
                summary: `剑雅 ${test.book} Test ${test.test} · ${scope.label}`
            }
        }
        if (source.key === 'cambridge_reading') {
            const test = context.readingTest
            const scope = context.readingScope
            if (!test || !test.id || !scope) return null
            const suffix = scope.scope === 'passage' ? ` ${scope.label.split(' · ')[0]}` : ' 整套'
            return {
                source_type: source.key,
                practice_test_id: test.id,
                practice_scope: scope.scope,
                practice_passage_number: scope.passageNumber || null,
                category: '雅思-阅读',
                detail: `${test.title || ('Cambridge IELTS ' + test.book + ' Test ' + test.test + ' Reading')}${suffix}`,
                plannedMinutes: scope.scope === 'passage' ? 20 : 60,
                summary: `剑雅 ${test.book} Test ${test.test} · ${scope.label}`
            }
        }
        return null
    },

    buildSelectedPracticePayload() {
        const source = SOURCE_OPTIONS[this.data.sourceIndex] || SOURCE_OPTIONS[0]
        if (source.key === 'custom') {
            return { source_type: 'custom' }
        }

        const listeningBooks = this.data.catalog.cambridge_listening || []
        const listeningBook = listeningBooks[this.data.listeningBookIndex] || {}
        const listeningTest = (listeningBook.tests || [])[this.data.listeningTestIndex] || {}
        const listeningScopes = [
            { label: '整套 Test', scope: 'test' },
            ...((listeningTest.sections || []).map(section => ({
                label: `${section.title || ('Part ' + section.number)} · ${section.question_name || ''}`,
                scope: 'section',
                sectionNumber: section.number
            })))
        ]

        const readingBooks = this.data.catalog.cambridge_reading || []
        const readingBook = readingBooks[this.data.readingBookIndex] || {}
        const readingTest = (readingBook.tests || [])[this.data.readingTestIndex] || {}
        const readingScopes = [
            { label: '整套 Test', scope: 'test' },
            ...((readingTest.passages || []).map(passage => ({
                label: `${passage.title || ('Passage ' + passage.number)} · ${passage.question_name || ''}`,
                scope: 'passage',
                passageNumber: passage.number
            })))
        ]

        const selected = this.getSelectedPractice({
            source,
            listeningBook,
            listeningTest,
            listeningScope: listeningScopes[this.data.listeningScopeIndex],
            readingBook,
            readingTest,
            readingScope: readingScopes[this.data.readingScopeIndex]
        })
        return selected || { source_type: source.key }
    },

    applySelectedPractice() {
        const selected = this.buildSelectedPracticePayload()
        if (!selected || selected.source_type === 'custom' || !selected.detail) return
        this.setData({
            'form.category': selected.category,
            'form.detail': selected.detail,
            'form.plannedMinutes': selected.plannedMinutes
        })
    },

    handleSourceChange(e) {
        this.setData({ sourceIndex: Number(e.detail.value) || 0 }, () => this.refreshPracticeOptions(true))
    },

    handleListeningBookChange(e) {
        this.setData({
            listeningBookIndex: Number(e.detail.value) || 0,
            listeningTestIndex: 0,
            listeningScopeIndex: 0
        }, () => this.refreshPracticeOptions(true))
    },

    handleListeningTestChange(e) {
        this.setData({
            listeningTestIndex: Number(e.detail.value) || 0,
            listeningScopeIndex: 0
        }, () => this.refreshPracticeOptions(true))
    },

    handleListeningScopeChange(e) {
        this.setData({ listeningScopeIndex: Number(e.detail.value) || 0 }, () => this.refreshPracticeOptions(true))
    },

    handleReadingBookChange(e) {
        this.setData({
            readingBookIndex: Number(e.detail.value) || 0,
            readingTestIndex: 0,
            readingScopeIndex: 0
        }, () => this.refreshPracticeOptions(true))
    },

    handleReadingTestChange(e) {
        this.setData({
            readingTestIndex: Number(e.detail.value) || 0,
            readingScopeIndex: 0
        }, () => this.refreshPracticeOptions(true))
    },

    handleReadingScopeChange(e) {
        this.setData({ readingScopeIndex: Number(e.detail.value) || 0 }, () => this.refreshPracticeOptions(true))
    },

    handleDateChange(e) {
        this.setData({ 'form.date': e.detail.value })
    },

    handleInput(e) {
        const field = e.currentTarget.dataset.field
        if (!field) return
        this.setData({ [`form.${field}`]: e.detail.value })
    },

    async submitHomework() {
        const { form, schedule } = this.data
        const practicePayload = this.buildSelectedPracticePayload()
        const detail = (form.detail || '').trim()
        if (!detail) {
            wx.showToast({ title: '请填写作业内容', icon: 'none' })
            return
        }
        if (practicePayload.source_type !== 'custom' && !practicePayload.practice_test_id) {
            wx.showToast({ title: '请选择练习篇目', icon: 'none' })
            return
        }

        this.setData({ saving: true })
        wx.showLoading({ title: '保存中...' })
        try {
            const payload = {
                ...schedule,
                ...practicePayload,
                date: form.date,
                category: (form.category || '').trim(),
                detail,
                planned_minutes: Number(form.plannedMinutes) || 0,
                note: (form.note || '').trim()
            }
            const res = await request('/miniprogram/teacher/homework', {
                method: 'POST',
                data: payload
            })
            if (!res || !res.ok) {
                let msg = (res && res.error) || '保存失败'
                if (msg === 'student_not_found') msg = '未找到学生档案'
                if (msg === 'forbidden_schedule') msg = '当前课表不属于你'
                if (msg === 'invalid_date') msg = '日期格式不正确'
                if (msg === 'practice_not_found') msg = '未找到练习篇目'
                if (msg === 'invalid_practice_scope') msg = '练习范围不正确'
                wx.showToast({ title: msg, icon: 'none' })
                return
            }

            if (res.push_sent > 0) {
                wx.showToast({ title: '作业已布置并提醒学生', icon: 'success' })
                setTimeout(() => {
                    wx.navigateBack()
                }, 500)
                return
            }

            wx.showModal({
                title: '作业已保存',
                content: pushErrorMessage(res.push_error),
                showCancel: false,
                success: () => {
                    wx.navigateBack()
                }
            })
        } catch (err) {
            console.error(err)
            wx.showToast({ title: '网络错误', icon: 'none' })
        } finally {
            wx.hideLoading()
            this.setData({ saving: false })
        }
    }
})
