const app = getApp()
const { request } = require('../../../utils/request.js')
const { createReliableAudioPlayer } = require('../../../utils/dictation-audio.js')
const {
    buildMeaningChoiceOptions,
    contextCorrectionSubmissionValue,
    safeAnswerDisplay,
    selectedOptionLabel
} = require('../../../utils/vocabulary-interaction.js')
const { normalizeAnswerFeedback } = require('../../../utils/vocabulary-feedback.js')
const { createVocabularyPerformanceTracker } = require('../../../utils/vocabulary-performance.js')
const {
    forgotCountFromResponse,
    forgotItemsForDisplay,
    isForgotResponse,
    matchesAnswerEvent,
    shouldRecoverLearningAnswer
} = require('../../../utils/vocabulary-forgot.js')

const LEARNING_LOAD_TIMEOUT_MS = 10000
const LEARNING_MUTATION_TIMEOUT_MS = 15000

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
        supportsForgotResponse: false,
        groupNumber: 0,
        groupCount: 0,
        groupSize: 0,
        totalWordCount: 0,
        phase: '',
        phaseLabel: '',
        baseProgressCompleted: 0,
        baseProgressTotal: 0,
        remediationProgressCompleted: 0,
        remediationProgressTotal: 0,
        remediationAllocatedTotal: 0,
        remediationBudgetTotal: 0,
        remediationPendingCount: 0,
        deferredReviewCount: 0,
        groupPosition: 0,
        groupPositionTotal: 0,
        familiarity: [],
        familiarityIndex: 0,
        isLastFamiliarity: false,
        familiarityConfirming: false,
        familiarityEntering: false,
        currentQuestion: null,
        answerRenderEpoch: 0,
        inputValue: '',
        selectedOption: '',
        meaningOptions: [],
        isMeaningChoice: false,
        audioState: 'idle',
        audioButtonLabel: '播放发音',
        showResult: false,
        isCorrect: false,
        submittedAnswer: '',
        responseKind: 'answer',
        correctAnswer: '',
        answerFeedback: null,
        correctionRequired: false,
        correctionCompleted: false,
        correctionInputValue: '',
        correctionPlaceholder: '请重新输入正确答案',
        correctionPrompt: '请重新输入正确答案',
        correctionHasInput: false,
        correctionSubmitting: false,
        correctionIsCorrect: false,
        correctionCount: 0,
        correctionMaxAttempts: 2,
        correctionExhausted: false,
        appealSubmitting: false,
        appealSubmitted: false,
        submitting: false,
        finishing: false,
        finished: false,
        result: null,
        forgotItems: [],
        forgotCount: 0,
        diagnostics: [],
        traceId: '',
        startedAt: 0,
        readOnly: false,
        dateStatusText: ''
    },

    onLoad(options) {
        this._learningPageActive = true
        this._learningDeadlineTimers = new Set()
        this._learningTrace = createVocabularyPerformanceTracker(wx)
        this._learningTrace.mark('navigation_start')
        this._learningTrace.mark('page_onLoad')
        this.setData({ traceId: this._learningTrace.traceId })
        const rawTaskId = String((options || {}).taskId || (options || {}).id || '')
        if (!/^\d+$/.test(rawTaskId)) {
            this.setData({ loading: false, loadError: '任务链接无效' })
            return
        }
        this.setData({ taskId: rawTaskId, startedAt: Date.now() })
        this.audioPlayer = createReliableAudioPlayer(wx, {
            onStateChange: (state) => {
                // The player is destroyed before the page leaves. Keep this
                // guard as a second line of defence against native callbacks
                // delivered after page teardown.
                if (this._learningPageActive === false) return
                this.setData({
                    audioState: state,
                    audioButtonLabel: state === 'loading'
                        ? '正在加载…'
                        : (state === 'playing'
                            ? '正在播放'
                            : (state === 'ended'
                                ? '再听一遍'
                                : (state === 'failed' ? '播放失败，点击重试' : '播放发音')))
                })
            },
            onEvent: (name, detail) => {
                if (!this._learningTrace) return
                this._learningTrace.mark(name, detail)
                if (name === 'audio_canplay' || name === 'audio_play' || name === 'audio_error') {
                    this._learningTrace.logSnapshot(name)
                }
            },
            onError: () => {
                if (this._learningPageActive !== false) {
                    wx.showToast({ title: '音频播放失败，请重试', icon: 'none' })
                }
            }
        })
        this.fetchTaskAccess()
    },

    onUnload() {
        this._learningPageActive = false
        this.cancelLearningDeadlines()
        if (this.audioPlayer) this.audioPlayer.destroy()
        this.audioPlayer = null
    },

    isLearningPageActive() {
        return this._learningPageActive !== false
    },

    isLearningLoadBlocking() {
        // A rendered question can remain in data while its next queue load
        // is pending. The request version distinguishes that in-flight UI
        // from a page whose first queue has not been loaded yet.
        return this.data.loading && Number(this._learningQueueRequestVersion || 0) > 0
    },

    noop() {},

    requestWithDeadline(factory, timeoutMs, label) {
        if (!this.isLearningPageActive()) {
            return Promise.reject({ errMsg: 'request:fail abort', pageUnloaded: true })
        }
        const deadlineMs = Math.max(1, Number(timeoutMs) || 1)
        return new Promise((resolve, reject) => {
            let settled = false
            const entry = { timerId: null, cancel: null }
            const finish = (handler, value) => {
                if (settled) return
                settled = true
                if (entry.timerId !== null) clearTimeout(entry.timerId)
                this._learningDeadlineTimers.delete(entry)
                handler(value)
            }
            entry.cancel = () => finish(reject, {
                errMsg: 'request:fail abort',
                pageUnloaded: true
            })
            entry.timerId = setTimeout(() => finish(reject, {
                errMsg: `request:fail timeout (${label || 'learning_request'})`,
                deadline: true
            }), deadlineMs)
            this._learningDeadlineTimers.add(entry)
            Promise.resolve().then(() => {
                if (!this.isLearningPageActive()) {
                    throw { errMsg: 'request:fail abort', pageUnloaded: true }
                }
                return factory()
            }).then(
                (value) => finish(resolve, value),
                (error) => finish(reject, error)
            )
        })
    },

    cancelLearningDeadlines() {
        if (!this._learningDeadlineTimers) return
        Array.from(this._learningDeadlineTimers).forEach((entry) => entry.cancel())
    },

    queueUrl() {
        return `/miniprogram/student/tasks/${this.data.taskId}/vocabulary-queue?supports_correction=1`
    },

    fetchTaskAccess() {
        this.setData({ loading: true, loadError: '' })
        return this.requestWithDeadline(
            () => request(`/miniprogram/student/tasks/${this.data.taskId}`, {
                timeout: LEARNING_LOAD_TIMEOUT_MS
            }),
            LEARNING_LOAD_TIMEOUT_MS,
            'learning_task_access'
        ).then((res) => {
            if (!this.isLearningPageActive()) return
            if (!res || !res.ok || !res.task) throw new Error('task_load_failed')
            const task = res.task
            this.setData({
                readOnly: !!task.read_only,
                dateStatusText: task.status_label
                    || task.task_status_label
                    || task.availability_label
                    || '该任务当前仅可查看'
            })
            if (task.read_only) {
                if (task.status === 'completed' || task.task_status === 'completed') {
                    return this.fetchQueue()
                }
                this.setData({ loading: false })
                return
            }
            return this.fetchQueue()
        }).catch((err) => {
            if (err && err.pageUnloaded) return
            console.warn('load vocabulary task failed', err)
            this.setData({ loading: false, loadError: '任务加载失败，请重试' })
        })
    },

    fetchQueue() {
        const requestVersion = Number(this._learningQueueRequestVersion || 0) + 1
        this._learningQueueRequestVersion = requestVersion
        this.setData({ loading: true, loadError: '' })
        if (this._learningTrace) this._learningTrace.mark('request_start', { endpoint: 'learning_queue' })
        return this.requestWithDeadline(
            () => request(this.queueUrl(), { timeout: LEARNING_LOAD_TIMEOUT_MS }),
            LEARNING_LOAD_TIMEOUT_MS,
            'learning_queue'
        ).then((res) => {
            if (!this.isLearningPageActive() || requestVersion !== this._learningQueueRequestVersion) return
            if (this._learningTrace) {
                const bytes = this._learningTrace.estimateBytes(res)
                this._learningTrace.setMetric('response_bytes', bytes)
                this._learningTrace.mark('request_end', {
                    endpoint: 'learning_queue',
                    ok: !!(res && res.ok),
                    response_bytes: bytes
                })
                this._learningTrace.mark('response_parse_end')
            }
            if (!res || !res.ok) {
                if (res && res.error === 'vocabulary_review_required') {
                    wx.redirectTo({ url: `/pages/student/vocabulary-review/index?returnTaskId=${this.data.taskId}` })
                    return
                }
                throw new Error((res && res.error) || 'vocabulary_group_load_failed')
            }
            this.applyQueue(res)
        }).catch((err) => {
            if (!this.isLearningPageActive() || requestVersion !== this._learningQueueRequestVersion
                || (err && err.pageUnloaded)) return
            console.warn('load vocabulary group failed', err)
            if (this.handleMutationError(err)) return
            if (this._learningTrace) {
                this._learningTrace.mark('request_end', {
                    endpoint: 'learning_queue',
                    ok: false,
                    error: 'learning_queue_failed'
                })
                this._learningTrace.setMetric('error_load', 1)
                this._learningTrace.logSnapshot('learning_queue_error')
            }
            this.setData({
                loading: false,
                loadError: `小组学习加载失败，请重试（${this._learningTrace ? this._learningTrace.traceId : '稍后'}）`
            })
        })
    },

    handleMutationError(err) {
        const code = err && err.message
        const dateGateLabels = {
            task_not_open: '尚未开放',
            task_expired: '未完成·已截止',
            task_completed_read_only: '已完成·仅可查看'
        }
        if (dateGateLabels[code]) {
            this.setData({
                readOnly: true,
                dateStatusText: dateGateLabels[code],
                loading: false,
                loadError: '',
                submitting: false,
                correctionSubmitting: false,
                familiarityConfirming: false,
                familiarityEntering: false,
                finishing: false
            })
            wx.showToast({ title: dateGateLabels[code], icon: 'none' })
            return true
        }
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
        const isLastFamiliarity = queue.phase === 'familiarity'
            && familiarity.length > 0
            && displayIndex === familiarity.length - 1
        const baseProgressTotal = Number(queue.base_progress_total || 0)
        const baseProgressCompleted = Number(queue.base_progress_completed || 0)
        const groupPositionTotal = queue.phase === 'familiarity'
            ? familiarity.length
            : baseProgressTotal
        const groupPosition = queue.phase === 'familiarity'
            ? displayIndex + 1
            : Math.min(baseProgressCompleted + 1, Math.max(1, baseProgressTotal))
        const correctionRequired = !!queue.correction_required || !!(question && question.correction)
        const fallbackFeedback = correctionRequired
            ? normalizeAnswerFeedback({}, this.feedbackFallback(question))
            : null
        if (this._learningTrace) {
            this._learningTrace.setMetric('returned_words', familiarity.length)
            this._learningTrace.setMetric('actual_group_words', familiarity.length)
            this._learningTrace.setMetric('actual_session_items', question ? 1 : 0)
            this._learningTrace.setMetric('due_total', Number(queue.due_count || queue.remaining_due_count || 0))
            this._learningTrace.mark('normalize_end', { returned_words: familiarity.length })
            this._learningTrace.mark('scheduler_end', {
                actual_group_words: familiarity.length,
                actual_session_items: question ? 1 : 0
            })
        }
        this.setData({
            loading: false,
            queueToken: queue.queue_token || '',
            supportsForgotResponse: queue.supports_forgot_response === true,
            groupNumber: Number(queue.group_number || 0),
            groupCount: Number(queue.group_count || 0),
            groupSize: Number(queue.group_size || 0),
            totalWordCount: Number(queue.total_word_count || 0),
            phase: queue.phase || '',
            phaseLabel: queue.phase_label || PHASE_LABELS[queue.phase] || queue.phase || '',
            baseProgressCompleted,
            baseProgressTotal,
            remediationProgressCompleted: Number(queue.remediation_progress_completed || 0),
            remediationProgressTotal: Number(queue.remediation_progress_total || 0),
            remediationAllocatedTotal: Number(queue.remediation_allocated_total || queue.remediation_progress_total || 0),
            remediationBudgetTotal: Number(queue.remediation_budget_total || 0),
            remediationPendingCount: Number(queue.remediation_pending_count || 0),
            deferredReviewCount: Number(queue.deferred_review_count || 0),
            groupPosition,
            groupPositionTotal,
            familiarity,
            familiarityIndex: displayIndex,
            isLastFamiliarity,
            familiarityConfirming: false,
            familiarityEntering: false,
            currentQuestion: question,
            answerRenderEpoch: Number(this.data.answerRenderEpoch || 0) + 1,
            isMeaningChoice,
            meaningOptions,
            inputValue: '',
            selectedOption: '',
            showResult: correctionRequired,
            isCorrect: correctionRequired ? !!question.first_is_correct : false,
            submittedAnswer: correctionRequired
                ? (isForgotResponse({ first_response_kind: question.first_response_kind })
                    ? '忘了'
                    : safeAnswerDisplay(question.first_answer, this.answerOptions(question)))
                : '',
            responseKind: correctionRequired && question.first_response_kind === 'forgot' ? 'forgot' : 'answer',
            correctAnswer: correctionRequired
                ? safeAnswerDisplay(question.revealed_answer, this.answerOptions(question), '暂无法显示正确答案')
                : '',
            answerFeedback: fallbackFeedback,
            correctionRequired,
            correctionCompleted: false,
            correctionInputValue: '',
            correctionPlaceholder: this.correctionPlaceholder(question),
            correctionPrompt: this.correctionPrompt(question),
            correctionHasInput: false,
            correctionSubmitting: false,
            correctionIsCorrect: question && question.correction_is_correct === true,
            correctionCount: Number((question && question.correction_count) || 0),
            correctionMaxAttempts: Number((question && question.correction_max_attempts) || 2),
            correctionExhausted: !!(question && question.correction_exhausted),
            appealSubmitting: false,
            appealSubmitted: false,
            diagnostics: Array.isArray(queue.diagnostics) ? queue.diagnostics : [],
            forgotItems: forgotItemsForDisplay(queue.forgot_items),
            forgotCount: forgotCountFromResponse(queue, 'forgotten_count', queue.forgot_items),
            finished: false
        }, () => {
            if (this._learningTrace) {
                const firstSetDataBytes = this._learningTrace.estimateBytes({
                    phase: queue.phase || '',
                    familiarityIndex: displayIndex,
                    currentQuestion: question,
                    groupSize: familiarity.length
                })
                this._learningTrace.setMetric('first_set_data_bytes', firstSetDataBytes)
                this._learningTrace.mark('first_setData_end', { first_set_data_bytes: firstSetDataBytes })
                const firstPaint = !this._learningFirstPaintDone
                if (firstPaint) this._learningFirstPaintDone = true
                this._learningTrace.mark(firstPaint ? 'first_visible' : 'next_word_visible', {
                    index: displayIndex,
                    actual_group_words: familiarity.length
                })
                this._learningTrace.mark('first_interactive', { index: displayIndex })
                this._learningTrace.logSnapshot(firstPaint ? 'learning_first_visible' : 'learning_word_visible')
            }
            if (isFinished) {
                if (queue.settlement) {
                    const settlement = queue.settlement
                    const rows = Array.isArray(settlement.forgot_items)
                        ? settlement.forgot_items
                        : queue.forgot_items
                    this.setData({
                        finished: true,
                        result: settlement,
                        forgotItems: forgotItemsForDisplay(rows),
                        forgotCount: forgotCountFromResponse(settlement, 'forgotten_count', rows)
                    })
                    return
                }
                this.finishTask()
                return
            }
            this.preloadFamiliarityAudio(displayIndex)
            if (
                queue.phase === 'familiarity'
                || (question && String(question.mode || '').indexOf('audio_to_') === 0)
            ) this.playAudio({ auto: true })
        })
    },

    familiarityItem() {
        return this.data.familiarity[this.data.familiarityIndex] || null
    },

    isLastFamiliarityItem() {
        return this.data.phase === 'familiarity'
            && this.data.familiarity.length > 0
            && this.data.familiarityIndex === this.data.familiarity.length - 1
    },

    familiarityAudioSources(item) {
        item = item || {}
        return [item.audio_url, item.audio_tts_url, item.audio].filter(Boolean)
    },

    preloadFamiliarityAudio(index) {
        if (!this.audioPlayer || typeof this.audioPlayer.preload !== 'function') return
        const items = this.data.familiarity.slice(index, index + 3)
        const sources = []
        items.forEach((item) => {
            const itemSources = this.familiarityAudioSources(item)
            if (itemSources.length) sources.push(itemSources[0])
        })
        const trace = this._learningTrace
        const stats = typeof this.audioPlayer.stats === 'function'
            ? this.audioPlayer.stats()
            : null
        if (trace) {
            trace.setMetric('audio_cache_limit', Number(this.audioPlayer.maxCacheEntries) || 3)
            trace.setMetric('audio_preload_candidates', sources.length)
            if (stats && Number.isFinite(stats.maxConcurrentPreloadDownloads)) {
                trace.setMetric('audio_preload_max_concurrent', stats.maxConcurrentPreloadDownloads)
            }
            if (stats && Number.isFinite(stats.maxConcurrentDownloads)) {
                trace.setMetric('audio_download_max_concurrent', stats.maxConcurrentDownloads)
            }
        }
        if (!sources.length) return
        const preloadResult = this.audioPlayer.preload(sources, app.globalData.baseUrl)
        if (!preloadResult || typeof preloadResult.then !== 'function') return
        preloadResult.then(() => {
            if (!this.isLearningPageActive() || !this._learningTrace) return
            const after = typeof this.audioPlayer.stats === 'function'
                ? this.audioPlayer.stats()
                : null
            if (!after) return
            this._learningTrace.setMetric('audio_cache_entries', after.cacheEntries)
            this._learningTrace.setMetric('audio_inflight_downloads', after.inflightDownloads)
            if (Number.isFinite(after.maxConcurrentPreloadDownloads)) {
                this._learningTrace.setMetric(
                    'audio_preload_max_concurrent',
                    after.maxConcurrentPreloadDownloads
                )
            }
            if (Number.isFinite(after.maxConcurrentDownloads)) {
                this._learningTrace.setMetric(
                    'audio_download_max_concurrent',
                    after.maxConcurrentDownloads
                )
            }
            this._learningTrace.logSnapshot('learning_audio_preload')
        }).catch(() => {})
    },

    previousFamiliarity() {
        if (
            this.data.phase !== 'familiarity'
            || this.data.familiarityIndex <= 0
            || this.data.familiarityEntering
            || this.data.familiarityConfirming
        ) return
        const nextIndex = this.data.familiarityIndex - 1
        if (this._learningTrace) this._learningTrace.mark('next_word_start', { index: nextIndex, direction: 'previous' })
        this.setData({
            familiarityIndex: nextIndex,
            isLastFamiliarity: false
        }, () => {
            if (this._learningTrace) this._learningTrace.mark('next_word_visible', { index: nextIndex })
            this.playAudio({ auto: true })
        })
    },

    nextFamiliarity() {
        if (
            this.data.readOnly
            || this.data.phase !== 'familiarity'
            || this.data.familiarityEntering
            || this.data.familiarityConfirming
        ) return
        const item = this.familiarityItem()
        if (!item) return
        if (this.isLastFamiliarityItem()) {
            this.confirmFamiliarityCompletion()
            return
        }
        if (item.viewed) {
            const next = this.data.familiarityIndex + 1
            if (next < this.data.familiarity.length) {
                if (this._learningTrace) this._learningTrace.mark('next_word_start', { index: next })
                this.setData({
                    familiarityIndex: next,
                    isLastFamiliarity: next === this.data.familiarity.length - 1
                }, () => {
                    if (this._learningTrace) this._learningTrace.mark('next_word_visible', { index: next })
                    this.playAudio({ auto: true })
                })
            }
            return
        }
        this.requestWithDeadline(() => request(`/miniprogram/student/tasks/${this.data.taskId}/vocabulary-learning/familiarity`, {
            method: 'POST',
            timeout: LEARNING_MUTATION_TIMEOUT_MS,
            data: { queue_token: this.data.queueToken, word_id: item.word_id }
        }), LEARNING_MUTATION_TIMEOUT_MS, 'familiarity_view').then((res) => {
            if (!this.isLearningPageActive()) return
            if (!res || !res.ok) throw new Error((res && res.error) || 'familiarity_failed')
            this.applyQueue(res)
        }).catch((err) => {
            if (err && err.pageUnloaded) return
            console.warn('mark vocabulary familiarity failed', err)
            if (!this.handleMutationError(err)) this.fetchQueue()
        })
    },

    confirmFamiliarityCompletion() {
        if (this.data.readOnly || this.data.familiarityConfirming || this.data.familiarityEntering) return
        this.setData({ familiarityConfirming: true })
    },

    cancelFamiliarityCompletion() {
        if (this.data.familiarityEntering) return
        this.setData({ familiarityConfirming: false })
    },

    startFamiliarityDetection() {
        if (this.data.readOnly || this.data.familiarityEntering || !this.data.familiarityConfirming) return
        const item = this.familiarityItem()
        if (!item) {
            this.setData({ familiarityConfirming: false })
            return
        }
        this.setData({ familiarityEntering: true })
        this.requestWithDeadline(
            () => request(`/miniprogram/student/tasks/${this.data.taskId}/vocabulary-learning/familiarity`, {
                method: 'POST',
                timeout: LEARNING_MUTATION_TIMEOUT_MS,
                data: { queue_token: this.data.queueToken, word_id: item.word_id }
            }),
            LEARNING_MUTATION_TIMEOUT_MS,
            'familiarity_complete'
        ).then((res) => {
            if (!this.isLearningPageActive()) return
            if (!res || !res.ok) throw new Error((res && res.error) || 'familiarity_failed')
            this.applyQueue(res)
        }).catch((err) => {
            if (err && err.pageUnloaded) return
            console.warn('complete vocabulary familiarity failed', err)
            this.setData({ familiarityConfirming: false, familiarityEntering: false })
            if (!this.handleMutationError(err)) {
                wx.showToast({ title: '进入检测失败，请重试', icon: 'none' })
            }
        })
    },

    onInput(e) {
        if (this.data.readOnly || this.isLearningLoadBlocking() || this.data.loadError || this.data.showResult) return
        const question = this.data.currentQuestion
        if (!question || !matchesAnswerEvent(e, question, 'learningQuestionId',
            question.learning_question_id, this.data.answerRenderEpoch)) return
        this.setData({ inputValue: (e && e.detail && e.detail.value) || '' })
    },

    selectOption(e) {
        if (this.data.readOnly || this.isLearningLoadBlocking() || this.data.loadError || this.data.showResult) return
        const question = this.data.currentQuestion
        if (!question || !matchesAnswerEvent(e, question, 'learningQuestionId',
            question.learning_question_id, this.data.answerRenderEpoch)) return
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

    answerOptions(question) {
        const snapshot = question && question.question
        return snapshot && Array.isArray(snapshot.options) ? snapshot.options : []
    },

    correctionPlaceholder(question) {
        const mode = String(question && question.mode || '')
        return mode === 'en_to_zh' || mode === 'audio_to_zh'
            ? '请重新输入正确释义'
            : '请重新输入正确单词'
    },

    correctionPrompt(question) {
        const mode = String(question && question.mode || '')
        if (mode === 'context_choice') {
            const prompt = question && question.question && question.question.prompt
            const target = String(prompt && prompt.target_word || '').trim()
            return target ? `请重新输入目标词“${target}”` : '请重新输入目标词'
        }
        return this.correctionPlaceholder(question)
    },

    applyLearningAnswerResult(question, res, answer) {
        const responseKind = isForgotResponse(res) ? 'forgot' : 'answer'
        this.setData({
            currentQuestion: question,
            showResult: true,
            isCorrect: !!res.is_correct,
            responseKind,
            submittedAnswer: responseKind === 'forgot'
                ? '忘了'
                : safeAnswerDisplay(
                    res.student_answer !== undefined ? res.student_answer : answer,
                    this.answerOptions(question)
                ),
            correctAnswer: safeAnswerDisplay(
                res.revealed_answer,
                this.answerOptions(question),
                '暂无法显示正确答案'
            ),
            answerFeedback: normalizeAnswerFeedback(res, this.feedbackFallback(question)),
            correctionRequired: !!res.correction_required,
            correctionCompleted: false,
            correctionInputValue: '',
            correctionPlaceholder: this.correctionPlaceholder(question),
            correctionPrompt: this.correctionPrompt(question),
            correctionHasInput: false,
            correctionIsCorrect: false,
            correctionCount: 0,
            correctionMaxAttempts: Number(res.correction_limit || 2),
            correctionExhausted: false
        })
    },

    recoverLearningAnswer(pending, failure) {
        const recoveryUrl = `${this.queueUrl()}&attempt_id=${encodeURIComponent(pending.attemptId)}`
        return this.requestWithDeadline(
            () => request(recoveryUrl, { timeout: LEARNING_LOAD_TIMEOUT_MS }),
            LEARNING_LOAD_TIMEOUT_MS,
            'learning_answer_recovery'
        ).then((queue) => {
            if (!this.isLearningPageActive()) return false
            if (!queue || !queue.ok || String(queue.task_id) !== String(this.data.taskId)) {
                throw new Error('learning_answer_recovery_failed')
            }
            const saved = queue.saved_response || {}
            if (String(saved.learning_question_id) !== String(pending.learningQuestionId)
                || String(saved.attempt_id) !== String(pending.attemptId)) {
                wx.showToast({ title: '提交结果未确认，请重试', icon: 'none' })
                return false
            }
            if (queue.recovery_only && queue.review_required && !isForgotResponse(saved)) {
                this.setData({ submitting: false })
                wx.showToast({ title: '本题已保存，先完成今日复习', icon: 'none' })
                wx.redirectTo({ url: `/pages/student/vocabulary-review/index?returnTaskId=${this.data.taskId}` })
                return true
            }
            if ((queue.completed && queue.settlement) || (!isForgotResponse(saved) && (queue.completed || saved.correction_required))) {
                this.applyQueue(queue)
            } else {
                this.applyLearningAnswerResult(pending.question, saved, pending.answer)
            }
            wx.showToast({
                title: isForgotResponse(saved) ? '已记为未掌握' : '已恢复本题结果',
                icon: 'none'
            })
            return true
        }).catch((err) => {
            if (err && err.pageUnloaded) return false
            console.warn('recover vocabulary group answer failed', err)
            if (this.isLearningPageActive()) {
                wx.showToast({ title: failure ? '提交结果未确认，请重试' : '提交失败，请重试', icon: 'none' })
            }
            return false
        })
    },

    submitAnswer(event) {
        return this.submitResponse('answer', event)
    },

    submitForgot(event) {
        return this.submitResponse('forgot', event)
    },

    submitResponse(responseKind, event) {
        if (this.data.readOnly || this.isLearningLoadBlocking() || this.data.loadError || this.data.finishing || this.data.finished) return
        const question = this.data.currentQuestion
        if (!question || this.data.phase === 'familiarity' || this.data.appealSubmitting) return
        if (!matchesAnswerEvent(event, question, 'learningQuestionId',
            question.learning_question_id, this.data.answerRenderEpoch)) return
        if (this.data.submitting || this.data.correctionSubmitting) return
        if (this.data.showResult) {
            if (responseKind === 'answer' && this.data.responseKind !== 'forgot' && !this.data.correctionRequired) return this.fetchQueue()
            return
        }
        if (responseKind === 'forgot' && !this.data.supportsForgotResponse) return
        const answer = this.answerValue()
        if (responseKind !== 'forgot' && !answer) {
            wx.showToast({
                title: question.mode === 'context_choice' || this.data.isMeaningChoice
                    ? '请选择答案'
                    : '请输入答案',
                icon: 'none'
            })
            return
        }
        const retry = this.data.phase === 'retry'
        const attemptId = `vocabulary-group:${this.data.taskId}:${retry ? 'retry:' : 'first:'}${question.learning_question_id}`
        const pending = { question, learningQuestionId: question.learning_question_id, attemptId, answer }
        const postData = {
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
            retry,
            supports_correction: true,
            input_mode: 'native'
        }
        if (responseKind === 'forgot') postData.response_kind = 'forgot'
        this.setData({ submitting: true })
        return this.requestWithDeadline(() => request('/dictation/submit', {
            method: 'POST',
            timeout: LEARNING_MUTATION_TIMEOUT_MS,
            data: postData
        }), LEARNING_MUTATION_TIMEOUT_MS, 'learning_answer').then((res) => {
            if (!this.isLearningPageActive()) return
            if (!res || !res.ok) throw (res || new Error('vocabulary_group_answer_failed'))
            this.applyLearningAnswerResult(question, res, answer)
        }).catch((err) => {
            if (err && err.pageUnloaded) return
            console.warn('submit vocabulary group answer failed', err)
            if (shouldRecoverLearningAnswer(err)) return this.recoverLearningAnswer(pending, true)
            if (!this.handleMutationError(err)) wx.showToast({ title: '提交失败，请重试', icon: 'none' })
        }).finally(() => {
            if (this.isLearningPageActive()) this.setData({ submitting: false })
        })
    },

    continueAfterResult(event) {
        const question = this.data.currentQuestion
        if (!question || !this.data.showResult || this.data.correctionRequired
            || this.data.readOnly || this.data.submitting || this.data.finishing
            || this.data.finished || this.data.appealSubmitting
            || this.isLearningLoadBlocking() || this.data.loadError) return
        if (!matchesAnswerEvent(event, question, 'learningQuestionId',
            question.learning_question_id, this.data.answerRenderEpoch)) return
        return this.fetchQueue()
    },

    onCorrectionInput(e) {
        if (this.data.readOnly || this.data.correctionCompleted || this.data.correctionSubmitting) return
        const value = (e && e.detail && e.detail.value) || ''
        this.setData({
            correctionInputValue: value,
            correctionHasInput: String(value).trim().length > 0
        })
    },

    submitCorrection() {
        const question = this.data.currentQuestion || {}
        if (
            this.data.readOnly
            || !this.data.correctionRequired
            || this.data.correctionSubmitting
            || !question.learning_question_id
        ) return
        const typedAnswer = String(this.data.correctionInputValue || '').trim()
        const answer = contextCorrectionSubmissionValue(question, typedAnswer, this.data.correctAnswer)
        if (!typedAnswer) {
            wx.showToast({ title: '请先完成纠正', icon: 'none' })
            return
        }
        const correctionNumber = Number(question.correction_count || this.data.correctionCount || 0) + 1
        const attemptId = `vocabulary-group-correction:${this.data.taskId}:${question.learning_question_id}:${correctionNumber}`
        this.setData({ correctionSubmitting: true })
        this.requestWithDeadline(() => request(`/miniprogram/student/tasks/${this.data.taskId}/vocabulary-learning/correction`, {
            method: 'POST',
            timeout: LEARNING_MUTATION_TIMEOUT_MS,
            data: this.correctionRequestData(question, answer, attemptId)
        }), LEARNING_MUTATION_TIMEOUT_MS, 'learning_correction').then((res) => {
            if (!this.isLearningPageActive()) return
            if (!res || !res.ok) throw new Error((res && res.error) || 'vocabulary_correction_failed')
            const correctionRequired = res.correction_required !== undefined
                ? !!res.correction_required
                : !res.correction_completed
            this.setData({
                queueToken: res.queue_token || this.data.queueToken,
                currentQuestion: correctionRequired
                    ? (res.current_question || this.data.currentQuestion)
                    : this.data.currentQuestion,
                correctionRequired,
                correctionCompleted: !!res.correction_completed,
                correctionExhausted: !!res.correction_exhausted,
                correctionSubmitting: false,
                correctionInputValue: '',
                correctionHasInput: false,
                correctionIsCorrect: res.correction_is_correct === true,
                correctionCount: Number(res.correction_count || correctionNumber),
                baseProgressCompleted: Number(res.base_progress_completed ?? this.data.baseProgressCompleted),
                baseProgressTotal: Number(res.base_progress_total ?? this.data.baseProgressTotal),
                remediationProgressCompleted: Number(res.remediation_progress_completed ?? this.data.remediationProgressCompleted),
                remediationProgressTotal: Number(res.remediation_progress_total ?? this.data.remediationProgressTotal),
                remediationAllocatedTotal: Number(res.remediation_allocated_total ?? res.remediation_progress_total ?? this.data.remediationAllocatedTotal),
                remediationBudgetTotal: Number(res.remediation_budget_total ?? this.data.remediationBudgetTotal),
                remediationPendingCount: Number(res.remediation_pending_count ?? 0),
                deferredReviewCount: Number(res.deferred_review_count ?? 0)
            })
        }).catch((err) => {
            if (err && err.pageUnloaded) return
            console.warn('submit vocabulary correction failed', err)
            this.setData({ correctionSubmitting: false })
            if (this.handleMutationError(err)) {
                return
            } else if (err && ['state_conflict', 'correction_not_current', 'queue_changed'].indexOf(err.message) >= 0) {
                this.fetchQueue()
            } else {
                wx.showToast({ title: '纠正未保存，请重试', icon: 'none' })
            }
        })
    },

    correctionRequestData(question, answer, attemptId) {
        return {
            queue_token: this.data.queueToken,
            learning_question_id: question.learning_question_id,
            queue_item_id: question.queue_item_id,
            question_id: question.question_id,
            word_id: question.word_id,
            sense_id: question.sense_id,
            dimension: question.dimension,
            answer,
            attempt_id: attemptId
        }
    },

    submitAnswerAppeal() {
        const question = this.data.currentQuestion || {}
        const answer = String(this.data.submittedAnswer || '').trim()
        if (
            !this.data.showResult
            || this.data.isCorrect
            || this.data.responseKind === 'forgot'
            || this.data.appealSubmitting
            || this.data.appealSubmitted
            || question.mode === 'context_choice'
            || !question.word_id
            || !answer
        ) return
        wx.showModal({
            title: '申请人工复核',
            content: `你的答案“${answer}”将提交给老师审核。`,
            confirmText: '提交申诉',
            success: (modalRes) => {
                if (!modalRes.confirm || !this.isLearningPageActive()) return
                this.setData({ appealSubmitting: true })
                this.requestWithDeadline(() => request('/dictation/appeals', {
                    method: 'POST',
                    timeout: LEARNING_MUTATION_TIMEOUT_MS,
                    data: {
                        word_id: question.word_id,
                        task_id: Number(this.data.taskId),
                        answer,
                        mode: question.mode
                    }
                }), LEARNING_MUTATION_TIMEOUT_MS, 'learning_appeal').then((res) => {
                    if (!this.isLearningPageActive()) return
                    if (res && res.ok) {
                        this.setData({ appealSubmitting: false, appealSubmitted: true })
                        wx.showToast({ title: '已提交人工审核', icon: 'none' })
                        return
                    }
                    const title = res && res.error === 'answer_already_accepted'
                        ? '该答案现已可接受'
                        : '申诉提交失败'
                    this.setData({ appealSubmitting: false })
                    wx.showToast({ title, icon: 'none' })
                }).catch((err) => {
                    if (err && err.pageUnloaded) return
                    if (!this.isLearningPageActive()) return
                    this.setData({ appealSubmitting: false })
                    wx.showToast({ title: '网络错误', icon: 'none' })
                })
            }
        })
    },

    playAudio(options) {
        options = options || {}
        if (!this.isLearningPageActive()) return
        const question = this.data.currentQuestion || {}
        const prompt = question.question && question.question.prompt
        const familiarity = this.familiarityItem() || {}
        const feedback = this.data.answerFeedback || {}
        const sources = this.data.showResult
            ? [feedback.audio_url, feedback.audio_tts_url]
            : (this.data.phase === 'familiarity'
                ? this.familiarityAudioSources(familiarity)
                : [prompt && prompt.audio_url, prompt && prompt.audio_tts_url])
        const validSources = sources.filter(Boolean)
        if (!this.audioPlayer || !validSources.length) {
            wx.showToast({ title: '当前单词暂无发音', icon: 'none' })
            return
        }
        if (this._learningTrace && !options.auto) {
            this._learningTrace.mark('audio_click', { source: validSources[0] })
        }
        this.audioPlayer.play(validSources, app.globalData.baseUrl)
    },

    playForgotAudio(event) {
        const index = Number(event && event.currentTarget && event.currentTarget.dataset && event.currentTarget.dataset.index)
        const item = this.data.forgotItems[index]
        if (!this.isLearningPageActive() || !item) return
        if (!this.audioPlayer || !item.audioSources.length) {
            wx.showToast({ title: '当前单词暂无发音', icon: 'none' })
            return
        }
        this.audioPlayer.play(item.audioSources, app.globalData.baseUrl)
    },

    finishTask() {
        if (this.data.readOnly || this.data.finishing || this.data.finished) return
        this.setData({ finishing: true })
        return this.requestWithDeadline(() => request(`/miniprogram/student/tasks/${this.data.taskId}/submit`, {
            method: 'POST',
            timeout: LEARNING_MUTATION_TIMEOUT_MS,
            data: {
                queue_token: this.data.queueToken,
                duration_seconds: this.data.startedAt
                    ? Math.max(0, Math.floor((Date.now() - this.data.startedAt) / 1000))
                    : 0
            }
        }), LEARNING_MUTATION_TIMEOUT_MS, 'learning_finalize').then((res) => {
            if (!this.isLearningPageActive()) return
            if (!res || !res.ok) throw new Error((res && res.error) || 'vocabulary_group_finalize_failed')
            const rows = Array.isArray(res.forgot_items) ? res.forgot_items : this.data.forgotItems
            this.setData({
                finishing: false,
                finished: true,
                result: res,
                forgotItems: forgotItemsForDisplay(rows),
                forgotCount: forgotCountFromResponse(res, 'forgotten_count', rows)
            })
        }).catch((err) => {
            if (err && err.pageUnloaded) return
            console.warn('finalize vocabulary group failed', err)
            this.setData({ finishing: false })
            if (shouldRecoverLearningAnswer(err) || (err && err.error === 'task_already_completed')) {
                return this.recoverLearningSettlement()
            }
            if (!this.handleMutationError(err)) wx.showToast({ title: '任务结算失败，请重试', icon: 'none' })
        })
    },

    recoverLearningSettlement() {
        return this.requestWithDeadline(
            () => request(this.queueUrl(), { timeout: LEARNING_LOAD_TIMEOUT_MS }),
            LEARNING_LOAD_TIMEOUT_MS,
            'learning_finalize_recovery'
        ).then((queue) => {
            if (!this.isLearningPageActive()) return false
            if (!queue || !queue.ok || String(queue.task_id) !== String(this.data.taskId)) {
                throw new Error('learning_finalize_recovery_failed')
            }
            if (!queue.settlement) {
                wx.showToast({ title: '任务结算未确认，请重试', icon: 'none' })
                return false
            }
            const settlement = queue.settlement
            const rows = Array.isArray(settlement.forgot_items) ? settlement.forgot_items : queue.forgot_items
            this.setData({
                finished: true,
                result: settlement,
                forgotItems: forgotItemsForDisplay(rows),
                forgotCount: forgotCountFromResponse(settlement, 'forgotten_count', rows)
            })
            return true
        }).catch((err) => {
            if (err && err.pageUnloaded) return false
            console.warn('recover vocabulary group settlement failed', err)
            if (this.isLearningPageActive()) wx.showToast({ title: '任务结算未确认，请重试', icon: 'none' })
            return false
        })
    },

    retry() {
        return this.fetchTaskAccess()
    },

    exitPage() {
        wx.switchTab({ url: '/pages/student/home/index' })
    }
})
