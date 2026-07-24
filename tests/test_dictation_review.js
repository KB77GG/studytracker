const assert = require('assert')
const {
    buildFirstAttemptId,
    buildRunStorageKey,
    ensureAttemptPayload,
    firstAttemptForWord,
    firstAttemptStateFromResponse,
    hydrateQueueFirstAttempts,
    getOrCreateRunId,
    isSuccessfulResponse,
    legacyWrongItemBelongsToBook,
    missingQueueItems,
    summarizeQueue,
    queueMode
} = require('../miniprogram/utils/dictation-review.js')

assert.strictEqual(
    buildFirstAttemptId(42, 7, 9),
    'dictation:first:task-42:word-9'
)
assert.strictEqual(
    buildFirstAttemptId(null, 7, 9),
    'dictation:first:book-7-session:word-9'
)

const queue = [
    { word_id: 1, source: 'assigned', mode: 'audio_to_en' },
    { word_id: 2, source: 'auto_review', mode: 'zh_to_en' },
    { word_id: 3, source: 'assigned', mode: 'spelling_drill' }
]
assert.deepStrictEqual(summarizeQueue(queue), {
    assignedCount: 2,
    reviewCount: 1,
    totalCount: 3
})
assert.strictEqual(queueMode(queue[0], 'en_to_zh'), 'audio_to_en')
assert.strictEqual(queueMode({ source: 'auto_review' }, 'en_to_zh'), 'en_to_zh')

for (const mode of ['audio_to_en', 'zh_to_en', 'en_to_zh', 'spelling_drill']) {
    assert.strictEqual(queueMode({ mode }, 'audio_to_en'), mode)
}

const storage = { value: null, get() { return this.value }, set(value) { this.value = value } }
const run1 = getOrCreateRunId(storage, buildRunStorageKey('book-7'), () => 'run-1')
const run2 = getOrCreateRunId(storage, buildRunStorageKey('book-7'), () => 'run-2')
assert.strictEqual(run1, 'run-1')
assert.strictEqual(run2, 'run-1')

const payloads = {}
const first = ensureAttemptPayload(payloads, 'word-9', {
    attempt_id: buildFirstAttemptId(null, 7, 9, run1),
    answer: 'alpha'
})
const retry = ensureAttemptPayload(payloads, 'word-9', {
    attempt_id: buildFirstAttemptId(null, 7, 9, run2),
    answer: 'changed'
})
assert.strictEqual(retry.attempt_id, first.attempt_id)
assert.strictEqual(retry.answer, 'alpha')
assert.strictEqual(isSuccessfulResponse({ ok: true }), true)
assert.strictEqual(isSuccessfulResponse({ ok: false, statusCode: 409 }), false)
const historical = firstAttemptStateFromResponse({
    ok: true,
    is_correct: false,
    idempotent: true,
    student_answer: 'alhpa',
    attempt_id: 'task-first'
}, 'alpha')
assert.deepStrictEqual(historical, {
    correct: false,
    answer: 'alhpa',
    attemptId: 'task-first',
    idempotent: true,
    recovered: true
})
assert.strictEqual(
    firstAttemptStateFromResponse({ ok: true, is_correct: false, idempotent: true }, 'alpha').answer,
    ''
)
const legacyFirst = firstAttemptStateFromResponse({ ok: true, is_correct: true }, 'alpha')
assert.strictEqual(legacyFirst.answer, 'alpha')
const recoveredRetry = firstAttemptStateFromResponse({
    ok: true,
    first_attempt: false,
    is_correct: true,
    student_answer: 'alpha',
    first_attempt_is_correct: false,
    first_attempt_answer: 'alhpa',
    first_attempt_id: 'task-first'
}, 'alpha')
assert.strictEqual(recoveredRetry.correct, false)
assert.strictEqual(recoveredRetry.answer, 'alhpa')
const recoveredWords = [
    { id: 41, word: 'alpha', first_attempt_id: 'first-41', first_is_correct: false, first_answer: 'alhpa' },
    { id: 42, word: 'bravo' }
]
const recovered = hydrateQueueFirstAttempts(recoveredWords)
assert.strictEqual(firstAttemptForWord(recovered, recoveredWords[0]).answer, 'alhpa')
assert.strictEqual(firstAttemptForWord(recovered, recoveredWords[0]).correct, false)
assert.strictEqual(firstAttemptForWord(recovered, recoveredWords[1]), null)
assert.deepStrictEqual(
    missingQueueItems({
        ok: false,
        error: 'queue_incomplete',
        missing_word_ids: [3, 2, 3, 999]
    }, queue),
    [queue[2], queue[1]]
)
assert.deepStrictEqual(missingQueueItems({ error: 'queue_changed' }, queue), [])
const bookWords = [{ id: 1, word: 'alpha' }]
assert.strictEqual(legacyWrongItemBelongsToBook({ book_id: 8, word: 'alpha' }, 7, bookWords), false)
assert.strictEqual(legacyWrongItemBelongsToBook({ dictation_book_id: 8, word: 'alpha' }, 7, bookWords), false)
assert.strictEqual(legacyWrongItemBelongsToBook({ book_id: 7, word: 'other' }, 7, bookWords), true)
assert.strictEqual(legacyWrongItemBelongsToBook({ word: 'alpha' }, 7, bookWords), true)
assert.strictEqual(legacyWrongItemBelongsToBook({ name: 'alpha' }, 7, bookWords), true)

console.log('dictation review utility tests passed')
