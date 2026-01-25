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
                    timeSlots: weekData.timeSlots,
                    gridHeight: weekData.gridHeight,
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
            map[date].push(item)
        })
        return Object.keys(map).sort().map(date => ({
            date,
            items: map[date]
        }))
    },

    buildWeekView(list) {
        const startHour = this.data.gridStartHour || DEFAULT_START_HOUR
        const endHour = this.data.gridEndHour || DEFAULT_END_HOUR
        const hourHeight = this.data.hourHeight || HOUR_HEIGHT
        const minuteHeight = hourHeight / 60
        const daysCount = this.data.viewDays || 7

        const days = []
        const dayMap = {}
        for (let i = 0; i < daysCount; i += 1) {
            const d = new Date()
            d.setDate(d.getDate() + i)
            const date = this.formatDate(d)
            const label = this.formatDayLabel(d)
            const day = { date, label, items: [] }
            dayMap[date] = day
            days.push(day)
        }

        const extraDays = {}
        list.forEach(item => {
            const date = item.schedule_date || (item.start_time || '').split(' ')[0] || '待定'
            let target = dayMap[date]
            if (!target) {
                if (!extraDays[date]) {
                    extraDays[date] = {
                        date,
                        label: date === '待定' ? '待定' : date.slice(5),
                        items: []
                    }
                }
                target = extraDays[date]
            }
            const timeInfo = this.parseTimeRange(item, startHour, endHour)
            const top = Math.max(0, timeInfo.startMinutes - startHour * 60) * minuteHeight
            const height = Math.max(48, (timeInfo.endMinutes - timeInfo.startMinutes) * minuteHeight)
            const color = this.pickSubjectColor(item.course_name || '')
            const timeLabel = timeInfo.startLabel && timeInfo.endLabel
                ? `${timeInfo.startLabel}-${timeInfo.endLabel}`
                : '待定'
            target.items.push({
                ...item,
                _startMinutes: timeInfo.startMinutes,
                timeLabel,
                style: `top:${top}rpx;height:${height}rpx;background:${color.bg};border-left:6rpx solid ${color.border};`
            })
        })

        Object.keys(extraDays).sort().forEach(key => days.push(extraDays[key]))

        days.forEach(day => {
            day.items.sort((a, b) => (a._startMinutes || 0) - (b._startMinutes || 0))
        })

        const timeSlots = []
        for (let h = startHour; h < endHour; h += 1) {
            timeSlots.push(`${String(h).padStart(2, '0')}:00`)
        }

        return {
            days,
            timeSlots,
            gridHeight: (endHour - startHour) * hourHeight
        }
    },

    formatDate(dateObj) {
        const y = dateObj.getFullYear()
        const m = String(dateObj.getMonth() + 1).padStart(2, '0')
        const d = String(dateObj.getDate()).padStart(2, '0')
        return `${y}-${m}-${d}`
    },

    formatDayLabel(dateObj) {
        const days = ['日', '一', '二', '三', '四', '五', '六']
        const dateStr = this.formatDate(dateObj)
        return `${dateStr.slice(5)} 周${days[dateObj.getDay()]}`
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
        this.setData({ viewMode: mode })
    },

    switchRange(e) {
        const days = Number(e.currentTarget.dataset.days) || 7
        this.setData({ viewDays: days }, () => this.fetchSchedules())
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
