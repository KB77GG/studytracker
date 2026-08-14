const assert = require('node:assert/strict')
const test = require('node:test')

let definition = null
let requestCalls = 0
let requestHandler = null

global.getApp = () => ({ globalData: { baseUrl: '', token: '', guestMode: true } })
global.Page = page => { definition = page }
global.wx = {
    getStorageSync: () => '',
    request: options => {
        requestCalls += 1
        if (requestHandler) requestHandler(options)
    },
    showToast: () => {}
}

require('../miniprogram/pages/student/listening/practice/index.js')

function makePage(overrides = {}) {
    const page = Object.assign({}, definition)
    page.data = Object.assign({}, JSON.parse(JSON.stringify(definition.data)), overrides)
    page.setData = function setData(patch, callback) {
        Object.assign(this.data, patch)
        if (callback) callback()
    }
    return page
}

const segment = {
    globalIndex: 0,
    sourceText: 'WOMAN: I need a table at seven.',
    text: 'I need a table at seven.'
}

const legacyProgress = {
    segment_text: segment.sourceText,
    hidden_word_indices: [2, 4, 6],
    total_words: 3,
    answers_json: ['need', 'table', 'seven'],
    correct_words: 3,
    accuracy: 100,
    is_completed: true
}

const challengeProgress = {
    segment_text: segment.sourceText,
    hidden_word_indices: [1, 2, 3, 4, 5, 6],
    total_words: 6,
    answers_json: ['i', 'need', 'a', 'table', 'at', 'seven'],
    correct_words: 6,
    accuracy: 100,
    is_completed: true
}

test('saved progress keeps a safe inferred input form despite the global level', () => {
    const page = makePage({ difficultyIndex: 2 })
    assert.equal(page.getDictationLevelForSegment(segment, legacyProgress), 'standard')

    const freshPage = makePage({ difficultyIndex: 1 })
    assert.equal(freshPage.getDictationLevelForSegment(segment, challengeProgress), 'challenge')
})

test('a historical sentence does not overwrite the global difficulty for the next new sentence', () => {
    const page = makePage({
        difficultyIndex: 2,
        segments: [segment],
        progressMap: { '0': legacyProgress },
        repeatProgressMap: {}
    })
    page.pauseAudio = () => {}
    page.selectSegment(0, false)

    assert.equal(page.data.difficultyIndex, 2, 'global challenge preference is retained')
    assert.equal(page.data.dictationLevelKey, 'standard', 'legacy partial progress remains per-word')
    assert.equal(page.data.activeDifficultyIndex, 1, 'UI reflects the safe inferred historical level')
    assert.equal(page.data.dictationLevelFrozen, true)

    const newSegment = { ...segment, globalIndex: 1 }
    page.data.segments = [newSegment]
    page.data.progressMap = {}
    page.selectSegment(0, false)
    assert.equal(page.data.dictationLevelKey, 'challenge', 'next untouched sentence returns to the global choice')
})

test('new mini-program levels feed the shared selector instead of drifting to standard', () => {
    const page = makePage({ difficultyIndex: 2, progressMap: {} })
    const hidden = page.getHideIndices(segment, 'challenge', segment.sourceText, null)
    assert.deepEqual(hidden, [1, 2, 3, 4, 5, 6])
    const basic = page.getHideIndices(segment, 'basic', segment.sourceText, null)
    assert.equal(basic.length >= 1 && basic.length <= 2, true)
})

test('difficulty changes are rejected after a sentence starts or has saved progress', () => {
    const savedPage = makePage({
        currentSegment: segment,
        difficultyIndex: 1,
        progressMap: { '0': legacyProgress }
    })
    savedPage.getDictationLevelForSegment(segment, legacyProgress)
    savedPage.changeDifficulty({ currentTarget: { dataset: { index: '2' } } })
    assert.equal(savedPage.data.difficultyIndex, 1)

    const startedPage = makePage({
        currentSegment: segment,
        difficultyIndex: 1,
        progressMap: {}
    })
    startedPage.freezeDictationLevel(segment, null)
    startedPage.changeDifficulty({ currentTarget: { dataset: { index: '2' } } })
    assert.equal(startedPage.data.difficultyIndex, 1)
})

test('assigned task locks first attempt, then unlocks review and upward difficulty', () => {
    const assignedSegment = {
        ...segment,
        assignedTrainingLevel: 'standard',
        challengeAllowed: true,
        start: 0,
        end: 7
    }
    const page = makePage({
        trainingPolicy: { locked: true, review_only: false },
        mode: 'listen',
        showOriginal: true,
        showTranslation: true,
        segments: [assignedSegment],
        progressMap: {},
        repeatProgressMap: {}
    })
    page.pauseAudio = () => {}
    page.selectSegment(0, false)

    assert.equal(page.data.mode, 'dictation')
    assert.equal(page.data.modeLockedBeforeFirst, true)
    assert.equal(page.data.revealAllowed, false)
    assert.equal(page.data.showOriginal, false)
    assert.equal(page.data.dictationLevelKey, 'standard')
    assert.deepEqual(
        page.data.difficultyOptions.map(option => option.disabled),
        [true, false, true]
    )

    page.switchMode({ currentTarget: { dataset: { mode: 'listen' } } })
    assert.equal(page.data.mode, 'dictation')

    page.data.progressMap = {
        '0': { ...legacyProgress, training_level: 'standard' }
    }
    page.selectSegment(0, false)
    assert.equal(page.data.modeLockedBeforeFirst, false)
    assert.equal(page.data.revealAllowed, true)
    assert.deepEqual(
        page.data.difficultyOptions.map(option => option.disabled),
        [true, false, false]
    )

    page.changeDifficulty({ currentTarget: { dataset: { index: '2' } } })
    assert.equal(page.data.dictationLevelKey, 'challenge')
    assert.equal(page.data.correctionMode, true)
})

test('review-only task reveals after a full pass and saves completion', async () => {
    requestCalls = 0
    requestHandler = options => options.success({
        statusCode: 200,
        data: {
            ok: true,
            segment: {
                segment_index: 0,
                segment_text: segment.sourceText,
                is_completed: true,
                training_level: 'review',
                correct_words: 0,
                total_words: 0,
                accuracy: 0,
                hidden_word_indices: [],
                answers: [],
                results: []
            },
            task: { status: 'done', accuracy: 0, completion_rate: 100 }
        }
    })
    const reviewSegment = { ...segment, start: 0, end: 5, challengeAllowed: true }
    const page = makePage({
        taskId: 7,
        token: 'review-token',
        trainingPolicy: { locked: true, review_only: true },
        reviewOnly: true,
        mode: 'listen',
        segments: [reviewSegment],
        progressMap: {},
        repeatProgressMap: {}
    })
    page.pauseAudio = () => {}
    page.reviewListenedMap = new Set()
    page.selectSegment(0, false)
    page.audioCtx = { currentTime: 5 }
    page.segmentStopHandled = false
    page.handleAudioTimeUpdate()
    assert.equal(page.data.reviewListened, true)
    assert.equal(page.data.revealAllowed, true)
    page.toggleOriginal()
    await page.completeReviewSegment()
    assert.equal(requestCalls, 1)
    assert.equal(page.data.currentSegment.isCompleted, true)
    assert.equal(page.data.summary.completionRate, 100)
    requestHandler = null
})

test('blank first answers and local correction never issue a POST', async () => {
    requestCalls = 0
    requestHandler = null
    const page = makePage({
        taskId: 7,
        currentSegment: segment,
        progressMap: {},
        hiddenIndices: [2, 4],
        blankAnswers: ['', ''],
        difficultyIndex: 1,
        hasDictationTargets: true,
        dictationLocked: false,
        correctionMode: false
    })
    await page.submitCurrentSegment()
    assert.equal(requestCalls, 0, 'empty per-word first answer is blocked')

    const challengePage = makePage({
        taskId: 7,
        currentSegment: segment,
        progressMap: {},
        hiddenIndices: [1, 2, 3, 4, 5, 6],
        blankAnswers: [],
        challengeAnswer: '   ',
        difficultyIndex: 2,
        hasDictationTargets: true,
        dictationLocked: false,
        correctionMode: false
    })
    challengePage.dictationLevelMap = new Map([['0', 'challenge']])
    await challengePage.submitCurrentSegment()
    assert.equal(requestCalls, 0, 'empty challenge first answer is blocked')

    const correctionPage = makePage({
        taskId: 7,
        currentSegment: segment,
        progressMap: { '0': legacyProgress },
        hiddenIndices: [2, 4],
        blankAnswers: ['need', 'table'],
        difficultyIndex: 1,
        hasDictationTargets: true,
        dictationLocked: false,
        correctionMode: true
    })
    correctionPage.dictationLevelMap = new Map([['0', 'standard']])
    await correctionPage.submitCurrentSegment()
    assert.equal(requestCalls, 0, 'correction is evaluated locally only')
})

test('failed first save stays refresh-required after switching away and back', async () => {
    requestCalls = 0
    requestHandler = options => options.success({ statusCode: 500, data: { ok: false } })
    const page = makePage({
        taskId: 7,
        token: 'test-token',
        currentSegment: segment,
        currentIndex: 0,
        segments: [segment],
        progressMap: {},
        repeatProgressMap: {},
        hiddenIndices: [2, 4],
        blankAnswers: ['need', 'table'],
        difficultyIndex: 1,
        hasDictationTargets: true,
        dictationLocked: false,
        correctionMode: false,
        startedAt: Date.now() - 1000
    })
    page.pauseAudio = () => {}

    await page.submitCurrentSegment()
    assert.equal(requestCalls, 1)
    assert.equal(page.data.pendingSave, true)
    assert.match(page.data.dictationNotice, /首答保存未确认/)

    page.selectSegment(0, false)
    assert.equal(page.data.dictationLocked, true)
    assert.equal(page.data.pendingSave, true)
    assert.equal(page.data.currentResult.correctWords, 2)
    assert.match(page.data.dictationNotice, /刷新确认/)
    requestHandler = null
})

test('server canonical word judgments replace conflicting local colors and score', async () => {
    requestCalls = 0
    requestHandler = options => options.success({
        statusCode: 200,
        data: {
            ok: true,
            segment: {
                segment_text: segment.sourceText,
                hidden_word_indices: [2, 4, 6],
                answers: ['need', 'table', 'seven'],
                correct_words: 1,
                total_words: 3,
                accuracy: 33.3,
                results: [
                    { index: 0, wordIndex: 2, answer: 'need', rawAnswer: 'need', isCorrect: true, isExtra: false },
                    { index: 1, wordIndex: 4, answer: 'table', rawAnswer: 'table', isCorrect: false, isExtra: false },
                    { index: 2, wordIndex: 6, answer: 'seven', rawAnswer: 'seven', isCorrect: false, isExtra: false }
                ]
            },
            task: { accuracy: 33.3, completion_rate: 100 }
        }
    })
    const page = makePage({
        taskId: 7,
        token: 'test-token',
        currentSegment: segment,
        currentIndex: 0,
        segments: [segment],
        progressMap: {},
        repeatProgressMap: {},
        hiddenIndices: [2, 4, 6],
        blankAnswers: ['need', 'table', 'seven'],
        difficultyIndex: 1,
        hasDictationTargets: true,
        dictationLocked: false,
        correctionMode: false,
        startedAt: Date.now() - 1000
    })
    page.dictationLevelMap = new Map([['0', 'standard']])

    await page.submitCurrentSegment()

    assert.equal(page.data.currentResult.accuracy, 33.3)
    assert.equal(page.data.currentResult.correctWords, 1)
    const blanks = page.data.renderTokens.filter(item => item.kind === 'blank')
    assert.deepEqual(blanks.map(item => item.status), ['correct', 'wrong', 'wrong'])
    assert.equal(page.data.summary.accuracy, 33.3)
    requestHandler = null
})

test('unsaved mini-program answers survive mode and sentence rebuilds', () => {
    const page = makePage({
        currentSegment: segment,
        currentIndex: 0,
        segments: [segment],
        progressMap: {},
        repeatProgressMap: {},
        difficultyIndex: 1,
        dictationLevelKey: 'standard',
        blankAnswers: ['draft-one', 'draft-two'],
        challengeAnswer: '',
        dictationLocked: false,
        correctionMode: false
    })
    page.dictationStartedMap = new Set(['0'])
    page.correctionMap = new Set()
    page.firstAttemptGates = new Map()
    page.dictationLevelMap = new Map([['0', 'standard']])
    page.pendingFirstAttempts = new Map()
    page.dictationDraftMap = new Map()
    page.pauseAudio = () => {}

    page.saveCurrentDictationDraft()
    page.selectSegment(0, false)
    assert.equal(page.data.blankAnswers[0], 'draft-one')
    assert.equal(page.data.blankAnswers[1], 'draft-two')

    page.data.mode = 'dictation'
    page.switchMode({ currentTarget: { dataset: { mode: 'listen' } } })
    page.switchMode({ currentTarget: { dataset: { mode: 'dictation' } } })
    assert.equal(page.data.blankAnswers[0], 'draft-one')
})

test('unsaved challenge textarea survives a mode rebuild', () => {
    const page = makePage({
        currentSegment: segment,
        currentIndex: 0,
        segments: [segment],
        progressMap: {},
        repeatProgressMap: {},
        difficultyIndex: 2,
        dictationLevelKey: 'challenge',
        blankAnswers: [],
        challengeAnswer: 'I need a draft sentence',
        dictationLocked: false,
        correctionMode: false
    })
    page.dictationStartedMap = new Set(['0'])
    page.correctionMap = new Set()
    page.firstAttemptGates = new Map()
    page.dictationLevelMap = new Map([['0', 'challenge']])
    page.pendingFirstAttempts = new Map()
    page.dictationDraftMap = new Map()
    page.pauseAudio = () => {}

    page.saveCurrentDictationDraft()
    page.selectSegment(0, false)
    assert.equal(page.data.challengeAnswer, 'I need a draft sentence')
})

test('summary is derived from visible progress instead of stale task aggregates', () => {
    const second = { ...segment, globalIndex: 1 }
    const page = makePage()
    const summary = page.buildSummary(
        [segment, second],
        {
            '0': { is_completed: true, correct_words: 2, total_words: 3 }
        },
        { accuracy: 99, completion_rate: 100 }
    )
    assert.deepEqual(summary, {
        completedCount: 1,
        totalCount: 2,
        accuracy: 66.7,
        completionRate: 50
    })
})

test('audio playback waits for seek, never double-plays, and cancellation is effective', () => {
    const calls = { pause: 0, seek: [], play: 0 }
    const page = makePage({
        currentSegment: { ...segment, start: 4.5, end: 8.7 },
        audioReady: true,
        speedIndex: 1
    })
    page.audioCtx = {
        currentTime: 0,
        pause: () => { calls.pause += 1 },
        seek: value => calls.seek.push(value),
        play: () => { calls.play += 1 },
        playbackRate: 1
    }
    page.pendingPlaybackToken = 0
    page.pendingSeekPlayback = null
    page.audioBoundaryTimer = null
    page.pendingPlaybackFallback = null

    page.playCurrentSegment()
    const token = page.pendingPlaybackToken
    assert.deepEqual(calls.seek, [4.5])
    assert.equal(calls.play, 0, 'play is deferred until seek completes')
    assert.equal(page.completePendingPlayback(token), true)
    assert.equal(page.completePendingPlayback(token), false)
    assert.equal(calls.play, 1, 'seek and fallback cannot double-play')

    page.playCurrentSegment()
    const cancelledToken = page.pendingPlaybackToken
    page.pauseAudio()
    assert.equal(page.completePendingPlayback(cancelledToken), false)
    assert.equal(calls.play, 1, 'pause cancels a pending seek/play sequence')

    page.data.audioReady = false
    page.playCurrentSegment()
    assert.equal(page.pendingAutoplay, true, 'not-ready audio defers playback')
    page.cancelPendingPlayback()
})

test('audio boundary monitor clamps display and pauses at the sentence end', () => {
    let paused = 0
    const page = makePage({
        currentSegment: { ...segment, start: 4.5, end: 8.7 }
    })
    page.audioCtx = { currentTime: 9.1 }
    page.pauseAudio = () => { paused += 1 }
    page.segmentStopHandled = false
    page.handleAudioTimeUpdate()
    assert.equal(page.data.currentTimeText, '00:04')
    assert.equal(paused, 1)
})

test('mini-program audio events wait for canplay and seeked before one real play', () => {
    const originalSetInnerAudioOption = wx.setInnerAudioOption
    const originalCreateInnerAudioContext = wx.createInnerAudioContext
    const handlers = {}
    const calls = { seek: [], play: 0, pause: 0 }
    const audio = {
        currentTime: 0,
        onCanplay: callback => { handlers.canplay = callback },
        onSeeked: callback => { handlers.seeked = callback },
        onPlay: callback => { handlers.play = callback },
        onPause: callback => { handlers.pause = callback },
        onStop: callback => { handlers.stop = callback },
        onEnded: callback => { handlers.ended = callback },
        onTimeUpdate: callback => { handlers.timeupdate = callback },
        onError: callback => { handlers.error = callback },
        pause: () => { calls.pause += 1 },
        seek: value => calls.seek.push(value),
        play: () => { calls.play += 1 },
        stop: () => {},
        destroy: () => {},
        playbackRate: 1
    }
    wx.setInnerAudioOption = () => {}
    wx.createInnerAudioContext = () => audio

    try {
        const page = makePage({
            currentSegment: { ...segment, start: 4.5, end: 8.7 },
            audioReady: false,
            speedIndex: 1
        })
        page.pendingPlaybackToken = 0
        page.pendingSeekPlayback = null
        page.audioBoundaryTimer = null
        page.pendingPlaybackFallback = null
        page.initAudio()

        page.playCurrentSegment()
        assert.equal(page.pendingAutoplay, true)
        assert.equal(calls.play, 0)
        handlers.canplay()
        assert.deepEqual(calls.seek, [4.5])
        assert.equal(calls.play, 0)
        handlers.seeked()
        handlers.seeked()
        assert.equal(calls.play, 1, 'duplicate seeked events cannot double-play')
        page.destroyAudio()
    } finally {
        wx.setInnerAudioOption = originalSetInnerAudioOption
        wx.createInnerAudioContext = originalCreateInnerAudioContext
    }
})
