const test = require('node:test')
const assert = require('node:assert/strict')

const policy = require('../miniprogram/utils/dictation-input-policy.js')

test('only word-task English answer modes are classified as spelling input', () => {
    assert.equal(policy.isEnglishSpellingMode('audio_to_en'), true)
    assert.equal(policy.isEnglishSpellingMode('zh_to_en'), true)
    assert.equal(policy.isEnglishSpellingMode('spelling_drill'), true)
    assert.equal(policy.isEnglishSpellingMode('context_fill'), true)
    assert.equal(policy.isEnglishSpellingMode('en_to_zh'), false)
    assert.equal(policy.isEnglishSpellingMode('context_choice'), false)
})

test('mode classification normalizes case and whitespace', () => {
    assert.equal(policy.isEnglishSpellingMode('  AUDIO_TO_EN  '), true)
    assert.equal(policy.isEnglishSpellingMode(null), false)
})
