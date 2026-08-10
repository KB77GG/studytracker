const app = getApp()
const { request } = require('../../../utils/request.js')
const { createReliableAudioPlayer } = require('../../../utils/dictation-audio.js')
const {
    buildMeaningChoiceOptions,
    selectedOptionLabel
} = require('../../../utils/vocabulary-interaction.js')
const {
    isEnglishSpellingMode,
    normalizeKeyboardKey
} = require('../../../utils/dictation-input-policy.js')

const DIMENSION_LABELS = {
    meaning_recall: '词义提取',
    form_recall: '词形提取',
    audio_form_recall: '听音辨形',
    context_use: '语境运用'
}

Page({
    data: {
        loading: true,
        loadError: '',
        empty: false,
        sessionId: null,
        sessionToken: '',
        queueToken: '',
        returningToTask: false,
        items: [],
        currentIndex: 0,
        currentItem: null,
        inputValue: '',
        selectedOption: '',
        meaningOptions: [],
        isMeaningChoice: false,
        isEnglishSpelling: false,
        audioState: 'idle',
        audioButtonLabel: '播放发音',
        currentDimensionLabel: '',
        showResult: false,
        isCorrect: false,
        correctAnswer: '',
        submittedAnswer: '',
        submitting: false,
        settling: false,
        finished: false,
        result: null,
        remainingDueCount: 0
    },

    onLoad(options) {
        options = options || {}
        const rawReturnTaskId = String(options.returnTaskId || options.originTaskId || '')
        this.returnTaskId = /^\d+$/.test(rawReturnTaskId) ? rawReturnTaskId : ''
        this.setData({ returningToTask: !!this.returnTaskId })
        this.audioPlayer = createReliableAudioPlayer(wx, {
            onStateChange: (state) => this.setData({
                audioState: state,
                audioButtonLabel: state === 'loading'
                    ? '正在加载…'
                    : (state === 'playing' ? '正在播放' : '播放发音')
            }),
            onError: () => wx.showToast({ title: '音频播放失败，请重试', icon: 'none' })
        })
        this.fetchSession()
    },

    onUnload() {
        if (this.returnTimer) {
            clearTimeout(this.returnTimer)
            this.returnTimer = null
        }
        if (this.audioPlayer) this.audioPlayer.destroy()
        this.audioPlayer = null
    },

    fetchSession() {
        this.setData({ loading: true, loadError: '' })
        const query = this.returnTaskId ? `?origin_task_id=${encodeURIComponent(this.returnTaskId)}` : ''
        request(`/miniprogram/student/vocabulary-review/today${query}`)
            .then((res) => {
                if (!res || !res.ok) throw new Error((res && res.error) || 'review_load_failed')
                const items = Array.isArray(res.items) ? res.items : []
                const firstUnanswered = items.findIndex((item) => !item.first_attempt_id)
                const resumeIndex = firstUnanswered >= 0
                    ? firstUnanswered
                    : Math.max(0, items.length - 1)
                this.setData({
                    loading: false,
                    empty: !!res.empty || items.length === 0,
                    sessionId: res.session_id || null,
                    sessionToken: res.session_token || '',
                    queueToken: res.queue_token || '',
                    items,
                    remainingDueCount: Number(res.remaining_due_count || 0),
                    currentIndex: resumeIndex,
                    finished: false
                }, () => {
                    if (!items.length) return
                    this.showItem(resumeIndex)
                    if (firstUnanswered < 0) this.settle()
                })
            })
            .catch((err) => {
                console.warn('load autonomous vocabulary review failed', err)
                this.setData({ loading: false, loadError: '复习队列加载失败，请重试' })
            })
    },

    showItem(index) {
        const item = this.data.items[index]
        if (!item) return
        const answered = !!item.first_attempt_id
        const isEnglishSpelling = isEnglishSpellingMode(item.mode)
        const isMeaningChoice = item.mode === 'audio_to_zh'
        const meaningOptions = isMeaningChoice
            ? buildMeaningChoiceOptions(item, [])
            : []
        this.setData({
            currentIndex: index,
            currentItem: item,
            inputValue: answered && item.first_answer ? item.first_answer : '',
            selectedOption: answered ? (item.revealed_answer_option_id || '') : '',
            meaningOptions,
            isMeaningChoice,
            isEnglishSpelling,
            currentDimensionLabel: DIMENSION_LABELS[item.dimension] || '词汇复习',
            showResult: answered,
            isCorrect: !!item.first_is_correct,
            correctAnswer: answered ? (item.revealed_answer || '') : '',
            submittedAnswer: answered ? (item.first_answer || '') : ''
        }, () => {
            if (String(item.mode || '').indexOf('audio_to_') === 0) this.playAudio()
        })
    },

    onInput(e) {
        if (this.data.showResult || this.data.isEnglishSpelling) return
        this.setData({ inputValue: (e && e.detail && e.detail.value) || '' })
    },

    onKeyboardKey(e) {
        if (!this.data.isEnglishSpelling || this.data.showResult) return
        const key = normalizeKeyboardKey(e && e.detail && e.detail.key)
        const allowedSeparators = (this.data.currentItem && this.data.currentItem.answer_separators) || []
        if (!/^[a-z0-9é]$/.test(key) && !allowedSeparators.includes(key)) return
        const limit = Number(this.data.currentItem && this.data.currentItem.answer_length) || 100
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
        const item = this.data.currentItem || {}
        if (item.mode === 'context_choice') return this.data.selectedOption
        if (this.data.isMeaningChoice) {
            return selectedOptionLabel(this.data.meaningOptions, this.data.selectedOption)
        }
        return String(this.data.inputValue || '').trim()
    },

    submitAnswer() {
        const item = this.data.currentItem
        if (!item) return
        if (this.data.showResult) {
            this.nextItem()
            return
        }
        if (this.data.submitting) return
        const answer = this.answerValue()
        if (!answer) {
            wx.showToast({
                title: item.mode === 'context_choice' || this.data.isMeaningChoice
                    ? '请选择答案'
                    : '请输入答案',
                icon: 'none'
            })
            return
        }
        this.setData({ submitting: true })
        const attemptId = `wx-vocabulary-review:${this.data.sessionId}:${item.review_item_id}`
        request(`/miniprogram/student/vocabulary-review/sessions/${this.data.sessionId}/answers`, {
            method: 'POST',
            data: {
                session_token: this.data.sessionToken,
                review_item_id: item.review_item_id,
                question_id: item.question_id,
                word_id: item.word_id,
                sense_id: item.sense_id,
                dimension: item.dimension,
                answer,
                attempt_id,
                input_mode: this.data.isEnglishSpelling ? 'strict' : 'native'
            }
        }).then((res) => {
            if (!res || !res.ok) throw new Error((res && res.error) || 'review_answer_failed')
            const nextItems = this.data.items.slice()
            nextItems[this.data.currentIndex] = Object.assign({}, item, {
                first_attempt_id: res.attempt_id,
                first_is_correct: !!res.is_correct,
                first_answer: res.student_answer || answer,
                revealed_answer: res.revealed_answer || '',
                revealed_answer_option_id: res.revealed_answer_option_id || '',
                answered: true
            })
            this.setData({
                items: nextItems,
                currentItem: nextItems[this.data.currentIndex],
                submitting: false,
                showResult: true,
                isCorrect: !!res.is_correct,
                correctAnswer: res.revealed_answer || '',
                submittedAnswer: res.student_answer || answer
            })
        }).catch((err) => {
            console.warn('submit autonomous vocabulary review failed', err)
            this.setData({ submitting: false })
            wx.showToast({ title: '提交失败，请重试', icon: 'none' })
        })
    },

    nextItem() {
        const next = this.data.currentIndex + 1
        if (next < this.data.items.length) {
            this.showItem(next)
            return
        }
        this.settle()
    },

    settle() {
        if (this.data.settling || !this.data.sessionId) return
        this.setData({ settling: true })
        request(`/miniprogram/student/vocabulary-review/sessions/${this.data.sessionId}/settle`, {
            method: 'POST',
            data: {
                session_token: this.data.sessionToken,
                queue_token: this.data.queueToken,
                duration_seconds: 0
            }
        }).then((res) => {
            if (!res || !res.ok) throw new Error((res && res.error) || 'review_settle_failed')
            this.setData({
                settling: false,
                finished: true,
                result: res,
                remainingDueCount: Number(res.remaining_due_count || 0)
            })
            // Return to the task requested by this page instance. A shared
            // active session may have been opened from another tab/task, so
            // the server session's original task is not a safe navigation
            // target for this client.
            if (this.returnTaskId) {
                this.returnTimer = setTimeout(() => {
                    this.returnTimer = null
                    wx.redirectTo({ url: `/pages/student/task/index?id=${this.returnTaskId}&reviewDone=1` })
                }, 500)
            }
        }).catch((err) => {
            console.warn('settle autonomous vocabulary review failed', err)
            this.setData({ settling: false })
            wx.showToast({ title: '结算失败，请重试', icon: 'none' })
        })
    },

    continueReview() {
        if (this.returnTaskId) return
        if (!this.data.sessionId) return this.fetchSession()
        request(`/miniprogram/student/vocabulary-review/sessions/${this.data.sessionId}/continue`, {
            method: 'POST',
            data: { session_token: this.data.sessionToken }
        }).then((res) => {
            if (!res || !res.ok) throw new Error((res && res.error) || 'review_continue_failed')
            if (!res.items || !res.items.length) {
                this.setData({ empty: true, finished: false, result: res })
                return
            }
            this.setData({
                empty: false,
                finished: false,
                sessionId: res.session_id,
                sessionToken: res.session_token,
                queueToken: res.queue_token || '',
                items: res.items,
                currentIndex: 0,
                remainingDueCount: Number(res.remaining_due_count || 0)
            }, () => this.showItem(0))
        }).catch(() => wx.showToast({ title: '继续复习失败，请重试', icon: 'none' }))
    },

    playAudio() {
        const item = this.data.currentItem || {}
        const prompt = item.question && item.question.prompt
        if (!this.audioPlayer || !prompt || !prompt.audio_tts_url) {
            wx.showToast({ title: '当前单词暂无发音', icon: 'none' })
            return
        }
        this.audioPlayer.play(prompt.audio_tts_url, app.globalData.baseUrl)
    },

    retry() {
        this.fetchSession()
    },

    exitPage() {
        if (this.returnTimer) {
            clearTimeout(this.returnTimer)
            this.returnTimer = null
        }
        if (this.returnTaskId) {
            wx.redirectTo({ url: `/pages/student/task/index?id=${this.returnTaskId}&reviewDone=1` })
            return
        }
        wx.switchTab({ url: '/pages/student/home/index' })
    }
})
