const app = getApp()
const { request } = require('../../../utils/request.js')
const { buildParentTaskDetail } = require('../../../utils/demo-data.js')

const decodeParam = (value) => {
    if (value === undefined || value === null) return ''
    return decodeURIComponent(value)
}

const compactAccuracy = (value) => Number(value || 0).toFixed(1).replace(/\.0$/, '')

const formatAnswerValue = (value, emptyText = '未作答') => {
    if (Array.isArray(value)) return value.join('、') || emptyText
    if (value && typeof value === 'object') return JSON.stringify(value)
    if (value === null || value === undefined || value === '') return emptyText
    return String(value)
}

const attemptScoreText = (attempt) => {
    if (!attempt) return '旧版未留存'
    const ielts = attempt.ielts_score !== null && attempt.ielts_score !== undefined
        ? ` · IELTS ${attempt.ielts_score}`
        : ''
    return `${Number(attempt.correct_count || 0)}/${Number(attempt.total_count || 0)} · ${compactAccuracy(attempt.accuracy)}%${ielts}`
}

const formatAttemptTime = (value) => {
    if (!value) return ''
    const raw = String(value)
    const normalized = /(?:Z|[+-]\d{2}:?\d{2})$/i.test(raw) ? raw : `${raw}Z`
    const date = new Date(normalized)
    if (Number.isNaN(date.getTime())) return raw.replace('T', ' ').slice(0, 16)
    const month = String(date.getMonth() + 1).padStart(2, '0')
    const day = String(date.getDate()).padStart(2, '0')
    const hour = String(date.getHours()).padStart(2, '0')
    const minute = String(date.getMinutes()).padStart(2, '0')
    return `${month}-${day} ${hour}:${minute}`
}

const normalizeAttemptOverview = (source) => {
    if (!source || !source.latest_attempt) return null
    const attemptCount = Number(source.attempt_count || 1)
    const legacyMissing = Number(source.legacy_missing_attempts || 0)
    const delta = source.score_delta
    const attempts = (source.attempts || []).map((attempt, attemptIndex) => {
        const labels = []
        if (attempt.is_first) labels.push('首答')
        if (attempt.is_latest && !attempt.is_first) labels.push('最后一次')
        const wrongDetails = (attempt.wrong_details || []).map((detail, detailIndex) => ({
            ...detail,
            id: `${attempt.attempt_number || attemptIndex + 1}-${detailIndex}`,
            studentAnswerText: formatAnswerValue(detail.student_answer),
            correctAnswerText: formatAnswerValue(detail.correct_answer, '暂无参考答案')
        }))
        return {
            ...attempt,
            id: String(attempt.attempt_number || attemptIndex + 1),
            titleText: `第 ${attempt.attempt_number || attemptIndex + 1} 次${labels.length ? `（${labels.join('、')}）` : ''}`,
            scoreText: attemptScoreText(attempt),
            timeText: formatAttemptTime(attempt.submitted_at),
            wrongSummary: Number(attempt.wrong_count || 0) > 0
                ? `错 ${Number(attempt.wrong_count || 0)} 题`
                : '全部答对',
            wrongDetails
        }
    })
    return {
        ...source,
        firstScoreText: attemptScoreText(source.first_attempt),
        latestScoreText: attemptScoreText(source.latest_attempt),
        attemptCountText: `共 ${attemptCount} 次`,
        deltaText: delta === null || delta === undefined
            ? ''
            : `末答比首答 ${Number(delta) >= 0 ? '+' : ''}${compactAccuracy(delta)} 个百分点`,
        noticeText: legacyMissing > 0
            ? `其中 ${legacyMissing} 次旧版作答只留下次数，答案和分数“旧版未留存”，无法还原。`
            : attemptCount > 1
            ? '首答反映独立完成水平；最后一次反映反复练习后的结果。'
            : '',
        attempts,
        canExpand: attempts.length > 0
    }
}

Page({
    data: {
        taskId: '',
        studentName: '',
        detail: null,
        loading: true,
        errorMessage: '',
        activeFilter: 'all',
        filters: [],
        visibleItems: [],
        summaryMetrics: [],
        attemptHistoryExpanded: false
    },

    onLoad(options) {
        this.setData({
            taskId: decodeParam(options.task_id),
            studentName: decodeParam(options.student)
        })
        this.fetchDetail()
    },

    onPullDownRefresh() {
        this.fetchDetail()
    },

    onUnload() {
        if (this.audioContext) {
            this.audioContext.destroy()
            this.audioContext = null
        }
    },

    async fetchDetail() {
        const taskId = this.data.taskId
        if (!taskId) {
            this.setData({ loading: false, errorMessage: '缺少任务信息' })
            wx.stopPullDownRefresh()
            return
        }
        this.setData({ loading: true, errorMessage: '' })
        try {
            if (app.globalData.guestMode) {
                this.applyDetail(buildParentTaskDetail(taskId))
                return
            }
            const res = await request(`/miniprogram/parent/tasks/${encodeURIComponent(taskId)}`)
            if (res && res.ok && res.detail) {
                this.applyDetail(res.detail)
                return
            }
            const errorMap = {
                task_not_found: '没有找到这次练习',
                student_not_bound: '当前账号无权查看这次练习'
            }
            this.setData({ errorMessage: errorMap[res && res.error] || '练习详情加载失败' })
        } catch (err) {
            console.error(err)
            this.setData({ errorMessage: '网络异常，请稍后重试' })
        } finally {
            this.setData({ loading: false })
            wx.stopPullDownRefresh()
        }
    },

    applyDetail(source) {
        const detail = Object.assign({}, source || {})
        const baseUrl = app.globalData.baseUrl || ''
        detail.items = (detail.items || []).map((item) => Object.assign({}, item, {
            next_review_text: this.formatReviewDate(item.next_review_at),
            student_audio_url: item.student_audio
                ? (/^https?:\/\//.test(item.student_audio) ? item.student_audio : `${baseUrl}${item.student_audio}`)
                : ''
        }))
        detail.showAccuracy = detail.accuracy !== null && detail.accuracy !== undefined
        detail.evidence = this.normalizeEvidence(detail.evidence)
        detail.attemptOverview = normalizeAttemptOverview(detail.attempt_overview)
        const summary = detail.summary || {}
        const fourthMetric = Number(summary.pending_total || 0) > 0
            ? { label: '待批改', value: summary.pending_total || 0 }
            : { label: detail.kind === 'dictation' ? '需复习' : '错误', value: summary.wrong_total || 0 }
        const summaryMetrics = detail.kind === 'dictation'
            ? [
                { label: '应背', value: summary.assigned_total || 0 },
                { label: '已测', value: summary.attempted_total || 0 },
                { label: '正确', value: summary.correct_total || 0 },
                fourthMetric
            ]
            : [
                { label: '总题数', value: summary.assigned_total || 0 },
                { label: '已作答', value: summary.attempted_total || 0 },
                { label: '正确', value: summary.correct_total || 0 },
                fourthMetric
            ]
        const filters = this.buildFilters(detail)
        this.setData({
            detail,
            studentName: detail.student_name || this.data.studentName,
            filters,
            summaryMetrics,
            activeFilter: 'all',
            visibleItems: detail.items,
            attemptHistoryExpanded: false,
            errorMessage: '',
            loading: false
        })
    },

    buildFilters(detail) {
        const items = detail.items || []
        const wrongLabel = detail.kind === 'dictation' ? '错词' : '错题'
        const isWrong = (item) => ['wrong', 'incorrect', 'partial'].includes(item.result_status)
        const candidates = [
            { key: 'all', label: '全部', count: items.length },
            { key: 'wrong', label: wrongLabel, count: items.filter(isWrong).length },
            { key: 'correct', label: '正确', count: items.filter(item => item.result_status === 'correct').length },
            { key: 'pending', label: '待批改', count: items.filter(item => item.result_status === 'pending').length },
            { key: 'unanswered', label: '未作答', count: items.filter(item => item.result_status === 'unanswered').length }
        ]
        return candidates.filter(item => item.key === 'all' || item.count > 0)
    },

    normalizeEvidence(evidence) {
        const source = evidence || {}
        const baseUrl = app.globalData.baseUrl || ''
        const buildUrl = (url) => {
            if (!url) return ''
            if (/^https?:\/\//.test(url)) return url
            return `${baseUrl}${url}`
        }
        return {
            image: (source.image || []).map(buildUrl),
            audio: (source.audio || []).map(buildUrl),
            doc: (source.doc || []).map(buildUrl),
            other: (source.other || []).map(buildUrl)
        }
    },

    formatReviewDate(value) {
        if (!value) return ''
        const date = new Date(value)
        if (Number.isNaN(date.getTime())) return ''
        return `${date.getMonth() + 1}月${date.getDate()}日复习`
    },

    setFilter(e) {
        const key = e.currentTarget.dataset.filter || 'all'
        const items = (this.data.detail && this.data.detail.items) || []
        const isWrong = (item) => ['wrong', 'incorrect', 'partial'].includes(item.result_status)
        this.setData({
            activeFilter: key,
            visibleItems: key === 'all' ? items : items.filter(item => key === 'wrong' ? isWrong(item) : item.result_status === key)
        })
    },

    toggleAttemptHistory() {
        this.setData({ attemptHistoryExpanded: !this.data.attemptHistoryExpanded })
    },

    previewImage(e) {
        const current = e.currentTarget.dataset.url
        const urls = (this.data.detail && this.data.detail.evidence && this.data.detail.evidence.image) || []
        if (!current || !urls.length) return
        wx.previewImage({ current, urls })
    },

    playEvidenceAudio(e) {
        const url = e.currentTarget.dataset.url
        if (!url) return
        if (this.audioContext) this.audioContext.destroy()
        this.audioContext = wx.createInnerAudioContext()
        this.audioContext.src = url
        this.audioContext.play()
        wx.showToast({ title: '正在播放作业录音', icon: 'none' })
    },

    retry() {
        this.fetchDetail()
    }
})
