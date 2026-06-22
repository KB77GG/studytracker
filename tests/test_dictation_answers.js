const assert = require('assert')
const {
    isEnglishAnswerCorrect,
    parseAnswerVariants
} = require('../miniprogram/utils/dictation-answers.js')

assert.strictEqual(isEnglishAnswerCorrect('behavior', { word: 'behaviour' }), false)
assert.strictEqual(isEnglishAnswerCorrect('behaviour', { word: 'behavior' }), false)
assert.strictEqual(isEnglishAnswerCorrect('bicycle', { word: 'bike' }), false)
assert.strictEqual(isEnglishAnswerCorrect('effect', { word: 'affect' }), false)
assert.strictEqual(
    isEnglishAnswerCorrect(
        'mobile phone',
        { word: 'cell phone', accepted_answers: ['mobile phone'] }
    ),
    true
)
assert.deepStrictEqual(parseAnswerVariants('["bike", "bicycle"]'), ['bike', 'bicycle'])
assert.deepStrictEqual(parseAnswerVariants('n. bike / bicycle'), ['bike', 'bicycle'])
