const { request } = require('../../../utils/request.js')

Page({
    data: {
        month: '',
        subjects: [],
        total: null,
        loading: true
    },

    onShow() {
        if (!this.data.month) {
            this.initMonth()
        }
        this.fetchStats()
    },

    onPullDownRefresh() {
        this.fetchStats()
    },

    initMonth() {
        const now = new Date()
        const year = now.getFullYear()
        const month = String(now.getMonth() + 1).padStart(2, '0')
        this.setData({ month: `${year}-${month}` })
    },

    async fetchStats() {
        const month = this.data.month
        if (!month) return
        this.setData({ loading: true })
        wx.showLoading({ title: '加载中...' })
        try {
            const res = await request(`/miniprogram/teacher/monthly_stats?month=${month}`)
            if (res && res.ok) {
                this.setData({ subjects: res.subjects || [], total: res.total || null })
            } else {
                const msg = (res && res.error) || '加载失败'
                wx.showToast({ title: msg, icon: 'none' })
            }
        } catch (err) {
            console.error(err)
            wx.showToast({ title: '网络错误', icon: 'none' })
        } finally {
            this.setData({ loading: false })
            wx.hideLoading()
            wx.stopPullDownRefresh()
        }
    },

    onMonthChange(e) {
        const value = e.detail.value
        this.setData({ month: value }, () => this.fetchStats())
    },

    goSchedule() {
        wx.redirectTo({ url: '/pages/teacher/home/index' })
    }
})
