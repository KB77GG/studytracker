const assert = require('assert')

global.getApp = () => ({ globalData: {} })
let pageDefinition = null
global.Page = definition => {
    pageDefinition = definition
}

require('../miniprogram/pages/teacher/homework/index.js')

const makePage = () => {
    const page = {
        ...pageDefinition,
        data: JSON.parse(JSON.stringify(pageDefinition.data)),
        setData(update, callback) {
            Object.entries(update).forEach(([key, value]) => {
                this.data[key] = value
            })
            if (callback) callback()
        }
    }
    page.data.catalog = {
        cambridge_listening: [],
        listening_intensive: [],
        listening_jijing: [{
            label: '虾滑听力',
            title: 'Part 1 · 高频',
            tests: [{
                test_name: '001. Asia-Pacific Tours Activity Holidays',
                parts: [{
                    id: 'xiahuar_001_p1',
                    number: 1,
                    part_title: '练习',
                    question_name: 'Q1-10',
                    question_count: 10
                }]
            }]
        }],
        cambridge_reading: [],
        reading_jijing: [{
            label: 'ZYZ 5',
            book: 5,
            tests: [{
                id: 'reading_jijing_5_test_59',
                book: 5,
                test: 59,
                title: '阅读机经 5 Test 59',
                passages: [{
                    number: 1,
                    title: 'Passage 1',
                    question_name: 'Q1-14'
                }]
            }]
        }]
    }
    return page
}

const page = makePage()
assert.deepStrictEqual(
    page.data.sourceOptions.map(item => item.key),
    [
        'custom',
        'cambridge_listening',
        'listening_intensive',
        'listening_jijing',
        'cambridge_reading',
        'reading_jijing'
    ]
)

page.data.sourceIndex = page.findSourceIndex('listening_jijing')
page.refreshPracticeOptions(false)
assert.strictEqual(page.data.isJijingListeningSource, true)
assert.deepStrictEqual(page.data.jijingListeningBookLabels, ['Part 1 · 高频'])
assert.deepStrictEqual(
    page.data.jijingListeningTestLabels,
    ['001. Asia-Pacific Tours Activity Holidays']
)
const listening = page.buildSelectedPracticePayload()
assert.strictEqual(listening.source_type, 'listening_jijing')
assert.strictEqual(listening.practice_exercise_id, 'xiahuar_001_p1')
assert.strictEqual(listening.category, '雅思-听力-虾滑')
assert.ok(listening.summary.includes('Q1-10'))

const listeningEdit = page.buildEditSourceUpdate({
    source_type: 'listening_jijing',
    listening_exercise_id: 'xiahuar_001_p1'
})
assert.strictEqual(listeningEdit.jijingListeningBookIndex, 0)
assert.strictEqual(listeningEdit.jijingListeningTestIndex, 0)
assert.strictEqual(listeningEdit.jijingListeningPartIndex, 0)

page.data.sourceIndex = page.findSourceIndex('reading_jijing')
page.refreshPracticeOptions(false)
assert.strictEqual(page.data.isReadingJijingSource, true)
assert.deepStrictEqual(page.data.jijingReadingBookLabels, ['ZYZ 5'])
assert.deepStrictEqual(page.data.jijingReadingTestLabels, ['Test 59'])
assert.deepStrictEqual(
    page.data.jijingReadingScopeLabels,
    ['整套 Test', 'Passage 1 · Q1-14']
)
page.data.jijingReadingScopeIndex = 1
const reading = page.buildSelectedPracticePayload()
assert.strictEqual(reading.source_type, 'reading_jijing')
assert.strictEqual(reading.practice_test_id, 'reading_jijing_5_test_59')
assert.strictEqual(reading.practice_scope, 'passage')
assert.strictEqual(reading.practice_passage_number, 1)
assert.strictEqual(reading.category, '雅思-阅读-ZYZ')

const readingEdit = page.buildEditSourceUpdate({
    source_type: 'reading_jijing',
    reading_test_id: 'reading_jijing_5_test_59',
    reading_passage_number: 1
})
assert.strictEqual(readingEdit.jijingReadingBookIndex, 0)
assert.strictEqual(readingEdit.jijingReadingTestIndex, 0)
assert.strictEqual(readingEdit.jijingReadingScopeIndex, 1)

console.log('teacher jijing option tests passed')
