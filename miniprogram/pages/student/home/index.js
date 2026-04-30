const app = getApp()
const { request } = require('../../../utils/request.js')
const { getSubscribeSummary, requestTemplateSubscribe } = require('../../../utils/subscribe.js')
const TASK_TEMPLATE_ID = 'GElWxP8srvY_TwH-h69q4XcmgLyNZBsvjp6rSt8dhUU'
const COURSE_TEMPLATE_ID = 'AehPa5pMUTnQqXgq-q-wxTAMZyVU-qdkxaO9rbpo-QI'

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
        timerInterval: null,
        hasSubscribed: false,
        subscribeState: 'unknown',
        subscribeButtonText: '开启任务提醒',
        subscribeTip: '多次允许后，微信会出现“总是保持以上选择”，勾选即可长期免打扰',
        notebookCount: 0,
        reviewTaskCount: 0,
        isGuest: false,
        weekdayText: '',
        quickDates: []
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
            userInfo: app.globalData.userInfo || { nickName: '同学' },
            weekdayText: this.getWeekdayText(now),
            quickDates: this.buildQuickDates(dateString)
        })
    },

    onShow() {
        if (typeof this.getTabBar === 'function' && this.getTabBar()) {
            this.getTabBar().setData({
                selected: 0
            })
        }
        // Guest mode detection
        const isGuest = !!getApp().globalData.guestMode
        this.setData({ isGuest })

        this.fetchTasks()
        this.loadNotebookCount()
        this.updateGreeting()

        // Restore timer if there's an active one in storage
        this.restoreTimerIfNeeded()
        this.refreshSubscribeStatus()
    },

    // Restore timer state from storage
    restoreTimerIfNeeded() {
        try {
            // First check app.globalData, if not found check storage
            let activeTimer = getApp().globalData.activeTimer
            if (!activeTimer) {
                activeTimer = wx.getStorageSync('activeTimer')
                if (activeTimer && activeTimer.taskId) {
                    // Sync to app.globalData
                    getApp().globalData.activeTimer = activeTimer
                }
            }

            if (!activeTimer || !activeTimer.taskId) return

            const { taskId, sessionId, startTime } = activeTimer

            // Calculate elapsed time
            const now = Date.now()
            const elapsedMs = now - startTime
            const elapsedSeconds = Math.floor(elapsedMs / 1000)

            // Find the task in current tasks list
            const taskIndex = this.data.tasks.findIndex(t => t.id === taskId)
            if (taskIndex === -1) {
                // Task not found, clear storage and globalData
                wx.removeStorageSync('activeTimer')
                getApp().globalData.activeTimer = null
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

            // Start update interval
            if (this.data.timerInterval) {
                clearInterval(this.data.timerInterval)
            }
            const interval = setInterval(() => {
                this.updateTimerDisplay()
            }, 1000)
            this.setData({ timerInterval: interval })

            console.log(`Timer restored: ${elapsedSeconds}s elapsed`)

        } catch (e) {
            console.error('Restore timer error:', e)
        }
    },

    async refreshSubscribeStatus() {
        if (getApp().globalData.guestMode) {
            this.setData({
                hasSubscribed: false,
                subscribeState: 'guest',
                subscribeButtonText: '登录后开启提醒',
                subscribeTip: '登录后可接收作业和课程提醒'
            })
            return
        }
        const summary = await getSubscribeSummary([TASK_TEMPLATE_ID, COURSE_TEMPLATE_ID])
        this.setData(this.buildSubscribeView(summary))
    },

    buildSubscribeView(summary) {
        const state = summary && summary.state ? summary.state : 'unknown'
        if (state === 'accept') {
            return {
                hasSubscribed: true,
                subscribeState: state,
                subscribeButtonText: '提醒已开启',
                subscribeTip: '如需修改提醒偏好，请前往微信设置页'
            }
        }
        if (state === 'partial') {
            return {
                hasSubscribed: true,
                subscribeState: state,
                subscribeButtonText: '补全提醒',
                subscribeTip: '部分提醒已开启，建议再次确认任务和课程提醒'
            }
        }
        if (state === 'reject') {
            return {
                hasSubscribed: false,
                subscribeState: state,
                subscribeButtonText: '去设置开启',
                subscribeTip: '你已关闭提醒，请在设置里重新开启'
            }
        }
        if (state === 'ban') {
            return {
                hasSubscribed: false,
                subscribeState: state,
                subscribeButtonText: '查看提醒状态',
                subscribeTip: '当前模板不可用，请联系老师检查配置'
            }
        }
        if (state === 'off') {
            return {
                hasSubscribed: false,
                subscribeState: state,
                subscribeButtonText: '去设置开启',
                subscribeTip: '微信总提醒开关已关闭，请先开启'
            }
        }
        return {
            hasSubscribed: false,
            subscribeState: state,
            subscribeButtonText: '开启任务提醒',
            subscribeTip: '多次允许后，微信会出现“总是保持以上选择”，勾选即可长期免打扰'
        }
    },

    openSubscribeSettings() {
        wx.openSetting({
            success: () => {
                this.refreshSubscribeStatus()
            }
        })
    },

    requestSubscribe() {
        if (getApp().globalData.guestMode) {
            this.goLogin()
            return
        }
        if (['reject', 'off'].includes(this.data.subscribeState)) {
            wx.showModal({
                title: '开启提醒',
                content: '当前提醒已关闭，请在设置页重新开启任务提醒。',
                success: (res) => {
                    if (res.confirm) {
                        this.openSubscribeSettings()
                    }
                }
            })
            return
        }
        if (this.data.subscribeState === 'ban') {
            wx.showToast({ title: '提醒模板不可用', icon: 'none' })
            return
        }
        const tmplIds = [TASK_TEMPLATE_ID, COURSE_TEMPLATE_ID]
        requestTemplateSubscribe(tmplIds)
            .then((res) => {
                const accepted = tmplIds.some((id) => res[id] === 'accept')
                if (accepted) {
                    wx.showToast({ title: '提醒已记录', icon: 'success' })
                } else {
                    wx.showToast({ title: '本次未订阅，再次点击可重试', icon: 'none', duration: 3000 })
                }
                this.refreshSubscribeStatus()
            })
            .catch((err) => {
                console.warn('subscribe fail', err)
                wx.showToast({ title: '请通过按钮手动开启提醒', icon: 'none' })
            })
    },

    goNotebook() {
        wx.navigateTo({
            url: '/pages/student/notebook/index'
        })
    },

    loadNotebookCount() {
        try {
            const list = wx.getStorageSync('dictation_notebook') || []
            if (Array.isArray(list)) {
                this.setData({ notebookCount: list.length })
            } else {
                this.setData({ notebookCount: 0 })
            }
        } catch (e) {
            this.setData({ notebookCount: 0 })
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
        const dateObj = new Date(`${date}T00:00:00`)
        this.setData({
            currentDate: date,
            dateStr: `${year}/${month}/${day}`,
            weekdayText: this.getWeekdayText(dateObj),
            quickDates: this.buildQuickDates(date)
        })
        this.fetchTasks()
    },

    selectQuickDate(e) {
        const date = e.currentTarget.dataset.date
        if (!date || date === this.data.currentDate) return
        const [year, month, day] = date.split('-')
        const dateObj = new Date(`${date}T00:00:00`)
        this.setData({
            currentDate: date,
            dateStr: `${year}/${month}/${day}`,
            weekdayText: this.getWeekdayText(dateObj),
            quickDates: this.buildQuickDates(date)
        })
        this.fetchTasks()
    },

    getWeekdayText(dateObj) {
        const days = ['日', '一', '二', '三', '四', '五', '六']
        return days[dateObj.getDay()]
    },

    formatDateObj(dateObj) {
        const year = dateObj.getFullYear()
        const month = String(dateObj.getMonth() + 1).padStart(2, '0')
        const day = String(dateObj.getDate()).padStart(2, '0')
        return `${year}-${month}-${day}`
    },

    buildQuickDates(selectedDate) {
        const selected = new Date(`${selectedDate}T00:00:00`)
        const today = new Date()
        today.setHours(0, 0, 0, 0)
        const labels = {
            '-2': '前天',
            '-1': '昨天',
            '0': '今天',
            '1': '明天',
            '2': '后天'
        }
        return [-2, -1, 0, 1].map(offset => {
            const d = new Date(selected)
            d.setDate(selected.getDate() + offset)
            const diffFromToday = Math.round((d.getTime() - today.getTime()) / 86400000)
            return {
                date: this.formatDateObj(d),
                label: `${d.getMonth() + 1}/${d.getDate()}`,
                sub: labels[String(diffFromToday)] || `周${this.getWeekdayText(d)}`
            }
        })
    },

    goLogin() {
        getApp().globalData.guestMode = false
        wx.reLaunch({ url: '/pages/index/index' })
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
                const tasks = res.tasks.map(t => {
                    // Use actual_seconds from backend, default to 0 if not present
                    const actualSeconds = t.actual_seconds || 0
                    const plannedSeconds = t.planned_minutes * 60
                    const iconInfo = this.getModuleIcon(t.module || t.task_name || '')

                    return {
                        id: t.id,
                        task_name: t.task_name,
                        module: t.module,
                        moduleClass: this.getModuleClass(t.module),
                        iconText: iconInfo.text,
                        iconClass: iconInfo.cls,
                        planned_minutes: t.planned_minutes,
                        status: t.status,
                        statusText: this.getStatusText(t.status),
                        isDone: t.status === 'completed' || t.status === 'submitted',
                        // Dictation Fields
                        dictationBookId: t.dictation_book_id,
                        // Speaking Fields
                        speakingBookId: t.speaking_book_id,
                        materialType: t.material_type || null,
                        materialId: t.material_id || null,
                        // Listening Fields
                        listeningResourceType: t.listening_resource_type || 'intensive',
                        listeningToken: t.listening_token || '',
                        listeningUrl: t.listening_url || null,

                        // Timer state - show actual time spent from backend
                        timerStatus: 'idle',
                        elapsedSeconds: actualSeconds,
                        displayTime: this.formatTime(actualSeconds),
                        plannedTime: this.formatTime(plannedSeconds),
                        isOvertime: actualSeconds > plannedSeconds,
                        sessionId: null
                    }
                })

                // 计算进度
                const total = tasks.length
                const completed = tasks.filter(t => t.isDone).length
                const percent = total > 0 ? Math.round((completed / total) * 100) : 0
                const reviewTaskCount = tasks.filter(t => t.status === 'rejected').length

                this.setData({
                    tasks,
                    progress: { total, completed, percent },
                    reviewTaskCount
                })
            } else {
                this.setData({
                    tasks: [],
                    progress: { total: 0, completed: 0, percent: 0 },
                    reviewTaskCount: 0
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

    getModuleIcon(text) {
        const lower = text.toLowerCase()
        if (lower.includes('听') || lower.includes('听力') || lower.includes('朗读')) {
            return { text: 'L', cls: 'listening' } // Listening
        }
        if (lower.includes('读') || lower.includes('阅读')) {
            return { text: 'R', cls: 'reading' }
        }
        if (lower.includes('写') || lower.includes('作文') || lower.includes('写作')) {
            return { text: 'W', cls: 'writing' }
        }
        if (lower.includes('词') || lower.includes('单词') || lower.includes('词汇')) {
            return { text: 'V', cls: 'vocab' }
        }
        if (lower.includes('口语')) {
            return { text: 'S', cls: 'speaking' }
        }
        return { text: 'T', cls: 'default' };
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
        const task = this.data.tasks.find(t => t.id === taskId)
        if (this.openListeningTask(taskId, task)) return
        if (task && (task.materialType === 'reading_vocab_choice' || task.materialType === 'grammar' || task.materialType === 'translation')) {
            wx.navigateTo({
                url: `/pages/student/material-choice/practice/index?taskId=${taskId}`,
            })
            return
        }
        wx.navigateTo({
            url: `/pages/student/task/index?id=${taskId}`,
        })
    },

    openListeningTask(taskId, task) {
        if (!task || !task.listeningUrl) return false
        if (task.listeningResourceType === 'cambridge_test') {
            wx.navigateTo({
                url: `/pages/student/webview/index?url=${encodeURIComponent(task.listeningUrl)}`
            })
            return true
        }
        const token = encodeURIComponent(task.listeningToken || '')
        wx.navigateTo({
            url: `/pages/student/listening/practice/index?taskId=${taskId}&token=${token}`
        })
        return true
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
        console.log('Start button clicked', e) // Debug log
        const taskId = e.currentTarget.dataset.id
        console.log('Task ID:', taskId) // Debug log

        if (!taskId) {
            console.error('No task ID found')
            wx.showToast({ title: '任务ID丢失', icon: 'none' })
            return
        }
        const activeTimer = getApp().globalData.activeTimer

        // Dictation Routing
        const task = this.data.tasks.find(t => t.id === taskId)
        if (this.openListeningTask(taskId, task)) return

        if (task && task.dictationBookId) {
            wx.navigateTo({
                url: `/pages/student/dictation/practice/index?taskId=${taskId}&id=${task.dictationBookId}`
            })
            return
        }

        // Speaking Routing
        if (task && task.speakingBookId) {
            wx.navigateTo({
                url: `/pages/student/speaking/practice/index?taskId=${taskId}&id=${task.speakingBookId}`
            })
            return
        }

        if (task && (task.materialType === 'reading_vocab_choice' || task.materialType === 'grammar' || task.materialType === 'translation')) {
            wx.navigateTo({
                url: `/pages/student/material-choice/practice/index?taskId=${taskId}`
            })
            return
        }

        // Check if there's already an active timer for this task
        if (activeTimer && activeTimer.taskId === taskId) {
            wx.navigateTo({
                url: `/pages/student/task/index?id=${taskId}`
            })
            return
        }

        // If there's an active timer for a different task, warn user
        if (activeTimer && activeTimer.taskId !== taskId) {
            const res = await wx.showModal({
                title: '提示',
                content: '您有另一个任务正在计时中，是否要停止当前计时并开始新任务？',
                confirmText: '开始新任务',
                cancelText: '取消'
            })

            if (!res.confirm) return

            // User confirmed, clear old timer
            getApp().globalData.activeTimer = null
            wx.removeStorageSync('activeTimer')
        }

        try {
            wx.showLoading({ title: '启动中...' }) // Visual feedback
            // Call backend to create session - use miniprogram API
            const res = await request(`/miniprogram/student/tasks/${taskId}/timer/start`, {
                method: 'POST'
            })
            console.log('Start timer response:', res) // Debug log
            wx.hideLoading()

            if (res.ok) {
                const tasks = this.data.tasks.map(task => {
                    if (task.id === taskId) {
                        return {
                            ...task,
                            timerStatus: 'running',
                            sessionId: res.session_id,
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

                // Save to storage and globalData
                const timerData = {
                    taskId,
                    sessionId: res.session_id,
                    startTime: Date.now()
                }
                wx.setStorageSync('activeTimer', timerData)
                getApp().globalData.activeTimer = timerData

                // Navigate to task detail page
                wx.navigateTo({
                    url: `/pages/student/task/index?id=${taskId}`
                })
            }
        } catch (err) {
            wx.hideLoading()
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
            // Call backend to stop session - use miniprogram API
            const res = await request(`/miniprogram/student/tasks/${taskId}/timer/${task.sessionId}/stop`, {
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
