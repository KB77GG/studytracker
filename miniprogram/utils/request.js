const app = getApp()

const request = (url, options = {}) => {
    return new Promise((resolve, reject) => {
        // 获取 App 实例（如果 request.js 在 app.js 之前加载，可能需要动态获取）
        // 这里假设 request 在页面中使用，此时 app 已经初始化
        const baseUrl = getApp().globalData.baseUrl
        let token = getApp().globalData.token
        if (!token) {
            token = wx.getStorageSync('token')
            if (token) {
                getApp().globalData.token = token
            }
        }

        let header = options.header || {}
        if (token) {
            header['Authorization'] = `Bearer ${token}`
        }

        wx.request({
            url: `${baseUrl}${url}`,
            method: options.method || 'GET',
            data: options.data || {},
            header: header,
            timeout: options.timeout || 60000,
            success: (res) => {
                if (res.statusCode >= 200 && res.statusCode < 300) {
                    resolve(res.data)
                } else if (res.statusCode === 401) {
                    // Token 过期或无效
                    wx.removeStorageSync('token')
                    getApp().globalData.token = null
                    // In guest mode, don't redirect — just return error so pages show empty state
                    if (!getApp().globalData.guestMode) {
                        wx.reLaunch({
                            url: '/pages/index/index',
                        })
                    }
                    resolve({ ok: false, error: 'unauthorized', statusCode: res.statusCode })
                } else {
                    // 返回后由调用方自行处理错误信息
                    resolve(Object.assign({ ok: false, statusCode: res.statusCode }, res.data || {}))
                }
            },
            fail: (err) => {
                reject(err)
            }
        })
    })
}

module.exports = {
    request
}
