const app = getApp()
const { request } = require('../../../utils/request.js')
const { buildParentTaskDetail } = require('../../../utils/demo-data.js')

const decodeParam = (value) => {
    if (value === undefined || value === null) return ''
    return decodeURIComponent(value)
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
        summaryMetrics: []
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
            errorMessage: '',
            loading: false
        })
    },

    buildFilters(detail) {
        const items = detail.items || []
        const wrongLabel = detail.kind === 'dictation' ? '错词' : '错题'
        const candidates = [
            { key: 'all', label: '全部', count: items.length },
            { key: 'wrong', label: wrongLabel, count: items.filter(item => item.result_status === 'wrong').length },
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
        this.setData({
            activeFilter: key,
            visibleItems: key === 'all' ? items : items.filter(item => item.result_status === key)
        })
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
