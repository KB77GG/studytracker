const app = getApp()
const { request } = require('../../../utils/request.js')
const { createReliableAudioPlayer } = require('../../../utils/dictation-audio.js')
const {
    buildMeaningChoiceOptions,
    selectedOptionLabel
} = require('../../../utils/vocabulary-interaction.js')
const { normalizeAnswerFeedback } = require('../../../utils/vocabulary-feedback.js')

const PHASE_LABELS = {
    familiarity: '熟悉材料',
    active_recall: '主动提取',
    context_discrimination: '语境辨析',
    context_production: '语境产出',
    retry: '错题再测',
    complete: '本组完成'
}

Page({
    data: {
        loading: true,
        loadError: '',
        taskId: null,
        queueToken: '',
        groupNumber: 0,
        groupCount: 0,
        groupSize: 0,
        totalWordCount: 0,
        phase: '',
        phaseLabel: '',
        familiarity: [],
        familiarityIndex: 0,
        currentQuestion: null,
        inputValue: '',
        selectedOption: '',
        meaningOptions: [],
        isMeaningChoice: false,
        audioState: 'idle',
        audioButtonLabel: '播放发音',
        showResult: false,
        isCorrect: false,
        submittedAnswer: '',
        correctAnswer: '',
        answerFeedback: null,
        submitting: false,
        finishing: false,
        finished: false,
        result: null,
        diagnostics: [],
        startedAt: 0,
        readOnly: false,
        dateStatusText: ''
    },

    onLoad(options) {
        const rawTaskId = String((options || {}).taskId || (options || {}).id || '')
        if (!/^\d+$/.test(rawTaskId)) {
            this.setData({ loading: false, loadError: '任务链接无效' })
            return
        }
        this.setData({ taskId: rawTaskId, startedAt: Date.now() })
        this.audioPlayer = createReliableAudioPlayer(wx, {
            onStateChange: (state) => this.setData({
                audioState: state,
                audioButtonLabel: state === 'loading'
                    ? '正在加载…'
                    : (state === 'playing' ? '正在播放' : '播放发音')
            }),
            onError: () => wx.showToast({ title: '音频播放失败，请重试', icon: 'none' })
        })
        this.fetchTaskAccess()
    },

    onUnload() {
        if (this.audioPlayer) this.audioPlayer.destroy()
        this.audioPlayer = null
    },

    queueUrl() {
        return `/miniprogram/student/tasks/${this.data.taskId}/vocabulary-queue`
    },

    fetchTaskAccess() {
        request(`/miniprogram/student/tasks/${this.data.taskId}`).then((res) => {
            if (!res || !res.ok || !res.task) throw new Error('task_load_failed')
            const task = res.task
            this.setData({
                readOnly: !!task.read_only,
                dateStatusText: task.status_label || '该任务当前仅可查看'
            })
            if (task.read_only) {
                this.setData({ loading: false })
                return
            }
            this.fetchQueue()
        }).catch((err) => {
            console.warn('load vocabulary task failed', err)
            this.setData({ loading: false, loadError: '任务加载失败，请重试' })
        })
    },

    fetchQueue() {
        this.setData({ loading: true, loadError: '' })
        request(this.queueUrl()).then((res) => {
            if (!res || !res.ok) {
                if (res && res.error === 'vocabulary_review_required') {
                    wx.redirectTo({ url: `/pages/student/vocabulary-review/index?returnTaskId=${this.data.taskId}` })
                    return
                }
                throw new Error((res && res.error) || 'vocabulary_group_load_failed')
            }
            this.applyQueue(res)
        }).catch((err) => {
            console.warn('load vocabulary group failed', err)
            this.setData({ loading: false, loadError: '小组学习加载失败，请重试' })
        })
    },

    handleMutationError(err) {
        const code = err && err.message
        if (code === 'vocabulary_review_required') {
            wx.redirectTo({ url: `/pages/student/vocabulary-review/index?returnTaskId=${this.data.taskId}` })
            return true
        }
        if (code === 'state_conflict' || code === 'question_not_current' || code === 'queue_changed') {
            wx.showToast({ title: '学习状态已更新，正在恢复', icon: 'none' })
            this.fetchQueue()
            return true
        }
        return false
    },

    applyQueue(queue) {
        const familiarity = Array.isArray(queue.familiarity) ? queue.familiarity : []
        const firstUnviewed = familiarity.findIndex((item) => !item.viewed)
        const displayIndex = firstUnviewed >= 0 ? firstUnviewed : Math.max(0, familiarity.length - 1)
        const question = queue.current_question || null
        const isMeaningChoice = !!question && question.mode === 'audio_to_zh'
        const meaningOptions = isMeaningChoice
            ? buildMeaningChoiceOptions(question, familiarity)
            : []
        const isFinished = !!queue.completed
        this.setData({
            loading: false,
            queueToken: queue.queue_token || '',
            groupNumber: Number(queue.group_number || 0),
            groupCount: Number(queue.group_count || 0),
            groupSize: Number(queue.group_size || 0),
            totalWordCount: Number(queue.total_word_count || 0),
            phase: queue.phase || '',
            phaseLabel: queue.phase_label || PHASE_LABELS[queue.phase] || queue.phase || '',
            familiarity,
            familiarityIndex: displayIndex,
            currentQuestion: question,
            isMeaningChoice,
            meaningOptions,
            inputValue: '',
            selectedOption: '',
            showResult: false,
            submittedAnswer: '',
            correctAnswer: '',
            answerFeedback: null,
            diagnostics: Array.isArray(queue.diagnostics) ? queue.diagnostics : [],
            finished: false
        }, () => {
            if (isFinished) {
                this.finishTask()
                return
            }
            if (
                queue.phase === 'familiarity'
                || (question && String(question.mode || '').indexOf('audio_to_') === 0)
            ) this.playAudio()
        })
    },

    familiarityItem() {
        return this.data.familiarity[this.data.familiarityIndex] || null
    },

    previousFamiliarity() {
        if (this.data.phase !== 'familiarity' || this.data.familiarityIndex <= 0) return
        this.setData({ familiarityIndex: this.data.familiarityIndex - 1 }, () => this.playAudio())
    },

    nextFamiliarity() {
        if (this.data.readOnly) return
        if (this.data.phase !== 'familiarity') return
        const item = this.familiarityItem()
        if (!item) return
        if (item.viewed) {
            const next = this.data.familiarityIndex + 1
            if (next < this.data.familiarity.length) {
                this.setData({ familiarityIndex: next }, () => this.playAudio())
            }
            return
        }
        request(`/miniprogram/student/tasks/${this.data.taskId}/vocabulary-learning/familiarity`, {
            method: 'POST',
            data: { queue_token: this.data.queueToken, word_id: item.word_id }
        }).then((res) => {
            if (!res || !res.ok) throw new Error((res && res.error) || 'familiarity_failed')
            this.applyQueue(res)
        }).catch((err) => {
            console.warn('mark vocabulary familiarity failed', err)
            this.fetchQueue()
        })
    },

    onInput(e) {
        if (this.data.readOnly || this.data.showResult) return
        this.setData({ inputValue: (e && e.detail && e.detail.value) || '' })
    },

    selectOption(e) {
        if (this.data.readOnly || this.data.showResult) return
        const optionId = e && e.currentTarget && e.currentTarget.dataset && e.currentTarget.dataset.id
        if (optionId) this.setData({ selectedOption: String(optionId) })
    },

    answerValue() {
        const question = this.data.currentQuestion || {}
        if (question.mode === 'context_choice') return this.data.selectedOption
        if (this.data.isMeaningChoice) {
            return selectedOptionLabel(this.data.meaningOptions, this.data.selectedOption)
        }
        return String(this.data.inputValue || '').trim()
    },

    feedbackFallback(question) {
        const wordId = question && question.word_id
        return (this.data.familiarity || []).find(
            (item) => String(item.word_id) === String(wordId)
        ) || {}
    },

    submitAnswer() {
        if (this.data.readOnly) return
        const question = this.data.currentQuestion
        if (!question || this.data.phase === 'familiarity') return
        if (this.data.showResult) {
            this.fetchQueue()
            return
        }
        if (this.data.submitting) return
        const answer = this.answerValue()
        if (!answer) {
            wx.showToast({
                title: question.mode === 'context_choice' || this.data.isMeaningChoice
                    ? '请选择答案'
                    : '请输入答案',
                icon: 'none'
            })
            return
        }
        const retryPrefix = this.data.phase === 'retry' ? 'retry:' : 'first:'
        const attemptId = `vocabulary-group:${this.data.taskId}:${retryPrefix}${question.learning_question_id}`
        this.setData({ submitting: true })
        request('/dictation/submit', {
            method: 'POST',
            timeout: 15000,
            data: {
                task_id: Number(this.data.taskId),
                queue_token: this.data.queueToken,
                learning_question_id: question.learning_question_id,
                queue_item_id: question.queue_item_id,
                question_id: question.question_id,
                word_id: question.word_id,
                sense_id: question.sense_id,
                dimension: question.dimension,
                answer,
                attempt_id: attemptId,
                retry: this.data.phase === 'retry',
                input_mode: 'native'
            }
        }).then((res) => {
            if (!res || !res.ok) throw new Error((res && res.error) || 'vocabulary_group_answer_failed')
            const answerFeedback = normalizeAnswerFeedback(res, this.feedbackFallback(question))
            this.setData({
                submitting: false,
                showResult: true,
                isCorrect: !!res.is_correct,
                submittedAnswer: res.student_answer || answer,
                correctAnswer: res.revealed_answer || '',
                answerFeedback
            })
        }).catch((err) => {
            console.warn('submit vocabulary group answer failed', err)
            this.setData({ submitting: false })
            if (!this.handleMutationError(err)) wx.showToast({ title: '提交失败，请重试', icon: 'none' })
        })
    },

    playAudio() {
        const question = this.data.currentQuestion || {}
        const prompt = question.question && question.question.prompt
        const familiarity = this.familiarityItem() || {}
        const feedback = this.data.answerFeedback || {}
        const url = (this.data.showResult && feedback.audio_tts_url)
            || (prompt && (prompt.audio_tts_url || prompt.audio_url))
            || familiarity.audio_tts_url
        if (!this.audioPlayer || !url) {
            wx.showToast({ title: '当前单词暂无发音', icon: 'none' })
            return
        }
        this.audioPlayer.play(url, app.globalData.baseUrl)
    },

    finishTask() {
        if (this.data.readOnly || this.data.finishing || this.data.finished) return
        this.setData({ finishing: true })
        request(`/miniprogram/student/tasks/${this.data.taskId}/submit`, {
            method: 'POST',
            data: {
                queue_token: this.data.queueToken,
                duration_seconds: this.data.startedAt
                    ? Math.max(0, Math.floor((Date.now() - this.data.startedAt) / 1000))
                    : 0
            }
        }).then((res) => {
            if (!res || !res.ok) throw new Error((res && res.error) || 'vocabulary_group_finalize_failed')
            this.setData({ finishing: false, finished: true, result: res })
        }).catch((err) => {
            console.warn('finalize vocabulary group failed', err)
            this.setData({ finishing: false })
            if (!this.handleMutationError(err)) wx.showToast({ title: '任务结算失败，请重试', icon: 'none' })
        })
    },

    retry() {
        this.fetchQueue()
    },

    exitPage() {
        wx.switchTab({ url: '/pages/student/home/index' })
    }
})
