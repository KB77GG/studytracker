const { request } = require('../../../../utils/request.js')

Page({
    data: {
        taskId: null,
        task: {},
        questions: [],
        currentIndex: 0,
        currentQuestion: null,
        selectedAnswers: {},
        selectedAnswer: '',
        answeredCount: 0,
        note: '',
        loading: true,
        submitting: false,
        startedAt: 0
    },

    onLoad(options) {
        const taskId = parseInt(options.taskId, 10)
        this.setData({ taskId, startedAt: Date.now() })
        this.fetchPractice()
    },

    async fetchPractice() {
        wx.showLoading({ title: '加载中...' })
        try {
            const res = await request(`/miniprogram/student/tasks/${this.data.taskId}/reading-vocab-practice`)
            if (!res.ok) {
                wx.showToast({ title: '加载失败', icon: 'none' })
                return
            }

            const selectedAnswers = res.previous_answers || {}
            const questions = res.questions || []
            this.setData({
                task: res.task || {},
                questions,
                selectedAnswers,
                answeredCount: Object.keys(selectedAnswers).filter(key => selectedAnswers[key]).length,
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
        const currentQuestion = this.data.questions[index] || null
        const selectedAnswer = currentQuestion ? (this.data.selectedAnswers[currentQuestion.id] || '') : ''
        this.setData({
            currentIndex: index,
            currentQuestion,
            selectedAnswer
        })
    },

    selectOption(e) {
        const key = e.currentTarget.dataset.key
        const currentQuestion = this.data.currentQuestion
        if (!currentQuestion) return

        const selectedAnswers = {
            ...this.data.selectedAnswers,
            [currentQuestion.id]: key
        }
        this.setData({
            selectedAnswers,
            selectedAnswer: key,
            answeredCount: Object.values(selectedAnswers).filter(Boolean).length
        })
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

    async submitPractice() {
        if (this.data.submitting) return

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

        this.setData({ submitting: true })
        wx.showLoading({ title: '提交中...' })
        try {
            const durationSeconds = Math.max(1, Math.round((Date.now() - this.data.startedAt) / 1000))
            const res = await request(`/miniprogram/student/tasks/${this.data.taskId}/reading-vocab-practice/submit`, {
                method: 'POST',
                data: {
                    answers,
                    duration_seconds: durationSeconds,
                    note: this.data.note
                }
            })

            if (!res.ok) {
                wx.showToast({ title: '提交失败', icon: 'none' })
                return
            }

            const wrongCount = (res.wrong_items || []).length
            await wx.showModal({
                title: '练习完成',
                content: `正确 ${res.correct_count}/${res.total_count}，正确率 ${res.accuracy}%`,
                showCancel: false,
                confirmText: wrongCount > 0 ? `错 ${wrongCount} 题` : '完成'
            })
            wx.navigateBack()
        } catch (err) {
            console.error(err)
            wx.showToast({ title: '网络错误', icon: 'none' })
        } finally {
            wx.hideLoading()
            this.setData({ submitting: false })
        }
    }
})
