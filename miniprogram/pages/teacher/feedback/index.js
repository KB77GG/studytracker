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
        baseUrl: ''
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
