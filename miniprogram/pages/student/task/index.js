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
        ttsSpeed: 1.0,
        vocabularyWords: [],
        sentenceWords: [],
        paragraphText: '',
        ttsContext: null,
        currentPlayingText: null,
        isPlaying: false
    },

    onLoad(options) {
        this.setData({ taskId: options.id })
        this.fetchTaskDetail()
        this.setupRecorder()
        this.initTTS()
    },

    onUnload() {
        if (this.data.ttsContext) {
            this.data.ttsContext.destroy()
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

    async submitTask() {
        // Check if timer was used (reminder for students who forgot to start timer)
        const actualSeconds = this.data.task.actual_seconds || 0
        if (actualSeconds < 60) { // Less than 1 minute
            const res = await wx.showModal({
                title: '提醒',
                content: '您还没有记录学习时间（或时间少于1分钟）。\n\n建议：返回首页启动计时器记录真实学习时长。\n\n确定要继续提交吗？',
                confirmText: '继续提交',
                cancelText: '返回',
                confirmColor: '#667eea'
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

        // 分割词汇表达 - 按换行或分号分割，保持短语完整性
        const vocabulary = q.content || ''
        const vocabularyWords = vocabulary.split(/[\n;]+/).map(w => w.trim()).filter(w => w.length > 0)

        // 分割句型表达 - 按换行分割
        const sentences = q.hint || ''
        const sentenceWords = sentences.split(/[\n]+/).map(w => w.trim()).filter(w => w.length > 0)

        // 示范段落 - 保持完整文本
        const paragraphText = q.reference_answer || ''

        this.setData({
            vocabularyWords,
            sentenceWords,
            paragraphText
        })
    },

    /**
     * 设置语速
     */
    setSpeed(e) {
        const speed = parseFloat(e.currentTarget.dataset.speed)
        this.setData({ ttsSpeed: speed })
    },

    /**
     * 朗读/暂停文本
     */
    async playText(e) {
        const text = e.currentTarget.dataset.text
        if (!text) {
            wx.showToast({ title: '内容为空', icon: 'none' })
            return
        }

        const ctx = this.data.ttsContext

        // 如果点击的是当前正在播放/暂停的文本
        if (this.data.currentPlayingText === text) {
            if (this.data.isPlaying) {
                ctx.pause()
            } else {
                ctx.play()
            }
            return
        }

        // 如果是新的文本
        wx.showLoading({ title: '准备中...' })

        try {
            const res = await request('/tts/synthesize', {
                method: 'POST',
                data: {
                    text: text,
                    speed: this.data.ttsSpeed
                }
            })

            if (res.ok && res.audio_url) {
                ctx.src = this.data.baseUrl + res.audio_url
                ctx.play()
                this.setData({ currentPlayingText: text })
            } else {
                wx.showToast({ title: '生成失败', icon: 'none' })
            }
        } catch (err) {
            console.error('TTS错误:', err)
            wx.showToast({ title: '生成失败', icon: 'none' })
        } finally {
            wx.hideLoading()
        }
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
            const res = await request('/tts/word', {
                method: 'POST',
                data: { word }
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
