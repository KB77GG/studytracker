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
        selectedAnswers: {},       // qid -> answer key (choice questions, local picks this session)
        selectedAnswer: '',
        textAnswers: {},           // qid -> typed text (writing questions)
        currentTextAnswer: '',     // current writing question's text (mirrors textAnswers[currentQid])
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
            const previousAnswers = res.previous_answers || {}
            const answerRecords = res.answer_records || {}
            const questions = res.questions || []

            // Split previousAnswers into choice (ABCD key) vs writing (free text)
            // based on each question's is_writing flag.
            const selectedAnswers = {}
            const textAnswers = {}
            questions.forEach(q => {
                const prior = previousAnswers[q.id]
                if (!prior) return
                if (q.is_writing) {
                    textAnswers[q.id] = prior
                } else {
                    selectedAnswers[q.id] = prior
                }
            })

            // Build reviewFlags for quick lookup in WXML
            const reviewFlags = {}
            let correctCount = 0
            let wrongCount = 0
            const uncertainFlags = {}
            questions.forEach(q => {
                const rec = answerRecords[q.id]
                const userKey = rec ? rec.answer_key : ''
                const correctKey = q.correct_key || ''
                // Writing questions are reviewed manually — they don't count
                // toward correct/wrong stats and never appear "wrong" here.
                const isCorrect = !q.is_writing && !!(rec && rec.is_correct)
                const isUncertain = !q.is_writing && !!(rec && rec.is_uncertain)
                if (rec && !q.is_writing) {
                    if (isCorrect) correctCount++
                    if (!isCorrect || isUncertain) wrongCount++
                }
                reviewFlags[q.id] = { userKey, correctKey, isCorrect, isUncertain }
                uncertainFlags[q.id] = isUncertain
            })

            const choiceAnsweredCount = Object.keys(selectedAnswers).filter(k => selectedAnswers[k]).length
            const writingAnsweredCount = Object.keys(textAnswers).filter(k => (textAnswers[k] || '').trim()).length
            this.setData({
                task: res.task || {},
                questions,
                selectedAnswers,
                textAnswers,
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
                answeredCount: choiceAnsweredCount + writingAnsweredCount,
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

        const currentTextAnswer = baseQuestion && baseQuestion.is_writing
            ? (this.data.textAnswers[baseQuestion.id] || '')
            : ''

        this.setData({
            currentIndex: index,
            currentQuestion,
            selectedAnswer,
            currentTextAnswer,
            currentUncertain: !!this.data.uncertainFlags[currentQuestion ? currentQuestion.id : ''],
            currentFeedback: currentQuestion && !currentQuestion.is_writing
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
        if (currentQuestion.is_writing) return  // writing questions use textarea
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
        const writingCount = Object.values(this.data.textAnswers).filter(v => (v || '').trim()).length
        this.setData({
            selectedAnswers,
            selectedAnswer: key,
            sessionResults,
            answeredCount: Object.values(selectedAnswers).filter(Boolean).length + writingCount
        }, () => this.loadQuestion(this.data.currentIndex))
    },

    onTextAnswerInput(e) {
        if (this.data.mode === 'review') return
        const currentQuestion = this.data.currentQuestion
        if (!currentQuestion || !currentQuestion.is_writing) return
        const value = e.detail.value || ''
        const textAnswers = {
            ...this.data.textAnswers,
            [currentQuestion.id]: value
        }
        // Re-count: choice answers + non-empty writing answers
        const choiceCount = Object.values(this.data.selectedAnswers).filter(Boolean).length
        const writingCount = Object.values(textAnswers).filter(v => (v || '').trim()).length
        this.setData({
            textAnswers,
            currentTextAnswer: value,
            answeredCount: choiceCount + writingCount
        })
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
            textAnswers: {},
            currentTextAnswer: '',
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

        // Count separately: choice questions (need answer_key) vs writing
        // questions (need text). Both contribute to "unanswered" check.
        let choiceUnanswered = 0
        let writingUnanswered = 0
        this.data.questions.forEach(q => {
            if (q.is_writing) {
                if (!(this.data.textAnswers[q.id] || '').trim()) writingUnanswered++
            } else {
                if (!this.data.selectedAnswers[q.id]) choiceUnanswered++
            }
        })
        const unanswered = choiceUnanswered + writingUnanswered
        if (unanswered > 0) {
            const modal = await wx.showModal({
                title: '还有未作答题目',
                content: `还有 ${unanswered} 题未作答，仍要提交吗？`,
                confirmText: '继续提交',
                cancelText: '返回作答'
            })
            if (!modal.confirm) return
        }

        // Build separate payloads — backend distinguishes by `is_writing`
        // (no options) and routes to the right grading branch.
        const answers = []
        const textAnswers = []
        this.data.questions.forEach(q => {
            if (q.is_writing) {
                const text = (this.data.textAnswers[q.id] || '').trim()
                if (text) {
                    textAnswers.push({ question_id: q.id, text_answer: text })
                }
            } else {
                answers.push({
                    question_id: q.id,
                    answer_key: this.data.selectedAnswers[q.id] || ''
                })
            }
        })
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
                        text_answers: textAnswers,
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
            const writingTotal = res.writing_total || 0
            const writingAnswered = res.writing_answered || 0
            const choiceTotal = res.choice_total || res.total_count || 0
            const writingNote = writingTotal > 0
                ? `\n改写题已提交 ${writingAnswered}/${writingTotal}（待老师批改）`
                : ''
            const accuracyLine = choiceTotal > 0
                ? `单选正确 ${res.correct_count}/${choiceTotal}，正确率 ${res.accuracy}%`
                : '本次练习无单选题'
            await wx.showModal({
                title: '练习完成',
                content: `${accuracyLine}${writingNote}${wrongCount > 0 ? `\n错 ${wrongCount} 题` : ''}${uncertainCount > 0 ? `\n标记不清楚 ${uncertainCount} 题` : ''}${(wrongCount + uncertainCount) > 0 ? '\n可以点"查看错题"复盘' : ''}`,
                showCancel: false,
                confirmText: choiceTotal > 0 ? '查看错题回看' : '完成'
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
