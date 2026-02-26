const app = getApp()

Page({
    data: {
        stats: {
            streak: 0,
            total_hours: 0,
            level: 1,
            weekly_activity: [],
            badges: []
        },
        loading: true,
        isGuest: false
    },

    onShow() {
        if (typeof this.getTabBar === 'function' && this.getTabBar()) {
            this.getTabBar().setData({
                selected: 1
            })
        }
        // Guest mode detection
        const isGuest = !!getApp().globalData.guestMode
        this.setData({ isGuest })
        if (!isGuest) {
            this.fetchStats()
        } else {
            this.setData({ loading: false })
        }
    },

    onPullDownRefresh() {
        if (this.data.isGuest) {
            wx.stopPullDownRefresh()
            return
        }
        this.fetchStats().then(() => {
            wx.stopPullDownRefresh()
        })
    },

    goLogin() {
        getApp().globalData.guestMode = false
        wx.reLaunch({ url: '/pages/index/index' })
    },

    fetchStats() {
        return new Promise((resolve, reject) => {
            wx.request({
                url: `${app.globalData.baseUrl}/miniprogram/student/stats`,
                method: 'GET',
                header: {
                    'Authorization': `Bearer ${app.globalData.token}`
                },
                success: (res) => {
                    if (res.data.ok) {
                        this.setData({
                            stats: res.data.stats,
                            loading: false
                        })
                        resolve()
                    } else {
                        console.error('Fetch stats failed:', res.data.error)
                        this.setData({ loading: false })
                        reject()
                    }
                },
                fail: (err) => {
                    console.error('Request failed:', err)
                    this.setData({ loading: false })
                    reject()
                }
            })
        })
    },

    handleUnbind() {
        wx.showModal({
            title: '提示',
            content: '确定要解除绑定并退出吗？',
            confirmText: '解绑',
            success: async (res) => {
                if (res.confirm) {
                    wx.showLoading({ title: '处理中...' })
                    try {
                        // 尝试调用后端解绑
                        await new Promise((resolve) => {
                            wx.request({
                                url: `${app.globalData.baseUrl}/wechat/unbind`,
                                method: 'POST',
                                header: { 'Authorization': `Bearer ${app.globalData.token}` },
                                complete: resolve // 无论成功失败都继续
                            })
                        })

                        // 强制登出逻辑
                        wx.clearStorageSync()
                        app.globalData.token = null
                        app.globalData.userInfo = null
                        app.globalData.role = null

                        wx.showToast({ title: '已解绑', icon: 'success' })
                        setTimeout(() => {
                            wx.reLaunch({ url: '/pages/index/index' })
                        }, 1500)

                    } catch (err) {
                        console.error('Unbind error:', err)
                        // 异常保底
                        wx.clearStorageSync()
                        wx.reLaunch({ url: '/pages/index/index' })
                    } finally {
                        wx.hideLoading()
                    }
                }
            }
        })
    },

    handleLogout() {
        wx.showModal({
            title: '提示',
            content: '确定要退出登录吗？',
            success: (res) => {
                if (res.confirm) {
                    wx.clearStorageSync()
                    app.globalData.token = null
                    app.globalData.userInfo = null
                    app.globalData.role = null

                    wx.reLaunch({
                        url: '/pages/index/index'
                    })
                }
            }
        })
    }
})
