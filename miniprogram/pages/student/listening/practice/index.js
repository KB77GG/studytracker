const app = getApp()
const { request } = require('../../../../utils/request.js')
const ListeningCloze = require('../../../../utils/listening-cloze.js')

const DIFFICULTY_OPTIONS = ListeningCloze.LEVELS

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
        readOnly: false,
        dateStatusText: '',
        trainingPolicy: { locked: false, review_only: false },
        trainingModeLabel: '',
        reviewOnly: false,
        revealAllowed: true,
        reviewListened: false,
        modeLockedBeforeFirst: false,
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
        dictationStarted: false,
        hasDictationTargets: false,
        correctionMode: false,
        pendingSave: false,
        challengeAnswer: '',
        challengeResults: [],
        dictationNotice: '',
        repeatRecording: false,
        repeatFilePath: '',
        repeatPlayingRecord: false,
        repeatUploading: false,
        mode: 'dictation',
        showOriginal: false,
        showTranslation: false,
        difficultyOptions: DIFFICULTY_OPTIONS,
        difficultyIndex: 1,
        activeDifficultyIndex: 1,
        dictationLevelKey: 'standard',
        dictationLevelFrozen: false,
        speedOptions: SPEED_OPTIONS,
        speedIndex: 1,
        audioReady: false,
        audioPlaying: false,
        audioNotice: '音频加载中…',
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
        this.dictationStartedMap = new Set()
        this.correctionMap = new Set()
        this.firstAttemptGates = new Map()
        this.dictationLevelMap = new Map()
        this.pendingFirstAttempts = new Map()
        this.dictationDraftMap = new Map()
        this.reviewListenedMap = new Set()
        this.pendingPlaybackToken = 0
        this.pendingSeekPlayback = null
        this.audioBoundaryTimer = null
        this.pendingPlaybackFallback = null
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
            this.setData({ audioReady: true, audioNotice: '' })
            if (this.pendingAutoplay) {
                this.pendingAutoplay = false
                this.playCurrentSegment()
            }
        })

        if (typeof this.audioCtx.onSeeked === 'function') {
            this.audioCtx.onSeeked(() => {
                const pending = this.pendingSeekPlayback
                if (pending) this.completePendingPlayback(pending.token)
            })
        }

        this.audioCtx.onPlay(() => {
            this.setData({ audioPlaying: true })
            this.startAudioBoundaryMonitor()
        })

        this.audioCtx.onPause(() => {
            this.setData({ audioPlaying: false })
            this.stopAudioBoundaryMonitor()
        })

        this.audioCtx.onStop(() => {
            this.setData({ audioPlaying: false })
            this.stopAudioBoundaryMonitor()
        })

        this.audioCtx.onEnded(() => {
            this.setData({ audioPlaying: false })
            this.stopAudioBoundaryMonitor()
        })

        this.audioCtx.onTimeUpdate(() => {
            this.handleAudioTimeUpdate()
        })

        this.audioCtx.onError((err) => {
            console.error('listening audio error', err)
            this.cancelPendingPlayback()
            this.setData({ audioPlaying: false, audioReady: false, audioNotice: '音频加载失败，请重试' })
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
        this.cancelPendingPlayback()
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
        this.cancelPendingPlayback()
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
            const trainingPolicy = (res.task && res.task.listening_training_policy)
                || { locked: false, review_only: false }
            const readOnly = !!(res.task && res.task.read_only)
            const initialMode = readOnly
                ? 'listen'
                : trainingPolicy.locked
                ? (trainingPolicy.review_only ? 'listen' : 'dictation')
                : this.data.mode

            this.setData({
                task: res.task || {},
                readOnly,
                dateStatusText: (res.task && (res.task.status_label || res.task.task_status_label || res.task.availability_label)) || '',
                trainingPolicy,
                trainingModeLabel: trainingPolicy.label || '',
                reviewOnly: !!trainingPolicy.review_only,
                mode: initialMode,
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
                this.setData({ audioReady: false, audioNotice: '音频加载中…' })
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
        if (detail.ok && detail.task) {
            this.setData({
                token: detail.task.listening_token || '',
                task: detail.task,
                readOnly: !!detail.task.read_only,
                dateStatusText: detail.task.status_label || detail.task.task_status_label || detail.task.availability_label || ''
            })
        }
        if (detail.ok && detail.task && detail.task.listening_token) {
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
                    sourceText: segment.text || '',
                    text: ListeningCloze.stripSpeakerLabel(segment.text || ''),
                    translation: segment.translation || '',
                    assignedTrainingLevel: segment.assigned_training_level || '',
                    challengeAllowed: segment.challenge_allowed !== false
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

        let totalCorrect = 0
        let totalWords = 0
        Object.values(progressMap).forEach(progress => {
            if (!progress || !progress.is_completed) return
            totalCorrect += Number(progress.correct_words || 0)
            totalWords += Number(progress.total_words || 0)
        })
        const accuracy = totalWords > 0
            ? Number(((totalCorrect / totalWords) * 100).toFixed(1))
            : Number(task.accuracy || 0)
        const completionRate = totalCount > 0
            ? Number(((completedCount / totalCount) * 100).toFixed(1))
            : Number(task.completion_rate || 0)

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

    getDictationStateKey(segment) {
        return String(segment && segment.globalIndex)
    },

    ensureDictationState() {
        if (!this.dictationStartedMap) this.dictationStartedMap = new Set()
        if (!this.correctionMap) this.correctionMap = new Set()
        if (!this.firstAttemptGates) this.firstAttemptGates = new Map()
        if (!this.dictationLevelMap) this.dictationLevelMap = new Map()
        if (!this.pendingFirstAttempts) this.pendingFirstAttempts = new Map()
        if (!this.dictationDraftMap) this.dictationDraftMap = new Map()
    },

    getDictationDraftKey(segment, levelKey) {
        return `${this.getDictationStateKey(segment)}:${levelKey}`
    },

    saveCurrentDictationDraft() {
        const segment = this.data.currentSegment
        if (!segment || this.data.readOnly || this.data.dictationLocked || this.data.correctionMode) return
        this.ensureDictationState()
        const progress = this.data.progressMap[String(segment.globalIndex)]
        if (progress || this.getPendingFirstAttempt(segment)) return
        const levelKey = this.data.dictationLevelKey || this.getDictationLevelForSegment(segment, progress)
        this.dictationDraftMap.set(this.getDictationDraftKey(segment, levelKey), {
            blankAnswers: [...(this.data.blankAnswers || [])],
            challengeAnswer: String(this.data.challengeAnswer || '')
        })
    },

    getSelectedDictationLevel() {
        return DIFFICULTY_OPTIONS[this.data.difficultyIndex] || DIFFICULTY_OPTIONS[1]
    },

    getDictationLevelForSegment(segment, progress) {
        this.ensureDictationState()
        const key = this.getDictationStateKey(segment)
        if (this.dictationLevelMap.has(key)) {
            return this.dictationLevelMap.get(key)
        }
        const selected = this.getSelectedDictationLevel().key
        // Historical progress has no difficulty field. Only an exact complete
        // spoken-token coverage is safe to present as challenge; partial legacy
        // records must remain per-word regardless of the currently selected UI.
        if (progress) {
            const sourceText = this.getProgressSegmentText(progress, segment)
            const inferred = progress.training_level
                || ListeningCloze.inferSavedDictationLevel(sourceText, progress)
            this.dictationLevelMap.set(key, inferred)
            return inferred
        }
        if (this.data.trainingPolicy.locked && segment && segment.assignedTrainingLevel) {
            this.dictationLevelMap.set(key, segment.assignedTrainingLevel)
            return segment.assignedTrainingLevel
        }
        return selected
    },

    freezeDictationLevel(segment, progress) {
        this.ensureDictationState()
        const key = this.getDictationStateKey(segment)
        const level = this.getDictationLevelForSegment(segment, progress)
        this.dictationLevelMap.set(key, level)
        return level
    },

    isDictationLevelFrozen(segment, progress) {
        this.ensureDictationState()
        if (this.data.trainingPolicy.locked && progress) return false
        return !!progress || this.dictationLevelMap.has(this.getDictationStateKey(segment))
    },

    getProgressSegmentText(progress, segment) {
        return String((progress && progress.segment_text) || (segment && segment.sourceText) || '').trim()
    },

    getFirstAttemptGate(segment, hasSavedProgress) {
        this.ensureDictationState()
        const key = this.getDictationStateKey(segment)
        if (!this.firstAttemptGates.has(key)) {
            this.firstAttemptGates.set(key, ListeningCloze.createFirstAttemptGate(hasSavedProgress))
        }
        return this.firstAttemptGates.get(key)
    },

    getPendingFirstAttempt(segment) {
        this.ensureDictationState()
        return this.pendingFirstAttempts.get(this.getDictationStateKey(segment)) || null
    },

    markFirstAttemptSavePending(segment, attempt) {
        this.ensureDictationState()
        this.pendingFirstAttempts.set(this.getDictationStateKey(segment), attempt)
    },

    resultFromProgress(sourceText, hiddenIndices, progress) {
        if (!progress) return null
        const localGrade = ListeningCloze.gradeAnswers(sourceText, hiddenIndices, progress.answers_json || [])
        const canonicalResults = Array.isArray(progress.results) ? progress.results : []
        const grade = canonicalResults.length
            ? {
                ...localGrade,
                results: canonicalResults,
                accuracy: Number(progress.accuracy || 0),
                correctWords: Number(progress.correct_words || 0),
                totalWords: Number(progress.total_words || 0)
            }
            : localGrade
        return {
            grade,
            summary: {
                accuracy: Number(progress.accuracy || 0),
                correctWords: Number(progress.correct_words || 0),
                totalWords: Number(progress.total_words || 0)
            }
        }
    },

    selectSegment(index, autoplay = false) {
        const segments = this.data.segments || []
        if (index < 0 || index >= segments.length) return

        this.saveCurrentDictationDraft()
        this.pauseAudio()

        const currentSegment = segments[index]
        const progress = this.data.progressMap[String(currentSegment.globalIndex)]
        const repeatProgress = this.data.repeatProgressMap[String(currentSegment.globalIndex)]
        const stateKey = this.getDictationStateKey(currentSegment)
        const pendingAttempt = this.getPendingFirstAttempt(currentSegment)
        const sourceText = pendingAttempt
            ? pendingAttempt.sourceText
            : this.getProgressSegmentText(progress, currentSegment)
        const levelKey = pendingAttempt
            ? pendingAttempt.level
            : this.getDictationLevelForSegment(currentSegment, progress)
        const effectiveDifficultyIndex = Math.max(0, DIFFICULTY_OPTIONS.findIndex(option => option.key === levelKey))
        const hiddenIndices = pendingAttempt
            ? pendingAttempt.hiddenIndices
            : this.getHideIndices(currentSegment, levelKey, sourceText, progress)
        this.ensureDictationState()
        const draft = this.dictationDraftMap.get(this.getDictationDraftKey(currentSegment, levelKey)) || null
        const presetAnswers = pendingAttempt
            ? pendingAttempt.answers
            : (progress && Array.isArray(progress.answers_json)
                ? progress.answers_json
                : (draft ? draft.blankAnswers : []))
        const resultFromProgress = this.resultFromProgress(sourceText, hiddenIndices, progress)
        const resultToRender = pendingAttempt
            ? {
                grade: pendingAttempt.grade,
                summary: {
                    accuracy: pendingAttempt.grade.accuracy,
                    correctWords: pendingAttempt.grade.correctWords,
                    totalWords: pendingAttempt.grade.totalWords
                }
            }
            : resultFromProgress
        const correctionMode = this.correctionMap.has(stateKey)
        const built = this.buildRenderTokens(
            sourceText,
            hiddenIndices,
            correctionMode ? [] : presetAnswers,
            correctionMode ? null : resultToRender && resultToRender.grade
        )
        const expected = ListeningCloze.expectedTokens(sourceText, hiddenIndices)
        const dictationLevelFrozen = this.isDictationLevelFrozen(currentSegment, progress)
        const lockedPolicy = !!this.data.trainingPolicy.locked
        const reviewOnly = !!this.data.trainingPolicy.review_only
        const modeLockedBeforeFirst = lockedPolicy && !reviewOnly && !progress
        const reviewListened = !!(this.reviewListenedMap
            && this.reviewListenedMap.has(stateKey))
        const revealAllowed = !lockedPolicy || !!progress || (reviewOnly && reviewListened)
        const ranks = { basic: 0, standard: 1, challenge: 2 }
        const assignedLevel = currentSegment.assignedTrainingLevel
        const savedLevel = (progress && progress.training_level) || assignedLevel
        const difficultyOptions = DIFFICULTY_OPTIONS.map(option => ({
            ...option,
            disabled: (option.key === 'challenge' && !currentSegment.challengeAllowed)
                || (lockedPolicy && !progress && option.key !== assignedLevel)
                || (lockedPolicy && progress && savedLevel
                    && ranks[option.key] < ranks[savedLevel])
                || (!lockedPolicy && dictationLevelFrozen && option.key !== levelKey)
        }))
        const challengeAnswer = correctionMode
            ? ''
            : (resultToRender && levelKey === 'challenge'
                ? resultToRender.grade.results
                    .filter(result => !result.isExtra)
                    .map(result => result.isCorrect ? result.rawAnswer : result.answer)
                    .join(' ')
                : (draft ? draft.challengeAnswer : ''))

        this.segmentStopHandled = false
        this.getFirstAttemptGate(currentSegment, !!progress)

        this.setData({
            currentIndex: index,
            currentSegment,
            mode: reviewOnly ? 'listen' : (modeLockedBeforeFirst ? 'dictation' : this.data.mode),
            showOriginal: revealAllowed ? this.data.showOriginal : false,
            showTranslation: revealAllowed ? this.data.showTranslation : false,
            revealAllowed,
            reviewListened,
            modeLockedBeforeFirst,
            difficultyOptions,
            // Keep the global choice for the next untouched sentence. A saved
            // legacy result may need a different, safely inferred render mode.
            activeDifficultyIndex: effectiveDifficultyIndex,
            dictationLevelKey: levelKey,
            dictationLevelFrozen,
            hiddenIndices,
            renderTokens: built.renderTokens,
            blankAnswers: built.blankAnswers,
            currentResult: resultToRender && !correctionMode ? resultToRender.summary : null,
            currentRepeatResult: repeatProgress ? this.buildRepeatResult(repeatProgress) : null,
            dictationLocked: (!!progress || !!pendingAttempt) && !correctionMode,
            dictationStarted: !!progress || !!pendingAttempt || this.dictationStartedMap.has(stateKey),
            hasDictationTargets: expected.length > 0,
            correctionMode,
            pendingSave: !!pendingAttempt && !correctionMode,
            challengeAnswer,
            challengeResults: resultToRender && !correctionMode && levelKey === 'challenge'
                ? resultToRender.grade.results.map((result, index) => ({
                    index,
                    answer: result.isExtra ? result.rawAnswer : result.answer,
                    isCorrect: result.isCorrect,
                    isExtra: !!result.isExtra
                }))
                : [],
            dictationNotice: correctionMode
                ? '订正仅在本地核对，不会再次提交或改写首答成绩。'
                : (pendingAttempt ? '首答保存未确认；请刷新确认，避免重复提交覆盖成绩。' : ''),
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
        if (this.data.readOnly) return
        if (this.data.reviewOnly || (this.data.modeLockedBeforeFirst && mode !== 'dictation')) {
            wx.showToast({ title: this.data.reviewOnly ? '本任务为听辨核对' : '首答后开放复盘模式', icon: 'none' })
            return
        }
        this.saveCurrentDictationDraft()
        this.setData({ mode }, () => {
            if (mode === 'dictation') this.selectSegment(this.data.currentIndex, false)
        })
    },

    toggleOriginal() {
        if (!this.data.revealAllowed) {
            wx.showToast({ title: this.data.reviewOnly ? '请先完整听完本句' : '首答后开放原文', icon: 'none' })
            return
        }
        this.setData({ showOriginal: !this.data.showOriginal })
    },

    toggleTranslation() {
        if (!this.data.revealAllowed) {
            wx.showToast({ title: this.data.reviewOnly ? '请先完整听完本句' : '首答后开放译文', icon: 'none' })
            return
        }
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
        if (this.data.readOnly) return
        const difficultyIndex = Number(e.currentTarget.dataset.index || 0)
        const option = (this.data.difficultyOptions || [])[difficultyIndex]
        if (!option || option.disabled) {
            wx.showToast({ title: option && option.key === 'challenge' && !this.data.currentSegment.challengeAllowed
                ? '长句不开放整句听写'
                : (this.data.modeLockedBeforeFirst ? '首答使用布置档位' : '复盘只能保持或升档'), icon: 'none' })
            return
        }
        const currentSegment = this.data.currentSegment
        const progress = currentSegment && this.data.progressMap[String(currentSegment.globalIndex)]
        if (currentSegment && this.isDictationLevelFrozen(currentSegment, progress)) {
            const notice = progress
                ? '已保存的本句难度已冻结，切到未开始的新句后再选择。'
                : '本句已开始作答，难度已冻结以保留答案。'
            this.setData({ dictationNotice: notice })
            wx.showToast({ title: '本句难度已冻结', icon: 'none' })
            return
        }
        if (option.key === this.data.dictationLevelKey) return
        if (this.data.trainingPolicy.locked && progress) {
            const stateKey = this.getDictationStateKey(currentSegment)
            this.dictationLevelMap.set(stateKey, option.key)
            this.correctionMap.add(stateKey)
            this.dictationStartedMap.add(stateKey)
        }
        this.setData({ difficultyIndex }, () => {
            if (this.data.currentSegment) this.selectSegment(this.data.currentIndex, false)
        })
    },

    rebuildCurrentTokens(preserveAnswers = true, hiddenIndices = this.data.hiddenIndices) {
        const currentSegment = this.data.currentSegment
        if (!currentSegment) return
        const answers = preserveAnswers ? (this.data.blankAnswers || []) : []
        const progress = this.data.progressMap[String(currentSegment.globalIndex)]
        const sourceText = this.getProgressSegmentText(progress, currentSegment)
        const built = this.buildRenderTokens(sourceText, hiddenIndices, answers)
        this.setData({
            renderTokens: built.renderTokens,
            blankAnswers: built.blankAnswers
        })
    },

    startCurrentDictation() {
        if (this.data.readOnly) return
        const segment = this.data.currentSegment
        if (!segment) return
        const progress = this.data.progressMap[String(segment.globalIndex)]
        this.freezeDictationLevel(segment, progress)
        this.dictationStartedMap.add(this.getDictationStateKey(segment))
        this.selectSegment(this.data.currentIndex, false)
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

    stopAudioBoundaryMonitor() {
        if (this.audioBoundaryTimer) {
            clearInterval(this.audioBoundaryTimer)
            this.audioBoundaryTimer = null
        }
    },

    startAudioBoundaryMonitor() {
        this.stopAudioBoundaryMonitor()
        this.audioBoundaryTimer = setInterval(() => this.handleAudioTimeUpdate(), 50)
    },

    cancelPendingPlayback() {
        this.pendingPlaybackToken = Number(this.pendingPlaybackToken || 0) + 1
        this.pendingSeekPlayback = null
        this.pendingAutoplay = false
        if (this.pendingPlaybackFallback) {
            clearTimeout(this.pendingPlaybackFallback)
            this.pendingPlaybackFallback = null
        }
        this.stopAudioBoundaryMonitor()
    },

    completePendingPlayback(token) {
        const pending = this.pendingSeekPlayback
        if (!pending || pending.token !== token || token !== this.pendingPlaybackToken) return false
        const current = this.data.currentSegment
        if (!this.audioCtx || !current || current.globalIndex !== pending.segmentIndex) {
            this.cancelPendingPlayback()
            return false
        }
        if (this.pendingPlaybackFallback) {
            clearTimeout(this.pendingPlaybackFallback)
            this.pendingPlaybackFallback = null
        }
        this.pendingSeekPlayback = null
        this.audioCtx.playbackRate = pending.speed
        this.audioCtx.play()
        return true
    },

    playCurrentSegment() {
        if (!this.audioCtx || !this.data.currentSegment) return
        if (!this.data.audioReady) {
            this.pendingAutoplay = true
            this.setData({ audioNotice: '音频加载中，稍候会自动播放…' })
            return
        }

        const segment = this.data.currentSegment
        const speed = SPEED_OPTIONS[this.data.speedIndex].value
        this.segmentStopHandled = false

        try {
            this.cancelPendingPlayback()
            this.audioCtx.pause()
            this.audioCtx.playbackRate = speed
            const token = this.pendingPlaybackToken
            this.pendingSeekPlayback = {
                token,
                segmentIndex: segment.globalIndex,
                speed
            }
            this.audioCtx.seek(Math.max(0, segment.start))
            this.pendingPlaybackFallback = setTimeout(() => {
                this.completePendingPlayback(token)
            }, 400)
        } catch (err) {
            console.error('playCurrentSegment failed', err)
            this.cancelPendingPlayback()
            this.setData({ audioNotice: '播放失败，请重试' })
            wx.showToast({ title: '播放失败', icon: 'none' })
        }
    },

    handleAudioTimeUpdate() {
        const segment = this.data.currentSegment
        if (!segment || !this.audioCtx) return

        const currentTime = Number(this.audioCtx.currentTime || 0)
        const duration = Math.max(0, segment.end - segment.start)
        const relative = Math.min(duration, Math.max(0, currentTime - segment.start))
        this.setData({
            currentTimeText: this.formatTime(relative)
        })

        if (!this.segmentStopHandled && currentTime >= Math.max(segment.start, segment.end)) {
            this.segmentStopHandled = true
            this.pauseAudio()
            if (this.data.reviewOnly && this.reviewListenedMap) {
                this.reviewListenedMap.add(this.getDictationStateKey(segment))
                this.setData({ reviewListened: true, revealAllowed: true })
            }
        }
    },

    onBlankInput(e) {
        if (this.data.readOnly || this.data.dictationLocked) return
        const blankIndex = Number(e.currentTarget.dataset.blankIndex)
        const value = e.detail.value || ''
        const blankAnswers = [...this.data.blankAnswers]
        blankAnswers[blankIndex] = value
        if (String(value).trim()) {
            const segment = this.data.currentSegment
            const progress = segment && this.data.progressMap[String(segment.globalIndex)]
            if (segment) this.freezeDictationLevel(segment, progress)
        }
        this.setData({ blankAnswers }, () => this.saveCurrentDictationDraft())
    },

    onChallengeInput(e) {
        if (this.data.readOnly || this.data.dictationLocked) return
        const value = e.detail.value || ''
        if (String(value).trim() && this.data.currentSegment) {
            const progress = this.data.progressMap[String(this.data.currentSegment.globalIndex)]
            this.freezeDictationLevel(this.data.currentSegment, progress)
        }
        this.setData({ challengeAnswer: value }, () => this.saveCurrentDictationDraft())
    },

    async submitCurrentSegment() {
        if (this.data.readOnly) return
        if (this.data.dictationLocked || !this.data.currentSegment) return
        if (!this.data.hasDictationTargets) {
            wx.showToast({ title: '当前句没有可听写单词', icon: 'none' })
            return
        }
        const progress = this.data.progressMap[String(this.data.currentSegment.globalIndex)]
        const sourceText = this.getProgressSegmentText(progress, this.data.currentSegment)
        const levelKey = this.getDictationLevelForSegment(this.data.currentSegment, progress)
        const expected = ListeningCloze.expectedTokens(sourceText, this.data.hiddenIndices)
        const hasAnyAnswer = levelKey === 'challenge'
            ? String(this.data.challengeAnswer || '').trim().length > 0
            : (this.data.blankAnswers || []).some(answer => String(answer || '').trim().length > 0)
        if (!hasAnyAnswer) {
            const notice = levelKey === 'challenge'
                ? '请先输入整句或意群，再提交首答。'
                : '请至少填写一个听写词，再提交首答。'
            this.setData({ dictationNotice: notice })
            wx.showToast({ title: '请先作答', icon: 'none' })
            return
        }
        this.freezeDictationLevel(this.data.currentSegment, progress)
        const rawAnswers = levelKey === 'challenge'
            ? ListeningCloze.splitChallengeAnswers(this.data.challengeAnswer, expected.length)
            : (this.data.blankAnswers || []).map(item => item || '')
        const grade = ListeningCloze.gradeAnswers(sourceText, this.data.hiddenIndices, rawAnswers)
        const built = this.buildRenderTokens(sourceText, this.data.hiddenIndices, rawAnswers, grade)
        const currentResult = {
            accuracy: grade.accuracy,
            correctWords: grade.correctWords,
            totalWords: grade.totalWords
        }
        const displayChallengeAnswer = grade.results
            .filter(result => !result.isExtra)
            .map(result => result.isCorrect ? result.rawAnswer : result.answer)
            .join(' ')

        this.setData({
            renderTokens: built.renderTokens,
            blankAnswers: built.blankAnswers,
            currentResult,
            dictationLocked: true,
            challengeAnswer: displayChallengeAnswer,
            challengeResults: levelKey === 'challenge'
                ? grade.results.map((result, index) => ({
                    index,
                    answer: result.isExtra ? result.rawAnswer : result.answer,
                    isCorrect: result.isCorrect,
                    isExtra: !!result.isExtra
                }))
                : [],
            dictationNotice: this.data.correctionMode
                ? '订正结果仅本地核对，首答成绩保持不变。'
                : '已显示首答逐词结果和正确答案。'
        })

        if (this.data.correctionMode) return

        const gate = this.getFirstAttemptGate(this.data.currentSegment, !!progress)
        if (!gate.beginFirstAttempt()) return

        try {
            const res = await request(
                `/student/listening/task/${this.data.taskId}/segment/${this.data.currentSegment.globalIndex}?token=${encodeURIComponent(this.data.token)}`,
                {
                    method: 'POST',
                    data: {
                        segment_text: sourceText,
                        hidden_word_indices: this.data.hiddenIndices,
                        answers: rawAnswers,
                        correct_words: grade.correctWords,
                        total_words: grade.totalWords,
                        training_level: levelKey,
                        duration_seconds: this.computeDurationSeconds()
                    }
                }
            )

            if (!res.ok) {
                this.markFirstAttemptSavePending(this.data.currentSegment, {
                    sourceText,
                    hiddenIndices: [...this.data.hiddenIndices],
                    level: levelKey,
                    answers: [...rawAnswers],
                    grade
                })
                this.setData({
                    pendingSave: true,
                    dictationNotice: '首答保存未确认；请刷新确认，避免重复提交覆盖成绩。'
                })
                wx.showToast({ title: '进度保存失败', icon: 'none' })
                return
            }

            const serverSegment = res.segment || {}
            const savedProgress = {
                segment_index: this.data.currentSegment.globalIndex,
                segment_text: serverSegment.segment_text || sourceText,
                correct_words: Number(serverSegment.correct_words ?? grade.correctWords),
                total_words: Number(serverSegment.total_words ?? grade.totalWords),
                accuracy: Number(serverSegment.accuracy ?? currentResult.accuracy),
                is_completed: true,
                hidden_word_indices: serverSegment.hidden_word_indices || this.data.hiddenIndices,
                answers_json: serverSegment.answers || rawAnswers,
                results: Array.isArray(serverSegment.results) ? serverSegment.results : [],
                training_level: serverSegment.training_level || levelKey
            }
            const progressMap = {
                ...this.data.progressMap,
                [String(this.data.currentSegment.globalIndex)]: savedProgress
            }

            const segments = this.decorateSegments(this.data.segments, progressMap, this.data.repeatProgressMap)
            const task = res.task ? {
                ...this.data.task,
                accuracy: res.task.accuracy,
                completion_rate: res.task.completion_rate
            } : this.data.task
            const summary = this.buildSummary(segments, progressMap, task)
            const allCompleted = summary.totalCount > 0 && summary.completedCount >= summary.totalCount
            const canonicalDisplay = this.resultFromProgress(
                savedProgress.segment_text,
                savedProgress.hidden_word_indices,
                savedProgress
            )
            const canonicalGrade = canonicalDisplay ? canonicalDisplay.grade : grade
            const canonicalBuilt = this.buildRenderTokens(
                savedProgress.segment_text,
                savedProgress.hidden_word_indices,
                savedProgress.answers_json,
                canonicalGrade
            )

            this.ensureDictationState()
            this.dictationDraftMap.delete(this.getDictationDraftKey(this.data.currentSegment, levelKey))
            this.pendingFirstAttempts.delete(this.getDictationStateKey(this.data.currentSegment))
            this.setData({
                progressMap,
                segments,
                task,
                summary,
                allCompleted,
                renderTokens: canonicalBuilt.renderTokens,
                blankAnswers: canonicalBuilt.blankAnswers,
                currentResult: canonicalDisplay ? canonicalDisplay.summary : currentResult,
                challengeAnswer: levelKey === 'challenge'
                    ? canonicalGrade.results
                        .filter(result => !result.isExtra)
                        .map(result => result.isCorrect ? result.rawAnswer : result.answer)
                        .join(' ')
                    : this.data.challengeAnswer,
                challengeResults: levelKey === 'challenge'
                    ? canonicalGrade.results.map((result, index) => ({
                        index,
                        answer: result.isExtra ? result.rawAnswer : result.answer,
                        isCorrect: result.isCorrect,
                        isExtra: !!result.isExtra
                    }))
                    : [],
                pendingSave: false,
                dictationNotice: '首答已保存；已显示逐词结果和正确答案。'
            }, () => this.selectSegment(this.data.currentIndex, false))

            wx.showToast({
                title: allCompleted ? '精听完成' : '本句已保存',
                icon: 'success'
            })
        } catch (err) {
            console.error(err)
            this.markFirstAttemptSavePending(this.data.currentSegment, {
                sourceText,
                hiddenIndices: [...this.data.hiddenIndices],
                level: levelKey,
                answers: [...rawAnswers],
                grade
            })
            this.setData({
                pendingSave: true,
                dictationNotice: '首答保存未确认；请刷新确认，避免重复提交覆盖成绩。'
            })
            wx.showToast({ title: '保存未确认，请刷新核对', icon: 'none' })
        }
    },

    startCorrection() {
        if (this.data.readOnly) return
        if (!this.data.currentSegment) return
        if (this.getPendingFirstAttempt(this.data.currentSegment)) {
            this.setData({ dictationNotice: '首答保存未确认；请先刷新确认，避免重复提交覆盖成绩。' })
            wx.showToast({ title: '请先刷新确认首答', icon: 'none' })
            return
        }
        const progress = this.data.progressMap[String(this.data.currentSegment.globalIndex)]
        const gate = this.getFirstAttemptGate(this.data.currentSegment, !!progress)
        if (!gate.enterCorrection()) return
        this.correctionMap.add(this.getDictationStateKey(this.data.currentSegment))
        this.dictationStartedMap.add(this.getDictationStateKey(this.data.currentSegment))
        this.selectSegment(this.data.currentIndex, false)
        this.playCurrentSegment()
    },

    redoCurrentSegment() {
        this.startCorrection()
    },

    async completeReviewSegment() {
        if (this.data.readOnly) return
        const segment = this.data.currentSegment
        if (!segment || !this.data.reviewOnly) return
        if (!this.data.reviewListened || !this.data.showOriginal) {
            wx.showToast({ title: '请先完整听完并查看原文', icon: 'none' })
            return
        }
        const existing = this.data.progressMap[String(segment.globalIndex)]
        if (existing && existing.is_completed) return
        try {
            const res = await request(
                `/student/listening/task/${this.data.taskId}/segment/${segment.globalIndex}/review?token=${encodeURIComponent(this.data.token)}`,
                {
                    method: 'POST',
                    data: {
                        listened: true,
                        revealed_original: true,
                        duration_seconds: this.computeDurationSeconds()
                    }
                }
            )
            if (!res || !res.ok) {
                wx.showToast({ title: '听辨进度保存失败', icon: 'none' })
                return
            }
            const progressMap = {
                ...this.data.progressMap,
                [String(segment.globalIndex)]: res.segment
            }
            const segments = this.decorateSegments(
                this.data.segments,
                progressMap,
                this.data.repeatProgressMap
            )
            const task = res.task ? { ...this.data.task, ...res.task } : this.data.task
            const summary = this.buildSummary(segments, progressMap, task)
            const currentSegment = segments.find(
                item => item.globalIndex === segment.globalIndex
            ) || segment
            this.setData({
                progressMap,
                segments,
                currentSegment,
                task,
                summary,
                allCompleted: summary.totalCount > 0 && summary.completedCount >= summary.totalCount
            })
            wx.showToast({ title: '本句听辨已完成', icon: 'success' })
        } catch (err) {
            console.error(err)
            wx.showToast({ title: '网络错误', icon: 'none' })
        }
    },

    startRepeatRecording() {
        if (this.data.readOnly || this.data.repeatUploading) return
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
        if (this.data.readOnly || !this.data.repeatRecording) return
        this.recorderManager.stop()
    },

    playRepeatRecording() {
        if (!this.data.repeatFilePath || !this.recordAudioCtx) return
        this.recordAudioCtx.src = this.data.repeatFilePath
        this.recordAudioCtx.play()
    },

    resetRepeatRecording() {
        if (this.data.readOnly) return
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
                formData: { task_id: this.data.taskId || '' },
                success: (res) => {
                    try {
                        const data = JSON.parse(res.data || '{}')
                        if (res.statusCode >= 200 && res.statusCode < 300 && data.ok) {
                            resolve(data)
                            return
                        }
                            reject(new Error(data.message || data.status_label || data.task_status_label || data.availability_label || data.error || 'upload_failed'))
                    } catch (err) {
                        reject(err)
                    }
                },
                fail: reject
            })
        })
    },

    async submitRepeatSegment() {
        if (this.data.readOnly) return
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

    buildRenderTokens(sourceText, hiddenIndices, presetAnswers = [], grade = null) {
        const words = ListeningCloze.tokenizeSentence(sourceText)
        const hiddenSet = new Set(hiddenIndices)
        const expectedByWordIndex = new Map(
            ListeningCloze.expectedTokens(sourceText, hiddenIndices)
                .map((token, blankIndex) => [token.index, { token, blankIndex }])
        )
        const renderTokens = []
        const blankAnswers = []

        words.forEach(word => {
            const answerMeta = expectedByWordIndex.get(word.index)
            if (!hiddenSet.has(word.index) || !answerMeta) {
                renderTokens.push({
                    tokenKey: `text-${word.index}`,
                    kind: 'text',
                    text: `${word.raw} `
                })
                return
            }

            const blankIndex = answerMeta.blankIndex
            const displayAnswer = word.display
            if (!displayAnswer) {
                renderTokens.push({
                    tokenKey: `text-${word.index}`,
                    kind: 'text',
                    text: `${word.raw} `
                })
                return
            }

            const suffixMatch = word.raw.match(/[.,!?;:"'”’)\]]+$/)
            const presetValue = presetAnswers[blankIndex] || ''
            const result = grade && grade.results[blankIndex]
            const displayValue = result ? (result.isCorrect ? result.rawAnswer : result.answer) : presetValue
            const answerLength = Array.from(String(displayAnswer || '')).length
            blankAnswers[blankIndex] = displayValue
            renderTokens.push({
                tokenKey: `blank-${word.index}`,
                kind: 'blank',
                blankIndex,
                answer: word.normalized,
                displayAnswer,
                value: displayValue,
                suffix: suffixMatch ? suffixMatch[0] : '',
                status: result ? (result.isCorrect ? 'correct' : 'wrong') : '',
                inputWidth: result ? Math.max(160, Math.min(360, answerLength * 28 + 40)) : 160,
                resultText: result ? (result.isCorrect ? '正确' : '需订正') : '',
                ariaLabel: result
                    ? `第 ${blankIndex + 1} 个听写词，${result.isCorrect ? '正确' : '需订正，正确答案 ' + result.answer}`
                    : `第 ${blankIndex + 1} 个听写词`
            })
        })

        return { renderTokens, blankAnswers }
    },

    getHideIndices(segment, levelKey = this.getSelectedDictationLevel().key, sourceText = '', existingProgress = null) {
        const existing = existingProgress || this.data.progressMap[String(segment.globalIndex)]
        const savedLevel = existing
            ? (existing.training_level
                || ListeningCloze.inferSavedDictationLevel(
                    sourceText || existing.segment_text || '',
                    existing
                ))
            : null
        if (existing && savedLevel === levelKey && Array.isArray(existing.hidden_word_indices)) {
            return existing.hidden_word_indices.map(Number).filter(Number.isInteger)
        }

        const level = DIFFICULTY_OPTIONS.find(option => option.key === levelKey)
            || this.getSelectedDictationLevel()
        return ListeningCloze.selectHiddenWordIndices(sourceText || segment.sourceText || '', level.key, {
            seed: `${this.data.taskId}:${segment.globalIndex}:${level.key}`
        })
    },

    normalizeWord(word) {
        return ListeningCloze.normalizeWord(word)
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
