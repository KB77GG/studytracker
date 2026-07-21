const app = getApp()
const { request } = require('../../../../utils/request.js')
const { isEnglishAnswerCorrect } = require('../../../../utils/dictation-answers.js')
const {
    INPUT_STRICT,
    answerInputLimit,
    chooseInputMode,
    defaultInputPolicy,
    inputModeStorageKey,
    isEnglishSpellingMode,
    normalizeKeyboardKey
} = require('../../../../utils/dictation-input-policy.js')

const MODE_HINT = {
    en_to_zh: '输入中文释义',
    zh_to_en: '输入英文表达',
    audio_to_en: '听音输入英文单词'
}

const LEVEL_LABEL = {
    1: '初次复习',
    2: '二次复习',
    3: '三次复习',
    4: '四次复习'
}

Page({
    data: {
        loading: true,
        loadError: '',
        words: [],
        currentIndex: 0,
        totalWords: 0,
        currentWord: null,
        currentMode: '',
        modeHint: '',
        levelLabel: '',
        inputValue: '',
        inputMode: 'native',
        inputPolicy: defaultInputPolicy('en_to_zh'),
        isEnglishSpelling: false,
        showResult: false,
        isCorrect: false,
        resultRevealed: false,
        correctAnswer: '',
        userAnswer: '',
        correctCount: 0,
        wrongCount: 0,
        finished: false,
        promotedCount: 0,
        appealSubmitted: false
    },

    onLoad() {
        this.audioCtx = wx.createInnerAudioContext()
        this.audioCtx.onError((err) => console.warn('audio error', err))
        this.fetchReviewQueue()
    },

    onUnload() {
        if (this.audioCtx) {
            try { this.audioCtx.stop() } catch (e) {}
            try { this.audioCtx.destroy() } catch (e) {}
            this.audioCtx = null
        }
    },

    fetchReviewQueue() {
        this.setData({ loading: true, loadError: '' })
        request('/dictation/review/today?limit=50')
            .then((res) => {
                if (!res || !res.ok) {
                    this.setData({
                        loading: false,
                        loadError: '加载复习队列失败，请稍后重试'
                    })
                    return
                }
                const words = res.items || []
                this.setData({
                    loading: false,
                    words: words,
                    totalWords: words.length,
                    currentIndex: 0
                })
                if (words.length > 0) {
                    this.showWord(0)
                }
            })
            .catch((err) => {
                console.warn('fetch review queue fail', err)
                this.setData({
                    loading: false,
                    loadError: '网络异常，请检查后重试'
                })
            })
    },

    showWord(index) {
        const word = this.data.words[index]
        if (!word) return
        const mode = word.mode || 'en_to_zh'
        this.setData({
            currentIndex: index,
            currentWord: word,
            currentMode: mode,
            modeHint: MODE_HINT[mode] || '输入答案',
            levelLabel: LEVEL_LABEL[word.review_level] || '',
            inputValue: '',
            inputMode: defaultInputPolicy(mode).defaultInputMode,
            inputPolicy: defaultInputPolicy(mode),
            isEnglishSpelling: isEnglishSpellingMode(mode),
            showResult: false,
            isCorrect: false,
            resultRevealed: false,
            correctAnswer: '',
            userAnswer: '',
            appealSubmitted: false
        }, () => this.loadInputPolicy(mode))
        if (mode === 'audio_to_en') {
            setTimeout(() => this.playAudio(), 250)
        }
    },

    loadInputPolicy(mode) {
        this.inputPolicyRequestToken = (this.inputPolicyRequestToken || 0) + 1
        const requestToken = this.inputPolicyRequestToken
        const fallback = defaultInputPolicy(mode)
        const storageKey = inputModeStorageKey({ mode })
        if (!fallback.isEnglishSpelling) return
        request('/dictation/input-policy', { data: { mode } })
            .then((res) => {
                if (requestToken !== this.inputPolicyRequestToken) return
                const raw = res && res.policy
                const policy = raw ? {
                    mode: raw.mode || mode,
                    isEnglishSpelling: !!raw.is_english_spelling,
                    defaultInputMode: raw.default_input_mode || INPUT_STRICT,
                    compatibleAllowed: !!raw.compatible_allowed,
                    grant: raw.grant || null
                } : fallback
                this.setData({
                    inputPolicy: policy,
                    inputMode: chooseInputMode(policy, wx.getStorageSync(storageKey))
                })
            })
            .catch(() => {
                if (requestToken !== this.inputPolicyRequestToken) return
                this.setData({ inputPolicy: fallback, inputMode: INPUT_STRICT })
            })
    },

    onInputModeChange(e) {
        const nextMode = e && e.detail && e.detail.mode
        if (!this.data.inputPolicy.compatibleAllowed || !nextMode || nextMode === this.data.inputMode) return
        const change = () => {
            wx.setStorageSync(inputModeStorageKey({ mode: this.data.currentMode }), nextMode)
            this.setData({ inputMode: nextMode, inputValue: '', resultRevealed: false })
        }
        if (this.data.inputValue) {
            wx.showModal({
                title: '切换输入方式',
                content: '切换后会清空当前答案，是否继续？',
                confirmText: '清空并切换',
                success: res => { if (res.confirm) change() }
            })
            return
        }
        change()
    },

    onKeyboardKey(e) {
        if (this.data.inputMode !== INPUT_STRICT || this.data.showResult) return
        const key = normalizeKeyboardKey(e && e.detail && e.detail.key)
        const answer = String(this.data.currentWord && this.data.currentWord.word || '')
        const limit = answerInputLimit(answer, this.data.currentWord.accepted_answers)
        if (!key || this.data.inputValue.length >= limit) return
        this.setData({ inputValue: `${this.data.inputValue}${key}` })
    },

    onKeyboardBackspace() {
        if (this.data.inputMode !== INPUT_STRICT || this.data.showResult) return
        this.setData({ inputValue: String(this.data.inputValue || '').slice(0, -1) })
    },

    retrySpelling() {
        if (!this.data.showResult || this.data.isCorrect || this.data.resultRevealed) return
        this.setData({ showResult: false, resultRevealed: false, inputValue: '', userAnswer: '' })
    },

    skipSpelling() {
        if (!this.data.showResult || this.data.isCorrect || this.data.resultRevealed) return
        this.setData({ resultRevealed: true })
    },

    playAudio() {
        const word = this.data.currentWord
        if (!word || !word.word) return
        if (!this.audioCtx) return
        const base = app.globalData.baseUrl
        this.audioCtx.src = `${base}/dictation/tts?word=${encodeURIComponent(word.word.trim())}`
        try {
            this.audioCtx.play()
        } catch (e) {
            console.warn('play fail', e)
        }
    },

    onInput(e) {
        if (this.data.inputMode === INPUT_STRICT) return
        this.setData({ inputValue: e.detail.value })
    },

    checkAnswer() {
        const word = this.data.currentWord
        if (!word) return
        const raw = this.data.inputValue
        if (!raw || !raw.trim()) {
            wx.showToast({ title: '请先输入答案', icon: 'none' })
            return
        }
        const mode = this.data.currentMode
        const userAns = raw.trim()
        const expected = mode === 'en_to_zh' ? (word.translation || '') : (word.word || '')
        // For zh_to_en and audio_to_en the canonical match is letter-case-insensitive.
        // For en_to_zh we accept a substring match against the translation, since
        // translations often carry parts of speech or multiple synonyms.
        let isCorrect
        if (mode === 'en_to_zh') {
            const ans = userAns.replace(/[，,；;。.\s]+/g, '')
            const exp = (expected || '').replace(/[，,；;。.\s]+/g, '')
            isCorrect = ans.length > 0 && exp.indexOf(ans) >= 0
        } else {
            isCorrect = isEnglishAnswerCorrect(userAns, word)
        }

        // Submit to server (which updates mastery row + records the attempt)
        const prevLevel = word.review_level
        request('/dictation/submit', {
            method: 'POST',
            data: {
                word_id: word.word_id,
                book_id: word.book_id,
                answer: userAns,
                mode: mode,
                input_mode: this.data.inputMode,
                input_grant_id: this.data.inputPolicy.grant && this.data.inputPolicy.grant.id
            }
        })
            .then((res) => {
                // Server may report a different correctness for en_to_zh than our
                // client-side fuzzy match; treat server as source of truth when it
                // disagrees and is more lenient than ours.
                let serverCorrect = isCorrect
                if (res && res.ok && typeof res.is_correct === 'boolean') {
                    serverCorrect = res.is_correct || isCorrect
                }
                const counts = {
                    correctCount: this.data.correctCount + (serverCorrect ? 1 : 0),
                    wrongCount: this.data.wrongCount + (serverCorrect ? 0 : 1)
                }
                // Best-effort promotion detection: a 2-correct streak at the same
                // session usually means at least one promotion happened.
                const promoted = serverCorrect && prevLevel > 0
                this.setData({
                    showResult: true,
                    isCorrect: serverCorrect,
                    resultRevealed: serverCorrect || mode === 'en_to_zh',
                    userAnswer: userAns,
                    correctAnswer: mode === 'en_to_zh' ? (word.translation || '') : (word.word || ''),
                    correctCount: counts.correctCount,
                    wrongCount: counts.wrongCount
                })
                if (mode === 'zh_to_en') this.playAudio()
                if (promoted && serverCorrect) {
                    // Subtle hint that progress was made — backend will do the
                    // actual promotion math; we just acknowledge here.
                }
            })
            .catch((err) => {
                console.warn('submit fail', err)
                wx.showToast({ title: '提交失败，请重试', icon: 'none' })
            })
    },

    nextWord() {
        const next = this.data.currentIndex + 1
        if (next >= this.data.totalWords) {
            this.setData({ finished: true })
            return
        }
        this.showWord(next)
    },

    replayAudio() {
        this.playAudio()
        wx.showToast({ title: '已重播', icon: 'none', duration: 800 })
    },

    startSpellReview() {
        wx.navigateTo({
            url: '/pages/student/dictation/spell/index?mode=review'
        })
    },

    reportExample(e) {
        const wordId = e.currentTarget.dataset.id
        if (!wordId) return
        request(`/dictation/example/report/${wordId}`, { method: 'POST' })
            .then((res) => {
                if (res && res.ok) {
                    wx.showToast({ title: '已反馈，助教会复审', icon: 'none' })
                } else {
                    wx.showToast({ title: '反馈失败', icon: 'none' })
                }
            })
            .catch(() => {
                wx.showToast({ title: '网络错误', icon: 'none' })
            })
    },

    submitAnswerAppeal() {
        if (this.data.appealSubmitted || this.data.isCorrect) return
        const word = this.data.currentWord || {}
        const answer = String(this.data.userAnswer || '').trim()
        if (!(word.word_id || word.id) || !answer) return
        wx.showModal({
            title: '申请人工复核',
            content: `你的答案“${answer}”将提交给老师审核。`,
            confirmText: '提交申诉',
            success: (modalRes) => {
                if (!modalRes.confirm) return
                request('/dictation/appeals', {
                    method: 'POST',
                    data: {
                        word_id: word.word_id || word.id,
                        answer,
                        mode: this.data.currentMode
                    }
                }).then((res) => {
                    if (res && res.ok) {
                        this.setData({ appealSubmitted: true })
                        wx.showToast({ title: '已提交人工审核', icon: 'none' })
                        return
                    }
                    wx.showToast({ title: '申诉提交失败', icon: 'none' })
                }).catch(() => wx.showToast({ title: '网络错误', icon: 'none' }))
            }
        })
    },

    backToHome() {
        wx.navigateBack({
            fail() {
                wx.switchTab({ url: '/pages/student/home/index' })
            }
        })
    },

    restartReview() {
        // Refetch — server may have new words due now (after just completing the
        // current batch the queue should be empty, but allow manual retry).
        this.setData({
            finished: false,
            correctCount: 0,
            wrongCount: 0
        })
        this.fetchReviewQueue()
    }
})
