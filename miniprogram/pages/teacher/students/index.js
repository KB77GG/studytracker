const app = getApp()
const { request } = require('../../../utils/request.js')

const currentMonth = () => {
    const now = new Date()
    return `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}`
}

const encodeQuery = (params) => Object.keys(params)
    .filter(key => params[key] !== undefined && params[key] !== null && params[key] !== '')
    .map(key => `${key}=${encodeURIComponent(params[key])}`)
    .join('&')

Page({
    data: {
        isGuest: false,
        loading: true,
        searchText: '',
        month: '',
        students: [],
        filteredStudents: [],
        errorText: ''
    },

    onLoad(options) {
        this.setData({ month: options.month || currentMonth() })
    },

    onShow() {
        this.setData({ isGuest: !!app.globalData.guestMode })
        this.fetchStudents()
    },

    async fetchStudents() {
        if (this.data.isGuest || app.globalData.guestMode) {
            this.setData({ loading: false, students: [], filteredStudents: [], errorText: '' })
            return
        }
        this.setData({ loading: true, errorText: '' })
        try {
            const res = await request('/miniprogram/teacher/practice-students', {
                method: 'GET',
                data: { month: this.data.month || currentMonth() }
            })
            if (res && res.ok) {
                this.setData({ students: res.students || [] }, () => this.applyFilter())
            } else {
                const errorText = res && res.error === 'missing_scheduler_teacher_id'
                    ? '请先在教师首页绑定排课老师 ID'
                    : '学生列表加载失败，请稍后重试'
                this.setData({ students: [], filteredStudents: [], errorText })
            }
        } catch (error) {
            console.warn('teacher practice students load failed', error)
            this.setData({ students: [], filteredStudents: [], errorText: '网络错误，请稍后重试' })
        } finally {
            this.setData({ loading: false })
        }
    },

    handleSearch(e) {
        this.setData({ searchText: e.detail.value || '' }, () => this.applyFilter())
    },

    applyFilter() {
        const query = (this.data.searchText || '').trim().toLowerCase()
        const filteredStudents = (this.data.students || []).filter(student => {
            if (!query) return true
            const studentText = `${student.student_name || ''} ${student.student_id || ''}`.toLowerCase()
            const subjectText = (student.subjects || [])
                .map(subject => `${subject.subject_label || ''} ${subject.subject_key || ''}`)
                .join(' ')
                .toLowerCase()
            return `${studentText} ${subjectText}`.includes(query)
        })
        this.setData({ filteredStudents })
    },

    authorizeCompatibleInput(e) {
        const profileId = e.currentTarget.dataset.profileId
        if (!profileId) {
            wx.showToast({ title: '该学生尚未绑定账号', icon: 'none' })
            return
        }
        wx.showActionSheet({
            itemList: ['单词任务原生输入 7 天', '单词任务原生输入 30 天'],
            success: (choice) => {
                const durationDays = choice.tapIndex === 1 ? 30 : 7
                wx.showLoading({ title: '授权中...' })
                request('/dictation/input-grants', {
                    method: 'POST',
                    data: {
                        student_profile_id: Number(profileId),
                        duration_days: durationDays,
                        reason: '教师授权单词任务实体键盘兼容模式'
                    }
                }).then((res) => {
                    if (res && res.ok) {
                        wx.showToast({ title: `已授权 ${durationDays} 天`, icon: 'success' })
                    } else {
                        wx.showToast({
                            title: res && res.error === 'student_has_no_login'
                                ? '学生尚未绑定登录账号'
                                : '授权失败',
                            icon: 'none'
                        })
                    }
                }).catch(() => {
                    wx.showToast({ title: '网络错误，请重试', icon: 'none' })
                }).finally(() => wx.hideLoading())
            }
        })
    },

    openSubject(e) {
        const data = e.currentTarget.dataset || {}
        if (!data.contextToken || !data.subjectKey || !data.allowedSource) {
            wx.showToast({ title: '快捷入口已失效，请刷新重试', icon: 'none' })
            return
        }
        const params = {
            quick_practice: '1',
            subject_key: data.subjectKey,
            allowed_source: data.allowedSource,
            practice_context_token: data.contextToken,
            schedule_uid: data.scheduleUid,
            schedule_id: data.scheduleId,
            student_id: data.studentId,
            student_name: data.studentName,
            teacher_id: data.teacherId,
            teacher_name: data.teacherName,
            course_name: data.courseName,
            start_time: data.startTime,
            end_time: data.endTime,
            schedule_date: data.scheduleDate
        }
        wx.navigateTo({
            url: `/pages/teacher/homework/index?${encodeQuery(params)}`
        })
    }
})
