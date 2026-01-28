const app = getApp()
const { request } = require('../../../utils/request.js')
const FEEDBACK_TEMPLATE_ID = 'jh8kXPp8x2qnzE3g894HlDzdJ5j7ItGHVG0Qx6oD7PA'

Page({
    data: {
        userInfo: null,
        feedbackSubscribed: false
    },

    onShow() {
        if (typeof this.getTabBar === 'function' && this.getTabBar()) {
            this.getTabBar().setData({
                selected: 1 // Index 1 is '我的' for parent
            })
        }

        // Load user info
        const userInfo = wx.getStorageSync('userInfo')
        if (userInfo) {
            this.setData({ userInfo })
        }
        const feedbackSubscribed = wx.getStorageSync('feedback_subscribed') || false
        this.setData({ feedbackSubscribed })
    },

    requestFeedbackSubscribe() {
        if (this.data.feedbackSubscribed) {
            wx.showToast({ title: '已订阅课堂反馈', icon: 'none' })
            return
        }
        if (!FEEDBACK_TEMPLATE_ID) {
            wx.showToast({ title: '模板未配置', icon: 'none' })
            return
        }
        wx.requestSubscribeMessage({
            tmplIds: [FEEDBACK_TEMPLATE_ID],
            success: (res) => {
                if (res[FEEDBACK_TEMPLATE_ID] === 'accept') {
                    wx.setStorageSync('feedback_subscribed', true)
                    this.setData({ feedbackSubscribed: true })
                    wx.showToast({ title: '订阅成功', icon: 'success' })
                } else {
                    wx.showToast({ title: '已拒绝或未选择', icon: 'none' })
                }
            },
            fail: (err) => {
                console.warn('subscribe fail', err)
                wx.showToast({ title: '订阅失败', icon: 'none' })
            }
        })
    },

    async handleUnbind() {
        const res = await wx.showModal({
            title: '确认解绑',
            content: '解绑后将无法查看孩子的学习数据，确定要解除微信绑定吗？',
            confirmColor: '#ff4d4f'
        })

        if (res.confirm) {
            wx.showLoading({ title: '解绑中...' })
            try {
                const result = await request('/wechat/unbind', { method: 'POST' })
                if (result.ok) {
                    wx.showToast({ title: '解绑成功', icon: 'success' })
                    this.clearSessionAndRedirect()
                } else {
                    wx.showToast({ title: '解绑失败', icon: 'none' })
                }
            } catch (err) {
                console.error(err)
                wx.showToast({ title: '请求失败', icon: 'none' })
            } finally {
                wx.hideLoading()
            }
        }
    },

    async handleLogout() {
        const res = await wx.showModal({
            title: '确认退出',
            content: '确定要退出登录吗？'
        })

        if (res.confirm) {
            this.clearSessionAndRedirect()
        }
    },

    clearSessionAndRedirect() {
        // Clear local storage
        wx.removeStorageSync('token')
        wx.removeStorageSync('userInfo')
        wx.removeStorageSync('role')

        // Clear global data
        app.globalData.token = null
        app.globalData.userInfo = null
        app.globalData.role = null

        // Redirect to login page
        wx.reLaunch({
            url: '/pages/index/index'
        })
    }
})
