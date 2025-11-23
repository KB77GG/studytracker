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
    }
})
