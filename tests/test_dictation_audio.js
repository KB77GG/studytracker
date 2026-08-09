const assert = require('assert')
const fs = require('fs')
const path = require('path')
const { resolveAudioUrl } = require('../miniprogram/utils/dictation-audio.js')

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

console.log('dictation audio URL tests passed')
