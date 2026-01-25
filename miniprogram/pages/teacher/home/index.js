const app = getApp()
const { request } = require('../../../utils/request.js')
const COURSE_TEMPLATE_ID = 'AehPa5pMUTnQqXgq-q-wxTAMZyVU-qdkxaO9rbpo-QI'

Page({
    data: {
        loading: true,
        viewDays: 7,
        schedules: [],
        hasSubscribed: false,
        bindRequired: false,
        schedulerTeacherId: '',
        bindLoading: false
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
                const grouped = this.groupByDate(res.schedules || [])
                this.setData({ schedules: grouped, bindRequired: false })
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
    }
})
