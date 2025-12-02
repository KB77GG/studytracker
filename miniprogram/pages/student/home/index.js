const app = getApp()
const { request } = require('../../../utils/request.js')

Page({
    data: {
        dateStr: '',
        currentDate: '', // YYYY-MM-DD 格式，用于 picker value 和 API 参数
        greeting: '',
        userInfo: null,
        tasks: [],
        progress: {
            total: 0,
            completed: 0,
            percent: 0
        },
        loading: true,
        activeTimerId: null,
        timerInterval: null
    },

    onLoad() {
        this.updateGreeting()
        const now = new Date()
        const year = now.getFullYear()
        const month = (now.getMonth() + 1).toString().padStart(2, '0')
        const day = now.getDate().toString().padStart(2, '0')
        const dateString = `${year}-${month}-${day}`

        this.setData({
            dateStr: `${year}/${month}/${day}`,
            currentDate: dateString,
            userInfo: app.globalData.userInfo || { nickName: '同学' }
        })
    },

    onShow() {
        if (typeof this.getTabBar === 'function' && this.getTabBar()) {
            this.getTabBar().setData({
                selected: 0
            })
        }
        this.fetchTasks()
        this.updateGreeting()

        // Restore timer if there's an active one in storage
        this.restoreTimerIfNeeded()
    },

    // Restore timer state from storage
    restoreTimerIfNeeded() {
        try {
            const activeTimer = wx.getStorageSync('activeTimer')
            if (!activeTimer || !activeTimer.taskId) return

            const { taskId, sessionId, startTime } = activeTimer

            // Calculate elapsed time
            const now = Date.now()
            const elapsedMs = now - startTime
            const elapsedSeconds = Math.floor(elapsedMs / 1000)

            // Find the task in current tasks list
            const taskIndex = this.data.tasks.findIndex(t => t.id === taskId)
            if (taskIndex === -1) {
                // Task not found, clear storage
                wx.removeStorageSync('activeTimer')
                return
            }

            // Restore timer state
            const tasks = this.data.tasks.map(task => {
                if (task.id === taskId) {
                    const planned = task.planned_minutes * 60
                    const isOvertime = elapsedSeconds > planned

                    return {
                        ...task,
                        timerStatus: 'running',
                        sessionId: sessionId,
                        elapsedSeconds: elapsedSeconds,
                        displayTime: this.formatTime(elapsedSeconds),
                        plannedTime: this.formatTime(planned),
                        isOvertime: isOvertime
                    }
                }
                return task
            })

            this.setData({
                tasks,
                activeTimerId: taskId
            })

            // Restart interval
            if (this.data.timerInterval) {
                clearInterval(this.data.timerInterval)
            }
            const interval = setInterval(() => {
                this.updateTimerDisplay()
            }, 1000)
            this.setData({ timerInterval: interval })

            console.log(`Timer restored: ${elapsedSeconds}s elapsed`)

        } catch (err) {
            console.error('Failed to restore timer:', err)
        }
    },

    onHide() {
        // Clear interval when page is hidden to prevent memory leaks
        if (this.data.timerInterval) {
            clearInterval(this.data.timerInterval)
            this.setData({ timerInterval: null })
        }
        // Note: We don't clear activeTimer storage here, 
        // so it can be restored when page is shown again
    },

    handleDateChange(e) {
        const date = e.detail.value // YYYY-MM-DD
        const [year, month, day] = date.split('-')
        this.setData({
            currentDate: date,
            dateStr: `${year}/${month}/${day}`
        })
        this.fetchTasks()
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
            const res = await request(`/miniprogram/student/tasks/today?date=${this.data.currentDate}`)
            console.log('Tasks response:', res)

            if (res.ok && res.tasks) {
                const tasks = res.tasks.map(t => ({
                    id: t.id,
                    task_name: t.task_name,
                    module: t.module,
                    moduleClass: this.getModuleClass(t.module),
                    planned_minutes: t.planned_minutes,
                    status: t.status,
                    statusText: this.getStatusText(t.status),
                    isDone: t.status === 'completed' || t.status === 'submitted',
                    // Timer state
                    timerStatus: 'idle',
                    elapsedSeconds: 0,
                    displayTime: '00:00',
                    plannedTime: this.formatTime(t.planned_minutes * 60),
                    isOvertime: false,
                    sessionId: null
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

    getModuleClass(module) {
        const map = {
            '语文': 'chinese',
            '数学': 'math',
            '英语': 'english'
        }
        return map[module] || ''
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
    },

    // Timer helper: format seconds to MM:SS
    formatTime(seconds) {
        const mins = Math.floor(seconds / 60)
        const secs = seconds % 60
        return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
    },

    // Update timer display every second
    updateTimerDisplay() {
        const tasks = this.data.tasks.map(task => {
            if (task.id === this.data.activeTimerId && task.timerStatus === 'running') {
                const elapsed = task.elapsedSeconds + 1
                const planned = task.planned_minutes * 60
                const isOvertime = elapsed > planned

                return {
                    ...task,
                    elapsedSeconds: elapsed,
                    displayTime: this.formatTime(elapsed),
                    isOvertime: isOvertime,
                    timerStatus: 'running'
                }
            }
            return task
        })
        this.setData({ tasks })
    },

    // Start timer
    async startTimer(e) {
        const taskId = e.currentTarget.dataset.id

        try {
            // Call backend to create session
            const res = await request(`/student/plan-items/${taskId}/timer/start`, {
                method: 'POST'
            })

            if (res.ok) {
                const tasks = this.data.tasks.map(task => {
                    if (task.id === taskId) {
                        return {
                            ...task,
                            timerStatus: 'running',
                            sessionId: res.session_id, // Note: backend returns session_id directly in res for app.py
                            elapsedSeconds: 0,
                            displayTime: '00:00',
                            plannedTime: this.formatTime(task.planned_minutes * 60),
                            isOvertime: false
                        }
                    }
                    return task
                })

                this.setData({
                    tasks,
                    activeTimerId: taskId
                })

                // Start interval
                if (this.data.timerInterval) {
                    clearInterval(this.data.timerInterval)
                }
                const interval = setInterval(() => {
                    this.updateTimerDisplay()
                }, 1000)
                this.setData({ timerInterval: interval })

                // Save to storage
                wx.setStorageSync('activeTimer', {
                    taskId,
                    sessionId: res.session_id,
                    startTime: Date.now()
                })

                // Navigate to task detail page
                wx.navigateTo({
                    url: `/pages/student/task/index?id=${taskId}`
                })
            }
        } catch (err) {
            console.error('Start timer error:', err)
            wx.showToast({ title: '启动计时失败', icon: 'none' })
        }
    },

    // Pause timer
    pauseTimer(e) {
        const taskId = e.currentTarget.dataset.id

        if (this.data.timerInterval) {
            clearInterval(this.data.timerInterval)
            this.setData({ timerInterval: null })
        }

        const tasks = this.data.tasks.map(task => {
            if (task.id === taskId) {
                return { ...task, timerStatus: 'paused' }
            }
            return task
        })

        this.setData({ tasks })
    },

    // Resume timer
    resumeTimer(e) {
        const taskId = e.currentTarget.dataset.id

        // Restart interval
        if (this.data.timerInterval) {
            clearInterval(this.data.timerInterval)
        }
        const interval = setInterval(() => {
            this.updateTimerDisplay()
        }, 1000)
        this.setData({ timerInterval: interval })

        const tasks = this.data.tasks.map(task => {
            if (task.id === taskId) {
                return { ...task, timerStatus: 'running' }
            }
            return task
        })

        this.setData({
            tasks,
            activeTimerId: taskId
        })
    },

    // Stop timer
    async stopTimer(e) {
        const taskId = e.currentTarget.dataset.id
        const task = this.data.tasks.find(t => t.id === taskId)

        if (!task) return

        try {
            // Call backend to stop session
            const res = await request(`/student/plan-items/${taskId}/timer/${task.sessionId}/stop`, {
                method: 'POST'
            })

            if (res.ok) {
                // Clear interval
                if (this.data.timerInterval) {
                    clearInterval(this.data.timerInterval)
                    this.setData({ timerInterval: null })
                }

                // Update task status
                const tasks = this.data.tasks.map(t => {
                    if (t.id === taskId) {
                        return {
                            ...t,
                            timerStatus: 'idle',
                            elapsedSeconds: 0,
                            displayTime: '00:00'
                        }
                    }
                    return t
                })

                this.setData({
                    tasks,
                    activeTimerId: null
                })

                // Clear storage
                wx.removeStorageSync('activeTimer')

                wx.showToast({ title: '计时已保存', icon: 'success' })

                // Refresh tasks
                this.fetchTasks()
            }
        } catch (err) {
            console.error('Stop timer error:', err)
            wx.showToast({ title: '保存失败', icon: 'none' })
        }
    }
})
