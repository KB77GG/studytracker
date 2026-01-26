const app = getApp()
const { request } = require('../../../utils/request.js')
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
        bindRequired: false,
        schedulerTeacherId: '',
        bindLoading: false,
        viewMode: 'week',
        weekDays: [],
        selectedDate: '',
        selectedItems: [],
        timeSlots: [],
        gridStartHour: DEFAULT_START_HOUR,
        gridEndHour: DEFAULT_END_HOUR,
        hourHeight: HOUR_HEIGHT,
        gridHeight: (DEFAULT_END_HOUR - DEFAULT_START_HOUR) * HOUR_HEIGHT
    },

    onShow() {
        this.fetchSchedules()
        const subFlag = wx.getStorageSync('task_subscribed') || false
        this.setData({ hasSubscribed: subFlag })
        if (typeof this.getTabBar === 'function' && this.getTabBar()) {
            this.getTabBar().setData({ selected: 0 })
        }
    },

    async fetchSchedules() {
        this.setData({ loading: true })
        try {
            const res = await request('/miniprogram/teacher/schedules', {
                method: 'GET',
                data: { days: this.data.viewDays }
            })
            if (res && res.ok !== false) {
                const list = res.schedules || []
                const grouped = this.groupByDate(list)
                const weekData = this.buildWeekView(list)
                this.setData({
                    schedules: grouped,
                    weekDays: weekData.days,
                    selectedDate: weekData.selectedDate,
                    selectedItems: weekData.selectedItems,
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

    formatDate(dateObj) {
        const y = dateObj.getFullYear()
        const m = String(dateObj.getMonth() + 1).padStart(2, '0')
        const d = String(dateObj.getDate()).padStart(2, '0')
        return `${y}-${m}-${d}`
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
        const mode = e.currentTarget.dataset.mode || 'week'
        if (mode === 'week' && this.data.viewDays !== 7) {
            this.setData({ viewMode: mode, viewDays: 7 }, () => this.fetchSchedules())
            return
        }
        this.setData({ viewMode: mode })
    },

    switchRange(e) {
        const days = Number(e.currentTarget.dataset.days) || 7
        const next = { viewDays: days }
        if (days === 30 && this.data.viewMode === 'week') {
            next.viewMode = 'list'
        }
        this.setData(next, () => this.fetchSchedules())
    },

    selectDay(e) {
        const date = e.currentTarget.dataset.date
        const day = this.data.weekDays.find(item => item.date === date)
        this.setData({
            selectedDate: date,
            selectedItems: day ? day.items : []
        })
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
            wx.showToast({ title: '网络错误', icon: 'none' })
        } finally {
            this.setData({ bindLoading: false })
        }
    },

    requestSubscribe() {
        if (this.data.hasSubscribed) {
            wx.showToast({ title: '已开启提醒', icon: 'none' })
            return
        }
        const tmplIds = [COURSE_TEMPLATE_ID]
        wx.requestSubscribeMessage({
            tmplIds,
            success: (res) => {
                const accepted = tmplIds.some(id => res[id] === 'accept')
                if (accepted) {
                    wx.setStorageSync('task_subscribed', true)
                    this.setData({ hasSubscribed: true })
                    wx.showToast({ title: '提醒已开启', icon: 'success' })
                } else {
                    wx.showToast({ title: '已拒绝或未选择', icon: 'none' })
                }
            },
            fail: (err) => {
                console.warn('subscribe fail', err)
                wx.showToast({ title: '订阅失败', icon: 'none' })
            }
        })
    },

    handleFeedback(e) {
        wx.showToast({ title: '功能筹备中', icon: 'none' })
    }
})
