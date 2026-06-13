const app = getApp()
const { request } = require('../../../utils/request.js')

Page({
    data: {
        loading: true,
        tasks: [],
        pendingCount: 0,
        savingId: null,
        playingUrl: ''
    },

    onLoad() {
        this.audioContext = wx.createInnerAudioContext()
        this.audioContext.obeyMuteSwitch = false
        this.audioContext.onEnded(() => this.setData({ playingUrl: '' }))
        this.audioContext.onStop(() => this.setData({ playingUrl: '' }))
        this.audioContext.onError(() => {
            this.setData({ playingUrl: '' })
            wx.showToast({ title: '录音播放失败', icon: 'none' })
        })
    },

    onShow() {
        this.fetchTasks()
    },

    onPullDownRefresh() {
        this.fetchTasks()
    },

    onUnload() {
        if (this.audioContext) {
            this.audioContext.destroy()
            this.audioContext = null
        }
    },

    absoluteUrl(url) {
        if (!url) return ''
        const rootUrl = (app.globalData.baseUrl || '').replace(/\/api\/?$/, '')
        return url.startsWith('http') ? url : `${rootUrl}${url}`
    },

    formatDuration(seconds) {
        const value = Math.max(0, Number(seconds) || 0)
        const minutes = Math.floor(value / 60)
        const rest = value % 60
        return `${minutes}:${String(rest).padStart(2, '0')}`
    },

    formatSubmittedAt(value) {
        if (!value) return ''
        return String(value).replace('T', ' ').slice(0, 16)
    },

    normalizeTask(task) {
        return {
            ...task,
            studentInitial: String(task.student_name || '学').slice(0, 1),
            submittedLabel: this.formatSubmittedAt(task.submitted_at),
            durationLabel: this.formatDuration(task.actual_seconds),
            audioFiles: (task.audio_files || []).map((url, index) => ({
                url: this.absoluteUrl(url),
                label: `录音 ${index + 1}`
            })),
            imageFiles: (task.image_files || []).map(url => this.absoluteUrl(url)),
            accuracyInput: task.accuracy === null || task.accuracy === undefined ? '' : String(task.accuracy),
            completionInput: task.completion_rate === null || task.completion_rate === undefined
                ? '100'
                : String(task.completion_rate),
            feedbackInput: task.feedback_text || ''
        }
    },

    async fetchTasks() {
        this.setData({ loading: true })
        try {
            const res = await request('/miniprogram/teacher/grading')
            if (!res || !res.ok) {
                wx.showToast({ title: (res && res.error) || '加载失败', icon: 'none' })
                return
            }
            const tasks = (res.tasks || []).map(task => this.normalizeTask(task))
            this.setData({
                tasks,
                pendingCount: Number(res.pending_count || tasks.length)
            })
        } catch (error) {
            console.error('teacher grading load failed', error)
            wx.showToast({ title: '网络错误', icon: 'none' })
        } finally {
            this.setData({ loading: false })
            wx.stopPullDownRefresh()
        }
    },

    playAudio(e) {
        const url = e.currentTarget.dataset.url
        if (!url || !this.audioContext) return
        if (this.data.playingUrl === url) {
            this.audioContext.stop()
            return
        }
        this.audioContext.stop()
        this.audioContext.src = url
        this.audioContext.play()
        this.setData({ playingUrl: url })
    },

    previewImage(e) {
        const current = e.currentTarget.dataset.url
        const index = Number(e.currentTarget.dataset.index)
        const task = this.data.tasks[index]
        if (!current || !task) return
        wx.previewImage({ current, urls: task.imageFiles || [] })
    },

    updateField(e) {
        const index = Number(e.currentTarget.dataset.index)
        const field = e.currentTarget.dataset.field
        if (!field || !this.data.tasks[index]) return
        this.setData({ [`tasks[${index}].${field}`]: e.detail.value })
    },

    async submitGrading(e) {
        const index = Number(e.currentTarget.dataset.index)
        const task = this.data.tasks[index]
        if (!task || this.data.savingId) return

        const accuracy = task.accuracyInput === '' ? null : Number(task.accuracyInput)
        const completionRate = task.completionInput === '' ? 100 : Number(task.completionInput)
        if (accuracy !== null && (!Number.isFinite(accuracy) || accuracy < 0 || accuracy > 100)) {
            wx.showToast({ title: '得分需在 0-100 之间', icon: 'none' })
            return
        }
        if (!Number.isFinite(completionRate) || completionRate < 0 || completionRate > 100) {
            wx.showToast({ title: '完成度需在 0-100 之间', icon: 'none' })
            return
        }

        this.setData({ savingId: task.id })
        wx.showLoading({ title: '提交批改...' })
        try {
            const res = await request(`/miniprogram/teacher/grading/${task.id}`, {
                method: 'POST',
                data: {
                    accuracy,
                    completion_rate: completionRate,
                    feedback_text: task.feedbackInput || ''
                }
            })
            if (!res || !res.ok) {
                wx.showToast({ title: (res && res.error) || '提交失败', icon: 'none' })
                return
            }
            const tasks = this.data.tasks.filter(item => item.id !== task.id)
            this.setData({
                tasks,
                pendingCount: tasks.length
            })
            wx.showToast({ title: '批改已完成', icon: 'success' })
        } catch (error) {
            console.error('teacher grading submit failed', error)
            wx.showToast({ title: '网络错误', icon: 'none' })
        } finally {
            wx.hideLoading()
            this.setData({ savingId: null })
        }
    }
})
