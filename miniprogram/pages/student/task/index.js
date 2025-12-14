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
        submitting: false,
        showAudio: false,
        playingFeedback: false,
        baseUrl: 'https://studytracker.xin',
        // TTS相关
        ttsProvider: 'iflytek',  // 使用科大讯飞（单词点读）
        vocabularyWords: [],
        sentenceWords: [],
        paragraphText: '',
        ttsContext: null,
        currentPlayingText: null,
        isPlaying: false,
        // Timer related
        timerRunning: false,
        timerPaused: false,
        displayTime: '00:00',
        plannedTime: '00:00',
        timerInterval: null,
        elapsedSeconds: 0
    },

    onLoad(options) {
        this.setData({ taskId: parseInt(options.id) })
        this.fetchTaskDetail()
        this.setupRecorder()
        this.initTTS()
        this.checkTimer()
    },

    checkTimer() {
        // Check if there's a running timer for this task
        const activeTimer = app.globalData.activeTimer
        if (activeTimer && activeTimer.taskId === this.data.taskId) {
            // Restore timer state
            const elapsed = Math.floor((Date.now() - activeTimer.startTime) / 1000)
            this.setData({
                timerRunning: true,
                elapsedSeconds: elapsed,
                displayTime: this.formatTime(elapsed),
                plannedTime: this.formatTime((this.data.task.planned_minutes || 20) * 60)
            })

            // Start interval
            const interval = setInterval(() => {
                this.updateTimer()
            }, 1000)
            this.setData({ timerInterval: interval })
        }
    },

    updateTimer() {
        if (!this.data.timerRunning) return

        const activeTimer = app.globalData.activeTimer
        if (!activeTimer) {
            this.stopTimerDisplay()
            return
        }

        const elapsed = Math.floor((Date.now() - activeTimer.startTime) / 1000)
        this.setData({
            elapsedSeconds: elapsed,
            displayTime: this.formatTime(elapsed)
        })
    },

    formatTime(seconds) {
        const mins = Math.floor(seconds / 60)
        const secs = seconds % 60
        return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`
    },

    onUnload() {
        if (this.data.ttsContext) {
            this.data.ttsContext.destroy()
        }
        // Clear timer interval but keep timer running in background
        if (this.data.timerInterval) {
            clearInterval(this.data.timerInterval)
        }
    },

    initTTS() {
        const ctx = wx.createInnerAudioContext()
        ctx.onPlay(() => this.setData({ isPlaying: true }))
        ctx.onPause(() => this.setData({ isPlaying: false }))
        ctx.onStop(() => this.setData({ isPlaying: false, currentPlayingText: null }))
        ctx.onEnded(() => this.setData({ isPlaying: false, currentPlayingText: null }))
        ctx.onError((res) => {
            console.error('TTS Error:', res)
            this.setData({ isPlaying: false, currentPlayingText: null })
            wx.showToast({ title: '播放出错', icon: 'none' })
        })
        this.setData({ ttsContext: ctx })
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
                // 检查是否是口语任务（通过 module 或 material.type）
                const isSpeaking =
                    (res.task.module && (res.task.module.includes('口语') || res.task.module.includes('Speaking'))) ||
                    (res.task.material && res.task.material.type && res.task.material.type.startsWith('speaking'))

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

                // 如果是口语朗读材料，分割单词
                if (res.task.material && res.task.material.type === 'speaking_reading') {
                    this.splitWords()
                }
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

    pauseTimer() {
        if (!this.data.timerRunning || this.data.timerPaused) return

        // Clear interval
        if (this.data.timerInterval) {
            clearInterval(this.data.timerInterval)
        }

        this.setData({
            timerPaused: true,
            timerInterval: null
        })

        wx.showToast({ title: '计时已暂停', icon: 'none' })
    },

    resumeTimer() {
        if (!this.data.timerRunning || !this.data.timerPaused) return

        // Resume interval
        const interval = setInterval(() => {
            this.updateTimer()
        }, 1000)

        this.setData({
            timerPaused: false,
            timerInterval: interval
        })

        wx.showToast({ title: '计时继续', icon: 'none' })
    },

    async stopTimer() {
        if (!this.data.timerRunning) return

        const res = await wx.showModal({
            title: '结束计时',
            content: '确定要结束当前计时吗？',
            confirmText: '确定',
            cancelText: '取消'
        })

        if (!res.confirm) return

        try {
            const activeTimer = app.globalData.activeTimer
            if (!activeTimer) return

            // Call backend to stop timer
            const stopRes = await request(`/miniprogram/student/tasks/${this.data.taskId}/timer/${activeTimer.sessionId}/stop`, {
                method: 'POST'
            })

            if (stopRes.ok) {
                // Clear timer state
                this.stopTimerDisplay()
                app.globalData.activeTimer = null
                wx.removeStorageSync('activeTimer')

                wx.showToast({ title: '计时已结束', icon: 'success' })
            }
        } catch (err) {
            console.error('Stop timer error:', err)
            wx.showToast({ title: '结束计时失败', icon: 'none' })
        }
    },

    stopTimerDisplay() {
        if (this.data.timerInterval) {
            clearInterval(this.data.timerInterval)
        }
        this.setData({
            timerRunning: false,
            timerInterval: null,
            displayTime: '00:00',
            elapsedSeconds: 0
        })
    },

    async submitTask() {
        // Check if timer was used (reminder for students who forgot to start timer)
        const actualSeconds = this.data.task.actual_seconds || 0
        if (actualSeconds < 60) { // Less than 1 minute
            const res = await wx.showModal({
                title: '提醒',
                content: '您还没有记录学习时间（或时间少于1分钟）。\n\n建议：返回首页启动计时器记录真实学习时长。\n\n确定要继续提交吗？',
                confirmText: '继续提交',
                cancelText: '返回',
                confirmColor: '#1F6C65'
            })

            if (!res.confirm) {
                return // User chose to go back
            }
        }

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
                this.runConfetti() // 触发撒花
                wx.showToast({ title: '提交成功！', icon: 'success' })
                setTimeout(() => {
                    wx.navigateBack()
                }, 2000) // 延长到2秒，让动画播完
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
    },

    // 播放老师语音反馈
    playFeedbackAudio() {
        const audioUrl = `${this.data.baseUrl}${this.data.task.feedback_audio}`;
        const innerAudioContext = wx.createInnerAudioContext();

        if (this.data.playingFeedback) {
            innerAudioContext.stop();
            this.setData({ playingFeedback: false });
        } else {
            innerAudioContext.src = audioUrl;
            innerAudioContext.play();
            this.setData({ playingFeedback: true });

            innerAudioContext.onEnded(() => {
                this.setData({ playingFeedback: false });
            });

            innerAudioContext.onError((res) => {
                wx.showToast({ title: '播放失败', icon: 'none' });
                this.setData({ playingFeedback: false });
            });
        }
    },

    // 预览批注图片
    previewFeedbackImage() {
        const imageUrl = `${this.data.baseUrl}${this.data.task.feedback_image}`;
        wx.previewImage({
            urls: [imageUrl],
            current: imageUrl
        });
    },

    // --- 撒花特效 ---
    runConfetti() {
        this.setData({ showConfetti: true })
        const query = wx.createSelectorQuery()
        query.select('#confetti')
            .fields({ node: true, size: true })
            .exec((res) => {
                const canvas = res[0].node
                const ctx = canvas.getContext('2d')
                const width = res[0].width
                const height = res[0].height

                canvas.width = width * 2 // Retina 屏优化
                canvas.height = height * 2
                ctx.scale(2, 2)

                const particles = []
                const colors = ['#ff0000', '#00ff00', '#0000ff', '#ffff00', '#00ffff', '#ff00ff']

                for (let i = 0; i < 100; i++) {
                    particles.push({
                        x: width / 2,
                        y: height / 2,
                        vx: (Math.random() - 0.5) * 20,
                        vy: (Math.random() - 0.5) * 20 - 10,
                        life: 100 + Math.random() * 50,
                        color: colors[Math.floor(Math.random() * colors.length)],
                        size: Math.random() * 5 + 5
                    })
                }

                const render = () => {
                    ctx.clearRect(0, 0, width, height)
                    let active = false

                    particles.forEach(p => {
                        if (p.life > 0) {
                            active = true
                            p.life--
                            p.x += p.vx
                            p.y += p.vy
                            p.vy += 0.5 // 重力

                            ctx.fillStyle = p.color
                            ctx.fillRect(p.x, p.y, p.size, p.size)
                        }
                    })

                    if (active) {
                        canvas.requestAnimationFrame(render)
                    } else {
                        this.setData({ showConfetti: false })
                    }
                }

                canvas.requestAnimationFrame(render)
            })
    },

    // ========== TTS 功能 ==========

    /**
     * 分割文本为单词数组
     */
    splitWords() {
        const { task } = this.data
        if (!task.material || !task.material.questions || !task.material.questions[0]) {
            return
        }

        const q = task.material.questions[0]

        // 按换行符分割，保留完整短语（包括中文翻译）
        const splitByLines = (text) => {
            if (!text) return []
            return text.split(/\n+/).map(line => line.trim()).filter(line => line.length > 0)
        }

        // 词汇表达 - 保留完整短语
        const vocabulary = q.content || ''
        const vocabularyWords = splitByLines(vocabulary)

        // 句型表达 - 保留完整短语
        const sentences = q.hint || ''
        const sentenceWords = splitByLines(sentences)

        // 示范段落 - 保留完整短语
        const paragraphText = q.reference_answer || ''
        const paragraphWords = splitByLines(paragraphText)

        this.setData({
            vocabularyWords,
            sentenceWords,
            paragraphWords
        })
    },

    /**
     * 朗读单个单词
     */
    async playWord(e) {
        const word = e.currentTarget.dataset.word
        if (!word) return

        const ctx = this.data.ttsContext

        // 如果点击的是当前正在播放的单词，则暂停/继续
        if (this.data.currentPlayingText === word) {
            if (this.data.isPlaying) {
                ctx.pause()
            } else {
                ctx.play()
            }
            return
        }

        wx.showLoading({ title: '准备中...' })

        try {
            // 根据 provider 选择 API 端点
            const endpoint = this.data.ttsProvider === 'azure' ? '/azure-tts/word' : '/tts/word'

            const res = await request(endpoint, {
                method: 'POST',
                data: {
                    word,
                    voice: this.data.ttsProvider === 'azure' ? 'en-US-JennyNeural' : undefined
                }
            })

            if (res.ok && res.audio_url) {
                ctx.src = this.data.baseUrl + res.audio_url
                ctx.play()
                this.setData({ currentPlayingText: word })
            } else {
                wx.showToast({ title: '生成失败', icon: 'none' })
            }
        } catch (err) {
            console.error('单词朗读错误:', err)
            wx.showToast({ title: '生成失败，请重试', icon: 'none' })
        } finally {
            wx.hideLoading()
        }
    }
})
