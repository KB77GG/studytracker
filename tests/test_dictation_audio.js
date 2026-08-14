const assert = require('assert')
const fs = require('fs')
const path = require('path')
const {
    resolveAudioUrl,
    createReliableAudioPlayer
} = require('../miniprogram/utils/dictation-audio.js')
const {
    buildMeaningChoiceOptions,
    selectedOptionLabel
} = require('../miniprogram/utils/vocabulary-interaction.js')

const base = 'https://studytracker.xin/api'
assert.strictEqual(
    resolveAudioUrl('/dictation/words/7/tts', base),
    'https://studytracker.xin/api/dictation/words/7/tts'
)
assert.strictEqual(
    resolveAudioUrl('/api/dictation/words/7/tts', base),
    'https://studytracker.xin/api/dictation/words/7/tts'
)
assert.strictEqual(
    resolveAudioUrl('https://cdn.example.test/a.mp3', base),
    'https://cdn.example.test/a.mp3'
)

const practiceSource = fs.readFileSync(
    path.join(__dirname, '../miniprogram/pages/student/dictation/practice/index.js'),
    'utf8'
)
const baseUrlCallCount = (
    practiceSource.match(/resolveAudioUrl\([\s\S]*?app\.globalData\.baseUrl\s*\)/g) || []
).length
assert.strictEqual(
    baseUrlCallCount,
    2,
    'playback and prefetch must both resolve relative word-id TTS URLs against the API base URL'
)

let innerAudioOptions = null
let canplayHandler = null
let playHandler = null
let playCount = 0
let destroyCount = 0
const fakeAudioContext = {
    src: '',
    stop() {},
    pause() {},
    seek() {},
    play() {
        playCount += 1
        if (playHandler) playHandler()
    },
    destroy() { destroyCount += 1 },
    onCanplay(handler) { canplayHandler = handler },
    onPlay(handler) { playHandler = handler },
    onEnded() {},
    onStop() {},
    onError() {}
}
const states = []
const fakeWx = {
    setInnerAudioOption(options) { innerAudioOptions = options },
    createInnerAudioContext() { return fakeAudioContext },
    downloadFile(options) {
        options.success({ statusCode: 206, tempFilePath: '/tmp/word.mp3' })
        return { abort() {} }
    }
}
const player = createReliableAudioPlayer(fakeWx, {
    onStateChange(state) { states.push(state) }
})
assert.strictEqual(innerAudioOptions.obeyMuteSwitch, false)
assert.strictEqual(fakeAudioContext.obeyMuteSwitch, false)
assert.strictEqual(player.play('/dictation/words/7/tts', base), true)
assert.strictEqual(playCount, 0, 'audio must wait for canplay before playing')
assert.strictEqual(fakeAudioContext.src, '/tmp/word.mp3')
canplayHandler()
assert.strictEqual(playCount, 1)
assert.deepStrictEqual(states.slice(0, 2), ['loading', 'playing'])
player.destroy()
assert.strictEqual(destroyCount, 1)

let failedAudioSrc = ''
const failedStates = []
const failedErrors = []
const failedPlayer = createReliableAudioPlayer({
    createInnerAudioContext() {
        return {
            get src() { return failedAudioSrc },
            set src(value) { failedAudioSrc = value },
            stop() {},
            play() {},
            destroy() {},
            onCanplay() {},
            onPlay() {},
            onEnded() {},
            onStop() {},
            onError() {}
        }
    },
    downloadFile(options) {
        options.success({ statusCode: 502, tempFilePath: '/tmp/error-response' })
        return { abort() {} }
    }
}, {
    onStateChange(state) { failedStates.push(state) },
    onError(error) { failedErrors.push(error) }
})
assert.strictEqual(failedPlayer.play('/dictation/words/8/tts', base), true)
assert.strictEqual(failedAudioSrc, '', 'HTTP failures must not be retried through InnerAudioContext')
assert.deepStrictEqual(failedStates, ['loading', 'error'])
assert.strictEqual(failedErrors.length, 1)
assert.strictEqual(failedErrors[0].statusCode, 502)
failedPlayer.destroy()

const question = {
    question_id: 'fixed-question',
    word_id: 7,
    question: { options: [] }
}
const familiarity = [
    { word_id: 1, meaning: '甲' },
    { word_id: 2, meaning: '乙' },
    { word_id: 3, meaning: '丙' },
    { word_id: 4, meaning: '丁' },
    { word_id: 7, meaning: '正确释义' },
    { word_id: 8, meaning: '戊' }
]
const meaningOptions = buildMeaningChoiceOptions(question, familiarity)
assert.strictEqual(meaningOptions.length, 4)
const correctOption = meaningOptions.find((option) => option.label === '正确释义')
assert(correctOption, 'local choices must always retain the correct meaning')
assert.strictEqual(selectedOptionLabel(meaningOptions, correctOption.id), '正确释义')
assert.deepStrictEqual(meaningOptions, buildMeaningChoiceOptions(question, familiarity))

console.log('dictation audio URL tests passed')
