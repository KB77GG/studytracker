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
        loading: true
    },

    onShow() {
        this.fetchStats()
    },

    onPullDownRefresh() {
        this.fetchStats().then(() => {
            wx.stopPullDownRefresh()
        })
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
                        reject()
                    }
                },
                fail: (err) => {
                    console.error('Request failed:', err)
                    reject()
                }
            })
        })
    },

    handleUnbind() {
        const app = getApp()
        wx.showModal({
            title: '解除绑定',
            content: '确定要解除微信绑定吗？解绑后需要重新选择身份。',
            success: (res) => {
                if (res.confirm) {
                    wx.request({
                        url: `${app.globalData.baseUrl}/wechat/unbind`,
                        method: 'POST',
                        header: {
                            'Authorization': `Bearer ${app.globalData.token}`
                        },
                        success: (res) => {
                            if (res.data.ok) {
                                wx.showToast({ title: '解绑成功', icon: 'success' })
                                // 清除本地数据
                                wx.removeStorageSync('token')
                                wx.removeStorageSync('userInfo')
                                wx.removeStorageSync('role')
                                app.globalData.token = null
                                app.globalData.userInfo = null
                                app.globalData.role = null

                                // 跳转到登录页
                                wx.reLaunch({
                                    url: '/pages/index/index'
                                })
                            } else {
                                wx.showToast({ title: '解绑失败', icon: 'none' })
                            }
                        },
                        fail: () => {
                            wx.showToast({ title: '请求失败', icon: 'none' })
                        }
                    })
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
                    wx.removeStorageSync('token')
                    wx.removeStorageSync('userInfo')
                    wx.removeStorageSync('role')
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
