const app = getApp()
const { request } = require('../../utils/request.js')

Page({
    data: {
        hasToken: false,
        isGuest: false,
        showBindForm: false,
        showLoginForm: false,  // 新增：控制是否显示登录表单
        targetRole: '',
        bindName: '',
        bindStudentName: '',
        bindPhone: '',
        privacyAgreed: false,
        showPreview: false
    },

    showLogin() {
        // 显示登录表单
        this.setData({
            showLoginForm: true,
            privacyAgreed: false  // 默认为false，必须用户手动勾选
        })
    },

    backToWelcome() {
        // 返回欢迎页
        this.setData({ showLoginForm: false, showPreview: false })
    },

    handlePrivacyChange(e) {
        this.setData({
            privacyAgreed: e.detail.value.length > 0
        })
    },

    showPreview() {
        this.setData({ showPreview: true, showLoginForm: false })
    },

    onLoad(options) {
        // 支持直接进入绑定模式（用于添加第二个孩子）
        if (options && options.action === 'bind_parent') {
            this.setData({
                hasToken: true,
                isGuest: false,
                showBindForm: true,
                targetRole: 'parent'
            })
            return
        }

        if (app.globalData.token) {
            this.setData({ hasToken: true })
            this.checkUserRole()
        }
    },

    openPrivacyContract() {
        wx.openPrivacyContract({
            success: () => { },
            fail: () => {
                wx.showToast({ title: '打开失败', icon: 'none' })
            }
        })
    },

    handleLogin() {
        if (!this.data.privacyAgreed) {
            wx.showToast({ title: '请先阅读并同意隐私协议', icon: 'none' })
            return
        }

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

                            // Save role to storage
                            if (result.user.role) {
                                wx.setStorageSync('role', result.user.role)
                                app.globalData.role = result.user.role
                            }

                            // 如果用户没有绑定身份（has_profile 为 false），显示角色选择
                            // 否则直接跳转到对应角色的首页
                            if (!result.user.has_profile) {
                                // 显示角色选择
                                this.setData({ isGuest: true })
                            } else {
                                // 已绑定，直接跳转
                                this.handleRoleRedirect(result.user.role)
                            }
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
                wx.setStorageSync('role', res.data.role)
                app.globalData.role = res.data.role
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
        // 如果是从其他页面 navigateTo 过来的，直接返回
        const pages = getCurrentPages()
        if (pages.length > 1) {
            wx.navigateBack()
            return
        }

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

        // 家长绑定时需要填写孩子姓名
        if (this.data.targetRole === 'parent' && !this.data.bindStudentName) {
            wx.showToast({ title: '请输入孩子的姓名', icon: 'none' })
            return
        }

        wx.showLoading({ title: '绑定中...' })
        try {
            const requestData = {
                role: this.data.targetRole,
                name: this.data.bindName,
                phone: this.data.bindPhone
            }

            // 家长角色需要提供学生姓名
            if (this.data.targetRole === 'parent') {
                requestData.student_name = this.data.bindStudentName
            }

            const res = await request('/wechat/bind', {
                method: 'POST',
                data: requestData
            })

            if (res.ok) {
                wx.showToast({ title: '绑定成功', icon: 'success' })
                wx.setStorageSync('role', this.data.targetRole)
                app.globalData.role = this.data.targetRole
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
