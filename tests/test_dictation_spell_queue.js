const assert = require('assert')
const {
    isCorrectionWord,
    resolveWrongAnswer
} = require('../miniprogram/utils/dictation-spell-queue.js')

function word(id) {
    return { id, word: id, _originIndex: id === 'n' ? 0 : Number(id.slice(1)), _key: id }
}

const initial = [word('n'), ...Array.from({ length: 49 }, (_, index) => word(`w${index + 1}`))]
const firstWrong = resolveWrongAnswer(initial, initial[0])
assert.strictEqual(firstWrong.completeCurrent, false)
assert.strictEqual(firstWrong.queue.length, 51)
assert.strictEqual(firstWrong.queue[50].word, 'n')
assert.strictEqual(isCorrectionWord(firstWrong.queue[50]), true)

const duplicateWrong = resolveWrongAnswer(firstWrong.queue, firstWrong.queue[0])
assert.strictEqual(duplicateWrong.queue.length, 51, 'one word may only enter correction once')

let queue = firstWrong.queue.slice(1)
let completed = new Set()
let steps = 1
let wrongWordAppearances = 1
while (queue.length) {
    assert(steps < 60, 'a 50-word queue must finish in a bounded number of answers')
    const current = queue[0]
    if (current.word === 'n') {
        wrongWordAppearances += 1
        const transition = resolveWrongAnswer(queue, current)
        assert.strictEqual(transition.completeCurrent, true)
        completed.add(current._originIndex)
        queue = transition.queue
    } else {
        completed.add(current._originIndex)
    }
    queue = queue.slice(1).filter(item => !completed.has(item._originIndex))
    steps += 1
}
assert.strictEqual(steps, 51)
assert.strictEqual(wrongWordAppearances, 2)
assert.strictEqual(completed.size, 50)

const multiWrong = [word('n'), word('w1'), word('w2')]
let transition = resolveWrongAnswer(multiWrong, multiWrong[0])
transition = resolveWrongAnswer(transition.queue.slice(1), transition.queue[1])
assert.deepStrictEqual(
    transition.queue.filter(isCorrectionWord).map(item => item.word),
    ['n', 'w1'],
    'correction order follows first wrong encounter order'
)

const correctionOnly = transition.queue.find(item => isCorrectionWord(item))
const correctionWrong = resolveWrongAnswer([correctionOnly], correctionOnly)
assert.strictEqual(correctionWrong.completeCurrent, true)
assert.strictEqual(correctionWrong.queue.length, 1, 'wrong correction must not requeue itself')
