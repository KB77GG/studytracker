const { request } = require('../../../utils/request.js')

const decodeParam = (value) => {
    if (value === undefined || value === null) return ''
    return decodeURIComponent(value)
}

const pushErrorMessage = (code) => {
    const mapping = {
        missing_template_id: '作业已保存，但服务端没有配置任务提醒模板。',
        no_student_openid: '作业已保存，但学生还没有完成微信绑定。',
        user_refused: '作业已保存，但学生当前没有可用的任务提醒订阅，请让学生在小程序里重新开启提醒。',
        invalid_template_id: '作业已保存，但任务提醒模板 ID 配置错误。',
        invalid_page: '作业已保存，但提醒跳转页面配置错误。',
        template_param_error: '作业已保存，但提醒模板字段与后端参数不匹配。',
        missing_access_token: '作业已保存，但微信服务认证失败，请稍后再试。',
        send_failed: '作业已保存，但提醒发送失败，请稍后重试。'
    }
    return mapping[code] || '作业已保存，但提醒发送失败。'
}

Page({
    data: {
        schedule: {
            schedule_uid: '',
            schedule_id: '',
            student_id: '',
            student_name: '',
            teacher_id: '',
            teacher_name: '',
            course_name: '',
            start_time: '',
            end_time: '',
            schedule_date: ''
        },
        form: {
            date: '',
            category: '',
            detail: '',
            plannedMinutes: 30,
            note: ''
        },
        saving: false
    },

    onLoad(options) {
        const schedule = {
            schedule_uid: decodeParam(options.schedule_uid),
            schedule_id: decodeParam(options.schedule_id),
            student_id: decodeParam(options.student_id),
            student_name: decodeParam(options.student_name),
            teacher_id: decodeParam(options.teacher_id),
            teacher_name: decodeParam(options.teacher_name),
            course_name: decodeParam(options.course_name),
            start_time: decodeParam(options.start_time),
            end_time: decodeParam(options.end_time),
            schedule_date: decodeParam(options.schedule_date)
        }
        const courseName = schedule.course_name || '课后作业'
        this.setData({
            schedule,
            form: {
                date: this.getTodayString(),
                category: courseName.slice(0, 32),
                detail: `${courseName}课后练习`,
                plannedMinutes: 30,
                note: ''
            }
        })
    },

    getTodayString() {
        const now = new Date()
        const year = now.getFullYear()
        const month = String(now.getMonth() + 1).padStart(2, '0')
        const day = String(now.getDate()).padStart(2, '0')
        return `${year}-${month}-${day}`
    },

    handleDateChange(e) {
        this.setData({ 'form.date': e.detail.value })
    },

    handleInput(e) {
        const field = e.currentTarget.dataset.field
        if (!field) return
        this.setData({ [`form.${field}`]: e.detail.value })
    },

    async submitHomework() {
        const { form, schedule } = this.data
        const detail = (form.detail || '').trim()
        if (!detail) {
            wx.showToast({ title: '请填写作业内容', icon: 'none' })
            return
        }

        this.setData({ saving: true })
        wx.showLoading({ title: '保存中...' })
        try {
            const payload = {
                ...schedule,
                date: form.date,
                category: (form.category || '').trim(),
                detail,
                planned_minutes: Number(form.plannedMinutes) || 0,
                note: (form.note || '').trim()
            }
            const res = await request('/miniprogram/teacher/homework', {
                method: 'POST',
                data: payload
            })
            if (!res || !res.ok) {
                let msg = (res && res.error) || '保存失败'
                if (msg === 'student_not_found') msg = '未找到学生档案'
                if (msg === 'forbidden_schedule') msg = '当前课表不属于你'
                if (msg === 'invalid_date') msg = '日期格式不正确'
                wx.showToast({ title: msg, icon: 'none' })
                return
            }

            if (res.push_sent > 0) {
                wx.showToast({ title: '作业已布置并提醒学生', icon: 'success' })
                setTimeout(() => {
                    wx.navigateBack()
                }, 500)
                return
            }

            wx.showModal({
                title: '作业已保存',
                content: pushErrorMessage(res.push_error),
                showCancel: false,
                success: () => {
                    wx.navigateBack()
                }
            })
        } catch (err) {
            console.error(err)
            wx.showToast({ title: '网络错误', icon: 'none' })
        } finally {
            wx.hideLoading()
            this.setData({ saving: false })
        }
    }
})
