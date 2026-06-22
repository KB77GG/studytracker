const assert = require('assert')
const {
    englishAnswerLengthHint,
    isEnglishAnswerCorrect,
    parseAnswerVariants
} = require('../miniprogram/utils/dictation-answers.js')

assert.strictEqual(isEnglishAnswerCorrect('behavior', { word: 'behaviour' }), true)
assert.strictEqual(isEnglishAnswerCorrect('behaviour', { word: 'behavior' }), true)
assert.strictEqual(
    isEnglishAnswerCorrect('bicycle', { word: 'bike' }, { allowSynonyms: true }),
    true
)
assert.strictEqual(isEnglishAnswerCorrect('bicycle', { word: 'bike' }), false)
assert.strictEqual(isEnglishAnswerCorrect('effect', { word: 'affect' }), false)
assert.strictEqual(
    isEnglishAnswerCorrect(
        'mobile phone',
        { word: 'cell phone', accepted_answers: ['mobile phone'] },
        { allowSynonyms: true }
    ),
    true
)
assert.deepStrictEqual(parseAnswerVariants('["bike", "bicycle"]'), ['bike', 'bicycle'])
assert.deepStrictEqual(parseAnswerVariants('n. bike / bicycle'), ['bike', 'bicycle'])
assert.strictEqual(
    englishAnswerLengthHint({ word: 'bike' }, { allowSynonyms: true }),
    '可接受答案：4 或 7 个字母'
)
assert.strictEqual(
    englishAnswerLengthHint({ word: 'behaviour' }),
    '可接受答案：8 或 9 个字母'
)
