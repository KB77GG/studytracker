const app = getApp()
const { request } = require('../../../../utils/request.js')

const DIFFICULTY_OPTIONS = [
    { label: '简单', ratio: 0.3 },
    { label: '标准', ratio: 0.5 },
    { label: '挑战', ratio: 0.8 }
]

const SPEED_OPTIONS = [
    { label: '0.75x', value: 0.75 },
    { label: '1.0x', value: 1.0 },
    { label: '1.25x', value: 1.25 },
    { label: '1.5x', value: 1.5 }
]

Page({
    data: {
        taskId: null,
        token: '',
        loading: true,
        rootUrl: '',
        task: {},
        exercise: {},
        segments: [],
        progressMap: {},
        repeatProgressMap: {},
        summary: {
            completedCount: 0,
            totalCount: 0,
            accuracy: 0,
            completionRate: 0
        },
        repeatSummary: {
            attemptedCount: 0,
            passedCount: 0,
            avgScore: 0,
            completionRate: 0,
            passRate: 0
        },
        allCompleted: false,
        currentIndex: 0,
        currentSegment: null,
        hiddenIndices: [],
        renderTokens: [],
        blankAnswers: [],
        currentResult: null,
        currentRepeatResult: null,
        dictationLocked: false,
        repeatRecording: false,
        repeatFilePath: '',
        repeatPlayingRecord: false,
        repeatUploading: false,
        mode: 'dictation',
        showOriginal: false,
        showTranslation: false,
        difficultyOptions: DIFFICULTY_OPTIONS,
        difficultyIndex: 1,
        speedOptions: SPEED_OPTIONS,
        speedIndex: 1,
        audioReady: false,
        audioPlaying: false,
        currentTimeText: '00:00',
        segmentDurationText: '00:00',
        startedAt: 0,
        passThresholds: {
            accuracy: 75,
            fluency: 70,
            completion: 90
        }
    },

    onLoad(options) {
        const taskId = parseInt(options.taskId, 10)
        const token = options.token ? decodeURIComponent(options.token) : ''
        this.setData({
            taskId,
            token,
            rootUrl: this.getRootUrl(),
            startedAt: Date.now()
        })
        this.initAudio()
        this.initRepeatRecorder()
        this.fetchPractice()
    },

    onHide() {
        this.pauseAudio()
        this.stopRepeatPlayback()
    },

    onUnload() {
        this.destroyAudio()
        this.destroyRepeatRecorder()
    },

    getRootUrl() {
        return (app.globalData.baseUrl || '').replace(/\/api\/?$/, '')
    },

    initAudio() {
        wx.setInnerAudioOption({
            obeyMuteSwitch: false,
            speakerOn: true
        })
        this.audioCtx = wx.createInnerAudioContext()
        this.audioCtx.obeyMuteSwitch = false
        this.audioCtx.autoplay = false

        this.audioCtx.onCanplay(() => {
            this.setData({ audioReady: true })
            if (this.pendingAutoplay) {
                this.pendingAutoplay = false
                this.playCurrentSegment()
            }
        })

        this.audioCtx.onPlay(() => {
            this.setData({ audioPlaying: true })
        })

        this.audioCtx.onPause(() => {
            this.setData({ audioPlaying: false })
        })

        this.audioCtx.onStop(() => {
            this.setData({ audioPlaying: false })
        })

        this.audioCtx.onEnded(() => {
            this.setData({ audioPlaying: false })
        })

        this.audioCtx.onTimeUpdate(() => {
            this.handleAudioTimeUpdate()
        })

        this.audioCtx.onError((err) => {
            console.error('listening audio error', err)
            this.setData({ audioPlaying: false })
            wx.showToast({ title: '音频播放失败', icon: 'none' })
        })
    },

    initRepeatRecorder() {
        this.recorderManager = wx.getRecorderManager()
        this.recorderManager.onStop((res) => {
            this.setData({
                repeatRecording: false,
                repeatFilePath: res.tempFilePath || ''
            })
        })
        this.recorderManager.onError((err) => {
            console.error('repeat recorder error', err)
            this.setData({ repeatRecording: false })
            wx.showToast({ title: '录音失败', icon: 'none' })
        })

        this.recordAudioCtx = wx.createInnerAudioContext()
        this.recordAudioCtx.onPlay(() => {
            this.setData({ repeatPlayingRecord: true })
        })
        this.recordAudioCtx.onStop(() => {
            this.setData({ repeatPlayingRecord: false })
        })
        this.recordAudioCtx.onEnded(() => {
            this.setData({ repeatPlayingRecord: false })
        })
        this.recordAudioCtx.onError((err) => {
            console.error('repeat record playback error', err)
            this.setData({ repeatPlayingRecord: false })
            wx.showToast({ title: '录音播放失败', icon: 'none' })
        })
    },

    destroyAudio() {
        if (!this.audioCtx) return
        try {
            this.audioCtx.stop()
            this.audioCtx.destroy()
        } catch (err) {
            console.warn('destroy audio failed', err)
        }
        this.audioCtx = null
    },

    destroyRepeatRecorder() {
        if (this.recordAudioCtx) {
            try {
                this.recordAudioCtx.stop()
                this.recordAudioCtx.destroy()
            } catch (err) {
                console.warn('destroy record audio failed', err)
            }
            this.recordAudioCtx = null
        }
    },

    pauseAudio() {
        if (!this.audioCtx) return
        try {
            this.audioCtx.pause()
        } catch (err) {
            console.warn('pause audio failed', err)
        }
    },

    stopRepeatPlayback() {
        if (!this.recordAudioCtx) return
        try {
            this.recordAudioCtx.stop()
        } catch (err) {
            console.warn('stop repeat playback failed', err)
        }
    },

    async fetchPractice() {
        wx.showLoading({ title: '加载中...' })
        try {
            const token = await this.ensureTaskToken()
            if (!token) {
                wx.showToast({ title: '任务缺少访问令牌', icon: 'none' })
                return
            }

            const res = await request(`/student/listening/task/${this.data.taskId}?token=${encodeURIComponent(token)}`)
            if (!res.ok) {
                wx.showToast({ title: '精听任务加载失败', icon: 'none' })
                return
            }

            const exercise = res.exercise || {}
            const rawProgress = res.progress || {}
            const rawRepeatProgress = res.repeat_progress || {}
            const progressMap = {}
            const repeatProgressMap = {}
            Object.keys(rawProgress).forEach(key => {
                progressMap[String(key)] = rawProgress[key]
            })
            Object.keys(rawRepeatProgress).forEach(key => {
                repeatProgressMap[String(key)] = rawRepeatProgress[key]
            })

            const segments = this.decorateSegments(
                this.flattenSegments(exercise),
                progressMap,
                repeatProgressMap
            )
            const summary = this.buildSummary(segments, progressMap, res.task || {})
            const repeatSummary = this.buildRepeatSummary(segments, repeatProgressMap, res.repeat_summary || {})
            const initialIndex = this.findInitialIndex(segments, progressMap)

            this.setData({
                task: res.task || {},
                exercise,
                progressMap,
                repeatProgressMap,
                segments,
                summary,
                repeatSummary,
                passThresholds: res.pass_thresholds || this.data.passThresholds,
                allCompleted: summary.totalCount > 0 && summary.completedCount >= summary.totalCount,
                loading: false
            })

            if (exercise.audio && this.audioCtx) {
                this.audioCtx.src = `${this.data.rootUrl}/static/listening/${exercise.audio}`
            }

            this.selectSegment(initialIndex, false)
        } catch (err) {
            console.error(err)
            wx.showToast({ title: '网络错误', icon: 'none' })
        } finally {
            wx.hideLoading()
        }
    },

    async ensureTaskToken() {
        if (this.data.token) return this.data.token
        const detail = await request(`/miniprogram/student/tasks/${this.data.taskId}`)
        if (detail.ok && detail.task && detail.task.listening_token) {
            this.setData({ token: detail.task.listening_token })
            return detail.task.listening_token
        }
        return ''
    },

    flattenSegments(exercise) {
        const parts = exercise.parts || []
        const segments = []
        let fallbackIndex = 0
        parts.forEach((part, partIndex) => {
            const items = part.segments || []
            items.forEach((segment, sentenceIndex) => {
                const sourceIndex = Number.isInteger(segment.source_index)
                    ? Number(segment.source_index)
                    : fallbackIndex
                segments.push({
                    globalIndex: sourceIndex,
                    partIndex,
                    partName: part.name || `Part ${partIndex + 1}`,
                    partShort: `P${partIndex + 1}`,
                    sentenceIndex,
                    start: Number(segment.start || 0),
                    end: Number(segment.end || 0),
                    text: segment.text || '',
                    translation: segment.translation || ''
                })
                fallbackIndex += 1
            })
        })
        return segments
    },

    decorateSegments(segments, progressMap, repeatProgressMap = {}) {
        return segments.map(segment => {
            const progress = progressMap[String(segment.globalIndex)]
            const repeatProgress = repeatProgressMap[String(segment.globalIndex)]
            return {
                ...segment,
                isCompleted: !!(progress && progress.is_completed),
                accuracy: progress ? Number(progress.accuracy || 0) : null,
                repeatAttempted: !!repeatProgress,
                repeatPassed: !!(repeatProgress && repeatProgress.is_passed),
                repeatScore: repeatProgress ? Number(repeatProgress.overall_score || 0) : null
            }
        })
    },

    buildSummary(segments, progressMap, task) {
        const totalCount = segments.length
        const completedCount = segments.filter(segment => {
            const progress = progressMap[String(segment.globalIndex)]
            return !!(progress && progress.is_completed)
        }).length

        let accuracy = Number(task.accuracy || 0)
        if (!accuracy && completedCount > 0) {
            let totalCorrect = 0
            let totalWords = 0
            Object.values(progressMap).forEach(progress => {
                totalCorrect += Number(progress.correct_words || 0)
                totalWords += Number(progress.total_words || 0)
            })
            accuracy = totalWords > 0 ? Number(((totalCorrect / totalWords) * 100).toFixed(1)) : 0
        }

        let completionRate = Number(task.completion_rate || 0)
        if (!completionRate && totalCount > 0) {
            completionRate = Number(((completedCount / totalCount) * 100).toFixed(1))
        }

        return {
            completedCount,
            totalCount,
            accuracy,
            completionRate
        }
    },

    buildRepeatSummary(segments, repeatProgressMap, serverSummary = {}) {
        const totalCount = segments.length
        const attemptedCount = segments.filter(segment => {
            const progress = repeatProgressMap[String(segment.globalIndex)]
            return !!progress
        }).length
        const passedCount = segments.filter(segment => {
            const progress = repeatProgressMap[String(segment.globalIndex)]
            return !!(progress && progress.is_passed)
        }).length

        let avgScore = Number(serverSummary.avg_score || 0)
        if (!avgScore && attemptedCount > 0) {
            const totalScore = Object.values(repeatProgressMap).reduce((sum, progress) => {
                return sum + Number(progress.overall_score || 0)
            }, 0)
            avgScore = Number((totalScore / attemptedCount).toFixed(1))
        }

        let completionRate = Number(serverSummary.completion_rate || 0)
        if (!completionRate && totalCount > 0) {
            completionRate = Number(((attemptedCount / totalCount) * 100).toFixed(1))
        }

        let passRate = Number(serverSummary.pass_rate || 0)
        if (!passRate && attemptedCount > 0) {
            passRate = Number(((passedCount / attemptedCount) * 100).toFixed(1))
        }

        return {
            attemptedCount,
            passedCount,
            avgScore,
            completionRate,
            passRate
        }
    },

    findInitialIndex(segments, progressMap) {
        const firstPending = segments.findIndex(segment => {
            const progress = progressMap[String(segment.globalIndex)]
            return !(progress && progress.is_completed)
        })
        return firstPending >= 0 ? firstPending : 0
    },

    selectSegment(index, autoplay = false) {
        const segments = this.data.segments || []
        if (index < 0 || index >= segments.length) return

        this.pauseAudio()

        const currentSegment = segments[index]
        const progress = this.data.progressMap[String(currentSegment.globalIndex)]
        const repeatProgress = this.data.repeatProgressMap[String(currentSegment.globalIndex)]
        const hiddenIndices = this.getHideIndices(currentSegment)
        const presetAnswers = progress && Array.isArray(progress.answers_json) ? progress.answers_json : []
        const built = this.buildRenderTokens(currentSegment, hiddenIndices, presetAnswers)

        this.segmentStopHandled = false

        this.setData({
            currentIndex: index,
            currentSegment,
            hiddenIndices,
            renderTokens: built.renderTokens,
            blankAnswers: built.blankAnswers,
            currentResult: progress ? {
                accuracy: Number(progress.accuracy || 0),
                correctWords: Number(progress.correct_words || 0),
                totalWords: Number(progress.total_words || 0)
            } : null,
            currentRepeatResult: repeatProgress ? this.buildRepeatResult(repeatProgress) : null,
            dictationLocked: !!progress,
            repeatFilePath: '',
            repeatRecording: false,
            repeatPlayingRecord: false,
            currentTimeText: '00:00',
            segmentDurationText: this.formatTime(Math.max(0, currentSegment.end - currentSegment.start))
        })

        if (autoplay) {
            setTimeout(() => this.playCurrentSegment(), 80)
        }
    },

    onSelectSegment(e) {
        const index = parseInt(e.currentTarget.dataset.index, 10)
        this.selectSegment(index, true)
    },

    switchMode(e) {
        const mode = e.currentTarget.dataset.mode
        if (!mode || mode === this.data.mode) return
        this.setData({ mode })
    },

    toggleOriginal() {
        this.setData({ showOriginal: !this.data.showOriginal })
    },

    toggleTranslation() {
        this.setData({ showTranslation: !this.data.showTranslation })
    },

    buildRepeatResult(progress) {
        if (!progress) return null
        const words = Array.isArray(progress.words) ? progress.words : []
        return {
            overallScore: Number(progress.overall_score || 0),
            pronAccuracy: Number(progress.pron_accuracy || 0),
            pronFluency: Number(progress.pron_fluency || 0),
            pronCompletion: Number(progress.pron_completion || 0),
            suggestedScore: Number(progress.suggested_score_100 || 0),
            isPassed: !!progress.is_passed,
            attemptCount: Number(progress.attempt_count || 0),
            audioUrl: progress.audio_url || '',
            issues: this.extractRepeatIssues(words)
        }
    },

    extractRepeatIssues(words = []) {
        if (!Array.isArray(words)) return []
        return words.map(item => {
            if (!item || typeof item !== 'object') return null
            const word = item.Word || item.word || item.Text || item.text || ''
            const accuracy = item.PronAccuracy ?? item.pronAccuracy ?? item.Accuracy ?? item.accuracy
            const accuracyVal = Number(accuracy)
            if (!word || Number.isNaN(accuracyVal) || accuracyVal >= this.data.passThresholds.accuracy) {
                return null
            }
            return {
                word,
                accuracy: Number(accuracyVal.toFixed(1))
            }
        }).filter(Boolean).sort((a, b) => a.accuracy - b.accuracy).slice(0, 5)
    },

    onSpeedChange(e) {
        const speedIndex = Number(e.detail.value || 0)
        this.setData({ speedIndex })
        if (this.audioCtx) {
            this.audioCtx.playbackRate = SPEED_OPTIONS[speedIndex].value
        }
    },

    changeDifficulty(e) {
        const difficultyIndex = Number(e.currentTarget.dataset.index || 0)
        if (difficultyIndex === this.data.difficultyIndex) return
        this.setData({ difficultyIndex })
        if (!this.data.currentResult && this.data.currentSegment) {
            const hiddenIndices = this.getHideIndices(this.data.currentSegment, difficultyIndex)
            this.setData({ hiddenIndices })
            this.rebuildCurrentTokens(true, hiddenIndices)
        }
    },

    rebuildCurrentTokens(preserveAnswers = true, hiddenIndices = this.data.hiddenIndices) {
        const currentSegment = this.data.currentSegment
        if (!currentSegment) return
        const answers = preserveAnswers ? (this.data.blankAnswers || []) : []
        const built = this.buildRenderTokens(currentSegment, hiddenIndices, answers)
        this.setData({
            renderTokens: built.renderTokens,
            blankAnswers: built.blankAnswers
        })
    },

    togglePlay() {
        if (this.data.audioPlaying) {
            this.pauseAudio()
            return
        }
        this.playCurrentSegment()
    },

    repeatSegment() {
        this.playCurrentSegment()
    },

    prevSegment() {
        if (this.data.currentIndex <= 0) {
            wx.showToast({ title: '已经是第一句', icon: 'none' })
            return
        }
        this.selectSegment(this.data.currentIndex - 1, true)
    },

    nextSegment() {
        const nextIndex = this.data.currentIndex + 1
        if (nextIndex >= this.data.segments.length) {
            wx.showToast({ title: '已经到最后一句', icon: 'none' })
            return
        }
        this.selectSegment(nextIndex, true)
    },

    playCurrentSegment() {
        if (!this.audioCtx || !this.data.currentSegment) return
        if (!this.data.audioReady) {
            this.pendingAutoplay = true
            return
        }

        const segment = this.data.currentSegment
        const speed = SPEED_OPTIONS[this.data.speedIndex].value
        this.segmentStopHandled = false

        try {
            this.audioCtx.pause()
            this.audioCtx.playbackRate = speed
            this.audioCtx.seek(Math.max(0, segment.start))
            setTimeout(() => {
                if (!this.audioCtx || !this.data.currentSegment || this.data.currentSegment.globalIndex !== segment.globalIndex) {
                    return
                }
                this.audioCtx.playbackRate = speed
                this.audioCtx.play()
            }, 120)
        } catch (err) {
            console.error('playCurrentSegment failed', err)
            wx.showToast({ title: '播放失败', icon: 'none' })
        }
    },

    handleAudioTimeUpdate() {
        const segment = this.data.currentSegment
        if (!segment || !this.audioCtx) return

        const currentTime = Number(this.audioCtx.currentTime || 0)
        const relative = Math.max(0, currentTime - segment.start)
        this.setData({
            currentTimeText: this.formatTime(relative)
        })

        if (!this.segmentStopHandled && currentTime >= Math.max(segment.start, segment.end - 0.05)) {
            this.segmentStopHandled = true
            this.pauseAudio()
        }
    },

    onBlankInput(e) {
        if (this.data.dictationLocked) return
        const blankIndex = Number(e.currentTarget.dataset.blankIndex)
        const value = e.detail.value || ''
        const blankAnswers = [...this.data.blankAnswers]
        blankAnswers[blankIndex] = value
        this.setData({ blankAnswers })
    },

    async submitCurrentSegment() {
        if (this.data.dictationLocked || !this.data.currentSegment) return

        const rawAnswers = (this.data.blankAnswers || []).map(item => item || '')
        if (rawAnswers.length === 0) {
            wx.showToast({ title: '当前句没有可听写单词', icon: 'none' })
            return
        }

        const filledCount = rawAnswers.filter(item => item.trim()).length
        if (filledCount === 0) {
            wx.showToast({ title: '请先输入答案', icon: 'none' })
            return
        }

        let correctWords = 0
        const updatedTokens = this.data.renderTokens.map(token => {
            if (token.kind !== 'blank') return token
            const raw = rawAnswers[token.blankIndex] || ''
            const normalized = this.normalizeWord(raw)
            const isCorrect = normalized === token.answer
            if (isCorrect) correctWords += 1
            return {
                ...token,
                status: isCorrect ? 'correct' : 'wrong',
                value: isCorrect ? raw : token.displayAnswer
            }
        })

        const currentResult = {
            accuracy: rawAnswers.length > 0 ? Number(((correctWords / rawAnswers.length) * 100).toFixed(1)) : 0,
            correctWords,
            totalWords: rawAnswers.length
        }

        const displayAnswers = updatedTokens
            .filter(token => token.kind === 'blank')
            .map(token => token.value || '')

        this.setData({
            renderTokens: updatedTokens,
            blankAnswers: displayAnswers,
            currentResult,
            dictationLocked: true
        })

        try {
            const res = await request(
                `/student/listening/task/${this.data.taskId}/segment/${this.data.currentSegment.globalIndex}?token=${encodeURIComponent(this.data.token)}`,
                {
                    method: 'POST',
                    data: {
                        segment_text: this.data.currentSegment.text,
                        hidden_word_indices: this.data.hiddenIndices,
                        answers: rawAnswers,
                        correct_words: correctWords,
                        total_words: rawAnswers.length,
                        duration_seconds: this.computeDurationSeconds()
                    }
                }
            )

            if (!res.ok) {
                wx.showToast({ title: '进度保存失败', icon: 'none' })
                return
            }

            const progressMap = {
                ...this.data.progressMap,
                [String(this.data.currentSegment.globalIndex)]: {
                    segment_index: this.data.currentSegment.globalIndex,
                    correct_words: correctWords,
                    total_words: rawAnswers.length,
                    accuracy: currentResult.accuracy,
                    is_completed: true,
                    hidden_word_indices: this.data.hiddenIndices,
                    answers_json: rawAnswers
                }
            }

            const segments = this.decorateSegments(this.data.segments, progressMap)
            const task = res.task ? {
                ...this.data.task,
                accuracy: res.task.accuracy,
                completion_rate: res.task.completion_rate
            } : this.data.task
            const summary = this.buildSummary(segments, progressMap, task)
            const allCompleted = summary.totalCount > 0 && summary.completedCount >= summary.totalCount

            this.setData({
                progressMap,
                segments,
                task,
                summary,
                allCompleted
            })

            wx.showToast({
                title: allCompleted ? '精听完成' : '本句已保存',
                icon: 'success'
            })
        } catch (err) {
            console.error(err)
            wx.showToast({ title: '网络错误', icon: 'none' })
        }
    },

    redoCurrentSegment() {
        if (!this.data.currentSegment) return
        const built = this.buildRenderTokens(this.data.currentSegment, this.data.hiddenIndices, [])
        this.setData({
            renderTokens: built.renderTokens,
            blankAnswers: built.blankAnswers,
            currentResult: null,
            dictationLocked: false
        })
    },

    startRepeatRecording() {
        if (this.data.repeatUploading) return
        this.pauseAudio()
        this.stopRepeatPlayback()
        this.setData({
            repeatRecording: true,
            repeatFilePath: ''
        })
        this.recorderManager.start({
            format: 'mp3',
            sampleRate: 16000,
            numberOfChannels: 1
        })
    },

    stopRepeatRecording() {
        if (!this.data.repeatRecording) return
        this.recorderManager.stop()
    },

    playRepeatRecording() {
        if (!this.data.repeatFilePath || !this.recordAudioCtx) return
        this.recordAudioCtx.src = this.data.repeatFilePath
        this.recordAudioCtx.play()
    },

    resetRepeatRecording() {
        this.stopRepeatPlayback()
        this.setData({
            repeatFilePath: '',
            repeatRecording: false
        })
    },

    uploadRepeatAudio(filePath) {
        const token = app.globalData.token || wx.getStorageSync('token') || ''
        const baseUrl = app.globalData.baseUrl || ''
        return new Promise((resolve, reject) => {
            wx.uploadFile({
                url: `${baseUrl}/miniprogram/upload`,
                filePath,
                name: 'file',
                header: token ? { Authorization: `Bearer ${token}` } : {},
                success: (res) => {
                    try {
                        const data = JSON.parse(res.data || '{}')
                        if (res.statusCode >= 200 && res.statusCode < 300 && data.ok) {
                            resolve(data)
                            return
                        }
                        reject(new Error(data.error || 'upload_failed'))
                    } catch (err) {
                        reject(err)
                    }
                },
                fail: reject
            })
        })
    },

    async submitRepeatSegment() {
        if (!this.data.currentSegment) return
        if (!this.data.repeatFilePath) {
            wx.showToast({ title: '请先录音', icon: 'none' })
            return
        }
        this.setData({ repeatUploading: true })
        wx.showLoading({ title: '评测中...' })
        try {
            const uploadRes = await this.uploadRepeatAudio(this.data.repeatFilePath)
            const res = await request(
                `/student/listening/task/${this.data.taskId}/segment/${this.data.currentSegment.globalIndex}/repeat?token=${encodeURIComponent(this.data.token)}`,
                {
                    method: 'POST',
                    data: {
                        audio_url: uploadRes.url,
                        segment_text: this.data.currentSegment.text,
                        duration_seconds: this.computeDurationSeconds()
                    }
                }
            )

            if (!res.ok) {
                wx.showModal({
                    title: '评测失败',
                    content: res.message || this.repeatErrorMessage(res),
                    showCancel: false
                })
                return
            }

            const repeatProgressMap = {
                ...this.data.repeatProgressMap,
                [String(this.data.currentSegment.globalIndex)]: res.segment
            }
            const segments = this.decorateSegments(this.data.segments, this.data.progressMap, repeatProgressMap)
            const repeatSummary = this.buildRepeatSummary(segments, repeatProgressMap, res.summary || {})
            const currentRepeatResult = this.buildRepeatResult(res.segment)

            this.setData({
                repeatProgressMap,
                segments,
                repeatSummary,
                currentRepeatResult,
                passThresholds: res.pass_thresholds || this.data.passThresholds
            })

            wx.showToast({
                title: currentRepeatResult && currentRepeatResult.isPassed ? '跟读通过' : '结果已保存',
                icon: 'success'
            })
        } catch (err) {
            console.error(err)
            wx.showToast({ title: '网络错误', icon: 'none' })
        } finally {
            wx.hideLoading()
            this.setData({ repeatUploading: false })
        }
    },

    repeatErrorMessage(res = {}) {
        const details = res.details || {}
        const code = details.code || res.code || ''
        const error = details.error || res.error || ''
        if (code === 'AuthFailure.AccountUnavailable') {
            return '腾讯口语评测服务未开通或账号欠费，请联系老师处理。'
        }
        if (error === 'tencent_soe_disabled') {
            return '跟读评测服务未启用，请联系老师处理。'
        }
        if (error === 'missing_tencent_soe_secret') {
            return '跟读评测密钥未配置，请联系老师处理。'
        }
        if (error === 'missing_tencent_soe_app_id') {
            return '跟读评测 AppID 未配置，请联系老师处理。'
        }
        if (code === 4002 || code === '4002') {
            return '腾讯口语评测鉴权失败，请联系老师检查 AppID 和密钥。'
        }
        if (code === 4003 || code === '4003') {
            return '腾讯口语评测 AppID 未开通新版服务，请联系老师处理。'
        }
        if (code === 4004 || code === '4004') {
            return '腾讯口语评测资源包已耗尽，请联系老师处理。'
        }
        if (code === 4005 || code === '4005') {
            return '腾讯云账号欠费，口语评测已暂停。'
        }
        if (code === 4007 || code === '4007') {
            return '录音解码失败，请重新录音后提交。'
        }
        if ([4102, '4102', 4103, '4103', 4104, '4104', 4110, '4110', 4114, '4114'].includes(code)) {
            return '跟读文本不符合评测要求，请联系老师检查原文。'
        }
        if ([4105, '4105', 4108, '4108'].includes(code)) {
            return '录音里没有识别到有效人声，请重新录音。'
        }
        if (error === 'tencent_audio_download_failed') {
            return '录音文件读取失败，请重新录音后提交。'
        }
        if (error === 'tencent_audio_empty') {
            return '录音文件为空，请重新录音。'
        }
        if (error === 'tencent_audio_too_large') {
            return '录音文件过大，请缩短录音后重试。'
        }
        if (error === 'tencent_soe_timeout') {
            return '跟读评测超时，请稍后重试。'
        }
        return '跟读评测暂时失败，请稍后重试。'
    },

    buildRenderTokens(segment, hiddenIndices, presetAnswers = []) {
        const words = (segment.text || '').split(/\s+/).filter(Boolean)
        const hiddenSet = new Set(hiddenIndices)
        const renderTokens = []
        const blankAnswers = []
        let blankIndex = 0

        words.forEach((word, wordIndex) => {
            if (!hiddenSet.has(wordIndex)) {
                renderTokens.push({
                    tokenKey: `text-${wordIndex}`,
                    kind: 'text',
                    text: `${word} `
                })
                return
            }

            const displayAnswer = word.replace(/^[.,!?;:"'“”‘’()]+|[.,!?;:"'“”‘’()]+$/g, '')
            if (!displayAnswer) {
                renderTokens.push({
                    tokenKey: `text-${wordIndex}`,
                    kind: 'text',
                    text: `${word} `
                })
                return
            }

            const suffixMatch = word.match(/[.,!?;:"'”’)\]]+$/)
            const presetValue = presetAnswers[blankIndex] || ''
            blankAnswers[blankIndex] = presetValue
            renderTokens.push({
                tokenKey: `blank-${wordIndex}`,
                kind: 'blank',
                blankIndex,
                answer: this.normalizeWord(displayAnswer),
                displayAnswer,
                value: presetValue,
                width: Math.max(76, displayAnswer.length * 18),
                suffix: suffixMatch ? suffixMatch[0] : '',
                status: ''
            })
            blankIndex += 1
        })

        return { renderTokens, blankAnswers }
    },

    getHideIndices(segment, difficultyIndex = this.data.difficultyIndex) {
        const existing = this.data.progressMap[String(segment.globalIndex)]
        if (existing && Array.isArray(existing.hidden_word_indices) && existing.hidden_word_indices.length) {
            return existing.hidden_word_indices
        }

        const words = (segment.text || '').split(/\s+/).filter(Boolean)
        if (!words.length) return []

        const ratio = DIFFICULTY_OPTIONS[difficultyIndex].ratio
        const hideCount = Math.max(1, Math.round(words.length * ratio))
        const indices = Array.from({ length: words.length }, (_, index) => index)
        const rng = this.seededRandom(this.hashCode(`${this.data.taskId}-${segment.globalIndex}-${segment.text.slice(0, 20)}-${hideCount}`))

        for (let i = indices.length - 1; i > 0; i -= 1) {
            const j = Math.floor(rng() * (i + 1))
            ;[indices[i], indices[j]] = [indices[j], indices[i]]
        }
        return indices.slice(0, hideCount).sort((a, b) => a - b)
    },

    normalizeWord(word) {
        return String(word || '')
            .toLowerCase()
            .replace(/[^\w]/g, '')
    },

    hashCode(text) {
        let hash = 0
        for (let i = 0; i < text.length; i += 1) {
            hash = ((hash << 5) - hash) + text.charCodeAt(i)
            hash |= 0
        }
        return hash
    },

    seededRandom(seed) {
        let value = seed || 1
        return () => {
            value = (value * 1664525 + 1013904223) & 0x7fffffff
            return value / 0x7fffffff
        }
    },

    computeDurationSeconds() {
        return Math.max(1, Math.round((Date.now() - this.data.startedAt) / 1000))
    },

    formatTime(seconds) {
        const total = Math.max(0, Math.floor(Number(seconds || 0)))
        const minutes = Math.floor(total / 60)
        const remain = total % 60
        return `${String(minutes).padStart(2, '0')}:${String(remain).padStart(2, '0')}`
    }
})
