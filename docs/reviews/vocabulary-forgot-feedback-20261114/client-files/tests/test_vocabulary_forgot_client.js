const assert = require('node:assert/strict')
const fs = require('node:fs')
const test = require('node:test')
const { forgotItemsForDisplay } = require('../miniprogram/utils/vocabulary-forgot.js')

const requests = []
const handlers = []
const toasts = []
const redirects = []
const storage = new Map()
const pages = {}
let registering = ''

global.getApp = () => ({ globalData: { baseUrl: 'https://studytracker.test/api', token: 'student-token' } })
global.Page = (config) => { pages[registering] = config }
global.wx = {
    request(options) {
        requests.push(options)
        const handler = handlers.shift()
        assert.ok(handler, `unexpected request ${options.method} ${options.url}`)
        handler(options)
    },
    getStorageSync(key) { return storage.get(key) || '' },
    setStorageSync(key, value) { storage.set(key, value) },
    removeStorageSync(key) { storage.delete(key) },
    reLaunch() {},
    showToast(options) { toasts.push(options.title) },
    redirectTo(options) { redirects.push(options.url) },
    switchTab() {}
}

registering = 'learning'
require('../miniprogram/pages/student/vocabulary-learning/index.js')
registering = 'review'
require('../miniprogram/pages/student/vocabulary-review/index.js')

function reset() {
    requests.length = 0
    handlers.length = 0
    toasts.length = 0
    redirects.length = 0
    storage.clear()
}

function pageFor(kind) {
    const page = Object.assign({}, pages[kind])
    page.data = JSON.parse(JSON.stringify(pages[kind].data))
    page.setData = function (changes, callback) {
        Object.assign(this.data, changes)
        if (callback) callback()
    }
    page.audioPlayer = { play() {}, destroy() {} }
    if (kind === 'learning') {
        page._learningPageActive = true
        page._learningDeadlineTimers = new Set()
        page.setData({ taskId: '42', queueToken: 'queue-token', phase: 'active_recall', supportsForgotResponse: true })
    } else {
        page._reviewPageActive = true
        page.returnTaskId = ''
        page._reviewQueue = []
        page._reviewSkippedItems = []
        page.setData({ sessionId: 7, sessionToken: 'session-token', queueToken: 'queue-token', supportsForgotResponse: true })
    }
    return page
}

function learningQuestion(id = 11, mode = 'zh_to_en') {
    return {
        learning_question_id: id,
        queue_item_id: id + 100,
        question_id: `q-${id}`,
        word_id: id,
        sense_id: id,
        dimension: 'form_recall',
        mode,
        question: { prompt: { meaning: '分析', word: 'analyze' }, options: [] }
    }
}

function learningQueue(question, changes = {}) {
    return Object.assign({
        ok: true,
        task_id: 42,
        queue_token: 'queue-token',
        supports_forgot_response: true,
        phase: 'active_recall',
        current_question: question,
        familiarity: [{ word_id: 11, word: 'analyze', meaning: '分析' }],
        completed: false,
        forgot_items: []
    }, changes)
}

function reviewItem(id, changes = {}) {
    return Object.assign({
        review_item_id: id,
        question_id: `q-${id}`,
        word_id: id,
        sense_id: id,
        dimension: 'form_recall',
        mode: 'zh_to_en',
        question: { prompt: { meaning: '分析' }, options: [] },
        first_attempt_id: '',
        first_answer: '',
        correction_required: false
    }, changes)
}

function reviewPage(items) {
    const page = pageFor('review')
    page._reviewQueue = items
    page.setData({ totalCount: items.length })
    page.showItem(0)
    return page
}

function success(data) {
    return (request) => request.success({ statusCode: 200, data })
}

function failed(errMsg = 'request:fail network') {
    return (request) => request.fail({ errMsg })
}

function answerEvent(kind, item, renderEpoch) {
    const id = kind === 'learning'
        ? { learningQuestionId: item.learning_question_id }
        : { reviewItemId: item.review_item_id }
    return { currentTarget: { dataset: Object.assign(id, {
        questionId: item.question_id,
        renderEpoch
    }) } }
}

function inputEvent(kind, item, renderEpoch, value) {
    return Object.assign(answerEvent(kind, item, renderEpoch), { detail: { value } })
}

function optionEvent(kind, item, renderEpoch, optionId) {
    const event = answerEvent(kind, item, renderEpoch)
    event.currentTarget.dataset.id = optionId
    return event
}

async function flushRequestTurns() {
    for (let turn = 0; turn < 20; turn += 1) await Promise.resolve()
}

test('learning forget saves empty input, locks the other action, shows the answer until explicit continuation', async () => {
    reset()
    const first = learningQuestion()
    const second = learningQuestion(12)
    const page = pageFor('learning')
    page.setData({ currentQuestion: first, inputValue: '' })
    let pendingPost
    handlers.push((request) => { pendingPost = request })
    handlers.push(success(learningQueue(second, {
        last_saved_response: { learning_question_id: 11, attempt_id: 'vocabulary-group:42:first:11', response_kind: 'forgot' }
    })))

    const saving = page.submitForgot()
    page.submitAnswer()
    page.submitForgot()
    await Promise.resolve()
    assert.equal(requests.length, 1)
    assert.equal(requests[0].data.answer, '')
    assert.equal(requests[0].data.response_kind, 'forgot')
    assert.equal(requests[0].data.attempt_id, 'vocabulary-group:42:first:11')
    pendingPost.success({ statusCode: 200, data: {
        ok: true, response_kind: 'forgot', first_response_kind: 'forgot', is_correct: false, revealed_answer: 'analyze'
    } })
    await saving
    assert.equal(page.data.currentQuestion.learning_question_id, 11)
    assert.equal(page.data.showResult, true)
    assert.equal(page.data.correctAnswer, 'analyze')
    assert.equal(requests.length, 1)
    page.submitAnswer()
    page.submitForgot()
    assert.equal(requests.length, 1)
    await page.continueAfterResult(answerEvent('learning', page.data.currentQuestion, page.data.answerRenderEpoch))
    assert.equal(page.data.currentQuestion.learning_question_id, 12)
    assert.equal(page.data.submitting, false)
    assert.equal(requests.length, 2)
})

test('learning requires confirmation then locks navigation until the queue GET finishes', async () => {
    reset()
    const page = pageFor('learning')
    page.applyQueue(learningQueue(learningQuestion(11)))
    const oldEvent = answerEvent('learning', page.data.currentQuestion, page.data.answerRenderEpoch)
    let heldQueue
    const saved = { ok: true, response_kind: 'forgot', is_correct: false }
    handlers.push(success(saved), (request) => { heldQueue = request })
    await page.submitForgot(oldEvent)
    assert.equal(requests.length, 1)
    assert.equal(page.data.showResult, true)
    const first = page.continueAfterResult(oldEvent)
    await flushRequestTurns()
    assert.ok(heldQueue)
    assert.equal(page.data.loading, true)
    assert.equal(page.isLearningLoadBlocking(), true)
    page.submitForgot(oldEvent)
    page.submitAnswer(oldEvent)
    assert.deepEqual(requests.filter((request) => request.method === 'POST').map((request) => request.data.learning_question_id), [11])
    heldQueue.success({ statusCode: 200, data: learningQueue(learningQuestion(12)) })
    await first
    assert.equal(page.data.submitting, false)
    assert.equal(page.data.currentQuestion.learning_question_id, 12)
    handlers.push(success(saved), success(learningQueue(learningQuestion(13))))
    await page.submitForgot(answerEvent('learning', page.data.currentQuestion, page.data.answerRenderEpoch))
    assert.deepEqual(requests.filter((request) => request.method === 'POST').map((request) => request.data.learning_question_id), [11, 12])
    assert.equal(page.data.currentQuestion.learning_question_id, 12)
    await page.continueAfterResult(answerEvent('learning', page.data.currentQuestion, page.data.answerRenderEpoch))
    assert.equal(page.data.currentQuestion.learning_question_id, 13)
})

test('learning applies only the latest of two independent queue GET replies or errors', async () => {
    for (const olderOutcome of ['success', 'failure']) {
        reset()
        const page = pageFor('learning')
        page.applyQueue(learningQueue(learningQuestion(11)))
        let oldGet
        let newGet
        handlers.push((request) => { oldGet = request }, (request) => { newGet = request })
        const older = page.fetchQueue()
        const newer = page.fetchQueue()
        await flushRequestTurns()
        assert.ok(oldGet)
        assert.ok(newGet)
        newGet.success({ statusCode: 200, data: learningQueue(learningQuestion(13)) })
        await newer
        page.onInput(inputEvent('learning', page.data.currentQuestion, page.data.answerRenderEpoch, 'new q13 answer'))
        if (olderOutcome === 'success') {
            oldGet.success({ statusCode: 200, data: learningQueue(learningQuestion(12)) })
        } else {
            oldGet.fail({ errMsg: 'request:fail network' })
        }
        await older
        assert.equal(page.data.currentQuestion.learning_question_id, 13, olderOutcome)
        assert.equal(page.data.inputValue, 'new q13 answer', olderOutcome)
        assert.equal(page.data.loadError, '', olderOutcome)
    }
})

test('learning next-question tap cannot start a second queue GET while one is loading', async () => {
    reset()
    const page = pageFor('learning')
    page.applyQueue(learningQueue(learningQuestion(11)))
    page.setData({ showResult: true, isCorrect: true })
    const event = answerEvent('learning', page.data.currentQuestion, page.data.answerRenderEpoch)
    let heldQueue
    handlers.push((request) => { heldQueue = request })
    const first = page.submitAnswer(event)
    await flushRequestTurns()
    assert.ok(heldQueue)
    page.submitAnswer(event)
    assert.equal(requests.length, 1)
    heldQueue.success({ statusCode: 200, data: learningQueue(learningQuestion(12)) })
    await first
    assert.equal(page.data.currentQuestion.learning_question_id, 12)
})

test('learning queue failure blocks old answer events and the Retry control reloads without another POST', async () => {
    reset()
    const page = pageFor('learning')
    page.applyQueue(learningQueue(learningQuestion(11)))
    const oldEvent = answerEvent('learning', page.data.currentQuestion, page.data.answerRenderEpoch)
    handlers.push(success({ ok: true, response_kind: 'forgot', is_correct: false }), failed())
    await page.submitForgot(oldEvent)
    assert.equal(page.data.showResult, true)
    await page.continueAfterResult(answerEvent('learning', page.data.currentQuestion, page.data.answerRenderEpoch))
    assert.equal(page.data.loading, false)
    assert.ok(page.data.loadError)
    assert.equal(page.data.submitting, false)
    page.onInput(inputEvent('learning', page.data.currentQuestion, page.data.answerRenderEpoch, 'late old input'))
    assert.equal(page.data.inputValue, '')
    page.setData({ inputValue: 'old entered answer' })
    page.submitForgot(oldEvent)
    page.submitAnswer(oldEvent)
    assert.deepEqual(requests.filter((request) => request.method === 'POST').map((request) => request.data.learning_question_id), [11])
    handlers.push(success({ ok: true, task: { read_only: false } }), success(learningQueue(learningQuestion(12))))
    await page.retry()
    assert.equal(page.data.loadError, '')
    assert.equal(page.data.currentQuestion.learning_question_id, 12)
    assert.deepEqual(requests.filter((request) => request.method === 'POST').map((request) => request.data.learning_question_id), [11])
})

test('learning queue deadline and unload ignore late GET replies', async () => {
    for (const finish of ['deadline', 'unload']) {
        reset()
        const page = pageFor('learning')
        page.applyQueue(learningQueue(learningQuestion(11)))
        const originalDeadline = page.requestWithDeadline
        if (finish === 'deadline') {
            page.requestWithDeadline = function (factory, timeoutMs, label) {
                return originalDeadline.call(this, factory, label === 'learning_queue' ? 1 : timeoutMs, label)
            }
        }
        let heldQueue
        handlers.push(success({ ok: true, response_kind: 'forgot', is_correct: false }), (request) => { heldQueue = request })
        await page.submitForgot(answerEvent('learning', page.data.currentQuestion, page.data.answerRenderEpoch))
        const pending = page.continueAfterResult(answerEvent('learning', page.data.currentQuestion, page.data.answerRenderEpoch))
        await flushRequestTurns()
        assert.ok(heldQueue)
        if (finish === 'unload') page.onUnload()
        await pending
        heldQueue.success({ statusCode: 200, data: learningQueue(learningQuestion(12)) })
        await flushRequestTurns()
        assert.equal(page.data.currentQuestion.learning_question_id, 11, finish)
        if (finish === 'deadline') {
            assert.ok(page.data.loadError)
            assert.equal(page.data.submitting, false)
        }
    }
})

test('learning ignores late button and keyboard events after a real saved forget, then accepts the new question', async () => {
    reset()
    const page = pageFor('learning')
    page.setData({ currentQuestion: learningQuestion(11), inputValue: '' })
    const oldEvent = answerEvent('learning', page.data.currentQuestion, page.data.answerRenderEpoch)
    handlers.push(success({ ok: true, response_kind: 'forgot', is_correct: false }))
    handlers.push(success(learningQueue(learningQuestion(12))))
    await page.submitForgot(oldEvent)
    assert.equal(page.data.showResult, true)
    await page.continueAfterResult(answerEvent('learning', page.data.currentQuestion, page.data.answerRenderEpoch))
    assert.equal(page.data.currentQuestion.learning_question_id, 12)
    page.setData({ inputValue: 'typed on the new question' })
    page.submitForgot(oldEvent)
    page.submitAnswer(oldEvent)
    assert.deepEqual(requests.filter((request) => request.method === 'POST').map((request) => request.data.learning_question_id), [11])
    assert.equal(page.data.inputValue, 'typed on the new question')
    const newEvent = answerEvent('learning', page.data.currentQuestion, page.data.answerRenderEpoch)
    handlers.push(success({ ok: true, response_kind: 'forgot', is_correct: false }))
    handlers.push(success(learningQueue(learningQuestion(13))))
    await page.submitForgot(newEvent)
    assert.equal(page.data.showResult, true)
    await page.continueAfterResult(answerEvent('learning', page.data.currentQuestion, page.data.answerRenderEpoch))
    assert.deepEqual(requests.filter((request) => request.method === 'POST').map((request) => request.data.learning_question_id), [11, 12])
    assert.equal(page.data.currentQuestion.learning_question_id, 13)
})

test('learning rejects a prior render of the same question but accepts its current render', async () => {
    reset()
    const page = pageFor('learning')
    page.applyQueue(learningQueue(learningQuestion(11)))
    const oldEvent = answerEvent('learning', page.data.currentQuestion, page.data.answerRenderEpoch)
    page.applyQueue(learningQueue(learningQuestion(11)))
    page.submitForgot(oldEvent)
    const oldWithoutEpoch = answerEvent('learning', page.data.currentQuestion, page.data.answerRenderEpoch)
    delete oldWithoutEpoch.currentTarget.dataset.renderEpoch
    page.submitForgot(oldWithoutEpoch)
    assert.equal(requests.length, 0)
    const currentEvent = answerEvent('learning', page.data.currentQuestion, page.data.answerRenderEpoch)
    handlers.push(success({ ok: true, response_kind: 'forgot', is_correct: false }))
    handlers.push(success(learningQueue(learningQuestion(12))))
    await page.submitForgot(currentEvent)
    assert.equal(requests.filter((request) => request.method === 'POST').length, 1)
})

test('learning partial input forget at retry saves a real retry and finishes the bounded group', async () => {
    reset()
    const question = learningQuestion()
    const page = pageFor('learning')
    page.setData({ phase: 'retry', currentQuestion: question, inputValue: 'ana' })
    const forgot = [{ learning_question_id: 11, word_id: 11, word: 'analyze', meaning: '分析', revealed_answer: 'analyze', audio_tts_url: '/audio/11' }]
    handlers.push((request) => {
        assert.equal(request.data.retry, true)
        assert.equal(request.data.answer, 'ana')
        assert.equal(request.data.attempt_id, 'vocabulary-group:42:retry:11')
        request.success({ statusCode: 200, data: { ok: true, response_kind: 'forgot', is_correct: false } })
    })
    handlers.push(success(learningQueue(null, { phase: 'complete', completed: true, forgot_items: forgot })))
    handlers.push(success({ ok: true, correct_count: 0, total_count: 1, accuracy: 0, forgot_items: forgot }))

    await page.submitForgot()
    assert.equal(page.data.finished, false)
    assert.equal(page.data.showResult, true)
    assert.equal(requests.length, 1)
    await page.continueAfterResult(answerEvent('learning', page.data.currentQuestion, page.data.answerRenderEpoch))
    await flushRequestTurns()
    assert.equal(page.data.finished, true)
    assert.equal(page.data.result.accuracy, 0)
    assert.equal(page.data.forgotItems[0].word, 'analyze')
    assert.equal(requests.length, 3)
})

test('learning lost finalization reply restores the server settlement and zero score', async () => {
    reset()
    const page = pageFor('learning')
    page.setData({ phase: 'complete', currentQuestion: null })
    const forgot = [{ learning_question_id: 11, word_id: 11, word: 'analyze', meaning: '分析', revealed_answer: 'analyze' }]
    const settlement = { ok: true, correct_count: 0, total_count: 1, accuracy: 0, forgotten_count: 1, forgot_items: forgot }
    handlers.push(failed('request:fail timeout'))
    handlers.push(success(learningQueue(null, { completed: true, phase: 'complete', settlement, forgot_items: forgot })))
    await page.finishTask()
    assert.equal(page.data.finished, true)
    assert.equal(page.data.result.accuracy, 0)
    assert.equal(page.data.forgotItems[0].word, 'analyze')
    assert.equal(requests.length, 2)
})

test('learning completed read-only task reopens its saved settlement without writing', async () => {
    reset()
    const page = pageFor('learning')
    const forgot = [{ learning_question_id: 11, word_id: 11, word: 'analyze', meaning: '分析', revealed_answer: 'analyze' }]
    const settlement = { ok: true, correct_count: 0, total_count: 1, accuracy: 0, forgotten_count: 1, forgot_items: forgot }
    handlers.push(success({ ok: true, task: { id: 42, read_only: true, status: 'completed', status_label: '已完成' } }))
    handlers.push(success(learningQueue(null, { completed: true, phase: 'complete', settlement, forgot_items: forgot })))
    await page.fetchTaskAccess()
    assert.equal(page.data.readOnly, true)
    assert.equal(page.data.finished, true)
    assert.equal(page.data.result.accuracy, 0)
    assert.equal(requests.length, 2)
    assert.equal(requests.filter((request) => request.method === 'POST').length, 0)
})

test('learning timeout recovers the exact saved attempt and never substitutes a newer answer', async () => {
    reset()
    const first = learningQuestion()
    const second = learningQuestion(12)
    const page = pageFor('learning')
    page.setData({ currentQuestion: first })
    handlers.push(failed('request:fail timeout'))
    handlers.push((request) => {
        assert.ok(request.url.includes('attempt_id=vocabulary-group%3A42%3Afirst%3A11'))
        request.success({ statusCode: 200, data: learningQueue(second, {
            last_saved_response: { learning_question_id: 12, attempt_id: 'newer-answer', response_kind: 'answer' },
            saved_response: {
                learning_question_id: 11,
                attempt_id: 'vocabulary-group:42:first:11',
                response_kind: 'forgot',
                is_correct: false, revealed_answer: 'analyze'
            }
        }) })
    })
    await page.submitForgot()
    assert.equal(page.data.currentQuestion.learning_question_id, 11)
    assert.equal(page.data.showResult, true)
    assert.equal(page.data.correctAnswer, 'analyze')
    assert.equal(requests.length, 2)
    assert.equal(page.data.submitting, false)
})

test('learning exact saved forget shows the answer before continuing to a later due-review gate', async () => {
    reset()
    const page = pageFor('learning')
    page.setData({ currentQuestion: learningQuestion() })
    handlers.push(failed('request:fail timeout'))
    handlers.push(success({
        ok: true, task_id: 42, recovery_only: true, review_required: true, read_only: true,
        saved_response: {
            learning_question_id: 11, attempt_id: 'vocabulary-group:42:first:11',
            response_kind: 'forgot', is_correct: false, revealed_answer: 'analyze'
        }
    }))
    await page.submitForgot()
    assert.equal(redirects.length, 0)
    assert.equal(page.data.showResult, true)
    assert.equal(page.data.correctAnswer, 'analyze')
    handlers.push(success({ ok: false, error: 'vocabulary_review_required' }))
    await page.continueAfterResult(answerEvent('learning', page.data.currentQuestion, page.data.answerRenderEpoch))
    assert.equal(redirects[0], '/pages/student/vocabulary-review/index?returnTaskId=42')
    assert.equal(page.data.submitting, false)
})

test('learning failed recovery keeps the original partial input and permits retry', async () => {
    reset()
    const page = pageFor('learning')
    page.setData({ currentQuestion: learningQuestion(), inputValue: 'ana' })
    handlers.push(failed('request:fail timeout'), failed())
    await page.submitForgot()
    assert.equal(page.data.currentQuestion.learning_question_id, 11)
    assert.equal(page.data.inputValue, 'ana')
    assert.equal(page.data.showResult, false)
    assert.equal(page.data.submitting, false)
})

test('learning forget accepts empty values in meaning, audio and context question modes', async () => {
    for (const mode of ['en_to_zh', 'zh_to_en', 'audio_to_en', 'audio_to_zh', 'context_choice', 'context_fill']) {
        reset()
        const page = pageFor('learning')
        page.setData({ currentQuestion: learningQuestion(11, mode), inputValue: '', selectedOption: '', isMeaningChoice: mode === 'audio_to_zh' })
        handlers.push((request) => {
            assert.equal(request.data.answer, '', mode)
            assert.equal(request.data.response_kind, 'forgot', mode)
            request.success({ statusCode: 200, data: { ok: true, response_kind: 'forgot', is_correct: false, revealed_answer: 'analyze' } })
        })
        await page.submitForgot()
        assert.equal(page.data.currentQuestion.learning_question_id, 11, mode)
        assert.equal(page.data.showResult, true, mode)
        assert.equal(page.data.correctAnswer, 'analyze', mode)
        assert.equal(requests.length, 1, mode)
    }
})

test('old server gate and ordinary wrong answer retain the correction flow', async () => {
    reset()
    const page = pageFor('learning')
    page.setData({ currentQuestion: learningQuestion(), supportsForgotResponse: false, inputValue: 'wrong' })
    page.submitForgot()
    assert.equal(requests.length, 0)
    handlers.push(success({ ok: true, is_correct: false, student_answer: 'wrong', revealed_answer: 'analyze', correction_required: true }))
    await page.submitAnswer()
    assert.equal(requests[0].data.response_kind, undefined)
    assert.equal(page.data.showResult, true)
    assert.equal(page.data.correctionRequired, true)
    assert.equal(page.data.responseKind, 'answer')
})

test('learning concurrent ordinary answer wins over requested forget and shows its saved correction', async () => {
    reset()
    const page = pageFor('learning')
    page.setData({ currentQuestion: learningQuestion(), inputValue: 'wron' })
    handlers.push(success({
        ok: true, response_kind: 'answer', first_response_kind: 'answer',
        is_correct: false, student_answer: 'wrong', revealed_answer: 'analyze', correction_required: true
    }))
    await page.submitForgot()
    assert.equal(page.data.responseKind, 'answer')
    assert.equal(page.data.submittedAnswer, 'wrong')
    assert.equal(page.data.correctionRequired, true)
    assert.equal(requests.length, 1)
})

test('review empty forget waits for confirmation before advancing one item and the next unanswered item cannot be skipped', async () => {
    reset()
    const page = reviewPage([reviewItem(1), reviewItem(2)])
    handlers.push(success({
        ok: true, attempt_id: 'wx-vocabulary-review:7:1', response_kind: 'forgot',
        first_response_kind: 'forgot', is_correct: false, student_answer: '',
        revealed_answer: 'analyze', correction_required: false
    }))
    await page.submitForgot()
    assert.equal(requests[0].data.answer, '')
    assert.equal(requests[0].data.response_kind, 'forgot')
    assert.equal(page.data.currentIndex, 0)
    assert.equal(page.data.showResult, true)
    assert.equal(page.data.correctAnswer, 'analyze')
    assert.equal(page.data.correctionCompleted, false)
    page.submitAnswer()
    page.submitForgot()
    assert.equal(page.data.currentIndex, 0)
    page.nextItem(answerEvent('review', page.data.currentItem, page.data.answerRenderEpoch))
    assert.equal(page.data.currentIndex, 1)
    page.nextItem()
    assert.equal(page.data.currentIndex, 1)
    assert.equal(page.queueItems()[0].first_response_kind, 'forgot')
})

test('review keeps the forget action disabled when the server omits support', () => {
    reset()
    const page = reviewPage([reviewItem(1)])
    page.setData({ supportsForgotResponse: false })
    page.submitForgot()
    assert.equal(requests.length, 0)
    assert.equal(page.data.currentIndex, 0)
})

test('review forget accepts empty values in all supported modes and shares the submit lock', async () => {
    for (const mode of ['en_to_zh', 'zh_to_en', 'audio_to_en', 'audio_to_zh', 'context_choice', 'context_fill']) {
        reset()
        const page = reviewPage([reviewItem(1, {
            mode,
            question: { prompt: { meaning: '分析', word: 'analyze', sentence: 'Analyze it.', audio_url: '/audio/1' }, options: [{ id: 'a', label: '分析' }] }
        }), reviewItem(2)])
        page.setData({ isMeaningChoice: mode === 'audio_to_zh', inputValue: '', selectedOption: '' })
        let pendingPost
        handlers.push((request) => { pendingPost = request })
        const saving = page.submitForgot()
        page.submitAnswer()
        page.submitForgot()
        await Promise.resolve()
        assert.equal(requests.length, 1, mode)
        assert.equal(requests[0].data.answer, '', mode)
        pendingPost.success({ statusCode: 200, data: {
            ok: true, attempt_id: 'wx-vocabulary-review:7:1', response_kind: 'forgot',
            first_response_kind: 'forgot', is_correct: false, revealed_answer: 'analyze'
        } })
        await saving
        assert.equal(page.data.currentIndex, 0, mode)
        assert.equal(page.data.showResult, true, mode)
        assert.equal(page.data.correctAnswer, 'analyze', mode)
        assert.equal(requests.length, 1, mode)
    }
})

test('review rejected invalid source is not counted as forget or skipped locally', async () => {
    reset()
    const page = reviewPage([reviewItem(1)])
    page.setData({ inputValue: 'ana' })
    handlers.push((request) => request.success({ statusCode: 409, data: { ok: false, error: 'review_item_invalid', skip_reason: 'missing_answer' } }))
    await page.submitForgot()
    assert.equal(page.data.currentIndex, 0)
    assert.equal(page.data.inputValue, 'ana')
    assert.equal(page.data.showResult, false)
    assert.equal(page._reviewSkippedItems.length, 0)
    assert.equal(page.data.submitting, false)
    assert.equal(requests.length, 1)
})

test('review concurrent ordinary answer wins and remains in the immediate correction flow', async () => {
    reset()
    const page = reviewPage([reviewItem(1), reviewItem(2)])
    page.setData({ inputValue: 'wrong' })
    handlers.push(success({
        ok: true, attempt_id: 'wx-vocabulary-review:7:1', response_kind: 'answer',
        first_response_kind: 'answer', is_correct: false, student_answer: 'wrong',
        revealed_answer: 'analyze', correction_required: true
    }))
    await page.submitForgot()
    assert.equal(page.data.currentIndex, 0)
    assert.equal(page.data.responseKind, 'answer')
    assert.equal(page.data.correctionRequired, true)
    assert.equal(page.queueItems()[0].first_response_kind, 'answer')
})

test('review timeout recovers a saved forget in the same batch and shows its answer before continuation', async () => {
    reset()
    const page = reviewPage([reviewItem(1), reviewItem(2)])
    page.setData({ inputValue: 'ana' })
    handlers.push(failed('request:fail timeout'))
    handlers.push((request) => {
        assert.ok(request.url.includes('/sessions/7?session_token=session-token'))
        request.success({ statusCode: 200, data: {
            ok: true, session_id: 7, session_token: 'session-token', supports_forgot_response: true,
            items: [reviewItem(1, {
                first_attempt_id: 'wx-vocabulary-review:7:1', first_response_kind: 'forgot',
                first_answer: 'ana', first_is_correct: false, revealed_answer: 'analyze'
            }), reviewItem(2)]
        } })
    })
    await page.submitForgot()
    assert.equal(requests.length, 2)
    assert.equal(page.data.currentIndex, 0)
    assert.equal(page.data.showResult, true)
    assert.equal(page.data.correctAnswer, 'analyze')
    assert.equal(page.data.correctionCompleted, false)
    page.nextItem(answerEvent('review', page.data.currentItem, page.data.answerRenderEpoch))
    assert.equal(page.data.currentIndex, 1)
    assert.equal(page.queueItems()[0].first_answer, 'ana')
})

test('review last forget waits for confirmation then settles to zero and displays spelling, meaning and replay', async () => {
    reset()
    const page = reviewPage([reviewItem(1)])
    const forgotten = [{ review_item_id: 1, word_id: 1, correct_spelling: 'analyze', meaning: '分析', revealed_answer: 'analyze', audio_tts_url: '/audio/1' }]
    handlers.push(success({
        ok: true, attempt_id: 'wx-vocabulary-review:7:1', response_kind: 'forgot',
        first_response_kind: 'forgot', is_correct: false, revealed_answer: 'analyze'
    }))
    handlers.push(success({ ok: true, status: 'settled', total_count: 1, correct_count: 0, accuracy: 0, forgot_count: 1, forgot_items: forgotten }))
    await page.submitForgot()
    assert.equal(page.data.finished, false)
    assert.equal(page.data.showResult, true)
    assert.equal(page.data.correctAnswer, 'analyze')
    assert.equal(requests.length, 1)
    await page.nextItem(answerEvent('review', page.data.currentItem, page.data.answerRenderEpoch))
    assert.equal(page.data.finished, true)
    assert.equal(page.data.result.correct_count, 0)
    assert.equal(page.data.forgotCount, 1)
    assert.equal(page.data.forgotItems[0].word, 'analyze')
    assert.equal(page.data.forgotItems[0].meaning, '分析')
    assert.equal(page.data.forgotItems[0].audioSources[0], '/audio/1')
})

test('review ignores late button and keyboard events after a real saved forget, then accepts the new item', async () => {
    reset()
    const page = reviewPage([reviewItem(1), reviewItem(2), reviewItem(3)])
    const oldEvent = answerEvent('review', page.data.currentItem, page.data.answerRenderEpoch)
    handlers.push(success({ ok: true, attempt_id: 'wx-vocabulary-review:7:1',
        response_kind: 'forgot', first_response_kind: 'forgot', is_correct: false }))
    await page.submitForgot(oldEvent)
    assert.equal(page.data.showResult, true)
    await page.nextItem(answerEvent('review', page.data.currentItem, page.data.answerRenderEpoch))
    assert.equal(page.data.currentIndex, 1)
    page.setData({ inputValue: 'typed on the new item' })
    page.submitAnswer(oldEvent)
    page.submitForgot(oldEvent)
    assert.deepEqual(requests.filter((request) => request.method === 'POST').map((request) => request.data.review_item_id), [1])
    assert.equal(page.data.inputValue, 'typed on the new item')
    const newEvent = answerEvent('review', page.data.currentItem, page.data.answerRenderEpoch)
    handlers.push(success({ ok: true, attempt_id: 'wx-vocabulary-review:7:2',
        response_kind: 'forgot', first_response_kind: 'forgot', is_correct: false }))
    await page.submitForgot(newEvent)
    assert.equal(page.data.showResult, true)
    await page.nextItem(answerEvent('review', page.data.currentItem, page.data.answerRenderEpoch))
    assert.deepEqual(requests.filter((request) => request.method === 'POST').map((request) => request.data.review_item_id), [1, 2])
    assert.equal(page.data.currentIndex, 2)
})

test('review rejects a prior render of the same item but accepts its current render', async () => {
    reset()
    const page = reviewPage([reviewItem(1), reviewItem(2)])
    const oldEvent = answerEvent('review', page.data.currentItem, page.data.answerRenderEpoch)
    page.showItem(0)
    page.submitForgot(oldEvent)
    const oldWithoutEpoch = answerEvent('review', page.data.currentItem, page.data.answerRenderEpoch)
    delete oldWithoutEpoch.currentTarget.dataset.renderEpoch
    page.submitForgot(oldWithoutEpoch)
    assert.equal(requests.length, 0)
    const currentEvent = answerEvent('review', page.data.currentItem, page.data.answerRenderEpoch)
    handlers.push(success({ ok: true, attempt_id: 'wx-vocabulary-review:7:1',
        response_kind: 'forgot', first_response_kind: 'forgot', is_correct: false }))
    await page.submitForgot(currentEvent)
    assert.equal(requests.filter((request) => request.method === 'POST').length, 1)
    assert.equal(page.data.currentIndex, 0)
    page.nextItem(oldEvent)
    assert.equal(page.data.currentIndex, 0)
    page.nextItem(currentEvent)
    assert.equal(page.data.currentIndex, 1)
})

test('lost settlement reply restores the exact settled batch without asking for today', async () => {
    reset()
    const saved = reviewItem(1, { first_attempt_id: 'wx-vocabulary-review:7:1', first_response_kind: 'forgot', first_is_correct: false })
    const page = reviewPage([saved])
    const settlement = { ok: true, status: 'settled', total_count: 1, correct_count: 0, accuracy: 0, forgot_count: 1, forgot_items: [{ word_id: 1, correct_spelling: 'analyze', meaning: '分析', revealed_answer: 'analyze' }] }
    handlers.push(failed('request:fail timeout'))
    handlers.push(success({ ok: true, session_id: 7, session_token: 'session-token', status: 'settled', settlement, items: [saved] }))
    await page.settle()
    assert.equal(page.data.finished, true)
    assert.equal(page.data.result.correct_count, 0)
    assert.equal(requests.length, 2)
    assert.ok(requests[1].url.includes('/sessions/7?session_token='))
})

test('settlement uncertainty survives page exit and reopens the original batch', async () => {
    reset()
    const saved = reviewItem(1, { first_attempt_id: 'wx-vocabulary-review:7:1', first_response_kind: 'forgot', first_is_correct: false })
    const page = reviewPage([saved])
    handlers.push(failed('request:fail timeout'), failed('request:fail network'))
    await page.settle()
    assert.equal(page.data.finished, false)
    const reopened = pageFor('review')
    const marker = reopened.readPendingSettlement()
    assert.equal(marker.sessionId, 7)
    const settlement = { ok: true, status: 'settled', total_count: 1, correct_count: 0, accuracy: 0, forgot_count: 1, forgot_items: [] }
    handlers.push(success({ ok: true, session_id: 7, session_token: 'session-token', status: 'settled', settlement, items: [saved] }))
    await reopened.resumePendingSettlement(marker)
    assert.equal(reopened.data.finished, true)
    assert.equal(reopened.data.result.correct_count, 0)
    assert.equal(reopened.readPendingSettlement(), null)
    assert.equal(requests.length, 3)
    assert.ok(requests[2].url.includes('/sessions/7?session_token='))
})

test('summary mapping uses the server revealed answer and never exposes an option key', () => {
    const rows = forgotItemsForDisplay([{
        word_id: 1, correct_spelling: 'analyze', meaning: '分析', revealed_answer_option_id: 'option-a',
        question: { options: [{ id: 'option-a', label: '分析' }] }, audio_tts_url: '/audio/1'
    }])
    assert.equal(rows[0].answer, '分析')
    assert.equal(rows[0].word, 'analyze')
})

test('an explicit server count of zero wins over display rows in both student summaries', () => {
    reset()
    const row = { word_id: 11, word: 'analyze', meaning: '分析', revealed_answer: 'analyze' }
    const learning = pageFor('learning')
    learning.applyQueue(learningQueue(learningQuestion(11), {
        forgotten_count: 0, forgot_items: [row]
    }))
    assert.equal(learning.data.forgotCount, 0)
    const review = reviewPage([reviewItem(1)])
    review.applySettledSession({
        status: 'settled', session_id: 7, session_token: 'session-token',
        settlement: { forgot_count: 0, forgot_items: [row] }
    })
    assert.equal(review.data.forgotCount, 0)
})

test('learning late input cannot overwrite the next question or a fresh render', async () => {
    reset()
    const page = pageFor('learning')
    page.applyQueue(learningQueue(learningQuestion(11)))
    const oldInput = inputEvent('learning', page.data.currentQuestion, page.data.answerRenderEpoch, 'old answer')
    handlers.push(success({ ok: true, response_kind: 'forgot', is_correct: false }))
    handlers.push(success(learningQueue(learningQuestion(12))))
    await page.submitForgot(answerEvent('learning', page.data.currentQuestion, page.data.answerRenderEpoch))
    assert.equal(page.data.showResult, true)
    await page.continueAfterResult(answerEvent('learning', page.data.currentQuestion, page.data.answerRenderEpoch))
    page.onInput(oldInput)
    assert.equal(page.data.inputValue, '')
    const priorRender = inputEvent('learning', page.data.currentQuestion, page.data.answerRenderEpoch, 'prior render')
    page.applyQueue(learningQueue(learningQuestion(12)))
    page.onInput(priorRender)
    assert.equal(page.data.inputValue, '')
    page.onInput(inputEvent('learning', page.data.currentQuestion, page.data.answerRenderEpoch, 'new answer'))
    assert.equal(page.data.inputValue, 'new answer')
    handlers.push(success({ ok: true, response_kind: 'answer', is_correct: true }))
    await page.submitAnswer(answerEvent('learning', page.data.currentQuestion, page.data.answerRenderEpoch))
    assert.equal(requests.filter((request) => request.method === 'POST').at(-1).data.answer, 'new answer')
})

test('learning late option cannot overwrite the next question or a fresh render', async () => {
    reset()
    const page = pageFor('learning')
    page.applyQueue(learningQueue(learningQuestion(11, 'context_choice')))
    const oldOption = optionEvent('learning', page.data.currentQuestion, page.data.answerRenderEpoch, 'old-option')
    handlers.push(success({ ok: true, response_kind: 'forgot', is_correct: false }))
    handlers.push(success(learningQueue(learningQuestion(12, 'context_choice'))))
    await page.submitForgot(answerEvent('learning', page.data.currentQuestion, page.data.answerRenderEpoch))
    assert.equal(page.data.showResult, true)
    await page.continueAfterResult(answerEvent('learning', page.data.currentQuestion, page.data.answerRenderEpoch))
    page.selectOption(oldOption)
    assert.equal(page.data.selectedOption, '')
    const priorRender = optionEvent('learning', page.data.currentQuestion, page.data.answerRenderEpoch, 'prior-option')
    page.applyQueue(learningQueue(learningQuestion(12, 'context_choice')))
    page.selectOption(priorRender)
    assert.equal(page.data.selectedOption, '')
    page.selectOption(optionEvent('learning', page.data.currentQuestion, page.data.answerRenderEpoch, 'new-option'))
    assert.equal(page.data.selectedOption, 'new-option')
    handlers.push(success({ ok: true, response_kind: 'answer', is_correct: true }))
    await page.submitAnswer(answerEvent('learning', page.data.currentQuestion, page.data.answerRenderEpoch))
    assert.equal(requests.filter((request) => request.method === 'POST').at(-1).data.answer, 'new-option')
})

test('review late input cannot overwrite the next item or a fresh render', async () => {
    reset()
    const page = reviewPage([reviewItem(1), reviewItem(2), reviewItem(3)])
    const oldInput = inputEvent('review', page.data.currentItem, page.data.answerRenderEpoch, 'old answer')
    handlers.push(success({ ok: true, attempt_id: 'wx-vocabulary-review:7:1',
        response_kind: 'forgot', first_response_kind: 'forgot', is_correct: false }))
    await page.submitForgot(answerEvent('review', page.data.currentItem, page.data.answerRenderEpoch))
    assert.equal(page.data.showResult, true)
    await page.nextItem(answerEvent('review', page.data.currentItem, page.data.answerRenderEpoch))
    page.onInput(oldInput)
    assert.equal(page.data.inputValue, '')
    const priorRender = inputEvent('review', page.data.currentItem, page.data.answerRenderEpoch, 'prior render')
    page.showItem(1)
    page.onInput(priorRender)
    assert.equal(page.data.inputValue, '')
    page.onInput(inputEvent('review', page.data.currentItem, page.data.answerRenderEpoch, 'new answer'))
    assert.equal(page.data.inputValue, 'new answer')
    handlers.push(success({ ok: true, response_kind: 'answer', is_correct: true }))
    await page.submitAnswer(answerEvent('review', page.data.currentItem, page.data.answerRenderEpoch))
    assert.equal(requests.filter((request) => request.method === 'POST').at(-1).data.answer, 'new answer')
})

test('review late option cannot overwrite the next item or a fresh render', async () => {
    reset()
    const page = reviewPage([
        reviewItem(1, { mode: 'context_choice' }),
        reviewItem(2, { mode: 'context_choice' }),
        reviewItem(3)
    ])
    const oldOption = optionEvent('review', page.data.currentItem, page.data.answerRenderEpoch, 'old-option')
    handlers.push(success({ ok: true, attempt_id: 'wx-vocabulary-review:7:1',
        response_kind: 'forgot', first_response_kind: 'forgot', is_correct: false }))
    await page.submitForgot(answerEvent('review', page.data.currentItem, page.data.answerRenderEpoch))
    assert.equal(page.data.showResult, true)
    await page.nextItem(answerEvent('review', page.data.currentItem, page.data.answerRenderEpoch))
    page.selectOption(oldOption)
    assert.equal(page.data.selectedOption, '')
    const priorRender = optionEvent('review', page.data.currentItem, page.data.answerRenderEpoch, 'prior-option')
    page.showItem(1)
    page.selectOption(priorRender)
    assert.equal(page.data.selectedOption, '')
    page.selectOption(optionEvent('review', page.data.currentItem, page.data.answerRenderEpoch, 'new-option'))
    assert.equal(page.data.selectedOption, 'new-option')
    handlers.push(success({ ok: true, response_kind: 'answer', is_correct: true }))
    await page.submitAnswer(answerEvent('review', page.data.currentItem, page.data.answerRenderEpoch))
    assert.equal(requests.filter((request) => request.method === 'POST').at(-1).data.answer, 'new-option')
})

test('both student templates bind identity and render epoch to input and each choice', () => {
    for (const [page, idAttribute] of [
        ['vocabulary-learning', 'data-learning-question-id'],
        ['vocabulary-review', 'data-review-item-id']
    ]) {
        const source = fs.readFileSync(`${__dirname}/../miniprogram/pages/student/${page}/index.wxml`, 'utf8')
        const inputs = source.match(/<input\b[^>]*\bbindinput="onInput"[^>]*>/g) || []
        const choices = source.match(/<view\b[^>]*\bbindtap="selectOption"[^>]*>/g) || []
        assert.equal(inputs.length, 1, `${page} text input`)
        assert.equal(choices.length, 2, `${page} meaning and context choices`)
        for (const control of inputs.concat(choices)) {
            assert.ok(control.includes(`${idAttribute}="`), `${page} question identity`)
            assert.ok(control.includes('data-question-id="'), `${page} question snapshot`)
            assert.ok(control.includes('data-render-epoch="'), `${page} render epoch`)
        }
    }
})

test('forgot feedback preserves the server answer and explanation across four learning dimensions', async () => {
    for (const kind of ['learning', 'review']) {
        for (const [dimension, mode, revealedAnswer] of [
            ['meaning_recall', 'en_to_zh', '分析'],
            ['form_recall', 'zh_to_en', 'analyze'],
            ['listening', 'audio_to_en', 'analyze'],
            ['context_use', 'context_choice', 'option-b']
        ]) {
            reset()
            const question = { prompt: { meaning: '分析', word: 'analyze' }, options: [{ id: 'option-b', label: '分析这些结果' }] }
            const item = Object.assign(kind === 'learning' ? learningQuestion(11, mode) : reviewItem(11), { mode, dimension, question })
            const page = kind === 'learning' ? pageFor('learning') : reviewPage([item, reviewItem(12)])
            if (kind === 'learning') page.applyQueue(learningQueue(item))
            const oldEvent = answerEvent(kind, item, page.data.answerRenderEpoch)
            handlers.push(success({
                ok: true, response_kind: 'forgot', first_response_kind: 'forgot', is_correct: false,
                attempt_id: kind === 'learning' ? 'vocabulary-group:42:first:11' : 'wx-vocabulary-review:7:11',
                revealed_answer: revealedAnswer,
                answer_feedback: { word: 'analyze', core_meaning_zh: '分析', example_en: 'Analyze these results.' }
            }))
            await page.submitForgot(oldEvent)
            const expected = mode === 'context_choice' ? '分析这些结果' : revealedAnswer
            assert.equal(page.data.correctAnswer, expected, `${kind}/${dimension}`)
            assert.equal(page.data.answerFeedback.word, 'analyze')
            assert.equal(page.data.answerFeedback.example_en, 'Analyze these results.')
            assert.equal(page.data.showResult, true)
            assert.equal(page.data.correctionRequired, false)
            assert.equal(page.data.correctionCompleted, false)
            assert.equal(page.data.submittedAnswer, '忘了')
            page.submitAnswer(oldEvent)
            page.submitForgot(oldEvent)
            page.onInput(inputEvent(kind, item, page.data.answerRenderEpoch, 'late keyboard value'))
            assert.equal(page.data.showResult, true)
            assert.equal(page.data.correctAnswer, expected)
            assert.equal(requests.length, 1, `${kind}/${dimension} must not fetch or settle before confirmation`)
        }
    }
})

test('learning last forgotten answer recovered after timeout waits before its first settlement', async () => {
    reset()
    const page = pageFor('learning')
    page.applyQueue(learningQueue(learningQuestion(11), { phase: 'retry' }))
    const saved = { learning_question_id: 11, attempt_id: 'vocabulary-group:42:retry:11', response_kind: 'forgot', is_correct: false, revealed_answer: 'analyze' }
    const completed = learningQueue(null, { phase: 'complete', completed: true, saved_response: saved })
    handlers.push(failed('request:fail timeout'), success(completed))
    await page.submitForgot()
    assert.equal(page.data.currentQuestion.learning_question_id, 11)
    assert.equal(page.data.phase, 'retry')
    assert.equal(page.data.correctAnswer, 'analyze')
    assert.equal(page.data.finished, false)
    assert.equal(requests.length, 2)
    assert.equal(requests.filter((request) => /\/submit$/.test(request.url)).length, 1)
    handlers.push(success(completed), success({ ok: true, correct_count: 0, total_count: 1, accuracy: 0 }))
    const event = answerEvent('learning', page.data.currentQuestion, page.data.answerRenderEpoch)
    const moving = page.continueAfterResult(event)
    page.continueAfterResult(event)
    await moving
    await flushRequestTurns()
    assert.equal(page.data.finished, true)
    assert.equal(page.data.result.accuracy, 0)
    assert.equal(requests.filter((request) => request.url.endsWith('/tasks/42/submit')).length, 1)
})

test('learning recovery of an already settled forgotten answer restores the saved result without another write', async () => {
    reset()
    const page = pageFor('learning')
    page.applyQueue(learningQueue(learningQuestion(11), { phase: 'retry' }))
    const settlement = { ok: true, correct_count: 0, total_count: 1, accuracy: 0 }
    handlers.push(failed('request:fail timeout'), success(learningQueue(null, {
        completed: true, phase: 'complete', settlement,
        saved_response: { learning_question_id: 11, attempt_id: 'vocabulary-group:42:retry:11', response_kind: 'forgot', is_correct: false, revealed_answer: 'analyze' }
    })))
    await page.submitForgot()
    assert.equal(page.data.finished, true)
    assert.equal(page.data.result.accuracy, 0)
    assert.equal(requests.length, 2)
    assert.equal(requests.filter((request) => request.url.endsWith('/tasks/42/submit')).length, 0)
})

test('review last forgotten answer recovered after timeout stays visible until explicit settlement', async () => {
    reset()
    const page = reviewPage([reviewItem(1)])
    const saved = reviewItem(1, { first_attempt_id: 'wx-vocabulary-review:7:1', first_response_kind: 'forgot', first_is_correct: false, revealed_answer: 'analyze' })
    handlers.push(failed('request:fail timeout'), success({ ok: true, session_id: 7, session_token: 'session-token', supports_forgot_response: true, items: [saved] }))
    await page.submitForgot()
    assert.equal(page.data.finished, false)
    assert.equal(page.data.correctAnswer, 'analyze')
    assert.equal(page.data.correctionCompleted, false)
    assert.equal(requests.length, 2)
    handlers.push(success({ ok: true, status: 'settled', total_count: 1, correct_count: 0, accuracy: 0 }))
    const event = answerEvent('review', page.data.currentItem, page.data.answerRenderEpoch)
    const settling = page.nextItem(event)
    page.nextItem(event)
    await settling
    assert.equal(page.data.finished, true)
    assert.equal(page.data.result.accuracy, 0)
    assert.equal(requests.filter((request) => request.url.endsWith('/settle')).length, 1)
})

test('late confirmation controls cannot bypass another forgotten result', async () => {
    reset()
    const learning = pageFor('learning')
    learning.applyQueue(learningQueue(learningQuestion(11)))
    const oldLearning = answerEvent('learning', learning.data.currentQuestion, learning.data.answerRenderEpoch)
    learning.applyQueue(learningQueue(learningQuestion(12)))
    learning.applyLearningAnswerResult(learning.data.currentQuestion, { response_kind: 'forgot', revealed_answer: 'new answer' }, '')
    learning.continueAfterResult(oldLearning)
    assert.equal(learning.data.currentQuestion.learning_question_id, 12)
    assert.equal(learning.data.correctAnswer, 'new answer')
    const review = reviewPage([
        reviewItem(1, { first_attempt_id: 'first-1', first_response_kind: 'forgot' }),
        reviewItem(2, { first_attempt_id: 'first-2', first_response_kind: 'forgot', revealed_answer: 'new answer' })
    ])
    const oldReview = answerEvent('review', review.data.currentItem, review.data.answerRenderEpoch)
    review.showItem(1)
    review.nextItem(oldReview)
    assert.equal(review.data.currentIndex, 1)
    assert.equal(review.data.finished, false)
    assert.equal(review.data.correctAnswer, 'new answer')
    assert.equal(requests.length, 0)
})

test('templates expose an explicit answer-reading action and hide the unavailable forgotten-answer appeal', () => {
    const learning = fs.readFileSync(`${__dirname}/../miniprogram/pages/student/vocabulary-learning/index.wxml`, 'utf8')
    const review = fs.readFileSync(`${__dirname}/../miniprogram/pages/student/vocabulary-review/index.wxml`, 'utf8')
    assert.ok(learning.includes('bindtap="continueAfterResult"'))
    assert.ok(learning.includes("showResult && responseKind !== 'forgot' && !isCorrect"))
    for (const source of [learning, review]) {
        assert.ok(source.includes('看过答案，继续'))
        assert.ok(source.includes('已记为未掌握，后续仍会复习'))
        const nextButton = source.match(/<button\b[^>]*class="[^"]*next-question-btn[^"]*"[^>]*>/)[0]
        assert.ok(nextButton.includes('data-question-id='))
        assert.ok(nextButton.includes('data-render-epoch='))
    }
})
