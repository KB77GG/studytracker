const app = getApp()
const { request } = require('../../../utils/request.js')
const { getSubscribeSummary, requestTemplateSubscribe } = require('../../../utils/subscribe.js')
const FEEDBACK_TEMPLATE_ID = 'jh8kXPp8x2qnzE3g894HlDzdJ5j7ItGHVG0Qx6oD7PA'

Page({
    data: {
        userInfo: null,
        feedbackSubscribed: false,
        feedbackSubscribeText: '订阅课堂反馈',
        feedbackSubscribeHint: '点击后勾选“总是保持以上选择”更稳定',
        feedbackSubscribeState: 'unknown'
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
        this.refreshSubscribeStatus()
    },

    async refreshSubscribeStatus() {
        const summary = await getSubscribeSummary([FEEDBACK_TEMPLATE_ID])
        const state = summary && summary.state ? summary.state : 'unknown'
        if (state === 'accept') {
            this.setData({
                feedbackSubscribed: true,
                feedbackSubscribeState: state,
                feedbackSubscribeText: '课堂反馈提醒已开启',
                feedbackSubscribeHint: '如需修改提醒偏好，请前往微信设置页'
            })
            return
        }
        if (state === 'reject') {
            this.setData({
                feedbackSubscribed: false,
                feedbackSubscribeState: state,
                feedbackSubscribeText: '去设置开启课堂反馈',
                feedbackSubscribeHint: '你已关闭提醒，请在设置里重新开启'
            })
            return
        }
        if (state === 'off') {
            this.setData({
                feedbackSubscribed: false,
                feedbackSubscribeState: state,
                feedbackSubscribeText: '去设置开启课堂反馈',
                feedbackSubscribeHint: '微信总提醒开关已关闭，请先开启'
            })
            return
        }
        if (state === 'ban') {
            this.setData({
                feedbackSubscribed: false,
                feedbackSubscribeState: state,
                feedbackSubscribeText: '查看课堂反馈提醒状态',
                feedbackSubscribeHint: '当前模板不可用，请联系老师检查配置'
            })
            return
        }
        this.setData({
            feedbackSubscribed: false,
            feedbackSubscribeState: state,
            feedbackSubscribeText: '订阅课堂反馈',
            feedbackSubscribeHint: '点击后勾选“总是保持以上选择”更稳定'
        })
    },

    openSubscribeSettings() {
        wx.openSetting({
            success: () => {
                this.refreshSubscribeStatus()
            }
        })
    },

    requestFeedbackSubscribe() {
        if (!FEEDBACK_TEMPLATE_ID) {
            wx.showToast({ title: '模板未配置', icon: 'none' })
            return
        }
        if (['reject', 'off'].includes(this.data.feedbackSubscribeState)) {
            wx.showModal({
                title: '开启课堂反馈提醒',
                content: '当前课堂反馈提醒已关闭，请在设置页重新开启。',
                success: (res) => {
                    if (res.confirm) {
                        this.openSubscribeSettings()
                    }
                }
            })
            return
        }
        if (this.data.feedbackSubscribeState === 'ban') {
            wx.showToast({ title: '提醒模板不可用', icon: 'none' })
            return
        }
        requestTemplateSubscribe([FEEDBACK_TEMPLATE_ID])
            .then((res) => {
                if (res[FEEDBACK_TEMPLATE_ID] === 'accept') {
                    wx.showToast({ title: '提醒已记录', icon: 'success' })
                } else {
                    wx.showToast({ title: '建议勾选“总是保持以上选择”', icon: 'none', duration: 3000 })
                }
                this.refreshSubscribeStatus()
            })
            .catch((err) => {
                console.warn('subscribe fail', err)
                wx.showToast({ title: '订阅失败', icon: 'none' })
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
