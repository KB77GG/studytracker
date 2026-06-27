const app = getApp()
const { request } = require('../../../utils/request.js')
const { getSubscribeSummary, requestTemplateSubscribe } = require('../../../utils/subscribe.js')
const FEEDBACK_TEMPLATE_ID = 'jh8kXPp8x2qnzE3g894HlDzdJ5j7ItGHVG0Qx6oD7PA'

Page({
    data: {
        isGuest: false,
        userInfo: null,
        feedbackSubscribed: false,
        feedbackSubscribeText: '订阅课堂反馈',
        feedbackSubscribeHint: '多次允许后，微信会出现“总是保持以上选择”，勾选即可长期免打扰',
        feedbackSubscribeState: 'unknown'
    },

    onShow() {
        if (typeof this.getTabBar === 'function' && this.getTabBar()) {
            this.getTabBar().setData({
                selected: 1 // Index 1 is '我的' for parent
            })
        }

        if (app.globalData.guestMode) {
            this.setData({
                isGuest: true,
                userInfo: { display_name: '演示家长' },
                feedbackSubscribed: false,
                feedbackSubscribeState: 'guest',
                feedbackSubscribeText: '登录后可订阅课堂反馈',
                feedbackSubscribeHint: '演示模式下仅供浏览，登录后可接收课堂反馈提醒'
            })
            return
        }

        // Load user info
        const userInfo = wx.getStorageSync('userInfo')
        if (userInfo) {
            this.setData({ userInfo })
        }
        this.refreshSubscribeStatus()
    },

    promptLogin(content) {
        wx.showModal({
            title: '需要登录',
            content,
            confirmText: '去登录',
            success: (res) => {
                if (res.confirm) {
                    this.goLogin()
                }
            }
        })
    },

    goLogin() {
        app.globalData.guestMode = false
        app.globalData.guestRole = ''
        wx.reLaunch({ url: '/pages/index/index?action=login' })
    },

    exitGuest() {
        app.globalData.guestMode = false
        app.globalData.guestRole = ''
        wx.reLaunch({ url: '/pages/index/index' })
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
            feedbackSubscribeHint: '多次允许后，微信会出现“总是保持以上选择”，勾选即可长期免打扰'
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
        if (this.data.isGuest) {
            this.promptLogin('订阅课堂反馈需要先登录账号。')
            return
        }
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
                    wx.showToast({ title: '本次未订阅，再次点击可重试', icon: 'none', duration: 3000 })
                }
                this.refreshSubscribeStatus()
            })
            .catch((err) => {
                console.warn('subscribe fail', err)
                wx.showToast({ title: '订阅失败', icon: 'none' })
            })
    },

    async handleUnbind() {
        if (this.data.isGuest) {
            this.promptLogin('演示模式下未绑定账号，登录后可管理绑定。')
            return
        }
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
        if (this.data.isGuest) {
            this.exitGuest()
            return
        }
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
