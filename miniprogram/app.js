App({
    onLaunch() {
        // 展示本地存储能力
        const logs = wx.getStorageSync('logs') || []
        logs.unshift(Date.now())
        wx.setStorageSync('logs', logs)

        // 登录
        this.checkLogin()
    },

    checkLogin() {
        const token = wx.getStorageSync('token')
        const role = wx.getStorageSync('role')
        if (token) {
            this.globalData.token = token
            this.globalData.role = role
            // 可以验证 token 有效性，或者直接尝试获取用户信息
        } else {
            // 无 token，需要在页面中引导登录
        }
    },

    globalData: {
        userInfo: null,
        token: null,
        role: null,
        baseUrl: 'https://studytracker.xin/api',
        activeTimer: null
    }
})
