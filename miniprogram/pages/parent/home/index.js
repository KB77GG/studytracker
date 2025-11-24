const app = getApp()
const { request } = require('../../../utils/request.js')

Page({
    data: {
        students: [],
        currentStudentIndex: 0,
        stats: null,
        loading: true,
        todayDate: ''
    },

    onLoad() {
        const now = new Date()
        this.setData({
            todayDate: `${now.getMonth() + 1}月${now.getDate()}日`
        })
        this.fetchStudents()
    },

    onPullDownRefresh() {
        if (this.data.students.length > 0) {
            this.fetchStats(this.data.students[this.data.currentStudentIndex].name)
        } else {
            this.fetchStudents()
        }
    },

    async fetchStudents() {
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
        wx.showLoading({ title: '加载中...' })
        try {
            const res = await request(`/miniprogram/parent/stats?student_name=${encodeURIComponent(studentName)}`)
            if (res.ok) {
                this.setData({ stats: res })
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
        wx.navigateTo({
            url: '/pages/index/index?action=bind_parent'
        })
    },

    viewReport() {
        const student = this.data.students[this.data.currentStudentIndex]
        wx.navigateTo({
            url: `/pages/parent/report/index?student=${encodeURIComponent(student.name)}`
        })
    }
})
