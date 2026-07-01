const app = getApp()
const { request } = require('../../../../utils/request.js')
const {
    isEnglishAnswerCorrect,
    normalizeEnglishAnswer
} = require('../../../../utils/dictation-answers.js')

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
    const inputChars = Array.from(String(inputValue || '').replace(/\s+/g, ''))
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
            slots.push({ type: 'fixed', char })
            return
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
        inputFocus: true,
        showResult: false,
        resultCorrect: false,
        displayWord: '',
        diffTop: [],
        isLoadingAudio: false,
        summaryItems: [],
        remainingCount: 0,
        skipSpellInReview: false,
        keyboardHeight: 0,
        appealSubmitted: false
    },

    onKeyboardHeightChange(e) {
        const height = (e && e.detail && e.detail.height) || 0
        if (height === this.data.keyboardHeight) return
        this.setData({ keyboardHeight: height })
    },

    onLoad(options) {
        this.completedMap = {}
        this.firstAttempts = {}
        this.summaryMap = {}
        this.audioFileCache = {}
        this.playTokenCounter = 0
        this.currentDownloadTask = null
        this.drillStartedAt = null
        this.taskResultSubmitted = false

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
                    rangeEnd: task.dictation_word_end
                })
                this.fetchWords(task.dictation_book_id)
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
            bookTitle: this.data.bookTitle || fallbackTitle || '强化拼写'
        })
        this.drillStartedAt = null
        this.taskResultSubmitted = false
        this.prewarmAudio(words)
    },

    refocusHiddenInput(delay = 50) {
        this.setData({ inputFocus: false })
        setTimeout(() => {
            if (this.data.stage !== 'drill' || this.data.showResult) return
            this.setData({ inputFocus: true })
        }, delay)
    },

    startDrill() {
        this.drillStartedAt = Date.now()
        this.setData({ stage: 'drill' })
        this.showNextWord(this.data.queue.slice())
    },

    showNextWord(queue) {
        const nextQueue = (queue || []).filter(item => !this.completedMap[item._originIndex])
        if (this.data.completedCount >= this.data.totalWords || !nextQueue.length) {
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
            displayWord: word.syllables || word.word,
            diffTop: [],
            inputFocus: false,
            appealSubmitted: false
        }, () => this.refocusHiddenInput())
        setTimeout(() => this.playCurrentWord(), 240)
    },

    onInput(e) {
        const value = (e && e.detail && e.detail.value) || ''
        this.setData({
            inputValue: value,
            spellSlots: buildSpellSlots(value, this.data.currentWord.word)
        })
    },

    focusInput() {
        this.refocusHiddenInput(30)
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
        const raw = String(this.data.inputValue || '').trim()
        if (!raw) {
            wx.showToast({ title: '请输入答案', icon: 'none' })
            return
        }

        const isCorrect = isEnglishAnswerCorrect(raw, word)
        const key = word._originIndex
        if (!this.firstAttempts[key]) {
            this.firstAttempts[key] = {
                correct: isCorrect,
                answer: isCorrect ? word.word : raw
            }
        }

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
                displayWord: word.syllables || word.word,
                inputFocus: false
            })
            this.submitMastery(word)
            this.playCurrentWord()
            this.dismissKeyboard()
            // Correct: let the green word / syllables / phonetic land, then advance.
            this.scheduleAutoAdvance()
            return
        }

        this.reinsertCurrentWord()
        this.setData({
            showResult: true,
            resultCorrect: false,
            displayWord: word.syllables || word.word,
            diffTop: buildDiff(raw, word.word),
            inputFocus: false
        })
        // Wrong: keep the comparison on a clean screen; student taps → when ready.
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
        this.clearAutoAdvance()
        const queue = this.data.queue.slice(1)
        this.showNextWord(queue)
    },

    submitMastery(word) {
        const key = word._originIndex
        if (this.summaryMap[key] && this.summaryMap[key].submitted) return
        const first = this.firstAttempts[key] || { correct: true, answer: word.word }
        const answer = first.correct ? word.word : first.answer
        this.summaryMap[key] = {
            submitted: true,
            word: word.word,
            reviewLabel: first.correct ? '1天后复习' : '1天后复习'
        }
        this.updateSummaryItems()

        request('/dictation/submit', {
            method: 'POST',
            data: {
                word_id: word.word_id || word.id,
                book_id: word.book_id || this.data.bookId,
                task_id: this.data.taskId,
                answer,
                mode: 'spelling_drill',
                enroll: true
            }
        }).then((res) => {
            if (res && res.ok) {
                this.summaryMap[key] = {
                    submitted: true,
                    word: word.word,
                    reviewLabel: formatNextReview(res.next_review_at)
                }
                this.updateSummaryItems()
            }
        }).catch((err) => {
            console.warn('submit spell mastery failed', err)
        })
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
    },

    buildTaskResult() {
        const words = this.data.words || []
        const total = words.length
        let correct = 0
        const wrongWords = []

        words.forEach((word, index) => {
            const first = this.firstAttempts[index]
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
        request(`/miniprogram/student/tasks/${this.data.taskId}/submit`, {
            method: 'POST',
            data: {
                accuracy: result.accuracy,
                wrong_words: result.wrongWords.join(', '),
                duration_seconds: result.durationSeconds
            }
        }).then((res) => {
            if (!res || !res.ok) {
                this.taskResultSubmitted = false
                wx.showToast({ title: '任务提交失败', icon: 'none' })
            }
        }).catch((err) => {
            this.taskResultSubmitted = false
            console.warn('submit spell task result failed', err)
            wx.showToast({ title: '任务提交失败', icon: 'none' })
        })
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
            this.fetchReviewWords()
            return
        }
        wx.redirectTo({ url: '/pages/student/dictation/review/index' })
    },

    exitPage() {
        wx.navigateBack()
    },

    playCurrentWord() {
        const word = this.data.currentWord && this.data.currentWord.word
        if (!word || !this.audioCtx) return
        const text = String(word).trim()
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
