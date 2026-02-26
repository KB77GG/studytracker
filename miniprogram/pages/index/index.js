const app = getApp()
const { request } = require('../../utils/request.js')

Page({
    data: {
        hasToken: false,
        isGuest: false,
        showBindForm: false,
        showExistingBindForm: false,
        showLoginForm: false,  // 新增：控制是否显示登录表单
        privacyNeedAuth: false,
        landingAgreed: false,
        targetRole: '',
        bindName: '',
        bindStudentName: '',
        bindPhone: '',
        existingUsername: '',
        existingPassword: '',
        existingLoading: false,
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

    handleLandingPrivacyChange(e) {
        this.setData({
            landingAgreed: e.detail.value.length > 0
        })
    },

    showPreview() {
        // Navigate directly into student pages in guest mode (WeChat review compliance)
        app.globalData.guestMode = true
        wx.reLaunch({ url: '/pages/student/home/index' })
    },

    onLoad(options) {
        // 检查隐私授权状态
        if (typeof wx.getPrivacySetting === 'function') {
            wx.getPrivacySetting({
                success: (res) => {
                    this.setData({ privacyNeedAuth: !!res.needAuthorization })
                },
                fail: () => { }
            })
        } else {
            this.setData({ privacyNeedAuth: false })
        }

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
        if (typeof wx.openPrivacyContract === 'function') {
            wx.openPrivacyContract({
                success: () => { },
                fail: () => {
                    wx.showToast({ title: '打开失败', icon: 'none' })
                }
            })
        } else {
            wx.showToast({ title: '当前版本不支持', icon: 'none' })
        }
    },

    startUse() {
        // 欢迎页勾选一次
        if (!this.data.landingAgreed) {
            wx.showToast({ title: '请先阅读并同意隐私政策', icon: 'none' })
            return
        }
        // 同步勾选状态，进入登录
        this.setData({
            showLoginForm: true,
            privacyAgreed: true
        })
    },

    handleLogin() {
        if (!this.data.privacyAgreed) {
            wx.showToast({ title: '请先阅读并同意隐私协议', icon: 'none' })
            return
        }

        // 若平台要求弹出隐私协议，先调用官方弹窗
        if (this.data.privacyNeedAuth) {
            try {
                wx.openPrivacyContract({
                    success: () => { },
                    fail: () => { wx.showToast({ title: '请先查看隐私政策', icon: 'none' }) }
                })
            } catch (e) {
                // ignore
            }
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
                            app.globalData.guestMode = false
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
            },
            fail: () => {
                wx.hideLoading()
                wx.showToast({ title: '微信登录失败', icon: 'none' })
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
        app.globalData.guestMode = false
        if (role === 'student') {
            wx.reLaunch({ url: '/pages/student/home/index' })
        } else if (role === 'parent') {
            wx.reLaunch({ url: '/pages/parent/home/index' })
        } else if (role === 'teacher') {
            wx.reLaunch({ url: '/pages/teacher/home/index' })
        } else {
            // guest or other
            this.setData({ isGuest: true })
        }
    },

    selectRole(e) {
        const role = e.currentTarget.dataset.role
        if (role === 'teacher') {
            this.showExistingBind()
            return
        }
        this.setData({
            targetRole: role,
            showBindForm: true,
            showExistingBindForm: false,
            isGuest: false // 隐藏选择卡片
        })
    },

    showExistingBind() {
        this.setData({
            showExistingBindForm: true,
            showBindForm: false,
            isGuest: false
        })
    },

    cancelExistingBind() {
        this.setData({
            showExistingBindForm: false,
            existingUsername: '',
            existingPassword: '',
            existingLoading: false,
            isGuest: true
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
            showExistingBindForm: false,
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

    async confirmExistingBind() {
        const username = (this.data.existingUsername || '').trim()
        const password = this.data.existingPassword || ''
        if (!username || !password) {
            wx.showToast({ title: '请输入用户名和密码', icon: 'none' })
            return
        }

        this.setData({ existingLoading: true })
        try {
            const res = await request('/wechat/bind_existing', {
                method: 'POST',
                data: { username, password }
            })
            if (res && res.ok) {
                app.globalData.token = res.token
                wx.setStorageSync('token', res.token)
                if (res.user && res.user.role) {
                    wx.setStorageSync('role', res.user.role)
                    app.globalData.role = res.user.role
                }
                wx.showToast({ title: '绑定成功', icon: 'success' })
                this.setData({
                    showExistingBindForm: false,
                    existingUsername: '',
                    existingPassword: '',
                    existingLoading: false
                })
                this.handleRoleRedirect(res.user.role)
            } else {
                let msg = (res && res.error) || '绑定失败'
                if (res && res.error === 'invalid_credentials') msg = '用户名或密码错误'
                if (res && res.error === 'not_teacher') msg = '该账号不是老师角色'
                if (res && res.error === 'wechat_already_bound') msg = '该账号已绑定其他微信'
                if (res && res.error === 'user_inactive') msg = '账号已停用'
                if (res && res.error === 'role_conflict') msg = '当前微信已绑定学生/家长，无法合并'
                wx.showToast({ title: msg, icon: 'none', duration: 3000 })
            }
        } catch (err) {
            console.error('Bind existing error:', err)
            wx.showToast({ title: '请求错误', icon: 'none' })
        } finally {
            this.setData({ existingLoading: false })
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
