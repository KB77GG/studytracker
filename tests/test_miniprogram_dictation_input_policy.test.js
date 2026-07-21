const test = require('node:test')
const assert = require('node:assert/strict')

const policy = require('../miniprogram/utils/dictation-input-policy.js')

test('English spelling modes default to strict and English-to-Chinese stays native', () => {
    assert.equal(policy.defaultInputPolicy('audio_to_en').defaultInputMode, policy.INPUT_STRICT)
    assert.equal(policy.defaultInputPolicy('zh_to_en').defaultInputMode, policy.INPUT_STRICT)
    assert.equal(policy.defaultInputPolicy('spelling_drill').defaultInputMode, policy.INPUT_STRICT)
    assert.equal(policy.defaultInputPolicy('en_to_zh').defaultInputMode, policy.INPUT_NATIVE)
    assert.equal(policy.isEnglishSpellingMode('en_to_zh'), false)
})

test('stored compatible mode is ignored without an active server grant', () => {
    const strictPolicy = policy.defaultInputPolicy('zh_to_en')
    assert.equal(policy.chooseInputMode(strictPolicy, policy.INPUT_COMPATIBLE), policy.INPUT_STRICT)
    const authorized = Object.assign({}, strictPolicy, { compatibleAllowed: true })
    assert.equal(policy.chooseInputMode(authorized, policy.INPUT_COMPATIBLE), policy.INPUT_COMPATIBLE)
})

test('separator keys follow the actual answer', () => {
    assert.deepEqual(policy.answerSeparators('well-known'), [
        { key: '-', label: '-', ariaLabel: '连字符' }
    ])
    assert.deepEqual(policy.answerSeparators("don't stop"), [
        { key: ' ', label: '空格', ariaLabel: '空格' },
        { key: "'", label: "'", ariaLabel: '撇号' }
    ])
    assert.deepEqual(policy.answerSeparators('ordinary'), [])
})

test('keyboard key normalization never emits uppercase letters', () => {
    assert.equal(policy.normalizeKeyboardKey('A'), 'a')
    assert.equal(policy.normalizeKeyboardKey('’'), "'")
    assert.equal(policy.normalizeKeyboardKey(' '), ' ')
})

test('accepted answers can be longer than the canonical word', () => {
    assert.equal(policy.answerInputLimit('bike', ['bicycle']), 7)
    assert.equal(policy.answerInputLimit('bike', '["bicycle"]'), 7)
})
