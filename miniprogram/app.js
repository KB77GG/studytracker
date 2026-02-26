App({
    onLaunch() {
        // 展示本地存储能力
        const logs = wx.getStorageSync('logs') || []
        logs.unshift(Date.now())
        wx.setStorageSync('logs', logs)

        // 检测并应用小程序新版本
        this.setupUpdateManager()

        // 登录
        this.checkLogin()
    },

    setupUpdateManager() {
        if (!wx.canIUse('getUpdateManager')) return
        const updateManager = wx.getUpdateManager()

        updateManager.onCheckForUpdate(() => {})

        updateManager.onUpdateReady(() => {
            wx.showModal({
                title: '发现新版本',
                content: '新版本已准备好，点击“立即重启”完成更新。',
                showCancel: false,
                confirmText: '立即重启',
                success: () => {
                    updateManager.applyUpdate()
                }
            })
        })

        updateManager.onUpdateFailed(() => {
            wx.showModal({
                title: '更新提示',
                content: '新版本下载失败，请退出小程序后重新打开。',
                showCancel: false
            })
        })
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
        guestMode: false,
        baseUrl: 'https://studytracker.xin/api',
        activeTimer: null
    }
})
