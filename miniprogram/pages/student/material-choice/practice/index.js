const { request } = require('../../../../utils/request.js')
const app = getApp()

function getReadingNotebookCacheKey() {
    const token = app.globalData.token || wx.getStorageSync('token') || ''
    const suffix = token ? String(token).slice(-24) : 'guest'
    return `reading_vocab_notebook:${suffix}`
}

function readReadingNotebookCache() {
    const scoped = wx.getStorageSync(getReadingNotebookCacheKey())
    if (Array.isArray(scoped)) return scoped
    const legacy = wx.getStorageSync('reading_vocab_notebook')
    return Array.isArray(legacy) ? legacy : []
}

function writeReadingNotebookCache(list) {
    const next = Array.isArray(list) ? list : []
    wx.setStorageSync(getReadingNotebookCacheKey(), next)
    wx.setStorageSync('reading_vocab_notebook', next)
}

// View modes:
//  'practice'   — first-time answering, immediate per-question feedback
//  'review'     — task already done, show correct answer + user's pick for each question
//  'redo_wrong' — retry only previously-wrong questions with immediate feedback
//  'redo_all'   — retry all questions from scratch with immediate feedback
Page({
    data: {
        taskId: null,
        task: {},
        questions: [],
        currentIndex: 0,
        currentQuestion: null,
        selectedAnswers: {},       // qid -> answer key (local picks this session)
        selectedAnswer: '',
        answerRecords: {},         // qid -> { answer_key, is_correct } (prior submission)
        answeredCount: 0,
        note: '',
        loading: true,
        submitting: false,
        startedAt: 0,
        mode: 'practice',
        isDone: false,
        wrongCount: 0,
        correctCount: 0,
        uncertainFlags: {},       // qid -> boolean
        currentUncertain: false,
        sessionResults: {},       // qid -> { userKey, correctKey, correctText, hint, isCorrect }
        currentFeedback: null,
        // Per-question computed data for review UI
        reviewFlags: {}            // qid -> { userKey, correctKey, isCorrect, isUncertain }
    },

    onLoad(options) {
        const taskId = parseInt(options.taskId, 10)
        const initialMode = (options.mode || '').toLowerCase()
        this.setData({ taskId, startedAt: Date.now(), mode: initialMode || 'practice' })
        this.fetchPractice(initialMode)
    },

    async fetchPractice(requestedMode) {
        wx.showLoading({ title: '加载中...' })
        try {
            const query = requestedMode ? `?mode=${encodeURIComponent(requestedMode)}` : ''
            const res = await request(
                `/miniprogram/student/tasks/${this.data.taskId}/reading-vocab-practice${query}`
            )
            if (!res.ok) {
                const msg = res.error === 'no_wrong_questions' ? '没有错题可重练' : '加载失败'
                wx.showToast({ title: msg, icon: 'none' })
                if (res.error === 'no_wrong_questions') {
                    setTimeout(() => wx.navigateBack(), 800)
                }
                return
            }

            const effectiveMode = res.mode || (res.is_done ? 'review' : 'practice')
            const selectedAnswers = res.previous_answers || {}
            const answerRecords = res.answer_records || {}
            const questions = res.questions || []

            // Build reviewFlags for quick lookup in WXML
            const reviewFlags = {}
            let correctCount = 0
            let wrongCount = 0
            const uncertainFlags = {}
            questions.forEach(q => {
                const rec = answerRecords[q.id]
                const userKey = rec ? rec.answer_key : ''
                const correctKey = q.correct_key || ''
                const isCorrect = !!(rec && rec.is_correct)
                const isUncertain = !!(rec && rec.is_uncertain)
                if (rec) {
                    if (isCorrect) correctCount++
                    if (!isCorrect || isUncertain) wrongCount++
                }
                reviewFlags[q.id] = { userKey, correctKey, isCorrect, isUncertain }
                uncertainFlags[q.id] = isUncertain
            })

            this.setData({
                task: res.task || {},
                questions,
                selectedAnswers,
                answerRecords,
                reviewFlags,
                mode: effectiveMode,
                isDone: !!res.is_done,
                correctCount,
                wrongCount,
                uncertainFlags,
                currentUncertain: false,
                sessionResults: {},
                currentFeedback: null,
                answeredCount: Object.keys(selectedAnswers).filter(k => selectedAnswers[k]).length,
                loading: false
            })
            this.loadQuestion(0)
        } catch (err) {
            console.error(err)
            wx.showToast({ title: '网络错误', icon: 'none' })
        } finally {
            wx.hideLoading()
        }
    },

    loadQuestion(index) {
        const baseQuestion = this.data.questions[index] || null
        const selectedAnswer = baseQuestion
            ? (this.data.selectedAnswers[baseQuestion.id] || '')
            : ''
        const currentQuestion = baseQuestion ? {
            ...baseQuestion,
            options: (baseQuestion.options || []).map(opt => ({ ...opt }))
        } : null

        // Enrich options with review state so WXML can just read flags
        if (currentQuestion) {
            const sessionResult = this.data.sessionResults[currentQuestion.id] || null
            const flags = this.data.reviewFlags[currentQuestion.id] || {}
            const isReview = this.data.mode === 'review'
            const correctKey = isReview ? flags.correctKey : (sessionResult ? sessionResult.correctKey : '')
            const userKey = isReview ? flags.userKey : (sessionResult ? sessionResult.userKey : '')
            const isCorrect = isReview ? !!flags.isCorrect : !!(sessionResult && sessionResult.isCorrect)
            currentQuestion.options = (currentQuestion.options || []).map(opt => ({
                ...opt,
                isCorrect: !!(correctKey && opt.key === correctKey),
                isUserPick: !!(userKey && opt.key === userKey),
                isUserWrong: !!(userKey && opt.key === userKey && !isCorrect)
            }))
        }

        this.setData({
            currentIndex: index,
            currentQuestion,
            selectedAnswer,
            currentUncertain: !!this.data.uncertainFlags[currentQuestion ? currentQuestion.id : ''],
            currentFeedback: currentQuestion
                ? (this.data.mode === 'review'
                    ? null
                    : (() => {
                        const feedback = this.data.sessionResults[currentQuestion.id] || null
                        if (!feedback) return null
                        return {
                            ...feedback,
                            isUncertain: !!this.data.uncertainFlags[currentQuestion.id]
                        }
                    })())
                : null
        })
    },

    selectOption(e) {
        if (this.data.mode === 'review') return  // read-only in review
        const key = e.currentTarget.dataset.key
        const currentQuestion = this.data.currentQuestion
        if (!currentQuestion) return
        if (this.data.sessionResults[currentQuestion.id]) return

        const selectedAnswers = {
            ...this.data.selectedAnswers,
            [currentQuestion.id]: key
        }
        const correctKey = currentQuestion.correct_key || ''
        const options = {}
        ;(currentQuestion.options || []).forEach(opt => {
            options[opt.key] = opt.text
        })
        const sessionResults = {
            ...this.data.sessionResults,
            [currentQuestion.id]: {
                userKey: key,
                correctKey,
                correctText: options[correctKey] || currentQuestion.correct_text || currentQuestion.hint || '',
                hint: currentQuestion.hint || '',
                isCorrect: !!(key && correctKey && key === correctKey)
            }
        }
        this.setData({
            selectedAnswers,
            selectedAnswer: key,
            sessionResults,
            answeredCount: Object.values(selectedAnswers).filter(Boolean).length
        }, () => this.loadQuestion(this.data.currentIndex))
    },

    toggleUncertain(e) {
        if (this.data.mode === 'review') return
        const checked = !!e.detail.value.length
        const currentQuestion = this.data.currentQuestion
        if (!currentQuestion) return
        const uncertainFlags = {
            ...this.data.uncertainFlags,
            [currentQuestion.id]: checked
        }
        this.setData({
            uncertainFlags,
            currentUncertain: checked
        }, () => this.loadQuestion(this.data.currentIndex))
    },

    prevQuestion() {
        if (this.data.currentIndex <= 0) return
        this.loadQuestion(this.data.currentIndex - 1)
    },

    nextQuestion() {
        if (this.data.currentIndex >= this.data.questions.length - 1) return
        this.loadQuestion(this.data.currentIndex + 1)
    },

    onNoteInput(e) {
        this.setData({ note: e.detail.value || '' })
    },

    // Action in review mode: redo only wrong questions
    async redoWrong() {
        if (!this.data.wrongCount) {
            wx.showToast({ title: '没有错题', icon: 'none' })
            return
        }
        this.resetAndReload('redo_wrong')
    },

    // Action in review mode: redo everything from scratch
    async redoAll() {
        const modal = await wx.showModal({
            title: '全部重做',
            content: '将清空本次作答记录，重新开始。继续吗？',
            confirmText: '继续'
        })
        if (!modal.confirm) return
        this.resetAndReload('redo_all')
    },

    resetAndReload(mode) {
        this.setData({
            mode,
            selectedAnswers: {},
            selectedAnswer: '',
            answeredCount: 0,
            currentIndex: 0,
            startedAt: Date.now(),
            loading: true,
            uncertainFlags: {},
            currentUncertain: false,
            sessionResults: {},
            currentFeedback: null
        })
        this.fetchPractice(mode)
    },

    // Back to task list
    goBack() {
        wx.navigateBack()
    },

    async submitPractice() {
        if (this.data.submitting) return
        if (this.data.mode === 'review') return  // no submit in review

        const total = this.data.questions.length
        const answered = Object.values(this.data.selectedAnswers).filter(Boolean).length
        const unanswered = total - answered
        if (unanswered > 0) {
            const modal = await wx.showModal({
                title: '还有未作答题目',
                content: `还有 ${unanswered} 题未作答，仍要提交吗？`,
                confirmText: '继续提交',
                cancelText: '返回作答'
            })
            if (!modal.confirm) return
        }

        const answers = this.data.questions.map(q => ({
            question_id: q.id,
            answer_key: this.data.selectedAnswers[q.id] || ''
        }))
        const uncertainQuestionIds = Object.keys(this.data.uncertainFlags)
            .filter(qid => this.data.uncertainFlags[qid])
            .map(qid => Number(qid))

        this.setData({ submitting: true })
        wx.showLoading({ title: '提交中...' })
        try {
            const durationSeconds = Math.max(1, Math.round((Date.now() - this.data.startedAt) / 1000))
            const submitMode = this.data.mode === 'redo_wrong'
                ? 'redo_wrong'
                : (this.data.mode === 'redo_all' ? 'redo_all' : '')
            const res = await request(
                `/miniprogram/student/tasks/${this.data.taskId}/reading-vocab-practice/submit`,
                {
                    method: 'POST',
                    data: {
                        answers,
                        uncertain_question_ids: uncertainQuestionIds,
                        duration_seconds: durationSeconds,
                        note: this.data.note,
                        mode: submitMode
                    }
                }
            )

            if (!res.ok) {
                wx.showToast({ title: '提交失败', icon: 'none' })
                return
            }

            // Save wrong items to local reading-vocab notebook for future review
            this.saveWrongItemsToNotebook(res.wrong_items || [])

            const wrongCount = (res.wrong_items || []).filter(item => !item.is_uncertain).length
            const uncertainCount = (res.wrong_items || []).filter(item => item.is_uncertain).length
            await wx.showModal({
                title: '练习完成',
                content: `正确 ${res.correct_count}/${res.total_count}，正确率 ${res.accuracy}%${wrongCount > 0 ? `\n错 ${wrongCount} 题` : ''}${uncertainCount > 0 ? `\n标记不清楚 ${uncertainCount} 题` : ''}${(wrongCount + uncertainCount) > 0 ? '\n可以点"查看错题"复盘' : ''}`,
                showCancel: false,
                confirmText: '查看错题回看'
            })

            // Transition into review mode in-place instead of navigating away
            this.setData({
                mode: 'review',
                isDone: true,
                loading: true,
                currentIndex: 0
            })
            this.fetchPractice('review')
        } catch (err) {
            console.error(err)
            wx.showToast({ title: '网络错误', icon: 'none' })
        } finally {
            wx.hideLoading()
            this.setData({ submitting: false })
        }
    },

    saveWrongItemsToNotebook(wrongItems) {
        try {
            const existing = readReadingNotebookCache()
            const now = Date.now()
            const preserved = (Array.isArray(existing) ? existing : []).filter(
                item => Number(item.taskId) !== Number(this.data.taskId)
            )
            const appended = (wrongItems || []).map(w => ({
                    entryKey: `${this.data.taskId}:${w.question_id}`,
                    word: w.word,
                    questionId: w.question_id,
                    correctKey: w.correct_key,
                    correctText: w.correct_text,
                    yourKey: w.selected_key,
                    yourText: w.selected_text,
                    isUncertain: !!w.is_uncertain,
                    taskId: this.data.taskId,
                    taskTitle: w.task_title || (this.data.task && this.data.task.material_title) || '',
                    hint: w.hint || '',
                    updatedAt: now
            }))
            const merged = preserved.concat(appended).sort((a, b) => (b.updatedAt || 0) - (a.updatedAt || 0))
            writeReadingNotebookCache(merged)
            wx.setStorageSync('reading_vocab_last_wrong', (wrongItems || []).map(w => w.word).filter(Boolean))
        } catch (err) {
            console.warn('saveWrongItemsToNotebook error', err)
        }
    }
})
