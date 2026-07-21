const app = getApp()
const { request } = require('../../../../utils/request.js')
const {
    isEnglishAnswerCorrect,
    normalizeEnglishAnswer
} = require('../../../../utils/dictation-answers.js')
const {
    buildFirstAttemptId,
    buildRunStorageKey,
    createAttemptRunId,
    ensureAttemptPayload,
    getOrCreateRunId,
    isSuccessfulResponse,
    missingQueueItems,
    summarizeQueue,
    queueMode
} = require('../../../../utils/dictation-review.js')
const {
    INPUT_COMPATIBLE,
    INPUT_STRICT,
    answerInputLimit,
    chooseInputMode,
    defaultInputPolicy,
    inputModeStorageKey,
    isEnglishSpellingMode,
    normalizeKeyboardKey
} = require('../../../../utils/dictation-input-policy.js')

const REINSERT_GAP = 3
const FIXED_SPELL_CHARS = "-‐‑‒–—'’‘`´.,，。.!！？?；;：:()（）[]{}<>/\\|_+*=~@#$%^&\""

function buildDiff(inputValue, answerValue) {
    const input = normalizeEnglishAnswer(inputValue).replace(/\s+/g, '')
    const answer = normalizeEnglishAnswer(answerValue).replace(/\s+/g, '')
    const m = input.length
    const n = answer.length
    const dp = Array.from({ length: m + 1 }, () => Array(n + 1).fill(0))
    for (let i = m - 1; i >= 0; i--) {
        for (let j = n - 1; j >= 0; j--) {
            dp[i][j] = input[i] === answer[j]
                ? dp[i + 1][j + 1] + 1
                : Math.max(dp[i + 1][j], dp[i][j + 1])
        }
    }

    const tokens = []
    let i = 0
    let j = 0
    while (i < m || j < n) {
        if (i < m && j < n && input[i] === answer[j]) {
            tokens.push({ char: input[i], status: 'ok' })
            i += 1
            j += 1
        } else if (i < m && (j >= n || dp[i + 1][j] >= dp[i][j + 1])) {
            tokens.push({ char: input[i], status: 'bad' })
            i += 1
        } else {
            tokens.push({ char: '', status: 'miss' })
            j += 1
        }
    }
    return tokens.length ? tokens : [{ char: '', status: 'miss' }]
}

function isSpellSlotChar(char) {
    return !(/\s/.test(char) || FIXED_SPELL_CHARS.indexOf(char) >= 0)
}

function buildSpellSlots(inputValue, answerWord) {
    const inputChars = Array.from(String(inputValue || ''))
    const answerChars = Array.from(String(answerWord || ''))
    const slots = []
    let inputIndex = 0
    let activeAssigned = false

    answerChars.forEach((char) => {
        if (/\s/.test(char)) {
            slots.push({ type: 'space' })
            return
        }

        if (!isSpellSlotChar(char)) {
            const typedSeparator = inputChars[inputIndex] || ''
            const normalizedTyped = typedSeparator === '’' || typedSeparator === '‘'
                ? "'"
                : typedSeparator
            const normalizedExpected = char === '’' || char === '‘' ? "'" : char
            if (normalizedTyped === normalizedExpected) inputIndex += 1
            slots.push({ type: 'fixed', char })
            return
        }

        while (inputIndex < inputChars.length && !isSpellSlotChar(inputChars[inputIndex])) {
            inputIndex += 1
        }
        const inputChar = inputChars[inputIndex] || ''
        inputIndex += inputChar ? 1 : 0
        const slot = {
            type: 'slot',
            char: inputChar,
            filled: !!inputChar
        }
        if (!slot.filled && !activeAssigned) {
            slot.active = true
            activeAssigned = true
        }
        slots.push(slot)
    })

    while (inputIndex < inputChars.length) {
        slots.push({
            type: 'slot',
            char: inputChars[inputIndex],
            filled: true,
            overflow: true
        })
        inputIndex += 1
    }

    return slots
}

function cleanPhonetic(value) {
    const text = String(value || '').trim()
    if (!text) return ''
    if (text[0] === '/' || text[0] === '[') return text
    return `/${text}/`
}

function formatNextReview(iso) {
    if (!iso) return '1天后复习'
    const then = new Date(String(iso).replace(' ', 'T')).getTime()
    if (!then || Number.isNaN(then)) return '1天后复习'
    const diff = Math.max(0, then - Date.now())
    const hour = 60 * 60 * 1000
    const day = 24 * hour
    if (diff < day) {
        return `${Math.max(1, Math.ceil(diff / hour))}小时后复习`
    }
    return `${Math.max(1, Math.ceil(diff / day))}天后复习`
}

function buildProgressDots(total, completed) {
    const dots = []
    for (let i = 0; i < total; i++) {
        dots.push({ done: i < completed })
    }
    return dots
}

Page({
    data: {
        stage: 'loading',
        sourceMode: 'book',
        bookId: null,
        taskId: null,
        bookTitle: '强化拼写',
        words: [],
        queue: [],
        currentWord: {},
        totalWords: 0,
        completedCount: 0,
        progressDots: [],
        inputValue: '',
        spellSlots: [],
        showResult: false,
        resultCorrect: false,
        resultRevealed: false,
        displayWord: '',
        diffTop: [],
        isLoadingAudio: false,
        summaryItems: [],
        remainingCount: 0,
        serverSummary: null,
        isCheckingFirstAnswer: false,
        isAdvancingWord: false,
        skipSpellInReview: false,
        inputMode: INPUT_STRICT,
        inputPolicy: defaultInputPolicy('spelling_drill'),
        isEnglishSpelling: true,
        dictationOrder: 'sequence',
        queueToken: '',
        assignedCount: 0,
        reviewCount: 0,
        appealSubmitted: false
    },

    onLoad(options) {
        options = options || {}
        this.completedMap = {}
        this.firstAttempts = {}
        this.firstAttemptPayloads = {}
        this.firstAttemptConfirmed = {}
        this.firstAttemptResults = {}
        this.summaryMap = {}
        this.audioFileCache = {}
        this.playTokenCounter = 0
        this.currentDownloadTask = null
        this.drillStartedAt = null
        this.taskResultSubmitted = false
        this.firstAttemptPromises = {}
        this.firstAttemptSent = {}
        this.firstAnswerInFlightKey = null
        this.wordAdvanceLocked = false
        this.attemptRunStorageKey = options.taskId
            ? null
            : buildRunStorageKey(options.mode === 'review' ? 'review' : `book-${options.id || 'unknown'}`)
        this.attemptSessionId = options.taskId ? '' : this.getOrCreateAttemptRunId()

        this.audioCtx = wx.createInnerAudioContext()
        this.audioCtx.obeyMuteSwitch = false
        this.audioCtx.onPlay(() => this.setData({ isLoadingAudio: false }))
        this.audioCtx.onStop(() => this.setData({ isLoadingAudio: false }))
        this.audioCtx.onEnded(() => this.setData({ isLoadingAudio: false }))
        this.audioCtx.onError(() => this.setData({ isLoadingAudio: false }))

        const skip = !!wx.getStorageSync('dictation_skip_spell_review')
        this.setData({ skipSpellInReview: skip })

        if (options.mode === 'review') {
            this.setData({ sourceMode: 'review', bookTitle: '复习强化拼写' })
            if (skip) {
                wx.redirectTo({ url: '/pages/student/dictation/review/index' })
                return
            }
            this.fetchReviewWords()
        } else if (options.taskId) {
            this.setData({ sourceMode: 'task', taskId: options.taskId })
            this.fetchTask(options.taskId)
        } else if (options.id) {
            this.setData({
                sourceMode: 'book',
                bookId: Number(options.id),
                bookTitle: options.title ? decodeURIComponent(options.title) : '强化拼写'
            })
            this.fetchWords(options.id)
        } else {
            wx.showToast({ title: '缺少词库参数', icon: 'none' })
            this.setData({ stage: 'summary' })
        }
    },

    onUnload() {
        this.clearAutoAdvance()
        if (this.currentDownloadTask && this.currentDownloadTask.abort) {
            try { this.currentDownloadTask.abort() } catch (e) {}
        }
        if (this.audioCtx) {
            try { this.audioCtx.stop() } catch (e) {}
            try { this.audioCtx.destroy() } catch (e) {}
            this.audioCtx = null
        }
    },

    getOrCreateAttemptRunId() {
        const key = this.attemptRunStorageKey
        return getOrCreateRunId(
            {
                get: () => wx.getStorageSync(key),
                set: value => wx.setStorageSync(key, value)
            },
            key,
            () => createAttemptRunId('spelling')
        )
    },

    clearAttemptRun() {
        if (!this.data.taskId && this.attemptRunStorageKey) {
            try { wx.removeStorageSync(this.attemptRunStorageKey) } catch (e) {}
        }
    },

    buildServerSummary(response) {
        const total = Number(response && response.total_count) || 0
        const correct = Number(response && response.correct_count) || 0
        return {
            accuracy: response && response.accuracy != null ? response.accuracy : 0,
            correct,
            total,
            wrongCount: Math.max(0, total - correct)
        }
    },

    fetchTask(taskId) {
        wx.showLoading({ title: '加载任务...' })
        request(`/miniprogram/student/tasks/${taskId}`)
            .then((res) => {
                if (!res || !res.ok || !res.task || !res.task.dictation_book_id) {
                    wx.hideLoading()
                    wx.showToast({ title: '任务配置错误', icon: 'none' })
                    return
                }
                const task = res.task
                this.setData({
                    bookTitle: task.task_name || '强化拼写',
                    bookId: task.dictation_book_id,
                    rangeStart: task.dictation_word_start,
                    rangeEnd: task.dictation_word_end,
                    dictationOrder: task.dictation_order || 'sequence'
                })
                this.fetchTaskQueue(taskId)
            })
            .catch(() => {
                wx.hideLoading()
                wx.showToast({ title: '网络错误', icon: 'none' })
            })
    },

    fetchTaskQueue(taskId) {
        request(`/miniprogram/student/tasks/${taskId}/dictation-queue`)
            .then((res) => {
                wx.hideLoading()
                if (!res || !res.ok) {
                    wx.showToast({ title: '加载合并队列失败', icon: 'none' })
                    return
                }
                const rawWords = res.words || []
                const words = rawWords.map(item => Object.assign({}, item, {
                    dictationMode: queueMode(item, res.task_mode)
                }))
                const counts = summarizeQueue(words)
                this.setData({
                    dictationOrder: res.dictation_order || 'sequence',
                    queueToken: res.queue_token || '',
                    assignedCount: res.assigned_count != null ? res.assigned_count : counts.assignedCount,
                    reviewCount: res.auto_review_count != null ? res.auto_review_count : counts.reviewCount
                })
                this.prepareWords(words, this.data.bookTitle)
            })
            .catch(() => {
                wx.hideLoading()
                wx.showToast({ title: '网络错误', icon: 'none' })
            })
    },

    fetchWords(bookId) {
        wx.showLoading({ title: '加载单词...' })
        request(`/dictation/books/${bookId}`)
            .then((res) => {
                wx.hideLoading()
                if (!res || !res.ok) {
                    wx.showToast({ title: '加载失败', icon: 'none' })
                    return
                }
                let words = res.words || []
                if (this.data.rangeStart || this.data.rangeEnd) {
                    const start = Math.max(0, (this.data.rangeStart || 1) - 1)
                    const end = this.data.rangeEnd || words.length
                    words = words.slice(start, end)
                }
                this.prepareWords(words, res.book && res.book.title)
            })
            .catch(() => {
                wx.hideLoading()
                wx.showToast({ title: '网络错误', icon: 'none' })
            })
    },

    fetchReviewWords() {
        wx.showLoading({ title: '加载复习...' })
        request('/dictation/review/today?limit=50')
            .then((res) => {
                wx.hideLoading()
                if (!res || !res.ok) {
                    wx.showToast({ title: '复习队列加载失败', icon: 'none' })
                    return
                }
                this.prepareWords(res.items || [], '复习强化拼写')
            })
            .catch(() => {
                wx.hideLoading()
                wx.showToast({ title: '网络错误', icon: 'none' })
            })
    },

    prepareWords(rawWords, fallbackTitle) {
        const words = (rawWords || []).map((item, index) => {
            const id = item.word_id || item.id
            return Object.assign({}, item, {
                id,
                word_id: id,
                _originIndex: index,
                _key: `${id || item.word || index}_${index}`,
                phonetic: cleanPhonetic(item.phonetic)
            })
        }).filter(item => item.word)

        if (!words.length) {
            wx.showModal({
                title: '没有可拼写的单词',
                content: '当前词库或复习队列为空。',
                showCancel: false,
                success: () => wx.navigateBack()
            })
            return
        }

        this.setData({
            stage: 'ready',
            words,
            queue: words.slice(),
            totalWords: words.length,
            completedCount: 0,
            progressDots: buildProgressDots(words.length, 0),
            bookTitle: this.data.bookTitle || fallbackTitle || '强化拼写',
            serverSummary: null
        })
        this.drillStartedAt = null
        this.taskResultSubmitted = false
        this.loadInputPolicy()
        this.prewarmAudio(words)
    },

    loadInputPolicy() {
        const mode = 'spelling_drill'
        const fallback = defaultInputPolicy(mode)
        const storageKey = inputModeStorageKey({ taskId: this.data.taskId, bookId: this.data.bookId, mode })
        this.setData({
            inputMode: INPUT_STRICT,
            inputPolicy: fallback,
            isEnglishSpelling: true
        })
        request('/dictation/input-policy', {
            data: {
                mode,
                task_id: this.data.taskId || undefined
            }
        }).then((res) => {
            const raw = res && res.policy
            const policy = raw ? {
                mode: raw.mode || mode,
                isEnglishSpelling: !!raw.is_english_spelling,
                defaultInputMode: raw.default_input_mode || INPUT_STRICT,
                compatibleAllowed: !!raw.compatible_allowed,
                grant: raw.grant || null
            } : fallback
            const stored = wx.getStorageSync(storageKey)
            this.setData({
                inputPolicy: policy,
                inputMode: chooseInputMode(policy, stored)
            })
        }).catch(() => {
            // Network failure is intentionally strict, never compatible.
            this.setData({ inputPolicy: fallback, inputMode: INPUT_STRICT })
        })
    },

    onInputModeChange(e) {
        const nextMode = e && e.detail && e.detail.mode
        if (!this.data.inputPolicy.compatibleAllowed || !nextMode) return
        if (nextMode === this.data.inputMode) return
        if (this.data.inputValue) {
            wx.showModal({
                title: '切换输入方式',
                content: '切换后会清空当前拼写，是否继续？',
                confirmText: '清空并切换',
                success: (res) => {
                    if (!res.confirm) return
                    this.setInputMode(nextMode)
                }
            })
            return
        }
        this.setInputMode(nextMode)
    },

    setInputMode(mode) {
        if (![INPUT_STRICT, INPUT_COMPATIBLE].includes(mode)) return
        const storageKey = inputModeStorageKey({ taskId: this.data.taskId, bookId: this.data.bookId, mode: 'spelling_drill' })
        wx.setStorageSync(storageKey, mode)
        this.setData({
            inputMode: mode,
            inputValue: '',
            spellSlots: buildSpellSlots('', this.data.currentWord.word),
            resultRevealed: false
        })
    },

    startDrill() {
        this.drillStartedAt = Date.now()
        this.setData({ stage: 'drill' })
        this.showNextWord(this.data.queue.slice())
    },

    showNextWord(queue, onReady) {
        const nextQueue = (queue || []).filter(item => !this.completedMap[item._originIndex])
        if (this.data.completedCount >= this.data.totalWords || !nextQueue.length) {
            if (onReady) onReady()
            this.finishDrill()
            return
        }
        const word = nextQueue[0]
        this.setData({
            queue: nextQueue,
            currentWord: word,
            inputValue: '',
            spellSlots: buildSpellSlots('', word.word),
            showResult: false,
            resultCorrect: false,
            resultRevealed: false,
            displayWord: word.syllables || word.word,
            diffTop: [],
            appealSubmitted: false
        }, () => {
            if (onReady) onReady()
            setTimeout(() => this.playCurrentWord(true), 240)
        })
    },

    onInput(e) {
        if (this.data.inputMode !== INPUT_COMPATIBLE) return
        const value = (e && e.detail && e.detail.value) || ''
        this.setData({
            inputValue: value,
            spellSlots: buildSpellSlots(value, this.data.currentWord.word)
        })
    },

    onKeyboardKey(e) {
        if (this.data.inputMode !== INPUT_STRICT || this.data.showResult) return
        const key = normalizeKeyboardKey(e && e.detail && e.detail.key)
        const limit = answerInputLimit(
            this.data.currentWord.word,
            this.data.currentWord.accepted_answers
        )
        if (!key || this.data.inputValue.length >= limit) return
        this.setData({
            inputValue: `${this.data.inputValue}${key}`,
            spellSlots: buildSpellSlots(`${this.data.inputValue}${key}`, this.data.currentWord.word)
        })
    },

    onKeyboardBackspace() {
        if (this.data.inputMode !== INPUT_STRICT || this.data.showResult) return
        const value = String(this.data.inputValue || '').slice(0, -1)
        this.setData({ inputValue: value, spellSlots: buildSpellSlots(value, this.data.currentWord.word) })
    },

    submitOrNext() {
        if (this.data.showResult) {
            this.nextAfterResult()
        } else {
            this.checkAnswer()
        }
    },

    checkAnswer() {
        const word = this.data.currentWord
        if (!word || !word.word) return
        if (this.data.isCheckingFirstAnswer) return
        const raw = String(this.data.inputValue || '').trim()
        if (!raw) {
            wx.showToast({ title: '请输入答案', icon: 'none' })
            return
        }

        const isCorrect = isEnglishAnswerCorrect(raw, word)
        const key = word._originIndex
        if (!this.firstAttempts[key]) {
            if (this.firstAnswerInFlightKey === key) return
            this.firstAnswerInFlightKey = key
            this.setData({ isCheckingFirstAnswer: true })
            this.submitFirstAttempt(word, raw)
                .then((res) => {
                    if (!isSuccessfulResponse(res)) throw new Error('first_attempt_not_acknowledged')
                    const serverCorrect = !!res.is_correct
                    this.firstAttempts[key] = {
                        correct: serverCorrect,
                        answer: raw
                    }
                    this.firstAnswerInFlightKey = null
                    this.setData({ isCheckingFirstAnswer: false }, () => {
                        this.applyAnswerResult(word, raw, serverCorrect, true)
                    })
                })
                .catch((err) => {
                    this.firstAnswerInFlightKey = null
                    this.setData({ isCheckingFirstAnswer: false, inputValue: raw })
                    wx.showToast({ title: '首答同步失败，请重试', icon: 'none' })
                    console.warn('submit spell first attempt failed', err)
                })
            return
        }

        this.applyAnswerResult(word, raw, isCorrect, false)
    },

    applyAnswerResult(word, raw, isCorrect, isFirstAttempt) {
        const key = word._originIndex
        if (isCorrect) {
            const nextCompleted = this.completedMap[key]
                ? this.data.completedCount
                : this.data.completedCount + 1
            this.completedMap[key] = true
            this.setData({
                completedCount: nextCompleted,
                progressDots: buildProgressDots(this.data.totalWords, nextCompleted),
                showResult: true,
                resultCorrect: true,
                resultRevealed: false,
                displayWord: word.syllables || word.word,
            })
            if (!isFirstAttempt) this.submitMastery(word)
            this.playCurrentWord(true)
            this.dismissKeyboard()
            // Correct: let the green word / syllables / phonetic land, then advance.
            this.scheduleAutoAdvance()
            return
        }

        this.reinsertCurrentWord()
        this.setData({
            showResult: true,
            resultCorrect: false,
            resultRevealed: false,
            displayWord: word.syllables || word.word,
            diffTop: buildDiff(raw, word.word),
        })
        // Wrong: keep the comparison on a clean screen; student taps → when ready.
        this.dismissKeyboard()
    },

    retrySpell() {
        if (!this.data.showResult || this.data.resultCorrect || this.data.resultRevealed) return
        this.clearAutoAdvance()
        this.setData({
            showResult: false,
            resultCorrect: false,
            resultRevealed: false,
            inputValue: '',
            spellSlots: buildSpellSlots('', this.data.currentWord.word),
            diffTop: [],
            appealSubmitted: false
        })
    },

    skipSpell() {
        if (!this.data.showResult || this.data.resultCorrect || this.data.resultRevealed) return
        this.setData({
            resultRevealed: true,
            displayWord: this.data.currentWord.syllables || this.data.currentWord.word
        })
        this.dismissKeyboard()
    },

    submitAnswerAppeal() {
        if (this.data.appealSubmitted || this.data.resultCorrect) return
        const word = this.data.currentWord || {}
        const answer = String(this.data.inputValue || '').trim()
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
                        task_id: this.data.taskId,
                        answer,
                        mode: 'spelling_drill'
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

    dismissKeyboard() {
        try { wx.hideKeyboard({}) } catch (e) {}
    },

    scheduleAutoAdvance() {
        this.clearAutoAdvance()
        this.autoAdvanceTimer = setTimeout(() => {
            this.autoAdvanceTimer = null
            if (this.data.stage === 'drill' && this.data.showResult && this.data.resultCorrect) {
                this.nextAfterResult()
            }
        }, 1100)
    },

    clearAutoAdvance() {
        if (this.autoAdvanceTimer) {
            clearTimeout(this.autoAdvanceTimer)
            this.autoAdvanceTimer = null
        }
    },

    reinsertCurrentWord() {
        const queue = this.data.queue.slice()
        const current = queue[0]
        const tail = queue.slice(1)
        const insertAt = Math.min(REINSERT_GAP, tail.length)
        tail.splice(insertAt, 0, Object.assign({}, current))
        this.setData({ queue: [current].concat(tail) })
    },

    nextAfterResult() {
        if (this.wordAdvanceLocked || this.data.isAdvancingWord || !this.data.showResult) return
        this.wordAdvanceLocked = true
        this.setData({ isAdvancingWord: true })
        this.clearAutoAdvance()
        const queue = this.data.queue.slice(1)
        this.showNextWord(queue, () => this.releaseWordAdvance())
    },

    releaseWordAdvance() {
        this.wordAdvanceLocked = false
        this.setData({ isAdvancingWord: false })
    },

    submitMastery(word) {
        const key = word._originIndex
        if (this.summaryMap[key] && this.summaryMap[key].submitted) return
        this.summaryMap[key] = {
            submitted: true,
            word: word.word,
            reviewLabel: '已同步首答'
        }
        this.updateSummaryItems()
    },

    submitFirstAttempt(word, answer) {
        const wordId = word && (word.word_id || word.id)
        if (!wordId) return Promise.resolve(null)
        const key = String(wordId)
        ensureAttemptPayload(this.firstAttemptPayloads, key, {
            word_id: wordId,
            book_id: word.book_id || this.data.bookId,
            task_id: this.data.taskId || null,
            answer,
            mode: 'spelling_drill',
            input_mode: this.data.inputMode,
            input_grant_id: this.data.inputPolicy.grant && this.data.inputPolicy.grant.id,
            attempt_id: buildFirstAttemptId(this.data.taskId, this.data.bookId, wordId, this.attemptSessionId),
            is_first_attempt: true,
            strict_queue: !!this.data.taskId,
            enroll: true
        })
        return this.sendFirstAttempt(key, word)
    },

    sendFirstAttempt(key, word) {
        if (this.firstAttemptConfirmed[key]) {
            return Promise.resolve(this.firstAttemptResults[key] || {
                ok: true,
                is_correct: !!(this.firstAttempts[key] && this.firstAttempts[key].correct)
            })
        }
        if (this.firstAttemptPromises[key]) return this.firstAttemptPromises[key]
        const payload = this.firstAttemptPayloads[key]
        if (!payload) return Promise.reject(new Error('missing_first_attempt_payload'))
        this.firstAttemptSent[key] = true
        const promise = request('/dictation/submit', {
            method: 'POST',
            data: payload
        }).then((res) => {
            if (!isSuccessfulResponse(res)) {
                const error = new Error((res && res.error) || 'first_attempt_rejected')
                error.response = res
                throw error
            }
            this.firstAttemptConfirmed[key] = true
            this.firstAttemptResults[key] = res
            this.summaryMap[word._originIndex] = {
                submitted: true,
                word: word.word,
                reviewLabel: res.next_review_at ? formatNextReview(res.next_review_at) : '无需自动复习'
            }
            this.updateSummaryItems()
            delete this.firstAttemptSent[key]
            delete this.firstAttemptPromises[key]
            return res
        }).catch((err) => {
            delete this.firstAttemptSent[key]
            delete this.firstAttemptPromises[key]
            throw err
        })
        this.firstAttemptPromises[key] = promise
        return promise
    },

    retryPendingFirstAttempts() {
        const keys = Object.keys(this.firstAttemptPayloads || {})
            .filter(key => !this.firstAttemptConfirmed[key])
        return Promise.all(keys.map(key => {
            const word = (this.data.words || []).find(item => String(item.word_id || item.id) === String(key)) || {}
            return this.sendFirstAttempt(key, word)
        }))
    },

    updateSummaryItems() {
        const words = this.data.words || []
        const items = words.map((word, index) => {
            const item = this.summaryMap[index] || {}
            return {
                key: word._key || index,
                word: word.word,
                reviewLabel: item.reviewLabel || '1天后复习'
            }
        })
        this.setData({ summaryItems: items })
    },

    finishDrill() {
        this.updateSummaryItems()
        this.setData({ stage: 'summary' })
        this.fetchReviewSummary()
        this.submitTaskResultIfNeeded()
        if (!this.data.taskId) this.clearAttemptRun()
    },

    buildTaskResult() {
        const words = this.data.words || []
        const total = words.length
        let correct = 0
        const wrongWords = []

        words.forEach((word, index) => {
            const first = this.firstAttempts[String(word.word_id || word.id)]
                || this.firstAttempts[index]
            if (first && first.correct) {
                correct += 1
            } else {
                wrongWords.push(word.word)
            }
        })

        return {
            accuracy: total > 0 ? ((correct / total) * 100).toFixed(1) : 0,
            wrongWords,
            durationSeconds: this.computeDurationSeconds()
        }
    },

    computeDurationSeconds() {
        if (!this.drillStartedAt) return 0
        return Math.max(1, Math.floor((Date.now() - this.drillStartedAt) / 1000))
    },

    submitTaskResultIfNeeded() {
        if (!this.data.taskId || this.taskResultSubmitted) return
        this.taskResultSubmitted = true

        const result = this.buildTaskResult()
        this.retryPendingFirstAttempts().then(() => request(`/miniprogram/student/tasks/${this.data.taskId}/submit`, {
            method: 'POST',
            data: {
                strict_queue: true,
                queue_token: this.data.queueToken,
                accuracy: result.accuracy,
                wrong_words: result.wrongWords.join(', '),
                duration_seconds: result.durationSeconds
            }
        })).then((res) => {
            if (!isSuccessfulResponse(res)) {
                this.taskResultSubmitted = false
                if (!this.recoverMissingTaskWords(res)) {
                    wx.showToast({ title: '任务提交失败', icon: 'none' })
                }
                return
            }
            this.setData({ serverSummary: this.buildServerSummary(res) })
        }).catch((err) => {
            this.taskResultSubmitted = false
            console.warn('submit spell task result failed', err)
            wx.showToast({ title: '任务提交失败', icon: 'none' })
        })
    },

    recoverMissingTaskWords(response) {
        const missingWords = missingQueueItems(response, this.data.words)
        if (!missingWords.length) return false
        missingWords.forEach(word => {
            delete this.completedMap[word._originIndex]
        })
        const completedCount = Object.keys(this.completedMap)
            .filter(key => this.completedMap[key]).length
        this.clearAutoAdvance()
        this.setData({
            stage: 'drill',
            completedCount,
            progressDots: buildProgressDots(this.data.totalWords, completedCount),
            serverSummary: null
        }, () => {
            this.showNextWord(missingWords.slice())
            wx.showModal({
                title: '补答后即可提交',
                content: `检测到 ${missingWords.length} 个单词没有同步，已为你自动定位。`,
                showCancel: false
            })
        })
        return true
    },

    fetchReviewSummary() {
        request('/dictation/review/summary')
            .then((res) => {
                if (res && res.ok) {
                    this.setData({ remainingCount: res.due_count || 0 })
                }
            })
            .catch(() => {})
    },

    goSummary() {
        this.updateSummaryItems()
        this.fetchReviewSummary()
        this.setData({ stage: 'summary' })
    },

    onSkipChange(e) {
        const checked = !!e.detail.value
        wx.setStorageSync('dictation_skip_spell_review', checked)
        this.setData({ skipSpellInReview: checked })
    },

    continueReview() {
        if (this.data.sourceMode === 'review') {
            this.beginNewAttemptRun('review')
            this.fetchReviewWords()
            return
        }
        wx.redirectTo({ url: '/pages/student/dictation/review/index' })
    },

    exitPage() {
        wx.navigateBack()
    },

    replayCurrentWord() {
        this.playCurrentWord(true)
        wx.showToast({ title: '已重播', icon: 'none', duration: 800 })
    },

    playCurrentWord(silent = false) {
        const word = this.data.currentWord && this.data.currentWord.word
        if (!word || !this.audioCtx) return
        const text = String(word).trim()
        if (!silent) {
            wx.showToast({ title: '已重播', icon: 'none', duration: 800 })
        }
        const cacheKey = text.toLowerCase()
        this.playTokenCounter += 1
        const token = this.playTokenCounter
        const cached = this.audioFileCache[cacheKey]
        this.setData({ isLoadingAudio: true })
        if (cached && cached.tempFilePath) {
            this.playPrepared(cached.tempFilePath, token)
            return
        }
        const url = `${app.globalData.baseUrl}/dictation/tts?word=${encodeURIComponent(text)}`
        this.downloadAndPlay(url, text, token, cacheKey, false)
    },

    playPrepared(path, token) {
        if (!this.audioCtx || token !== this.playTokenCounter) return
        this.audioCtx.src = path
        try {
            this.audioCtx.play()
        } catch (e) {
            this.setData({ isLoadingAudio: false })
        }
    },

    downloadAndPlay(url, word, token, cacheKey, isFallback) {
        if (this.currentDownloadTask && this.currentDownloadTask.abort) {
            try { this.currentDownloadTask.abort() } catch (e) {}
        }
        const task = wx.downloadFile({
            url,
            success: (res) => {
                if (token !== this.playTokenCounter) return
                if (res.statusCode === 200 && res.tempFilePath) {
                    this.audioFileCache[cacheKey] = { tempFilePath: res.tempFilePath }
                    this.playPrepared(res.tempFilePath, token)
                } else if (!isFallback) {
                    this.downloadAndPlay(
                        `https://dict.youdao.com/dictvoice?audio=${encodeURIComponent(word)}&type=2`,
                        word,
                        token,
                        cacheKey,
                        true
                    )
                } else {
                    this.setData({ isLoadingAudio: false })
                }
            },
            fail: () => {
                if (token !== this.playTokenCounter) return
                if (!isFallback) {
                    this.downloadAndPlay(
                        `https://dict.youdao.com/dictvoice?audio=${encodeURIComponent(word)}&type=2`,
                        word,
                        token,
                        cacheKey,
                        true
                    )
                } else {
                    this.setData({ isLoadingAudio: false })
                }
            }
        })
        this.currentDownloadTask = task
    },

    prewarmAudio(words) {
        const seen = {}
        const targets = []
        ;(words || []).forEach(item => {
            const word = String(item.word || '').trim()
            const key = word.toLowerCase()
            if (!word || seen[key]) return
            seen[key] = true
            targets.push(word)
        })
        if (!targets.length) return
        request('/dictation/tts/prewarm', {
            method: 'POST',
            data: { words: targets.slice(0, 60) }
        }).catch(() => {})
    }
})
