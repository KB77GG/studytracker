const app = getApp()
const { request } = require('../../../../utils/request.js')

const REINSERT_GAP = 3

function normalizeEnglishAnswer(value) {
    return String(value || '')
        .trim()
        .toLowerCase()
        .replace(/[’‘]/g, "'")
        .replace(/\.{3,}|…+/g, ' ')
        .replace(/[，,。.!！？?；;：:]/g, ' ')
        .replace(/[()（）]/g, ' ')
        .replace(/\s+/g, ' ')
        .trim()
}

function englishVariants(value) {
    const normalized = normalizeEnglishAnswer(value)
        .replace(/^(?:n|v|vt|vi|adj|adv|prep|conj|pron|phr)\.\s*/i, '')
        .replace(/\s+/g, ' ')
        .trim()
    if (!normalized) return []
    const variants = new Set([normalized])
    normalized.split(/\s*(?:[\/≈；;]|,(?=\s*[a-z]))\s*/).forEach(part => {
        const item = normalizeEnglishAnswer(part)
        if (item) variants.add(item)
    })
    return Array.from(variants)
}

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
        inputFocus: true,
        showResult: false,
        resultCorrect: false,
        displayWord: '',
        diffTop: [],
        isLoadingAudio: false,
        summaryItems: [],
        remainingCount: 0,
        skipSpellInReview: false
    },

    onLoad(options) {
        this.completedMap = {}
        this.firstAttempts = {}
        this.summaryMap = {}
        this.audioFileCache = {}
        this.playTokenCounter = 0
        this.currentDownloadTask = null

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
        this.prewarmAudio(words)
    },

    startDrill() {
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
            showResult: false,
            resultCorrect: false,
            displayWord: word.syllables || word.word,
            diffTop: [],
            inputFocus: true
        })
        setTimeout(() => this.playCurrentWord(), 240)
    },

    onInput(e) {
        this.setData({ inputValue: e.detail.value })
    },

    focusInput() {
        this.setData({ inputFocus: false })
        setTimeout(() => this.setData({ inputFocus: true }), 30)
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

        const answerVariants = englishVariants(word.word)
        const isCorrect = answerVariants.some(item => item === normalizeEnglishAnswer(raw))
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
