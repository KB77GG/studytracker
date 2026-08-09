const app = getApp()
const { request } = require('../../../utils/request.js')
const { resolveAudioUrl } = require('../../../utils/dictation-audio.js')
const {
    isEnglishSpellingMode,
    normalizeKeyboardKey
} = require('../../../utils/dictation-input-policy.js')

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
        isEnglishSpelling: false,
        showResult: false,
        isCorrect: false,
        submittedAnswer: '',
        correctAnswer: '',
        submitting: false,
        finishing: false,
        finished: false,
        result: null,
        diagnostics: [],
        startedAt: 0
    },

    onLoad(options) {
        const rawTaskId = String((options || {}).taskId || (options || {}).id || '')
        if (!/^\d+$/.test(rawTaskId)) {
            this.setData({ loading: false, loadError: '任务链接无效' })
            return
        }
        this.setData({ taskId: rawTaskId, startedAt: Date.now() })
        this.audioCtx = wx.createInnerAudioContext()
        this.audioCtx.onError(() => wx.showToast({ title: '音频播放失败', icon: 'none' }))
        this.fetchQueue()
    },

    onUnload() {
        if (this.audioCtx) {
            try { this.audioCtx.stop() } catch (e) {}
            try { this.audioCtx.destroy() } catch (e) {}
            this.audioCtx = null
        }
    },

    queueUrl() {
        return `/miniprogram/student/tasks/${this.data.taskId}/vocabulary-queue`
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
        const isEnglishSpelling = !!question && isEnglishSpellingMode(question.mode)
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
            isEnglishSpelling,
            inputValue: '',
            selectedOption: '',
            showResult: false,
            submittedAnswer: '',
            correctAnswer: '',
            diagnostics: Array.isArray(queue.diagnostics) ? queue.diagnostics : [],
            finished: false
        }, () => {
            if (isFinished) {
                this.finishTask()
                return
            }
            if (question && String(question.mode || '').indexOf('audio_to_') === 0) this.playAudio()
        })
    },

    familiarityItem() {
        return this.data.familiarity[this.data.familiarityIndex] || null
    },

    previousFamiliarity() {
        if (this.data.phase !== 'familiarity' || this.data.familiarityIndex <= 0) return
        this.setData({ familiarityIndex: this.data.familiarityIndex - 1 })
    },

    nextFamiliarity() {
        if (this.data.phase !== 'familiarity') return
        const item = this.familiarityItem()
        if (!item) return
        if (item.viewed) {
            const next = this.data.familiarityIndex + 1
            if (next < this.data.familiarity.length) this.setData({ familiarityIndex: next })
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
        if (this.data.showResult || this.data.isEnglishSpelling) return
        this.setData({ inputValue: (e && e.detail && e.detail.value) || '' })
    },

    onKeyboardKey(e) {
        if (!this.data.isEnglishSpelling || this.data.showResult) return
        const key = normalizeKeyboardKey(e && e.detail && e.detail.key)
        const separators = (this.data.currentQuestion && this.data.currentQuestion.answer_separators) || []
        if (!/^[a-z0-9é]$/.test(key) && !separators.includes(key)) return
        const limit = Number(this.data.currentQuestion && this.data.currentQuestion.answer_length) || 100
        if (Array.from(this.data.inputValue || '').length >= limit) return
        this.setData({ inputValue: `${this.data.inputValue || ''}${key}` })
    },

    onKeyboardBackspace() {
        if (!this.data.isEnglishSpelling || this.data.showResult) return
        const chars = Array.from(this.data.inputValue || '')
        chars.pop()
        this.setData({ inputValue: chars.join('') })
    },

    selectOption(e) {
        if (this.data.showResult) return
        const optionId = e && e.currentTarget && e.currentTarget.dataset && e.currentTarget.dataset.id
        if (optionId) this.setData({ selectedOption: String(optionId) })
    },

    answerValue() {
        const question = this.data.currentQuestion || {}
        return question.mode === 'context_choice'
            ? this.data.selectedOption
            : String(this.data.inputValue || '').trim()
    },

    submitAnswer() {
        const question = this.data.currentQuestion
        if (!question || this.data.phase === 'familiarity') return
        if (this.data.showResult) {
            this.fetchQueue()
            return
        }
        if (this.data.submitting) return
        const answer = this.answerValue()
        if (!answer) {
            wx.showToast({ title: question.mode === 'context_choice' ? '请选择答案' : '请输入答案', icon: 'none' })
            return
        }
        const retryPrefix = this.data.phase === 'retry' ? 'retry:' : 'first:'
        const attemptId = `vocabulary-group:${this.data.taskId}:${retryPrefix}${question.learning_question_id}`
        this.setData({ submitting: true })
        request('/dictation/submit', {
            method: 'POST',
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
                input_mode: this.data.isEnglishSpelling ? 'strict' : 'native'
            }
        }).then((res) => {
            if (!res || !res.ok) throw new Error((res && res.error) || 'vocabulary_group_answer_failed')
            this.setData({
                submitting: false,
                showResult: true,
                isCorrect: !!res.is_correct,
                submittedAnswer: res.student_answer || answer,
                correctAnswer: res.revealed_answer || ''
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
        const url = (prompt && (prompt.audio_tts_url || prompt.audio_url)) || familiarity.audio_tts_url
        if (!this.audioCtx || !url) return
        this.audioCtx.src = resolveAudioUrl(url, app.globalData.baseUrl)
        try { this.audioCtx.play() } catch (e) {}
    },

    finishTask() {
        if (this.data.finishing || this.data.finished) return
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
