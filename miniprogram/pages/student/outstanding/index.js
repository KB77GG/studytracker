const app = getApp()
const { request } = require('../../../utils/request.js')

Page({
    data: {
        tasks: [],
        windowDays: 5,
        loading: true,
        isGuest: false
    },

    onLoad() {
        this.setData({ isGuest: !!getApp().globalData.guestMode })
    },

    onShow() {
        this.fetchOutstanding()
    },

    onPullDownRefresh() {
        this.fetchOutstanding(() => wx.stopPullDownRefresh())
    },

    async fetchOutstanding(done) {
        if (this.data.isGuest || getApp().globalData.guestMode) {
            this.setData({ tasks: [], loading: false })
            if (done) done()
            return
        }
        try {
            const res = await request('/miniprogram/student/tasks/outstanding')
            if (res.ok && Array.isArray(res.items)) {
                this.applyItems(res.items, res.window_days)
            } else {
                this.setData({ tasks: [] })
            }
        } catch (err) {
            console.error('Fetch outstanding error:', err)
        } finally {
            this.setData({ loading: false })
            if (done) done()
        }
    },

    applyItems(items, windowDays) {
        let lastDate = null
        const tasks = items.map(item => {
            const showDateHeader = item.date !== lastDate
            lastDate = item.date
            return {
                id: item.id,
                date: item.date,
                showDateHeader,
                dateHeaderLabel: this.buildDateLabel(item.date),
                task_name: item.task_name,
                module: item.module,
                planned_minutes: item.planned_minutes || 0,
                status: item.status,
                statusText: this.getStatusText(item.status),
                iconText: this.getModuleIcon(item.module || item.task_name || ''),
                assignedByLabel: this.getAssignerLabel(item.assigned_by_role)
            }
        })
        this.setData({ tasks, windowDays: windowDays || this.data.windowDays })
    },

    buildDateLabel(dateStr) {
        const parts = (dateStr || '').split('-')
        if (parts.length !== 3) return '更早任务'
        const target = new Date(`${dateStr}T00:00:00`)
        const today = new Date()
        today.setHours(0, 0, 0, 0)
        const diff = Math.round((today.getTime() - target.getTime()) / 86400000)
        const dayLabel = `${Number(parts[1])}月${Number(parts[2])}日`
        if (diff === 1) return `昨天 · ${dayLabel}`
        if (diff === 2) return `前天 · ${dayLabel}`
        return dayLabel
    },

    getStatusText(status) {
        const map = {
            'pending': '待完成',
            'in_progress': '进行中',
            'progress': '进行中',
            'submitted': '审核中',
            'rejected': '需修改'
        }
        return map[status] || '待完成'
    },

    getModuleIcon(text) {
        const lower = (text || '').toLowerCase()
        if (lower.includes('听') || lower.includes('朗读')) return 'L'
        if (lower.includes('读') || lower.includes('阅读')) return 'R'
        if (lower.includes('写') || lower.includes('作文')) return 'W'
        if (lower.includes('词') || lower.includes('单词') || lower.includes('词汇')) return 'V'
        if (lower.includes('口语')) return 'S'
        return 'T'
    },

    getAssignerLabel(role) {
        return role === 'assistant' ? '助教布置' : ''
    },

    goTask(e) {
        const date = e.currentTarget.dataset.date
        if (!date) return
        // 把目标日期交给首页，切回任务 tab 后定位到该日期完成。
        getApp().globalData.pendingTaskDate = date
        wx.switchTab({ url: '/pages/student/home/index' })
    }
})
