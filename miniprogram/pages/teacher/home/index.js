const app = getApp()
const { request } = require('../../../utils/request.js')
const { getSubscribeSummary, requestTemplateSubscribe } = require('../../../utils/subscribe.js')
const COURSE_TEMPLATE_ID = 'AehPa5pMUTnQqXgq-q-wxTAMZyVU-qdkxaO9rbpo-QI'
const DEFAULT_START_HOUR = 8
const DEFAULT_END_HOUR = 22
const HOUR_HEIGHT = 72

Page({
    data: {
        loading: true,
        viewDays: 7,
        schedules: [],
        hasSubscribed: false,
        subscribeState: 'unknown',
        subscribeButtonText: '开启提醒',
        subscribeTip: '多次允许后，微信会出现“总是保持以上选择”，勾选即可长期免打扰',
        teacherGreeting: '',
        bindRequired: false,
        schedulerTeacherId: '',
        bindLoading: false,
        viewMode: 'calendar',
        weekDays: [],
        monthDays: [],
        monthLabel: '',
        calendarMonth: '',
        weekHeaders: ['一', '二', '三', '四', '五', '六', '日'],
        todayDate: '',
        selectedDate: '',
        selectedItems: [],
        todayItems: [],
        scrollIntoView: '',
        dashboardStats: {
            todayCourses: 0,
            pendingHomework: 0,
            pendingFeedback: 0,
            studentCount: 0
        },
        touchStartX: 0,
        timeSlots: [],
        gridStartHour: DEFAULT_START_HOUR,
        gridEndHour: DEFAULT_END_HOUR,
        hourHeight: HOUR_HEIGHT,
        gridHeight: (DEFAULT_END_HOUR - DEFAULT_START_HOUR) * HOUR_HEIGHT
    },

    onShow() {
        this.updateGreeting()
        if (!this.data.calendarMonth) {
            const now = new Date()
            this.setData({
                calendarMonth: this.formatMonth(now),
                todayDate: this.formatDate(now)
            })
        }
        this.fetchSchedules()
        this.refreshSubscribeStatus()
        if (typeof this.getTabBar === 'function' && this.getTabBar()) {
            this.getTabBar().setData({ selected: 0 })
        }
    },

    updateGreeting() {
        const hour = new Date().getHours()
        let teacherGreeting = '你好'
        if (hour < 6) teacherGreeting = '夜深了'
        else if (hour < 12) teacherGreeting = '上午好'
        else if (hour < 14) teacherGreeting = '中午好'
        else if (hour < 18) teacherGreeting = '下午好'
        else teacherGreeting = '晚上好'
        this.setData({ teacherGreeting })
    },

    async fetchSchedules() {
        this.setData({ loading: true })
        try {
            const res = await request('/miniprogram/teacher/schedules', {
                method: 'GET',
                data: {
                    days: this.data.viewDays,
                    month: this.data.calendarMonth
                }
            })
            if (res && res.ok !== false) {
                const list = res.schedules || []
                let dashboardList = list
                const currentMonth = this.formatMonth(new Date())
                if (this.data.calendarMonth && this.data.calendarMonth !== currentMonth) {
                    const todayRes = await request('/miniprogram/teacher/schedules', {
                        method: 'GET',
                        data: { month: currentMonth }
                    })
                    if (todayRes && todayRes.ok !== false) {
                        dashboardList = todayRes.schedules || []
                    }
                }
                const grouped = this.groupByDate(list)
                const weekData = this.buildWeekView(list)
                const monthData = this.buildMonthView(list)
                const dashboard = this.buildDashboard(dashboardList)
                this.setData({
                    schedules: grouped,
                    weekDays: weekData.days,
                    monthDays: monthData.days,
                    monthLabel: monthData.label,
                    calendarMonth: monthData.month,
                    selectedDate: monthData.selectedDate || weekData.selectedDate,
                    selectedItems: monthData.selectedItems || weekData.selectedItems,
                    todayItems: dashboard.todayItems,
                    dashboardStats: dashboard.stats,
                    bindRequired: false
                })
            } else {
                if (res && res.error === 'missing_scheduler_teacher_id') {
                    this.setData({ bindRequired: true, schedules: [] })
                    wx.showToast({ title: '请先绑定排课老师ID', icon: 'none' })
                } else {
                    wx.showToast({ title: (res && res.error) || '加载失败', icon: 'none' })
                }
            }
        } catch (e) {
            console.warn('teacher home fetchSchedules failed', e)
            wx.showToast({ title: '网络错误', icon: 'none' })
        } finally {
            this.setData({ loading: false })
        }
    },

    groupByDate(list) {
        const map = {}
        list.forEach(item => {
            const date = item.schedule_date || (item.start_time || '').split(' ')[0] || '待定'
            if (!map[date]) map[date] = []
            const color = this.pickSubjectColor(item.course_name || '')
            map[date].push({
                ...item,
                timeRange: this.formatTimeRange(item.start_time, item.end_time),
                accentColor: color.border,
                accentBg: color.bg
            })
        })
        return Object.keys(map).sort().map(date => ({
            date,
            items: map[date],
            count: map[date].length
        }))
    },

    buildWeekView(list) {
        const weekStart = this.getWeekStartDate(new Date())
        const days = []
        const dayMap = {}
        for (let i = 0; i < 7; i += 1) {
            const d = new Date(weekStart)
            d.setDate(weekStart.getDate() + i)
            const date = this.formatDate(d)
            const weekday = this.formatWeekday(d)
            const day = {
                date,
                weekday,
                dayNum: d.getDate(),
                isToday: date === this.formatDate(new Date()),
                items: [],
                dots: [],
                count: 0
            }
            dayMap[date] = day
            days.push(day)
        }

        list.forEach(item => {
            const date = item.schedule_date || (item.start_time || '').split(' ')[0] || ''
            const target = dayMap[date]
            if (!target) return
            const timeInfo = this.parseTimeRange(item, 0, 24)
            const color = this.pickSubjectColor(item.course_name || '')
            target.items.push({
                ...item,
                timeRange: this.formatTimeRange(item.start_time, item.end_time),
                accentColor: color.border,
                accentBg: color.bg,
                _startMinutes: timeInfo.startMinutes
            })
        })

        days.forEach(day => {
            day.items.sort((a, b) => (a._startMinutes || 0) - (b._startMinutes || 0))
            day.count = day.items.length
            const dots = []
            day.items.forEach(item => {
                if (item.accentColor && !dots.includes(item.accentColor)) {
                    dots.push(item.accentColor)
                }
            })
            day.dots = dots.slice(0, 3)
        })

        const today = this.formatDate(new Date())
        let selectedDate = this.data.selectedDate
        if (!selectedDate || !dayMap[selectedDate]) {
            selectedDate = dayMap[today] ? today : days[0].date
        }

        return {
            days,
            selectedDate,
            selectedItems: dayMap[selectedDate] ? dayMap[selectedDate].items : []
        }
    },

    buildMonthView(list) {
        const monthValue = this.data.calendarMonth || this.formatMonth(new Date())
        const base = new Date(`${monthValue}-01T00:00:00`)
        const year = base.getFullYear()
        const month = base.getMonth()
        const monthLabel = `${year}年${month + 1}月`
        const firstDay = new Date(year, month, 1)
        const daysInMonth = new Date(year, month + 1, 0).getDate()
        const startOffset = (firstDay.getDay() + 6) % 7

        const dayMap = {}
        list.forEach(item => {
            const date = item.schedule_date || (item.start_time || '').split(' ')[0] || ''
            if (!date) return
            if (!dayMap[date]) dayMap[date] = []
            const timeInfo = this.parseTimeRange(item, 0, 24)
            const color = this.pickSubjectColor(item.course_name || '')
            dayMap[date].push({
                ...item,
                timeRange: this.formatTimeRange(item.start_time, item.end_time),
                accentColor: color.border,
                accentBg: color.bg,
                _startMinutes: timeInfo.startMinutes
            })
        })

        const days = []
        for (let i = 0; i < startOffset; i += 1) {
            days.push({ isPlaceholder: true })
        }

        for (let day = 1; day <= daysInMonth; day += 1) {
            const dateObj = new Date(year, month, day)
            const date = this.formatDate(dateObj)
            const items = (dayMap[date] || []).sort((a, b) => (a._startMinutes || 0) - (b._startMinutes || 0))
            const dots = []
            items.forEach(item => {
                if (item.accentColor && !dots.includes(item.accentColor)) dots.push(item.accentColor)
            })
            days.push({
                date,
                dayNum: day,
                isToday: date === this.formatDate(new Date()),
                items,
                dots: dots.slice(0, 3),
                count: items.length
            })
        }

        while (days.length % 7 !== 0) {
            days.push({ isPlaceholder: true })
        }

        const today = this.formatDate(new Date())
        let selectedDate = this.data.selectedDate
        const selectedInMonth = selectedDate && selectedDate.slice(0, 7) === monthValue
        if (!selectedInMonth) {
            selectedDate = today.slice(0, 7) === monthValue ? today : `${monthValue}-01`
        }

        return {
            days,
            label: monthLabel,
            month: monthValue,
            selectedDate,
            selectedItems: dayMap[selectedDate] || []
        }
    },

    buildDashboard(list) {
        const today = this.formatDate(new Date())
        const todayItems = []
        const students = {}
        let pendingFeedback = 0

        list.forEach(item => {
            const date = item.schedule_date || (item.start_time || '').split(' ')[0] || ''
            const color = this.pickSubjectColor(item.course_name || '')
            const decorated = {
                ...item,
                timeRange: this.formatTimeRange(item.start_time, item.end_time),
                accentColor: color.border,
                accentBg: color.bg
            }
            if (item.student_id || item.student_name) {
                students[item.student_id || item.student_name] = true
            }
            if (date === today) {
                todayItems.push(decorated)
                if (!item.feedback) pendingFeedback += 1
            }
        })

        todayItems.sort((a, b) => {
            const aTime = this.parseTimeRange(a, 0, 24)
            const bTime = this.parseTimeRange(b, 0, 24)
            return (aTime.startMinutes || 0) - (bTime.startMinutes || 0)
        })

        return {
            todayItems,
            stats: {
                todayCourses: todayItems.length,
                pendingHomework: todayItems.length,
                pendingFeedback,
                studentCount: Object.keys(students).length
            }
        }
    },

    formatDate(dateObj) {
        const y = dateObj.getFullYear()
        const m = String(dateObj.getMonth() + 1).padStart(2, '0')
        const d = String(dateObj.getDate()).padStart(2, '0')
        return `${y}-${m}-${d}`
    },

    formatMonth(dateObj) {
        const y = dateObj.getFullYear()
        const m = String(dateObj.getMonth() + 1).padStart(2, '0')
        return `${y}-${m}`
    },

    formatWeekday(dateObj) {
        const days = ['日', '一', '二', '三', '四', '五', '六']
        return `周${days[dateObj.getDay()]}`
    },

    getWeekStartDate(dateObj) {
        const d = new Date(dateObj)
        const day = d.getDay()
        const diff = (day + 6) % 7
        d.setDate(d.getDate() - diff)
        d.setHours(0, 0, 0, 0)
        return d
    },

    parseTimePart(value) {
        if (!value) return null
        let timeStr = value
        if (value.includes(' ')) {
            timeStr = value.split(' ')[1]
        }
        const parts = timeStr.split(':')
        const hour = Number(parts[0])
        const minute = Number(parts[1] || 0)
        if (Number.isNaN(hour) || Number.isNaN(minute)) return null
        return { hour, minute }
    },

    formatTime(timePart) {
        if (!timePart) return ''
        const h = String(timePart.hour).padStart(2, '0')
        const m = String(timePart.minute).padStart(2, '0')
        return `${h}:${m}`
    },

    parseTimeRange(item, startHour, endHour) {
        const startPart = this.parseTimePart(item.start_time)
        const endPart = this.parseTimePart(item.end_time)
        const startMinutesRaw = startPart ? startPart.hour * 60 + startPart.minute : startHour * 60
        let endMinutesRaw = endPart ? endPart.hour * 60 + endPart.minute : startMinutesRaw + 60
        if (endMinutesRaw <= startMinutesRaw) endMinutesRaw = startMinutesRaw + 60

        const minRange = startHour * 60
        const maxRange = endHour * 60
        const startMinutes = Math.max(minRange, startMinutesRaw)
        const endMinutes = Math.min(maxRange, endMinutesRaw)

        return {
            startMinutes,
            endMinutes: Math.max(startMinutes + 30, endMinutes),
            startLabel: startPart ? this.formatTime(startPart) : '',
            endLabel: endPart ? this.formatTime(endPart) : ''
        }
    },

    formatTimeRange(startValue, endValue) {
        const startPart = this.parseTimePart(startValue)
        const endPart = this.parseTimePart(endValue)
        const startLabel = startPart ? this.formatTime(startPart) : this.extractTimeText(startValue)
        const endLabel = endPart ? this.formatTime(endPart) : this.extractTimeText(endValue)
        if (startLabel && endLabel) return `${startLabel}-${endLabel}`
        return startLabel || endLabel || '待定'
    },

    extractTimeText(value) {
        if (!value) return ''
        const str = String(value)
        if (str.includes(' ')) {
            return str.split(' ')[1] || str
        }
        return str
    },

    pickSubjectColor(name) {
        const subject = name || ''
        if (subject.includes('听力')) return { bg: '#e0f2fe', border: '#0284c7' }
        if (subject.includes('阅读')) return { bg: '#e0f2f1', border: '#0f766e' }
        if (subject.includes('口语')) return { bg: '#ede9fe', border: '#7c3aed' }
        if (subject.includes('写作')) return { bg: '#fff7ed', border: '#ea580c' }
        if (subject.includes('词汇')) return { bg: '#fce7f3', border: '#db2777' }
        return { bg: '#f1f5f9', border: '#64748b' }
    },

    switchView(e) {
        const mode = e.currentTarget.dataset.mode || 'list'
        this.setData({ viewMode: mode })
    },

    switchRange(e) {
        const days = Number(e.currentTarget.dataset.days) || 7
        this.setData({ viewDays: days }, () => this.fetchSchedules())
    },

    selectDay(e) {
        const date = e.currentTarget.dataset.date
        if (!date) return
        const day = this.data.monthDays.find(item => item.date === date)
            || this.data.weekDays.find(item => item.date === date)
        this.setData({
            selectedDate: date,
            selectedItems: day ? day.items : []
        })
    },

    changeMonth(offset) {
        const current = this.data.calendarMonth || this.formatMonth(new Date())
        const base = new Date(`${current}-01T00:00:00`)
        base.setMonth(base.getMonth() + offset)
        const calendarMonth = this.formatMonth(base)
        this.setData({
            calendarMonth,
            selectedDate: `${calendarMonth}-01`,
            selectedItems: []
        }, () => this.fetchSchedules())
    },

    prevMonth() {
        this.changeMonth(-1)
    },

    nextMonth() {
        this.changeMonth(1)
    },

    onCalendarTouchStart(e) {
        const touch = e.touches && e.touches[0]
        if (!touch) return
        this.setData({ touchStartX: touch.clientX })
    },

    onCalendarTouchEnd(e) {
        const touch = e.changedTouches && e.changedTouches[0]
        if (!touch) return
        const delta = touch.clientX - this.data.touchStartX
        if (Math.abs(delta) < 50) return
        if (delta < 0) this.nextMonth()
        else this.prevMonth()
    },

    goStats() {
        wx.redirectTo({ url: '/pages/teacher/stats/index' })
    },

    goCalendar() {
        this.setData({ scrollIntoView: '' }, () => {
            this.setData({ scrollIntoView: 'calendar-section' })
        })
    },

    showUnavailable(e) {
        const name = e.currentTarget.dataset.name || '该功能'
        wx.showToast({ title: `${name}暂未开放`, icon: 'none' })
    },

    openClassRecord() {
        const target = (this.data.selectedItems && this.data.selectedItems[0])
            || (this.data.todayItems && this.data.todayItems[0])
        if (!target) {
            wx.showToast({ title: '请先选择有课程的日期', icon: 'none' })
            return
        }
        this.navigateFeedbackWithSchedule(target)
    },

    openFirstHomework() {
        const target = (this.data.selectedItems && this.data.selectedItems[0])
            || (this.data.todayItems && this.data.todayItems[0])
        if (!target) {
            wx.showToast({ title: '请先选择有课程的日期', icon: 'none' })
            return
        }
        this.navigateHomeworkWithSchedule(target)
    },

    async bindSchedulerTeacher() {
        const rawId = (this.data.schedulerTeacherId || '').trim()
        const parsedId = Number(rawId)
        if (!rawId) {
            wx.showToast({ title: '请输入排课老师ID', icon: 'none' })
            return
        }
        if (!Number.isInteger(parsedId) || parsedId <= 0) {
            wx.showToast({ title: '排课老师ID需为正整数', icon: 'none' })
            return
        }

        this.setData({ bindLoading: true })
        try {
            const res = await request('/miniprogram/bind_scheduler_teacher', {
                method: 'POST',
                data: { scheduler_teacher_id: parsedId }
            })
            if (res && res.ok) {
                wx.showToast({ title: '绑定成功', icon: 'success' })
                this.setData({ bindRequired: false, schedulerTeacherId: '' })
                this.fetchSchedules()
            } else {
                let msg = (res && res.error) || '绑定失败'
                if (res && res.error === 'scheduler_id_taken') {
                    msg = '该排课老师ID已被绑定'
                }
                wx.showToast({ title: msg, icon: 'none' })
            }
        } catch (e) {
            console.warn('teacher home bindTeacherId failed', e)
            wx.showToast({ title: '网络错误', icon: 'none' })
        } finally {
            this.setData({ bindLoading: false })
        }
    },

    async refreshSubscribeStatus() {
        const summary = await getSubscribeSummary([COURSE_TEMPLATE_ID])
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
        if (state === 'reject') {
            return {
                hasSubscribed: false,
                subscribeState: state,
                subscribeButtonText: '去设置开启',
                subscribeTip: '你已关闭课程提醒，请在设置里重新开启'
            }
        }
        if (state === 'ban') {
            return {
                hasSubscribed: false,
                subscribeState: state,
                subscribeButtonText: '查看提醒状态',
                subscribeTip: '当前模板不可用，请联系管理员检查'
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
            subscribeButtonText: '开启提醒',
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
        if (['reject', 'off'].includes(this.data.subscribeState)) {
            wx.showModal({
                title: '开启提醒',
                content: '当前课程提醒已关闭，请在设置页重新开启。',
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
        const tmplIds = [COURSE_TEMPLATE_ID]
        requestTemplateSubscribe(tmplIds)
            .then((res) => {
                if (res[COURSE_TEMPLATE_ID] === 'accept') {
                    wx.showToast({ title: '提醒已记录', icon: 'success' })
                } else {
                    wx.showToast({ title: '本次未订阅，再次点击可重试', icon: 'none', duration: 3000 })
                }
                this.refreshSubscribeStatus()
            })
            .catch((err) => {
                console.warn('subscribe fail', err)
                wx.showToast({ title: '请点击按钮手动开启提醒', icon: 'none' })
            })
    },

    openFeedback(e) {
        const data = e.currentTarget.dataset || {}
        this.navigateFeedbackWithSchedule(data)
    },

    navigateFeedbackWithSchedule(data = {}) {
        const params = {
            schedule_uid: data.scheduleUid || data.schedule_uid,
            schedule_id: data.scheduleId || data.schedule_id,
            student_id: data.studentId || data.student_id,
            student_name: data.studentName || data.student_name,
            course_name: data.courseName || data.course_name,
            start_time: data.startTime || data.start_time,
            end_time: data.endTime || data.end_time,
            teacher_name: data.teacherName || data.teacher_name,
            schedule_date: data.scheduleDate || data.schedule_date,
            feedback_text: data.feedbackText || (data.feedback && data.feedback.text),
            feedback_image: data.feedbackImage || (data.feedback && data.feedback.image)
        }
        const query = Object.keys(params)
            .filter(key => params[key] !== undefined && params[key] !== null && params[key] !== '')
            .map(key => `${key}=${encodeURIComponent(params[key])}`)
            .join('&')
        wx.navigateTo({
            url: `/pages/teacher/feedback/index?${query}`
        })
    },

    openHomework(e) {
        const data = e.currentTarget.dataset || {}
        this.navigateHomeworkWithSchedule(data)
    },

    navigateHomeworkWithSchedule(data = {}) {
        const params = {
            schedule_uid: data.scheduleUid || data.schedule_uid,
            schedule_id: data.scheduleId || data.schedule_id,
            student_id: data.studentId || data.student_id,
            student_name: data.studentName || data.student_name,
            teacher_id: data.teacherId || data.teacher_id,
            teacher_name: data.teacherName || data.teacher_name,
            course_name: data.courseName || data.course_name,
            start_time: data.startTime || data.start_time,
            end_time: data.endTime || data.end_time,
            schedule_date: data.scheduleDate || data.schedule_date
        }
        const query = Object.keys(params)
            .filter(key => params[key] !== undefined && params[key] !== null && params[key] !== '')
            .map(key => `${key}=${encodeURIComponent(params[key])}`)
            .join('&')
        wx.navigateTo({
            url: `/pages/teacher/homework/index?${query}`
        })
    }
})
