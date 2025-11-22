const app = getApp()
const { request } = require('../../utils/request.js')

Page({
    data: {
        studentName: '',
        stats: null,
        loading: true
    },

    onLoad(options) {
        if (options.student) {
            this.setData({ studentName: decodeURIComponent(options.student) })
            this.fetchStats(decodeURIComponent(options.student))
        } else {
            wx.showToast({ title: '参数错误', icon: 'none' })
        }
    },

    async fetchStats(studentName) {
        wx.showLoading({ title: '加载中...' })
        try {
            const res = await request(`/miniprogram/parent/stats?student_name=${encodeURIComponent(studentName)}`)
            if (res.ok) {
                this.setData({ stats: res })
            }
        } catch (err) {
            console.error(err)
            wx.showToast({ title: '加载失败', icon: 'none' })
        } finally {
            this.setData({ loading: false })
            wx.hideLoading()
        }
    }
})
