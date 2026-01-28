const app = getApp()
const { request } = require('../../../utils/request.js')

const decodeParam = (value) => {
    if (value === undefined || value === null) return ''
    return decodeURIComponent(value)
}

Page({
    data: {
        studentName: '',
        feedbacks: [],
        loading: true,
        singleMode: false,
        baseUrl: ''
    },

    onLoad(options) {
        const feedbackId = decodeParam(options.feedback_id)
        const studentName = decodeParam(options.student || options.student_name)
        const baseUrl = app.globalData.baseUrl || ''
        if (feedbackId) {
            this.setData({ singleMode: true, baseUrl })
            this.fetchFeedbackDetail(feedbackId)
            return
        }
        this.setData({ studentName, singleMode: false, baseUrl })
        this.fetchFeedback()
    },

    onPullDownRefresh() {
        if (this.data.singleMode) {
            wx.stopPullDownRefresh()
            return
        }
        this.fetchFeedback()
    },

    async fetchFeedback() {
        const studentName = this.data.studentName
        if (!studentName) {
            this.setData({ loading: false })
            return
        }
        wx.showLoading({ title: '加载中...' })
        try {
            const res = await request(`/miniprogram/parent/feedback?student_name=${encodeURIComponent(studentName)}`)
            if (res && res.ok) {
                this.setData({ feedbacks: res.feedback || [] })
            } else {
                let msg = '加载失败'
                if (res && res.error === 'feedback_table_missing') {
                    msg = '请先升级数据库'
                }
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

    async fetchFeedbackDetail(feedbackId) {
        if (!feedbackId) {
            this.setData({ loading: false })
            return
        }
        wx.showLoading({ title: '加载中...' })
        try {
            const res = await request(`/miniprogram/parent/feedback/detail?feedback_id=${encodeURIComponent(feedbackId)}`)
            if (res && res.ok) {
                const feedback = res.feedback || {}
                this.setData({
                    feedbacks: feedback ? [feedback] : [],
                    studentName: feedback.student_name || this.data.studentName
                })
            } else {
                let msg = '加载失败'
                if (res && res.error === 'feedback_table_missing') {
                    msg = '请先升级数据库'
                }
                wx.showToast({ title: msg, icon: 'none' })
            }
        } catch (err) {
            console.error(err)
            wx.showToast({ title: '网络错误', icon: 'none' })
        } finally {
            this.setData({ loading: false })
            wx.hideLoading()
        }
    },

    previewFeedbackImage(e) {
        const url = e.currentTarget.dataset.url
        if (!url) return
        wx.previewImage({
            urls: [url]
        })
    }
})
