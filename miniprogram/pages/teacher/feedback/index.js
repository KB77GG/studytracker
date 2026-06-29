const app = getApp()
const { request } = require('../../../utils/request.js')

const decodeParam = (value) => {
    if (value === undefined || value === null) return ''
    return decodeURIComponent(value)
}

const SECTION_FIELDS = [
    { key: 'homeworkStatus', label: '作业完成情况' },
    { key: 'classPerformance', label: '课堂表现及问题' },
    { key: 'suggestionHomework', label: '建议及作业' }
]

const escapeRegExp = (value) => value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')

const extractSection = (content, label, nextLabels) => {
    if (!content) return ''
    const escapedLabel = escapeRegExp(label)
    const escapedNext = nextLabels.map(escapeRegExp).join('|')
    const pattern = escapedNext
        ? `${escapedLabel}[：:][ \\t]*([\\s\\S]*?)(?=\\n\\s*(?:${escapedNext})[：:]|$)`
        : `${escapedLabel}[：:][ \\t]*([\\s\\S]*)$`
    const match = content.match(new RegExp(pattern))
    return match && match[1] ? match[1].trim() : ''
}

const parseFeedbackSections = (text) => {
    const normalized = (text || '').replace(/\r\n/g, '\n').trim()
    if (!normalized) {
        return {
            homeworkStatus: '',
            classPerformance: '',
            suggestionHomework: ''
        }
    }

    const hasStructuredTitle = SECTION_FIELDS.some((item) => (
        normalized.includes(`${item.label}：`) || normalized.includes(`${item.label}:`)
    ))
    if (!hasStructuredTitle) {
        return {
            homeworkStatus: '',
            classPerformance: normalized,
            suggestionHomework: ''
        }
    }

    return {
        homeworkStatus: extractSection(normalized, SECTION_FIELDS[0].label, [SECTION_FIELDS[1].label, SECTION_FIELDS[2].label]),
        classPerformance: extractSection(normalized, SECTION_FIELDS[1].label, [SECTION_FIELDS[2].label]),
        suggestionHomework: extractSection(normalized, SECTION_FIELDS[2].label, [])
    }
}

const buildFeedbackText = (feedbackForm) => SECTION_FIELDS
    .map((item) => `${item.label}：${(feedbackForm[item.key] || '').trim()}`)
    .join('\n\n')

Page({
    data: {
        schedule: {
            schedule_uid: '',
            schedule_id: '',
            student_id: '',
            student_name: '',
            course_name: '',
            start_time: '',
            end_time: '',
            teacher_name: '',
            schedule_date: ''
        },
        feedbackForm: {
            homeworkStatus: '',
            classPerformance: '',
            suggestionHomework: ''
        },
        feedbackImage: '',
        imagePreviewUrl: '',
        saving: false,
        uploadingImage: false,
        baseUrl: '',
        // 学生概况
        studentProfiles: [],
        hasStudentInfo: false,
        editingIndex: -1,
        profileForm: {
            grade_level: '',
            profile_summary: '',
            learning_goals: '',
            class_notes: ''
        },
        savingProfile: false
    },

    onLoad(options) {
        const schedule = {
            schedule_uid: decodeParam(options.schedule_uid),
            schedule_id: decodeParam(options.schedule_id),
            student_id: decodeParam(options.student_id),
            student_name: decodeParam(options.student_name),
            course_name: decodeParam(options.course_name),
            start_time: decodeParam(options.start_time),
            end_time: decodeParam(options.end_time),
            teacher_name: decodeParam(options.teacher_name),
            schedule_date: decodeParam(options.schedule_date)
        }
        if (!schedule.schedule_date && schedule.start_time && schedule.start_time.includes(' ')) {
            schedule.schedule_date = schedule.start_time.split(' ')[0]
        }
        const feedbackText = decodeParam(options.feedback_text)
        const feedbackForm = parseFeedbackSections(feedbackText)
        const feedbackImage = decodeParam(options.feedback_image)
        const baseUrl = app.globalData.baseUrl || ''
        const imagePreviewUrl = this.buildImageUrl(feedbackImage, baseUrl)
        this.setData({ schedule, feedbackForm, feedbackImage, imagePreviewUrl, baseUrl })
        this.loadStudentProfiles(schedule)
    },

    loadStudentProfiles(schedule) {
        const source = (app.globalData && app.globalData.feedbackProfileSource) || null
        if (app.globalData) {
            app.globalData.feedbackProfileSource = null
        }
        const entries = this.buildProfileEntries(source, schedule)
        this.setData({
            studentProfiles: entries,
            hasStudentInfo: entries.length > 0
        })
    },

    buildProfileEntries(source, schedule) {
        const entries = []
        const profilesArr = source && source.student_profiles
        if (Array.isArray(profilesArr) && profilesArr.length) {
            profilesArr.forEach((entry) => {
                const profile = entry.profile || entry
                entries.push(this.decorateProfileEntry({
                    scheduler_student_id: entry.scheduler_student_id,
                    name: entry.name || entry.student_name || '',
                    grade_level: profile.grade_level,
                    profile_summary: profile.profile_summary,
                    learning_goals: profile.learning_goals,
                    class_notes: profile.class_notes,
                    profile_updated_at: profile.profile_updated_at
                }))
            })
            return entries
        }

        const single = source && source.student_profile
        const schedulerStudentId = (source && source.scheduler_student_id) || ''
        const name = (source && source.student_name) || (schedule && schedule.student_name) || ''
        if (single) {
            entries.push(this.decorateProfileEntry({
                scheduler_student_id: schedulerStudentId,
                name,
                grade_level: single.grade_level,
                profile_summary: single.profile_summary,
                learning_goals: single.learning_goals,
                class_notes: single.class_notes,
                profile_updated_at: single.profile_updated_at
            }))
            return entries
        }

        // 没有概况对象，但已知排课学生ID时，仍给出一条空记录供老师补填
        if (schedulerStudentId) {
            entries.push(this.decorateProfileEntry({
                scheduler_student_id: schedulerStudentId,
                name,
                grade_level: '',
                profile_summary: '',
                learning_goals: '',
                class_notes: '',
                profile_updated_at: ''
            }))
        }
        return entries
    },

    decorateProfileEntry(raw) {
        const placeholder = '未填写'
        return {
            scheduler_student_id: raw.scheduler_student_id || '',
            name: raw.name || '该学生',
            grade_level: raw.grade_level || '',
            profile_summary: raw.profile_summary || '',
            learning_goals: raw.learning_goals || '',
            class_notes: raw.class_notes || '',
            profile_updated_at: raw.profile_updated_at || '',
            gradeLevelText: raw.grade_level || placeholder,
            summaryText: raw.profile_summary || placeholder,
            goalsText: raw.learning_goals || placeholder,
            notesText: raw.class_notes || placeholder,
            updatedText: this.formatProfileTime(raw.profile_updated_at)
        }
    },

    formatProfileTime(value) {
        if (!value) return ''
        const str = String(value).replace('T', ' ')
        // 2026-06-29 10:00:00 -> 2026-06-29 10:00
        const match = str.match(/^(\d{4}-\d{2}-\d{2})[ ](\d{2}:\d{2})/)
        if (match) return `${match[1]} ${match[2]}`
        return str.split('.')[0]
    },

    startEditProfile(e) {
        const index = Number(e.currentTarget.dataset.index)
        const entry = this.data.studentProfiles[index]
        if (!entry) return
        if (!entry.scheduler_student_id) {
            wx.showToast({ title: '缺少学生ID，无法编辑', icon: 'none' })
            return
        }
        this.setData({
            editingIndex: index,
            profileForm: {
                grade_level: entry.grade_level,
                profile_summary: entry.profile_summary,
                learning_goals: entry.learning_goals,
                class_notes: entry.class_notes
            }
        })
    },

    cancelEditProfile() {
        this.setData({ editingIndex: -1 })
    },

    handleProfileInput(e) {
        const field = e.currentTarget.dataset.field
        if (!field) return
        this.setData({ [`profileForm.${field}`]: e.detail.value })
    },

    async saveProfile() {
        const index = this.data.editingIndex
        const entry = this.data.studentProfiles[index]
        if (!entry) return
        const schedulerStudentId = entry.scheduler_student_id
        if (!schedulerStudentId) {
            wx.showToast({ title: '缺少学生ID，无法保存', icon: 'none' })
            return
        }
        const form = this.data.profileForm
        const payload = {
            grade_level: (form.grade_level || '').trim(),
            profile_summary: (form.profile_summary || '').trim(),
            learning_goals: (form.learning_goals || '').trim(),
            class_notes: (form.class_notes || '').trim()
        }

        this.setData({ savingProfile: true })
        wx.showLoading({ title: '保存中...' })
        try {
            const res = await request(`/miniprogram/students/${schedulerStudentId}/profile`, {
                method: 'PATCH',
                data: payload
            })
            if (res && res.ok) {
                const profile = (res.student && res.student.profile) || payload
                const updated = this.decorateProfileEntry({
                    scheduler_student_id: schedulerStudentId,
                    name: (res.student && res.student.name) || entry.name,
                    grade_level: profile.grade_level,
                    profile_summary: profile.profile_summary,
                    learning_goals: profile.learning_goals,
                    class_notes: profile.class_notes,
                    profile_updated_at: profile.profile_updated_at
                })
                this.setData({
                    [`studentProfiles[${index}]`]: updated,
                    hasStudentInfo: true,
                    editingIndex: -1
                })
                wx.showToast({ title: '已保存', icon: 'success' })
            } else {
                const msg = (res && (res.message || res.error)) || '保存失败'
                wx.showToast({ title: msg, icon: 'none' })
            }
        } catch (err) {
            console.error(err)
            wx.showToast({ title: '网络错误', icon: 'none' })
        } finally {
            wx.hideLoading()
            this.setData({ savingProfile: false })
        }
    },

    handleSectionInput(e) {
        const field = e.currentTarget.dataset.field
        if (!field) return
        this.setData({ [`feedbackForm.${field}`]: e.detail.value })
    },

    buildImageUrl(path, baseUrl) {
        if (!path) return ''
        if (path.startsWith('http://') || path.startsWith('https://')) return path
        return `${baseUrl || ''}${path}`
    },

    chooseImage() {
        if (this.data.uploadingImage) return
        wx.chooseImage({
            count: 1,
            sizeType: ['compressed'],
            sourceType: ['album', 'camera'],
            success: (res) => {
                const tempPath = res.tempFilePaths && res.tempFilePaths[0]
                if (tempPath) {
                    this.uploadImage(tempPath)
                }
            }
        })
    },

    uploadImage(filePath) {
        if (!filePath) return
        const token = app.globalData.token
        const baseUrl = this.data.baseUrl || app.globalData.baseUrl
        if (!baseUrl) {
            wx.showToast({ title: '缺少服务地址', icon: 'none' })
            return
        }
        this.setData({ uploadingImage: true })
        wx.showLoading({ title: '上传中...' })
        wx.uploadFile({
            url: `${baseUrl}/miniprogram/upload`,
            filePath,
            name: 'file',
            header: token ? { Authorization: `Bearer ${token}` } : {},
            success: (res) => {
                let data = null
                try {
                    data = JSON.parse(res.data)
                } catch (err) {
                    data = null
                }
                if (res.statusCode >= 200 && res.statusCode < 300 && data && data.ok) {
                    const imageUrl = data.url
                    this.setData({
                        feedbackImage: imageUrl,
                        imagePreviewUrl: this.buildImageUrl(imageUrl, baseUrl)
                    })
                } else {
                    wx.showToast({ title: '上传失败', icon: 'none' })
                }
            },
            fail: () => {
                wx.showToast({ title: '上传失败', icon: 'none' })
            },
            complete: () => {
                wx.hideLoading()
                this.setData({ uploadingImage: false })
            }
        })
    },

    previewImage() {
        if (!this.data.imagePreviewUrl) return
        wx.previewImage({
            urls: [this.data.imagePreviewUrl]
        })
    },

    removeImage() {
        this.setData({ feedbackImage: '', imagePreviewUrl: '' })
    },

    async submitFeedback() {
        const feedbackForm = this.data.feedbackForm || {}
        const feedbackText = buildFeedbackText(feedbackForm)

        this.setData({ saving: true })
        wx.showLoading({ title: '提交中...' })
        try {
            const payload = {
                ...this.data.schedule,
                feedback_text: feedbackText,
                feedback_image: this.data.feedbackImage
            }
            const res = await request('/miniprogram/teacher/feedback', {
                method: 'POST',
                data: payload
            })
            if (res && res.ok) {
                wx.showToast({ title: '反馈已提交', icon: 'success' })
                setTimeout(() => {
                    wx.navigateBack()
                }, 500)
            } else {
                let msg = (res && res.error) || '提交失败'
                if (res && res.error === 'feedback_table_missing') {
                    msg = '请先升级数据库'
                }
                wx.showToast({ title: msg, icon: 'none' })
            }
        } catch (err) {
            console.error(err)
            wx.showToast({ title: '网络错误', icon: 'none' })
        } finally {
            wx.hideLoading()
            this.setData({ saving: false })
        }
    }
})
