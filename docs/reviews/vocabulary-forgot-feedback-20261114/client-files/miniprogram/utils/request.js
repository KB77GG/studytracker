const app = getApp()

const TASK_DATE_GATE_ERRORS = new Set([
    'task_not_open',
    'task_expired',
    'task_completed_read_only'
])

const normalizeTaskDateGateError = (payload, statusCode) => {
    if (!payload || !TASK_DATE_GATE_ERRORS.has(payload.error)) return payload
    return Object.assign({
        taskDateBlocked: true,
        readOnly: true,
        availabilityStatus: payload.availability_status || payload.task_date_state || '',
        taskStatusLabel: payload.task_status_label || payload.status_label || '',
        availabilityLabel: payload.status_label || payload.task_status_label || payload.availability_label || payload.message || '当前仅可查看'
    }, payload, { statusCode })
}

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
                    resolve(normalizeTaskDateGateError(
                        Object.assign({ ok: false, statusCode: res.statusCode }, res.data || {}),
                        res.statusCode
                    ))
                }
            },
            fail: (err) => {
                console.warn('request fail', {
                    url: `${baseUrl}${url}`,
                    method: options.method || 'GET',
                    timeout: options.timeout || 60000,
                    err
                })
                reject(err)
            }
        })
    })
}

module.exports = {
    request,
    isTaskDateGateError: (payload) => !!(payload && payload.taskDateBlocked)
}
