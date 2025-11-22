const app = getApp()
const { request } = require('../../../utils/request.js')

Page({
    data: {
        dateStr: '',
        tasks: [],
        loading: true
    },

    onLoad() {
        this.setData({
            dateStr: new Date().toLocaleDateString()
        })
    },

    onShow() {
        this.fetchTasks()
    },

    async fetchTasks() {
        wx.showLoading({ title: '加载中...' })
        try {
            const res = await request('/miniprogram/student/tasks/today')
            console.log('Tasks response:', res)

            if (res.ok && res.tasks) {
                const tasks = res.tasks.map(t => ({
                    id: t.id,
                    task_name: t.task_name,
                    module: t.module,
                    planned_minutes: t.planned_minutes,
                    status: t.status,
                    statusText: this.getStatusText(t.status)
                }))
                this.setData({ tasks })
            } else {
                this.setData({ tasks: [] })
            }
        } catch (err) {
            console.error('Fetch tasks error:', err)
            wx.showToast({ title: '加载失败', icon: 'none' })
        } finally {
            wx.hideLoading()
            this.setData({ loading: false })
        }
    },

    getStatusText(status) {
        const map = {
            'pending': '待完成',
            'in_progress': '进行中',
            'submitted': '审核中',
            'completed': '已完成',
            'approved': '已通过',
            'rejected': '需修改'
        }
        return map[status] || status
    },

    goToTaskDetail(e) {
        const taskId = e.currentTarget.dataset.id
        wx.navigateTo({
            url: `/pages/student/task/index?id=${taskId}`,
        })
    }
})
