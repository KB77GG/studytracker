const assert = require('assert')
const fs = require('fs')
const path = require('path')
const test = require('node:test')

const { createAnswerTimeline, COALESCE_MS, MAX_EVENTS } = require('../miniprogram/utils/answer-timeline.js')

function fakeClock(start = 1_000_000) {
    let now = start
    return {
        now: () => now,
        advance: ms => { now += ms }
    }
}

test('records answers, leaves and returns as offsets from start', () => {
    const clock = fakeClock()
    const timeline = createAnswerTimeline({ now: clock.now })
    clock.advance(5000)
    timeline.recordAnswer(1)
    clock.advance(1000)
    timeline.markHidden()
    timeline.markHidden() // duplicate hide is ignored
    clock.advance(30000)
    timeline.markShown()
    timeline.markShown() // show without hide is ignored
    clock.advance(2000)
    timeline.recordAnswer('2')
    clock.advance(500)

    assert.deepStrictEqual(timeline.snapshot(), {
        v: 1,
        mode: 'practice',
        submitted_offset_ms: 38500,
        events: [[5000, 'a', '1'], [6000, 'h'], [36000, 's'], [38000, 'a', '2']]
    })
})

test('typing into the same blank is merged, revisits are kept', () => {
    const clock = fakeClock()
    const timeline = createAnswerTimeline({ now: clock.now })
    timeline.recordAnswer('5')
    clock.advance(COALESCE_MS - 1)
    timeline.recordAnswer('5')
    clock.advance(COALESCE_MS - 1)
    timeline.recordAnswer('5')
    clock.advance(1000)
    timeline.recordAnswer('6')
    clock.advance(1000)
    timeline.recordAnswer('5')
    const events = timeline.snapshot().events
    assert.deepStrictEqual(events.map(event => event[2]), ['5', '6', '5'])
    assert.strictEqual(events[0][0], 2 * (COALESCE_MS - 1))
})

test('ignores empty keys, caps event count, and reset starts a new session', () => {
    const clock = fakeClock()
    const timeline = createAnswerTimeline({ now: clock.now, mode: 'bogus' })
    timeline.recordAnswer('')
    timeline.recordAnswer(null)
    for (let i = 0; i < MAX_EVENTS + 50; i += 1) timeline.recordAnswer(`q${i}`)
    assert.strictEqual(timeline.snapshot().events.length, MAX_EVENTS)
    assert.strictEqual(timeline.snapshot().mode, 'practice')

    clock.advance(10000)
    timeline.markHidden()
    timeline.reset('redo_wrong')
    clock.advance(200)
    timeline.markShown() // hidden state cleared by reset, so nothing recorded
    const snapshot = timeline.snapshot()
    assert.strictEqual(snapshot.mode, 'redo_wrong')
    assert.strictEqual(snapshot.submitted_offset_ms, 200)
    assert.deepStrictEqual(snapshot.events, [])
})

test('snapshot is a copy that later answers do not mutate', () => {
    const clock = fakeClock()
    const timeline = createAnswerTimeline({ now: clock.now })
    timeline.recordAnswer('1')
    const first = timeline.snapshot()
    clock.advance(100)
    timeline.recordAnswer('1')
    assert.deepStrictEqual(first.events, [[0, 'a', '1']])
})

test('both reading homework pages send the timeline and track page visibility', () => {
    const pages = [
        'miniprogram/pages/student/reading/cambridge/index.js',
        'miniprogram/pages/student/material-choice/practice/index.js'
    ]
    for (const page of pages) {
        const source = fs.readFileSync(path.join(__dirname, '..', page), 'utf8')
        assert.match(source, /require\('..\/..\/..\/..\/utils\/answer-timeline.js'\)/, page)
        assert.match(source, /onHide\(\) \{\s+if \(this\.answerTimeline\) this\.answerTimeline\.markHidden\(\)/, page)
        assert.match(source, /onShow\(\) \{\s+if \(this\.answerTimeline\) this\.answerTimeline\.markShown\(\)/, page)
        assert.match(source, /integrity *[:=] *this\.answerTimeline[ .]/, page)
        assert.match(source, /this\.answerTimeline\.recordAnswer\(/, page)
        assert.match(source, /this\.answerTimeline\.reset\(/, page)
        assert.doesNotMatch(source, /wx\.request\(/, page)
    }
})
