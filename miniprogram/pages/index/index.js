const app = getApp()
const { request } = require('../../utils/request.js')

Page({
    data: {
        hasToken: false,
        isGuest: false,
        showBindForm: false,
        targetRole: '',
        bindName: '',
        bindPhone: ''
    },

    onLoad() {
        if (app.globalData.token) {
            this.setData({ hasToken: true })
            this.checkUserRole()
        }
    },

    handleLogin() {
        wx.showLoading({ title: '登录中...' })
        wx.login({
            success: async (res) => {
                if (res.code) {
                    try {
                        const result = await request('/wechat/login', {
                            method: 'POST',
                            data: { code: res.code }
                        })

                        if (result.ok) {
                            app.globalData.token = result.token
                            wx.setStorageSync('token', result.token)
                            this.setData({ hasToken: true })

                            // 处理角色跳转
                            this.handleRoleRedirect(result.user.role)
                        } else {
                            wx.showToast({ title: '登录失败', icon: 'none' })
                        }
                    } catch (err) {
                        console.error(err)
                        wx.showToast({ title: '请求失败', icon: 'none' })
                    } finally {
                        wx.hideLoading()
                    }
                }
            }
        })
    },

    async checkUserRole() {
        // 如果已有 token，调用 /me 接口确认角色（或者直接存储在本地）
        // 这里简化处理，假设 login 返回的 role 是准确的
        // 实际项目中应该调用 /api/v1/me
        try {
            const res = await request('/v1/me')
            if (res.ok) {
                this.handleRoleRedirect(res.data.role)
            }
        } catch (err) {
            // token 可能失效
            this.setData({ hasToken: false })
            wx.removeStorageSync('token')
        }
    },

    handleRoleRedirect(role) {
        if (role === 'student') {
            wx.reLaunch({ url: '/pages/student/home/index' })
        } else if (role === 'parent') {
            wx.reLaunch({ url: '/pages/parent/home/index' })
        } else {
            // guest or other
            this.setData({ isGuest: true })
        }
    },

    selectRole(e) {
        const role = e.currentTarget.dataset.role
        this.setData({
            targetRole: role,
            showBindForm: true,
            isGuest: false // 隐藏选择卡片
        })
    },

    cancelBind() {
        this.setData({
            showBindForm: false,
            isGuest: true
        })
    },

    async confirmBind() {
        if (!this.data.bindName) {
            wx.showToast({ title: '请输入姓名', icon: 'none' })
            return
        }

        wx.showLoading({ title: '绑定中...' })
        try {
            const res = await request('/wechat/bind', {
                method: 'POST',
                data: {
                    role: this.data.targetRole,
                    name: this.data.bindName,
                    phone: this.data.bindPhone
                }
            })

            if (res.ok) {
                wx.showToast({ title: '绑定成功', icon: 'success' })
                setTimeout(() => {
                    this.handleRoleRedirect(this.data.targetRole)
                }, 1500)
            } else {
                console.error('Bind error:', res)
                const errorMsg = res.error || '绑定失败'
                wx.showToast({ title: errorMsg, icon: 'none', duration: 3000 })
            }
        } catch (err) {
            console.error('Request error:', err)
            wx.showToast({ title: '请求错误: ' + JSON.stringify(err), icon: 'none', duration: 3000 })
        } finally {
            wx.hideLoading()
        }
    },

    async handleDebugUnbind() {
        // 先检查是否有 token
        if (!app.globalData.token) {
            wx.showToast({ title: '请先登录', icon: 'none' })
            return
        }

        try {
            console.log('Attempting to unbind...')
            const res = await request('/wechat/unbind', { method: 'POST' })
            console.log('Unbind response:', res)

            if (res.ok) {
                wx.showToast({ title: '解绑成功', icon: 'success' })
                wx.removeStorageSync('token')
                wx.removeStorageSync('userInfo')
                wx.removeStorageSync('role')
                app.globalData.token = null
                app.globalData.userInfo = null
                app.globalData.role = null

                this.setData({
                    hasToken: false,
                    isGuest: true,
                    showBindForm: false
                })
            } else {
                console.error('Unbind failed, response not ok:', res)
                wx.showToast({ title: `解绑失败: ${res.error || '未知错误'}`, icon: 'none', duration: 3000 })
            }
        } catch (err) {
            console.error('Unbind error:', err)
            wx.showToast({ title: `解绑失败: ${JSON.stringify(err)}`, icon: 'none', duration: 3000 })
        }
    }
})
