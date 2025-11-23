const app = getApp()
const { request } = require('../../../utils/request.js')

Page({
    data: {
        dateStr: '',
        greeting: '',
        userInfo: null,
        tasks: [],
        progress: {
            total: 0,
            completed: 0,
            percent: 0
        },
        loading: true
    },

    onLoad() {
        this.updateGreeting()
        this.setData({
            dateStr: new Date().toLocaleDateString(),
            userInfo: app.globalData.userInfo || { nickName: '同学' }
        })
    },

    onShow() {
        this.fetchTasks()
        this.updateGreeting()
    },

    updateGreeting() {
        const hour = new Date().getHours()
        let greeting = '你好'
        if (hour < 6) greeting = '夜深了'
        else if (hour < 11) greeting = '早上好'
        else if (hour < 14) greeting = '中午好'
        else if (hour < 18) greeting = '下午好'
        else greeting = '晚上好'

        this.setData({ greeting })
    },

    async fetchTasks() {
        // wx.showLoading({ title: '加载中...' }) // 移除 loading 以免闪烁
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
                    statusText: this.getStatusText(t.status),
                    isDone: t.status === 'completed' || t.status === 'submitted'
                }))

                // 计算进度
                const total = tasks.length
                const completed = tasks.filter(t => t.isDone).length
                const percent = total > 0 ? Math.round((completed / total) * 100) : 0

                this.setData({
                    tasks,
                    progress: { total, completed, percent }
                })
            } else {
                this.setData({
                    tasks: [],
                    progress: { total: 0, completed: 0, percent: 0 }
                })
            }
        } catch (err) {
            console.error('Fetch tasks error:', err)
            // wx.showToast({ title: '加载失败', icon: 'none' })
        } finally {
            // wx.hideLoading()
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
