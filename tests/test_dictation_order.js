const assert = require('assert')
const {
    applyDictationOrder,
    normalizeOrder
} = require('../miniprogram/utils/dictation-order.js')

const words = [
    { id: 1, word: 'ability' },
    { id: 2, word: 'account' },
    { id: 3, word: 'accuracy' },
    { id: 4, word: 'achieve' },
    { id: 5, word: 'adventure' },
    { id: 6, word: 'affect' }
]

assert.strictEqual(normalizeOrder('random'), 'random')
assert.strictEqual(normalizeOrder('bad'), 'sequence')

const sequence = applyDictationOrder(words, { order: 'sequence' })
assert.deepStrictEqual(sequence.map(item => item.id), [1, 2, 3, 4, 5, 6])
assert.notStrictEqual(sequence, words)

const firstRandom = applyDictationOrder(words, {
    order: 'random',
    taskId: 101,
    bookId: 7,
    start: 1,
    end: 6
})
const secondRandom = applyDictationOrder(words, {
    order: 'random',
    taskId: 101,
    bookId: 7,
    start: 1,
    end: 6
})
const otherTaskRandom = applyDictationOrder(words, {
    order: 'random',
    taskId: 102,
    bookId: 7,
    start: 1,
    end: 6
})

assert.deepStrictEqual(firstRandom.map(item => item.id), secondRandom.map(item => item.id))
assert.notDeepStrictEqual(firstRandom.map(item => item.id), words.map(item => item.id))
assert.notDeepStrictEqual(firstRandom.map(item => item.id), otherTaskRandom.map(item => item.id))
assert.deepStrictEqual(words.map(item => item.id), [1, 2, 3, 4, 5, 6])
