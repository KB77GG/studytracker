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
        // 这里简化处理，实际应该调用后端API获取单个任务详情
        // 暂时从首页传递过来的数据中模拟
        // TODO: 实现 GET /miniprogram/student/tasks/:id
        this.setData({
            task: {
                task_name: '口语练习 - TPO 1',
                module: 'Speaking',
                planned_minutes: 30,
                instructions: '请朗读 TPO 1 Passage 1，录音上传。要求发音清晰，流利度良好。',
                student_status: 'pending'
            },
            statusText: '待完成'
        })
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
