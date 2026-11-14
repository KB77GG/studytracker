const app = getApp()
const { request } = require('../../../utils/request.js')
const { createReliableAudioPlayer } = require('../../../utils/dictation-audio.js')
const {
    buildReviewAttemptId,
    buildReviewCorrectionAttemptId,
    classifyReviewAnswerFailure,
    answeredReviewItem,
    correctedReviewItem,
    findReviewItem,
    mergeAnswerResult
} = require('../../../utils/vocabulary-review-submit.js')
const {
    buildMeaningChoiceOptions,
    contextCorrectionSubmissionValue,
    safeAnswerDisplay,
    selectedOptionLabel
} = require('../../../utils/vocabulary-interaction.js')
const { normalizeAnswerFeedback } = require('../../../utils/vocabulary-feedback.js')
const { createVocabularyPerformanceTracker } = require('../../../utils/vocabulary-performance.js')
const { normalizeReviewQueue } = require('../../../utils/vocabulary-review-normalize.js')
const { forgotCountFromResponse, forgotItemsForDisplay, isForgotResponse, matchesAnswerEvent } = require('../../../utils/vocabulary-forgot.js')

const DIMENSION_LABELS = {
    meaning_recall: '词义提取',
    form_recall: '词形提取',
    audio_form_recall: '听音辨形',
    context_use: '语境运用'
}

const REVIEW_SUBMIT_TIMEOUT_MS = 15000
const REVIEW_RECOVERY_REQUEST_TIMEOUT_MS = 5000
const REVIEW_RECOVERY_DEADLINE_MS = 8000
const REVIEW_LOAD_TIMEOUT_MS = 10000
const PENDING_SETTLEMENT_KEY = 'vocabulary-review-pending-settlement-v1'
const PENDING_SETTLEMENT_MAX_AGE_MS = 7 * 24 * 60 * 60 * 1000

Page({
    data: {
        loading: true,
        loadError: '',
        empty: false,
        sessionId: null,
        sessionToken: '',
        queueToken: '',
        supportsForgotResponse: false,
        returningToTask: false,
        currentIndex: 0,
        totalCount: 0,
        answeredCount: 0,
        currentItem: null,
        answerRenderEpoch: 0,
        inputValue: '',
        selectedOption: '',
        meaningOptions: [],
        isMeaningChoice: false,
        audioState: 'idle',
        audioButtonLabel: '播放发音',
        currentDimensionLabel: '',
        stageLabel: '',
        showResult: false,
        isCorrect: false,
        correctAnswer: '',
        submittedAnswer: '',
        responseKind: 'answer',
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
        submitting: false,
        settling: false,
        finished: false,
        result: null,
        forgotItems: [],
        forgotCount: 0,
        remainingDueCount: 0,
        traceId: ''
    },

    onLoad(options) {
        options = options || {}
        this._reviewPageActive = true
        this._reviewQueue = []
        this._reviewSkippedItems = []
        this._reviewCurrentIndex = 0
        this._reviewTrace = createVocabularyPerformanceTracker(wx)
        this._reviewTrace.mark('navigation_start')
        this._reviewTrace.mark('page_onLoad')
        this.setData({ traceId: this._reviewTrace.traceId })
        const rawReturnTaskId = String(options.returnTaskId || options.originTaskId || '')
        this.returnTaskId = /^\d+$/.test(rawReturnTaskId) ? rawReturnTaskId : ''
        this.setData({ returningToTask: !!this.returnTaskId })
        this.audioPlayer = createReliableAudioPlayer(wx, {
            onStateChange: (state) => {
                if (this._reviewPageActive === false) return
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
                if (this._reviewTrace) this._reviewTrace.mark(name, detail)
            },
            onError: (error) => {
                if (this._reviewTrace) this._reviewTrace.mark('audio_error', error)
                if (this._reviewPageActive !== false) {
                    wx.showToast({ title: '音频播放失败，请重试', icon: 'none' })
                }
            }
        })
        const pendingSettlement = this.readPendingSettlement()
        if (pendingSettlement) this.resumePendingSettlement(pendingSettlement)
        else this.fetchSession()
    },

    onUnload() {
        this._reviewPageActive = false
        this.cancelReviewDeadlines()
        if (this.returnTimer) {
            clearTimeout(this.returnTimer)
            this.returnTimer = null
        }
        if (this.audioPlayer) this.audioPlayer.destroy()
        this.audioPlayer = null
        this._reviewQueue = []
    },

    isReviewPageActive() {
        return this._reviewPageActive !== false
    },

    noop() {},

    queueItems() {
        // `data.items` is accepted only as a test harness compatibility shim;
        // production data never declares or mutates that reactive field.
        return Array.isArray(this._reviewQueue)
            ? this._reviewQueue
            : (Array.isArray(this.data.items) ? this.data.items : [])
    },

    setReviewQueue(rawItems) {
        const normalized = normalizeReviewQueue(rawItems)
        this._reviewQueue = normalized.items
        this._reviewSkippedItems = normalized.skipped_items || []
        if (this._reviewTrace) {
            this._reviewTrace.setMetric('returned_items', normalized.items.length)
            this._reviewTrace.setMetric('skipped_items', normalized.skipped)
            Object.keys(normalized.reasons).forEach((reason) => {
                this._reviewTrace.setMetric(`skipped_${reason}`, normalized.reasons[reason])
            })
        }
        return normalized
    },

    updateQueueItem(index, updatedItem) {
        if (!Array.isArray(this._reviewQueue) || !this._reviewQueue[index]) return
        this._reviewQueue[index] = updatedItem
    },

    queueItemAt(index) {
        return this.queueItems()[index] || null
    },

    reviewIdentity() {
        const user = app.globalData.userInfo || {}
        const userId = user.id || user.user_id
        const token = app.globalData.token || (typeof wx.getStorageSync === 'function' ? wx.getStorageSync('token') : '')
        if (!token) return ''
        const source = userId ? `user:${userId}` : `token:${token}`
        let hash = 2166136261
        for (let index = 0; index < source.length; index += 1) {
            hash ^= source.charCodeAt(index)
            hash = Math.imul(hash, 16777619)
        }
        return String(hash >>> 0)
    },

    readPendingSettlement() {
        if (typeof wx.getStorageSync !== 'function') return null
        let marker
        try { marker = wx.getStorageSync(PENDING_SETTLEMENT_KEY) } catch (_err) { return null }
        if (!marker || typeof marker !== 'object') return null
        if (!marker.sessionId || !marker.sessionToken || !marker.identity
            || marker.identity !== this.reviewIdentity()
            || Date.now() - Number(marker.createdAt) > PENDING_SETTLEMENT_MAX_AGE_MS) {
            this.clearPendingSettlement()
            return null
        }
        return marker
    },

    savePendingSettlement() {
        const identity = this.reviewIdentity()
        if (!identity || !this.data.sessionId || !this.data.sessionToken || typeof wx.setStorageSync !== 'function') return
        try {
            wx.setStorageSync(PENDING_SETTLEMENT_KEY, {
                sessionId: this.data.sessionId,
                sessionToken: this.data.sessionToken,
                identity,
                createdAt: Date.now()
            })
        } catch (_err) { /* The exact-session recovery in this page still works. */ }
    },

    clearPendingSettlement() {
        if (typeof wx.removeStorageSync !== 'function') return
        try { wx.removeStorageSync(PENDING_SETTLEMENT_KEY) } catch (_err) { /* Storage can be unavailable. */ }
    },

    resumePendingSettlement(marker) {
        const token = encodeURIComponent(marker.sessionToken)
        const url = `/miniprogram/student/vocabulary-review/sessions/${marker.sessionId}?session_token=${token}`
        this.setData({ loading: true, loadError: '' })
        return this.requestWithDeadline(
            () => request(url, { timeout: REVIEW_LOAD_TIMEOUT_MS }),
            REVIEW_LOAD_TIMEOUT_MS,
            'review_pending_settlement'
        ).then((res) => {
            if (!this.isReviewPageActive()) return
            if (!res || !res.ok || String(res.session_id) !== String(marker.sessionId)) {
                throw new Error('review_pending_settlement_failed')
            }
            if (this.applySettledSession(res)) {
                this.clearPendingSettlement()
                return
            }
            this.applySessionSnapshot(res)
            wx.showToast({ title: '已恢复原复习批次', icon: 'none' })
        }).catch((err) => {
            if (!this.isReviewPageActive() || (err && err.pageUnloaded)) return
            console.warn('restore pending vocabulary review settlement failed', err)
            this.setData({ loading: false, loadError: '原复习批次状态未确认，请重试' })
        })
    },

    requestWithDeadline(factory, timeoutMs, timeoutLabel) {
        if (!this.isReviewPageActive()) {
            return Promise.reject({ errMsg: 'request:fail abort', pageUnloaded: true })
        }
        const deadlineMs = Math.max(1, Number(timeoutMs) || 1)
        if (!this._reviewDeadlineTimers) this._reviewDeadlineTimers = new Set()
        return new Promise((resolve, reject) => {
            let settled = false
            const entry = { timerId: null, cancel: null }
            const settle = (handler, value) => {
                if (settled) return
                settled = true
                if (entry.timerId !== null) clearTimeout(entry.timerId)
                this._reviewDeadlineTimers.delete(entry)
                handler(value)
            }
            entry.cancel = () => settle(reject, {
                errMsg: 'request:fail abort',
                pageUnloaded: true
            })
            entry.timerId = setTimeout(() => settle(reject, {
                errMsg: `request:fail timeout (${timeoutLabel || 'review_request'})`,
                deadline: true
            }), deadlineMs)
            this._reviewDeadlineTimers.add(entry)
            Promise.resolve().then(() => {
                if (!this.isReviewPageActive()) {
                    throw { errMsg: 'request:fail abort', pageUnloaded: true }
                }
                return factory()
            }).then(
                (value) => settle(resolve, value),
                (error) => settle(reject, error)
            )
        })
    },

    cancelReviewDeadlines() {
        if (!this._reviewDeadlineTimers) return
        Array.from(this._reviewDeadlineTimers).forEach((entry) => entry.cancel())
    },

    fetchSession() {
        this.setData({ loading: true, loadError: '' })
        const url = `/miniprogram/student/vocabulary-review/today${this.sessionQuery()}`
        if (this._reviewTrace) this._reviewTrace.mark('request_start', { endpoint: 'today' })
        return this.requestWithDeadline(
            () => request(url, { timeout: REVIEW_LOAD_TIMEOUT_MS }),
            REVIEW_LOAD_TIMEOUT_MS,
            'review_load'
        )
            .then((res) => {
                if (!this.isReviewPageActive()) return
                if (this._reviewTrace) {
                    this._reviewTrace.setMetric('response_bytes', this._reviewTrace.estimateBytes(res))
                    this._reviewTrace.mark('request_end', {
                        endpoint: 'today',
                        ok: !!(res && res.ok),
                        response_bytes: this._reviewTrace.estimateBytes(res)
                    })
                    this._reviewTrace.mark('response_parse_end')
                }
                if (!res || !res.ok) throw new Error((res && res.error) || 'review_load_failed')
                if (res.status === 'settled' && res.settlement) {
                    this.applySettledSession(res)
                    return
                }
                const rawItems = Array.isArray(res.items) ? res.items : []
                const normalized = this.setReviewQueue(rawItems)
                if (this._reviewTrace) this._reviewTrace.mark('normalize_end')
                if (rawItems.length && !normalized.items.length) throw new Error('review_items_invalid')
                const items = normalized.items
                const firstUnanswered = items.findIndex((item) => !item.first_attempt_id || item.correction_required)
                const resumeIndex = firstUnanswered >= 0
                    ? firstUnanswered
                    : Math.max(0, items.length - 1)
                const answeredCount = items.filter((item) => item.first_attempt_id && !item.correction_required).length
                if (this._reviewTrace) {
                    this._reviewTrace.setMetric('due_total', Number(res.due_count || 0))
                    this._reviewTrace.setMetric('actual_session_items', items.length)
                    this._reviewTrace.mark('scheduler_end', {
                        due_total: Number(res.due_count || 0),
                        actual_session_items: items.length
                    })
                }
                this.setData({
                    loading: false,
                    empty: !!res.empty || items.length === 0,
                    sessionId: res.session_id || null,
                    sessionToken: res.session_token || '',
                    queueToken: res.queue_token || '',
                    supportsForgotResponse: res.supports_forgot_response === true,
                    totalCount: items.length,
                    answeredCount,
                    remainingDueCount: Number(res.remaining_due_count || 0),
                    currentIndex: resumeIndex,
                    finished: false
                }, () => {
                    if (!this.isReviewPageActive()) return
                    if (this._reviewTrace) {
                        const firstSetDataBytes = this._reviewTrace.estimateBytes({
                            totalCount: items.length,
                            currentIndex: resumeIndex,
                            currentItem: items[resumeIndex] || null
                        })
                        this._reviewTrace.setMetric('first_set_data_bytes', firstSetDataBytes)
                        this._reviewTrace.mark('first_setData_end', {
                            first_set_data_bytes: firstSetDataBytes
                        })
                        this._reviewTrace.mark('first_interactive')
                    }
                    if (!items.length) return
                    this.showItem(resumeIndex)
                    if (firstUnanswered < 0) this.settle()
                })
            })
            .catch((err) => {
                if (err && err.pageUnloaded) return
                console.warn('load autonomous vocabulary review failed', err)
                if (this._reviewTrace) {
                    this._reviewTrace.mark('request_end', { endpoint: 'today', ok: false, error: 'review_load_failed' })
                    this._reviewTrace.setMetric('error_load', 1)
                }
                this.setData({ loading: false, loadError: `复习队列加载失败，请重试（${this._reviewTrace ? this._reviewTrace.traceId : '稍后'}）` })
            })
    },

    showItem(index, options) {
        options = options || {}
        const item = this.queueItemAt(index)
        if (!item) return
        const answered = !!item.first_attempt_id
        const correctionRequired = !!item.correction_required
        const isMeaningChoice = item.mode === 'audio_to_zh'
        const meaningOptions = isMeaningChoice
            ? buildMeaningChoiceOptions(item, [])
            : []
        const answerFeedback = answered
            ? normalizeAnswerFeedback({ answer_feedback: item.answer_feedback })
            : null
        const answerOptions = this.answerOptions(item)
        this.setData({
            currentIndex: index,
            currentItem: item,
            answerRenderEpoch: Number(this.data.answerRenderEpoch || 0) + 1,
            stageLabel: `阶段 ${Number(item.stage || 0) + 1}`,
            inputValue: answered && item.first_answer ? item.first_answer : (options.inputValue || ''),
            selectedOption: answered ? (item.revealed_answer_option_id || '') : (options.selectedOption || ''),
            meaningOptions,
            isMeaningChoice,
            currentDimensionLabel: DIMENSION_LABELS[item.dimension] || '词汇复习',
            showResult: answered,
            isCorrect: !!item.first_is_correct,
            correctAnswer: answered
                ? safeAnswerDisplay(item.revealed_answer_option_id || item.revealed_answer, answerOptions, '暂无法显示正确答案')
                : '',
            submittedAnswer: answered
                ? (isForgotResponse(item) ? '忘了' : safeAnswerDisplay(item.first_answer, answerOptions))
                : '',
            responseKind: isForgotResponse(item) ? 'forgot' : 'answer',
            answerFeedback,
            correctionRequired,
            correctionCompleted: answered && !correctionRequired && !isForgotResponse(item),
            correctionInputValue: '',
            correctionPlaceholder: this.correctionPlaceholder(item),
            correctionPrompt: this.correctionPrompt(item),
            correctionHasInput: false,
            correctionSubmitting: false,
            correctionIsCorrect: item.correction_is_correct === true,
            correctionCount: Number(item.correction_count || 0),
            correctionMaxAttempts: Number(item.correction_max_attempts || 2),
            correctionExhausted: !!item.correction_exhausted
        }, () => {
            if (!this.isReviewPageActive()) return
            if (this._reviewTrace) {
                this._reviewTrace.mark(index === 0 ? 'first_visible' : 'next_word_visible', {
                    index,
                    total_count: this.queueItems().length
                })
                this._reviewTrace.mark('first_interactive', { index })
                this._reviewTrace.logSnapshot(index === 0 ? 'review_first_visible' : 'review_word_visible')
            }
            if (String(item.mode || '').indexOf('audio_to_') === 0) this.playAudio({ auto: true })
            this.preloadUpcomingAudio(index)
            if (typeof options.onShown === 'function') options.onShown()
        })
    },

    onInput(e) {
        if (this.data.showResult) return
        const item = this.data.currentItem
        if (!item || !matchesAnswerEvent(e, item, 'reviewItemId',
            item.review_item_id, this.data.answerRenderEpoch)) return
        this.setData({ inputValue: (e && e.detail && e.detail.value) || '' })
    },

    answerOptions(item) {
        const snapshot = item && item.question
        return snapshot && Array.isArray(snapshot.options) ? snapshot.options : []
    },

    correctionPlaceholder(item) {
        const mode = String(item && item.mode || '')
        return mode === 'en_to_zh' || mode === 'audio_to_zh'
            ? '请重新输入正确释义'
            : '请重新输入正确单词'
    },

    correctionPrompt(item) {
        const mode = String(item && item.mode || '')
        if (mode === 'context_choice') {
            const prompt = item && item.question && item.question.prompt
            const target = String(prompt && prompt.target_word || '').trim()
            return target ? `请重新输入目标词“${target}”` : '请重新输入目标词'
        }
        return this.correctionPlaceholder(item)
    },

    audioSourcesForItem(item) {
        const prompt = item && item.question && item.question.prompt
        return [
            prompt && prompt.audio_url,
            prompt && prompt.audio_tts_url,
            item && item.audio_url,
            item && item.audio_tts_url
        ].filter(Boolean)
    },

    preloadUpcomingAudio(index) {
        if (!this.audioPlayer || typeof this.audioPlayer.preload !== 'function') return
        const sources = []
        this.queueItems().slice(index, index + 3).forEach((item) => {
            const itemSources = this.audioSourcesForItem(item)
            if (itemSources.length) sources.push(itemSources[0])
        })
        if (this._reviewTrace) {
            const stats = typeof this.audioPlayer.stats === 'function'
                ? this.audioPlayer.stats()
                : null
            this._reviewTrace.setMetric(
                'audio_cache_limit',
                Number(this.audioPlayer.maxCacheEntries) || 3
            )
            this._reviewTrace.setMetric('audio_preload_candidates', sources.length)
            if (stats && Number.isFinite(stats.maxConcurrentPreloadDownloads)) {
                this._reviewTrace.setMetric(
                    'audio_preload_max_concurrent',
                    stats.maxConcurrentPreloadDownloads
                )
            }
            if (stats && Number.isFinite(stats.maxConcurrentDownloads)) {
                this._reviewTrace.setMetric(
                    'audio_download_max_concurrent',
                    stats.maxConcurrentDownloads
                )
            }
        }
        if (!sources.length) return
        const preloadResult = this.audioPlayer.preload(sources, app.globalData.baseUrl)
        if (!preloadResult || typeof preloadResult.then !== 'function') return
        preloadResult.then(() => {
            if (!this.isReviewPageActive() || !this._reviewTrace) return
            const stats = typeof this.audioPlayer.stats === 'function'
                ? this.audioPlayer.stats()
                : null
            if (!stats) return
            this._reviewTrace.setMetric('audio_cache_entries', stats.cacheEntries)
            this._reviewTrace.setMetric('audio_inflight_downloads', stats.inflightDownloads)
            if (Number.isFinite(stats.maxConcurrentPreloadDownloads)) {
                this._reviewTrace.setMetric(
                    'audio_preload_max_concurrent',
                    stats.maxConcurrentPreloadDownloads
                )
            }
            if (Number.isFinite(stats.maxConcurrentDownloads)) {
                this._reviewTrace.setMetric(
                    'audio_download_max_concurrent',
                    stats.maxConcurrentDownloads
                )
            }
            this._reviewTrace.logSnapshot('review_audio_preload')
        }).catch(() => {})
    },

    selectOption(e) {
        if (this.data.showResult) return
        const item = this.data.currentItem
        if (!item || !matchesAnswerEvent(e, item, 'reviewItemId',
            item.review_item_id, this.data.answerRenderEpoch)) return
        const optionId = e && e.currentTarget && e.currentTarget.dataset && e.currentTarget.dataset.id
        if (optionId) this.setData({ selectedOption: String(optionId) })
    },

    onCorrectionInput(e) {
        if (!this.data.correctionRequired || this.data.correctionSubmitting) return
        const value = (e && e.detail && e.detail.value) || ''
        this.setData({
            correctionInputValue: value,
            correctionHasInput: String(value).trim().length > 0
        })
    },

    answerValue() {
        const item = this.data.currentItem || {}
        if (item.mode === 'context_choice') return this.data.selectedOption
        if (this.data.isMeaningChoice) {
            return selectedOptionLabel(this.data.meaningOptions, this.data.selectedOption)
        }
        return String(this.data.inputValue || '').trim()
    },

    correctionValue() {
        return String(this.data.correctionInputValue || '').trim()
    },

    applyAnswerResult(item, res, answer) {
        const updatedItem = mergeAnswerResult(item, res, answer)
        const responseFeedback = {
            answer_feedback: res.answer_feedback
        }
        const answerFeedback = normalizeAnswerFeedback({
            answer_feedback: responseFeedback.answer_feedback || updatedItem.answer_feedback
        })
        this.updateQueueItem(this.data.currentIndex, updatedItem)
        this.setData({
            currentItem: updatedItem,
            answeredCount: this.queueItems().filter((candidate) => candidate.first_attempt_id && !candidate.correction_required).length,
            showResult: true,
            isCorrect: !!updatedItem.first_is_correct,
            submittedAnswer: isForgotResponse(updatedItem)
                ? '忘了'
                : safeAnswerDisplay(updatedItem.first_answer, this.answerOptions(updatedItem)),
            responseKind: isForgotResponse(updatedItem) ? 'forgot' : 'answer',
            correctAnswer: safeAnswerDisplay(
                updatedItem.revealed_answer_option_id || updatedItem.revealed_answer,
                this.answerOptions(updatedItem),
                '暂无法显示正确答案'
            ),
            answerFeedback,
            correctionRequired: !!updatedItem.correction_required,
            correctionCompleted: !updatedItem.correction_required && !isForgotResponse(updatedItem),
            correctionIsCorrect: updatedItem.correction_is_correct === true,
            correctionCount: Number(updatedItem.correction_count || 0),
            correctionMaxAttempts: Number(updatedItem.correction_max_attempts || 2),
            correctionExhausted: !!updatedItem.correction_exhausted
        })
    },

    sessionQuery() {
        return this.returnTaskId ? `?origin_task_id=${encodeURIComponent(this.returnTaskId)}` : ''
    },

    requestCurrentSessionSnapshot() {
        const recoveryDeadlineMs = Math.max(
            1,
            Number(this.reviewRecoveryDeadlineMs) || REVIEW_RECOVERY_DEADLINE_MS
        )
        const recoveryDeadlineAt = Date.now() + recoveryDeadlineMs
        const requestSnapshot = (url) => {
            if (!this.isReviewPageActive()) {
                return Promise.reject({ errMsg: 'request:fail abort', pageUnloaded: true })
            }
            const remainingMs = recoveryDeadlineAt - Date.now()
            if (remainingMs <= 0) {
                return Promise.reject({ errMsg: 'request:fail timeout', deadline: true })
            }
            const requestTimeoutMs = Math.max(
                1,
                Math.min(
                    Number(this.reviewRecoveryRequestTimeoutMs) || REVIEW_RECOVERY_REQUEST_TIMEOUT_MS,
                    remainingMs
                )
            )
            return this.requestWithDeadline(
                () => request(url, { timeout: requestTimeoutMs }),
                remainingMs,
                'review_recovery'
            )
        }
        if (this.data.sessionId && this.data.sessionToken) {
            const token = encodeURIComponent(this.data.sessionToken)
            return requestSnapshot(
                `/miniprogram/student/vocabulary-review/sessions/${this.data.sessionId}?session_token=${token}`
            )
        }
        return Promise.reject(new Error('review_session_identity_missing'))
    },

    applySettledSession(res) {
        if (!res || res.status !== 'settled' || !res.settlement) return false
        const settled = res.settlement
        const pending = this.readPendingSettlement()
        if (pending && String(pending.sessionId) === String(res.session_id)) this.clearPendingSettlement()
        if (Array.isArray(res.items)) this.setReviewQueue(res.items)
        this.setData({
            loading: false,
            empty: false,
            sessionId: res.session_id || this.data.sessionId,
            sessionToken: res.session_token || this.data.sessionToken,
            supportsForgotResponse: res.supports_forgot_response === true,
            totalCount: this.queueItems().length,
            remainingDueCount: Number(settled.remaining_due_count || 0),
            finished: true,
            settling: false,
            submitting: false,
            result: settled,
            forgotCount: forgotCountFromResponse(settled, 'forgot_count', settled.forgot_items),
            forgotItems: forgotItemsForDisplay(settled.forgot_items)
        })
        return true
    },

    applySessionSnapshot(res, preferredReviewItemId, showOptions) {
        if (this.applySettledSession(res)) return null
        const rawItems = Array.isArray(res && res.items) ? res.items : []
        const normalized = this.setReviewQueue(rawItems)
        const items = normalized.items
        if (rawItems.length && !items.length) {
            this.setData({
                loading: false,
                empty: false,
                loadError: `复习队列数据异常，请重试（${this._reviewTrace ? this._reviewTrace.traceId : '稍后'}）`
            })
            return null
        }
        const preferredIndex = items.findIndex(
            (candidate) => String(candidate && candidate.review_item_id) === String(preferredReviewItemId)
        )
        const firstUnanswered = items.findIndex((item) => !item.first_attempt_id || item.correction_required)
        const resumeIndex = preferredIndex >= 0
            ? preferredIndex
            : (firstUnanswered >= 0 ? firstUnanswered : Math.max(0, items.length - 1))
        this.setData({
            loading: false,
            empty: !!(res && res.empty) || items.length === 0,
            sessionId: (res && res.session_id) || this.data.sessionId || null,
            sessionToken: (res && res.session_token) || this.data.sessionToken || '',
            queueToken: (res && res.queue_token) || this.data.queueToken || '',
            supportsForgotResponse: res && res.supports_forgot_response === true,
            totalCount: items.length,
            answeredCount: items.filter((item) => item.first_attempt_id && !item.correction_required).length,
            remainingDueCount: Number((res && res.remaining_due_count) || 0),
            currentIndex: resumeIndex,
            finished: false
        }, () => {
            if (items.length) this.showItem(resumeIndex, showOptions)
            else this.setData({
                currentItem: null,
                inputValue: '',
                selectedOption: '',
                meaningOptions: [],
                isMeaningChoice: false,
                showResult: false,
                isCorrect: false,
                correctAnswer: '',
                submittedAnswer: '',
                answerFeedback: null,
                responseKind: 'answer'
            })
        })
        return items[resumeIndex] || null
    },

    recoverSubmittedAnswer(pending, failure) {
        if (!this.isReviewPageActive()) return Promise.resolve(false)
        return this.requestCurrentSessionSnapshot().then((res) => {
            if (!res || !res.ok) throw (res || new Error('review_recovery_failed'))
            if (String(res.session_id) !== String(this.data.sessionId)) {
                throw new Error('review_recovery_session_changed')
            }
            if (this.applySettledSession(res)) return true
            const snapshotItems = normalizeReviewQueue(res.items).items
            const recoveredItem = findReviewItem(snapshotItems, pending.reviewItemId)
            const savedItem = pending.kind === 'correction'
                ? correctedReviewItem(snapshotItems, pending.reviewItemId, pending.attemptId)
                : answeredReviewItem(snapshotItems, pending.reviewItemId)
            this.applySessionSnapshot(
                res,
                pending.reviewItemId,
                recoveredItem && !savedItem ? {
                    inputValue: pending.answer,
                    selectedOption: pending.selectedOption
                } : {}
            )
            if (savedItem) {
                wx.showToast({
                    title: pending.kind === 'correction'
                        ? (savedItem.correction_attempt_id === pending.attemptId ? '纠正已保存' : '已恢复本题结果')
                        : (savedItem.first_attempt_id === pending.attemptId ? '答案已保存' : '已恢复本题结果'),
                    icon: 'none'
                })
                return true
            }
            if (!recoveredItem) {
                wx.showToast({ title: '复习队列已更新，请检查下一题', icon: 'none' })
                return false
            }
            wx.showToast({
                title: failure.uncertain ? '未确认保存，请重试' : failure.message,
                icon: 'none'
            })
            return false
        }).catch((err) => {
            console.warn('recover autonomous vocabulary review answer failed', err)
            if (!this.isReviewPageActive()) return false
            wx.showToast({
                title: failure.uncertain ? '提交结果未确认，请重试' : failure.message,
                icon: 'none'
            })
            return false
        })
    },

    handleSubmitFailure(err, pending) {
        if (!this.isReviewPageActive()) return Promise.resolve(false)
        const failure = classifyReviewAnswerFailure(err)
        if (failure.recoverable) {
            if (failure.message) wx.showToast({ title: failure.message, icon: 'none' })
            return this.recoverSubmittedAnswer(pending, failure)
        }
        wx.showToast({ title: failure.message, icon: 'none' })
        return Promise.resolve(false)
    },

    submitAnswer(event) {
        return this.submitResponse('answer', event)
    },

    submitForgot(event) {
        return this.submitResponse('forgot', event)
    },

    submitResponse(responseKind, event) {
        const item = this.data.currentItem
        if (!item) return
        if (!matchesAnswerEvent(event, item, 'reviewItemId',
            item.review_item_id, this.data.answerRenderEpoch)) return
        if (this.data.showResult) {
            if (responseKind !== 'answer' || this.data.responseKind === 'forgot' || this.data.correctionRequired) return
            this.nextItem()
            return
        }
        if (this.data.submitting || this.data.correctionSubmitting || this.data.settling || this.data.finished) return
        if (responseKind === 'forgot' && !this.data.supportsForgotResponse) return
        const answer = this.answerValue()
        if (responseKind !== 'forgot' && !answer) {
            wx.showToast({
                title: item.mode === 'context_choice' || this.data.isMeaningChoice
                    ? '请选择答案'
                    : '请输入答案',
                icon: 'none'
            })
            return
        }
        this.setData({ submitting: true })
        const answerRequestUrl = `/miniprogram/student/vocabulary-review/sessions/${this.data.sessionId}/answers`
        const attemptId = buildReviewAttemptId(this.data.sessionId, item.review_item_id)
        const pending = {
            attemptId,
            reviewItemId: item.review_item_id,
            answer,
            selectedOption: this.data.selectedOption,
            kind: 'first',
            responseKind
        }
        const postData = {
            session_token: this.data.sessionToken,
            review_item_id: item.review_item_id,
            question_id: item.question_id,
            word_id: item.word_id,
            sense_id: item.sense_id,
            dimension: item.dimension,
            answer,
            attempt_id: attemptId,
            supports_correction: true,
            input_mode: 'native'
        }
        if (responseKind === 'forgot') postData.response_kind = 'forgot'
        return this.requestWithDeadline(() => request(answerRequestUrl, {
            method: 'POST',
            timeout: 15000,
            data: postData
        }), this.reviewSubmitDeadlineMs || REVIEW_SUBMIT_TIMEOUT_MS, 'review_submit').then((res) => {
            if (!this.isReviewPageActive()) return
            if (!res || !res.ok) throw (res || new Error('review_answer_failed'))
            this.applyAnswerResult(item, res, answer)
        }).catch((err) => {
            console.warn('submit autonomous vocabulary review failed', err)
            return this.handleSubmitFailure(err, pending)
        }).finally(() => {
            if (this.isReviewPageActive()) this.setData({ submitting: false })
        })
    },

    submitCorrection() {
        const item = this.data.currentItem
        if (!item || !this.data.correctionRequired || this.data.correctionSubmitting) return
        const typedAnswer = this.correctionValue()
        if (!typedAnswer) {
            wx.showToast({ title: '请输入纠正答案', icon: 'none' })
            return
        }
        const answer = contextCorrectionSubmissionValue(item, typedAnswer, this.data.correctAnswer)
        const correctionNumber = Number(item.correction_count || this.data.correctionCount || 0) + 1
        const attemptId = buildReviewCorrectionAttemptId(
            this.data.sessionId,
            item.review_item_id,
            correctionNumber
        )
        const pending = {
            kind: 'correction',
            attemptId,
            reviewItemId: item.review_item_id,
            answer: typedAnswer,
            selectedOption: ''
        }
        this.setData({ correctionSubmitting: true })
        return this.requestWithDeadline(
            () => request(`/miniprogram/student/vocabulary-review/sessions/${this.data.sessionId}/corrections`, {
                method: 'POST',
                timeout: 15000,
                data: {
                    session_token: this.data.sessionToken,
                    review_item_id: item.review_item_id,
                    question_id: item.question_id,
                    word_id: item.word_id,
                    sense_id: item.sense_id,
                    dimension: item.dimension,
                    answer,
                    attempt_id: attemptId,
                    input_mode: 'native'
                }
            }),
            REVIEW_SUBMIT_TIMEOUT_MS,
            'review_correction'
        ).then((res) => {
            if (!this.isReviewPageActive()) return
            if (!res || !res.ok) throw (res || new Error('review_correction_failed'))
            const updatedItem = Object.assign({}, item, {
                correction_required: !!res.correction_required,
                correction_attempt_id: res.correction_attempt_id || attemptId,
                correction_is_correct: res.correction_is_correct,
                correction_answer: res.student_answer || answer,
                correction_count: Number(res.correction_count || correctionNumber),
                correction_max_attempts: Number(res.correction_max_attempts || 2),
                correction_retry_allowed: !!res.correction_retry_allowed,
                correction_exhausted: !!res.correction_exhausted,
                deferred_to_review: !!res.deferred_to_review
            })
            this.updateQueueItem(this.data.currentIndex, updatedItem)
            this.setData({
                currentItem: updatedItem,
                correctionRequired: !!res.correction_required,
                correctionCompleted: !!res.correction_completed,
                correctionSubmitting: false,
                correctionInputValue: '',
                correctionHasInput: false,
                correctionIsCorrect: res.correction_is_correct === true,
                correctionCount: Number(res.correction_count || correctionNumber),
                correctionMaxAttempts: Number(res.correction_max_attempts || 2),
                correctionExhausted: !!res.correction_exhausted
            })
            if (!res.correction_is_correct && res.correction_required) {
                wx.showToast({ title: '纠正仍不正确，请再试一次', icon: 'none' })
            }
        }).catch((err) => {
            console.warn('submit autonomous vocabulary correction failed', err)
            if (err && err.pageUnloaded) return
            if (!this.isReviewPageActive()) return
            this.setData({ correctionSubmitting: false })
            return this.handleSubmitFailure(err, pending)
        })
    },

    nextItem(event) {
        const current = this.data.currentItem
        if (!current || !matchesAnswerEvent(event, current, 'reviewItemId',
            current.review_item_id, this.data.answerRenderEpoch)) return
        if (this.data.submitting || this.data.correctionSubmitting || this.data.settling || this.data.finished) return
        const item = this.queueItemAt(this.data.currentIndex)
        // A second queued tap may arrive after showItem has already moved to
        // the next word. That word must have its own saved answer to advance.
        if (!item || !item.first_attempt_id || item.correction_required) return
        const next = this.data.currentIndex + 1
        if (this._reviewTrace) this._reviewTrace.mark('next_word_start', { index: next })
        if (next < this.queueItems().length) {
            return this.showItem(next)
        }
        return this.settle()
    },

    previousItem() {
        if (this.data.submitting || this.data.correctionSubmitting || this.data.settling || this.data.finished) return
        const previous = this.data.currentIndex - 1
        if (previous >= 0) this.showItem(previous)
    },

    recoverIncompleteSettlement() {
        const sessionId = this.data.sessionId
        const token = encodeURIComponent(this.data.sessionToken)
        // Recover this frozen batch only. A failed GET must not claim a new
        // batch through /today or silently treat this one as completed.
        return this.requestWithDeadline(() => request(
            `/miniprogram/student/vocabulary-review/sessions/${sessionId}?session_token=${token}`,
            { timeout: REVIEW_RECOVERY_REQUEST_TIMEOUT_MS }
        ), REVIEW_RECOVERY_DEADLINE_MS, 'review_settlement_recovery').then((res) => {
            if (!this.isReviewPageActive()) return
            if (!res || !res.ok || String(res.session_id) !== String(sessionId)) {
                throw new Error('review_settlement_recovery_failed')
            }
            if (this.applySettledSession(res)) return
            const current = this.applySessionSnapshot(res)
            if (!current) throw new Error('review_settlement_recovery_empty')
            wx.showToast({
                title: !current.first_attempt_id || current.correction_required
                    ? '还有未完成的词，已为你定位'
                    : '进度已同步，请再次完成本批复习',
                icon: 'none'
            })
        }).catch((err) => {
            if (!this.isReviewPageActive() || (err && err.pageUnloaded)) return
            wx.showToast({ title: '复习进度同步失败，请重试', icon: 'none' })
        })
    },

    settle() {
        if (this.data.submitting || this.data.correctionSubmitting || this.data.settling || this.data.finished || !this.data.sessionId) return
        const pendingIndex = this.queueItems().findIndex((item) => !item.first_attempt_id || item.correction_required)
        if (pendingIndex >= 0) {
            this.showItem(pendingIndex)
            wx.showToast({ title: '还有未完成的词，已为你定位', icon: 'none' })
            return
        }
        this.savePendingSettlement()
        this.setData({ settling: true })
        return this.requestWithDeadline(() => request(`/miniprogram/student/vocabulary-review/sessions/${this.data.sessionId}/settle`, {
            method: 'POST',
            timeout: REVIEW_SUBMIT_TIMEOUT_MS,
            data: {
                session_token: this.data.sessionToken,
                queue_token: this.data.queueToken,
                supports_correction: true,
                skipped_items: this._reviewSkippedItems || [],
                duration_seconds: 0
            }
        }), REVIEW_SUBMIT_TIMEOUT_MS, 'review_settle').then((res) => {
            if (!this.isReviewPageActive()) return
            if (!res || !res.ok) throw (res || new Error('review_settle_failed'))
            this.setData({
                settling: false,
                finished: true,
                result: res,
                remainingDueCount: Number(res.remaining_due_count || 0),
                forgotCount: forgotCountFromResponse(res, 'forgot_count', res.forgot_items),
                forgotItems: forgotItemsForDisplay(res.forgot_items)
            })
            this.clearPendingSettlement()
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
            if (err && err.pageUnloaded) return
            if (!this.isReviewPageActive()) return
            if (err && (
                err.error === 'review_session_incomplete'
                || classifyReviewAnswerFailure(err).recoverable
            )) {
                return this.recoverIncompleteSettlement()
            }
            console.warn('settle autonomous vocabulary review failed', err)
            wx.showToast({ title: '结算失败，请重试', icon: 'none' })
        }).finally(() => {
            if (this.isReviewPageActive()) this.setData({ settling: false })
        })
    },

    continueReview() {
        if (this.returnTaskId) return
        if (!this.data.sessionId) return this.fetchSession()
        this.requestWithDeadline(() => request(`/miniprogram/student/vocabulary-review/sessions/${this.data.sessionId}/continue`, {
            method: 'POST',
            timeout: REVIEW_LOAD_TIMEOUT_MS,
            data: { session_token: this.data.sessionToken }
        }), REVIEW_LOAD_TIMEOUT_MS, 'review_continue').then((res) => {
            if (!this.isReviewPageActive()) return
            if (!res || !res.ok) throw new Error((res && res.error) || 'review_continue_failed')
            if (!res.items || !res.items.length) {
                this._reviewQueue = []
                this.setData({ empty: true, finished: false, result: res, totalCount: 0, answeredCount: 0 })
                return
            }
            const normalized = this.setReviewQueue(res.items)
            if (!normalized.items.length) throw new Error('review_items_invalid')
            this.setData({
                empty: false,
                finished: false,
                sessionId: res.session_id,
                sessionToken: res.session_token,
                queueToken: res.queue_token || '',
                supportsForgotResponse: res.supports_forgot_response === true,
                totalCount: normalized.items.length,
                answeredCount: normalized.items.filter((item) => item.first_attempt_id && !item.correction_required).length,
                currentIndex: 0,
                remainingDueCount: Number(res.remaining_due_count || 0),
                forgotCount: 0,
                forgotItems: []
            }, () => this.showItem(0))
        }).catch((err) => {
            if (err && err.pageUnloaded) return
            if (!this.isReviewPageActive()) return
            wx.showToast({ title: '继续复习失败，请重试', icon: 'none' })
        })
    },

    playAudio() {
        if (!this.isReviewPageActive()) return
        const item = this.data.currentItem || {}
        const prompt = item.question && item.question.prompt
        const feedback = this.data.answerFeedback || {}
        const sources = this.data.showResult
            ? [feedback.audio_url, feedback.audio_tts_url]
            : this.audioSourcesForItem(item)
        const validSources = sources.filter(Boolean)
        if (!this.audioPlayer || !validSources.length) {
            wx.showToast({ title: '当前单词暂无发音', icon: 'none' })
            return
        }
        if (this._reviewTrace && !(arguments[0] && arguments[0].auto)) {
            this._reviewTrace.mark('audio_click', { source: validSources[0] })
        }
        this.audioPlayer.play(validSources, app.globalData.baseUrl)
    },

    playForgotAudio(event) {
        const index = Number(event && event.currentTarget && event.currentTarget.dataset && event.currentTarget.dataset.index)
        const item = this.data.forgotItems[index]
        if (!this.isReviewPageActive() || !item) return
        if (!this.audioPlayer || !item.audioSources.length) {
            wx.showToast({ title: '当前单词暂无发音', icon: 'none' })
            return
        }
        this.audioPlayer.play(item.audioSources, app.globalData.baseUrl)
    },

    retry() {
        const pendingSettlement = this.readPendingSettlement()
        if (pendingSettlement) return this.resumePendingSettlement(pendingSettlement)
        return this.fetchSession()
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
