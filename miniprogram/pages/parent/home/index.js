const app = getApp()
const { request } = require('../../../utils/request.js')
const { buildParentDemo } = require('../../../utils/demo-data.js')

Page({
    data: {
        isGuest: false,
        students: [],
        currentStudentIndex: 0,
        stats: null,
        loading: true,
        todayDate: '',
        lastUpdateTime: null,
        baseUrl: ''
    },

    onLoad() {
        const now = new Date()
        this.setData({
            todayDate: `${now.getMonth() + 1}月${now.getDate()}日`,
            baseUrl: app.globalData.baseUrl || ''
        })
        this.fetchStudents()
    },

    onShow() {
        if (typeof this.getTabBar === 'function' && this.getTabBar()) {
            this.getTabBar().setData({
                selected: 0
            })
        }
    },

    onPullDownRefresh() {
        if (this.data.students.length > 0) {
            this.fetchStats(this.data.students[this.data.currentStudentIndex].name)
        } else {
            this.fetchStudents()
        }
    },

    async fetchStudents() {
        if (app.globalData.guestMode) {
            const demo = buildParentDemo()
            const now = new Date()
            const timeStr = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`
            this.setData({
                isGuest: true,
                students: demo.students,
                stats: demo.stats,
                lastUpdateTime: timeStr,
                loading: false
            })
            return
        }
        try {
            const res = await request('/miniprogram/parent/students')
            if (res.ok && res.students.length > 0) {
                this.setData({ students: res.students })
                // 默认加载第一个学生
                this.fetchStats(res.students[0].name)
            } else {
                this.setData({ loading: false })
                wx.showToast({ title: '未绑定学生', icon: 'none' })
            }
        } catch (err) {
            console.error(err)
            this.setData({ loading: false })
        }
    },

    async fetchStats(studentName) {
        if (app.globalData.guestMode) {
            this.setData({ stats: buildParentDemo().stats, loading: false })
            wx.stopPullDownRefresh()
            return
        }
        wx.showLoading({ title: '加载中...' })
        try {
            const res = await request(`/miniprogram/parent/stats?student_name=${encodeURIComponent(studentName)}`)
            if (res.ok) {
                const now = new Date()
                const timeStr = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`

                this.setData({
                    stats: res,
                    lastUpdateTime: timeStr
                })
            }
        } catch (err) {
            console.error(err)
            wx.showToast({ title: '加载失败', icon: 'none' })
        } finally {
            this.setData({ loading: false })
            wx.hideLoading()
            wx.stopPullDownRefresh()
        }
    },

    switchStudent(e) {
        const index = e.detail.value
        this.setData({ currentStudentIndex: index })
        this.fetchStats(this.data.students[index].name)
    },

    navigateToAddStudent() {
        if (app.globalData.guestMode) {
            this.promptLogin('绑定孩子需要先登录账号。')
            return
        }
        wx.navigateTo({
            url: '/pages/index/index?action=bind_parent'
        })
    },

    promptLogin(content) {
        wx.showModal({
            title: '需要登录',
            content,
            confirmText: '去登录',
            success: (res) => {
                if (res.confirm) {
                    this.goLogin()
                }
            }
        })
    },

    goLogin() {
        app.globalData.guestMode = false
        app.globalData.guestRole = ''
        wx.reLaunch({ url: '/pages/index/index' })
    },

    viewReport() {
        const student = this.data.students[this.data.currentStudentIndex]
        wx.navigateTo({
            url: `/pages/parent/report/index?student=${encodeURIComponent(student.name)}`
        })
    },

    viewAllFeedback() {
        const student = this.data.students[this.data.currentStudentIndex]
        wx.navigateTo({
            url: `/pages/parent/feedback/index?student=${encodeURIComponent(student.name)}`
        })
    }
})
