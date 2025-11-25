const app = getApp()
const { request } = require('../../utils/request.js')

Page({
    data: {
        userInfo: null
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
