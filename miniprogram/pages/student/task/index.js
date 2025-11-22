const app = getApp()
const { request } = require('../../../utils/request.js')

const recorderManager = wx.getRecorderManager()
const innerAudioContext = wx.createInnerAudioContext()

Page({
    data: {
        taskId: null,
        task: {},
        statusText: '',
        recording: false,
        recordDuration: 0,
        audioFiles: [],
        images: [],
        note: '',
        submitting: false
    },

    onLoad(options) {
        this.setData({ taskId: options.id })
        this.fetchTaskDetail()
        this.setupRecorder()
    },

    setupRecorder() {
        recorderManager.onStop((res) => {
            const { tempFilePath, duration } = res
            this.setData({
                audioFiles: [...this.data.audioFiles, tempFilePath],
                recordDuration: Math.floor(duration / 1000)
            })
        })
    },

    async fetchTaskDetail() {
        wx.showLoading({ title: '加载中...' })
        try {
            const res = await request(`/miniprogram/student/tasks/${this.data.taskId}`)
            if (res.ok && res.task) {
                const isSpeaking = res.task.module && (res.task.module.includes('口语') || res.task.module.includes('Speaking'))

                // 处理图片URL
                const baseUrl = getApp().globalData.baseUrl
                const images = (res.task.evidence_photos || []).map(url => {
                    if (url.startsWith('http')) return url
                    return `${baseUrl}${url}`
                })

                this.setData({
                    task: res.task,
                    statusText: this.getStatusText(res.task.status),
                    showAudio: isSpeaking,
                    images: images,
                    note: res.task.student_note || ''
                })
            } else {
                wx.showToast({ title: '获取任务详情失败', icon: 'none' })
            }
        } catch (err) {
            console.error(err)
            wx.showToast({ title: '加载失败', icon: 'none' })
        } finally {
            wx.hideLoading()
        }
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
        return map[status] || '未知'
    },

    startRecord() {
        this.setData({ recording: true, recordDuration: 0 })
        recorderManager.start({
            duration: 600000, // 最长10分钟
            format: 'mp3'
        })
    },

    stopRecord() {
        this.setData({ recording: false })
        recorderManager.stop()
    },

    playAudio(e) {
        const url = e.currentTarget.dataset.url
        innerAudioContext.src = url
        innerAudioContext.play()
    },

    deleteAudio(e) {
        const index = e.currentTarget.dataset.index
        const audioFiles = this.data.audioFiles.filter((_, i) => i !== index)
        this.setData({ audioFiles })
    },

    chooseImage() {
        wx.chooseImage({
            count: 9 - this.data.images.length,
            sizeType: ['compressed'],
            sourceType: ['album', 'camera'],
            success: (res) => {
                this.setData({
                    images: [...this.data.images, ...res.tempFilePaths]
                })
            }
        })
    },

    previewImage(e) {
        const url = e.currentTarget.dataset.url
        wx.previewImage({
            current: url,
            urls: this.data.images
        })
    },

    deleteImage(e) {
        const index = e.currentTarget.dataset.index
        const images = this.data.images.filter((_, i) => i !== index)
        this.setData({ images })
    },

    async submitTask() {
        if (this.data.audioFiles.length === 0 && this.data.images.length === 0) {
            wx.showToast({ title: '请上传录音或照片', icon: 'none' })
            return
        }

        this.setData({ submitting: true })
        wx.showLoading({ title: '提交中...' })

        try {
            // 1. 上传音频文件
            const audioUrls = []
            for (const file of this.data.audioFiles) {
                const url = await this.uploadFile(file)
                audioUrls.push(url)
            }

            // 2. 上传图片
            const imageUrls = []
            for (const img of this.data.images) {
                const url = await this.uploadFile(img)
                imageUrls.push(url)
            }

            // 3. 提交任务
            const res = await request(`/miniprogram/student/tasks/${this.data.taskId}/submit`, {
                method: 'POST',
                data: {
                    note: this.data.note,
                    evidence_files: [...audioUrls, ...imageUrls]
                }
            })

            if (res.ok) {
                wx.showToast({ title: '提交成功！', icon: 'success' })
                setTimeout(() => {
                    wx.navigateBack()
                }, 1500)
            } else {
                wx.showToast({ title: res.error || '提交失败', icon: 'none' })
            }
        } catch (err) {
            console.error(err)
            wx.showToast({ title: '提交失败，请重试', icon: 'none' })
        } finally {
            wx.hideLoading()
            this.setData({ submitting: false })
        }
    },

    uploadFile(filePath) {
        return new Promise((resolve, reject) => {
            wx.uploadFile({
                url: `${getApp().globalData.baseUrl}/miniprogram/upload`,
                filePath: filePath,
                name: 'file',
                header: {
                    'Authorization': `Bearer ${getApp().globalData.token}`
                },
                success: (res) => {
                    const data = JSON.parse(res.data)
                    if (data.ok) {
                        resolve(data.url)
                    } else {
                        reject(data.error)
                    }
                },
                fail: reject
            })
        })
    }
})
