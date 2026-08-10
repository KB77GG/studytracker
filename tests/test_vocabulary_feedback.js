const assert = require('assert')

const { normalizeAnswerFeedback } = require('../miniprogram/utils/vocabulary-feedback.js')

const learning = normalizeAnswerFeedback({
    phonetic: ' ˈænəlɪst ',
    core_meaning_zh: '分析员；分析师',
    usage_pattern: 'financial analyst',
    example_en: 'He works as a financial analyst.',
    example_zh: '他是一名金融分析师。',
    usage_note: '常与 financial 搭配。'
}, {
    word: 'analyst',
    syllables: ['an', 'a', 'lyst'],
    audio_tts_url: '/dictation/words/1963/tts'
})

assert.deepStrictEqual(learning, {
    word: 'analyst',
    syllables: 'an · a · lyst',
    phonetic: 'ˈænəlɪst',
    core_meaning_zh: '分析员；分析师',
    usage_pattern: 'financial analyst',
    example_en: 'He works as a financial analyst.',
    example_zh: '他是一名金融分析师。',
    usage_note: '常与 financial 搭配。',
    audio_tts_url: '/dictation/words/1963/tts'
})

const restored = normalizeAnswerFeedback({
    answer_feedback: {
        word: 'audience',
        syllables: 'au·di·ence',
        phonetic: 'ˈɔːdiəns',
        core_meaning_zh: '观众；听众',
        audio_tts_url: '/dictation/words/1982/tts'
    }
})
assert.strictEqual(restored.word, 'audience')
assert.strictEqual(restored.syllables, 'au·di·ence')
assert.strictEqual(restored.core_meaning_zh, '观众；听众')
assert.strictEqual(restored.audio_tts_url, '/dictation/words/1982/tts')
assert.strictEqual(restored.usage_pattern, '')

assert.strictEqual(normalizeAnswerFeedback(null, null), null)
assert.strictEqual(normalizeAnswerFeedback({ answer_feedback: null }, {}), null)

console.log('vocabulary answer feedback tests passed')
