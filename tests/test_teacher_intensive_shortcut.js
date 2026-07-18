const assert = require('assert')
const {
    buildIntensiveQueueItems,
    findMatchingIntensiveParts
} = require('../miniprogram/utils/teacher-intensive-shortcut.js')

const catalog = [
    {
        series: 'cambridge',
        book: 18,
        label: '剑雅 18',
        tests: [{
            id: 'ielts18_test1',
            book: 18,
            test: 1,
            title: 'Cambridge IELTS 18 Test 1 Listening',
            parts: [
                { id: 'ielts18_test1_s1', number: 1, part_title: 'Part 1' },
                { id: 'ielts18_test1_s2', number: 2, part_title: 'Part 2' },
                { id: 'ielts18_test1_s3', number: 3, part_title: 'Part 3' }
            ]
        }]
    },
    {
        series: 'jfdr',
        book: 6,
        label: '9分达人 6',
        tests: [{
            id: 'jfdr6_test1',
            book: 6,
            test: 1,
            title: '9分达人听力6 Test 1 Listening',
            parts: [
                { id: 'jfdr6_test1_s1', number: 1, part_title: 'Part 1' },
                { id: 'jfdr6_test1_s2', number: 2, part_title: 'Part 2' }
            ]
        }]
    }
]

const ordinaryTask = (overrides = {}) => ({
    source_type: 'cambridge_listening',
    listening_exercise_id: 'ielts18_test1',
    ...overrides
})

const ids = items => items.map(item => item.practice_exercise_id || item.id)

assert.deepStrictEqual(
    ids(findMatchingIntensiveParts(catalog, ordinaryTask({ listening_section_number: 2 }))),
    ['ielts18_test1_s2']
)

assert.deepStrictEqual(
    ids(buildIntensiveQueueItems({
        catalog,
        listeningTask: ordinaryTask(),
        selectedPracticeList: [],
        existingTasks: [],
        date: '2026-07-18'
    })),
    ['ielts18_test1_s1', 'ielts18_test1_s2', 'ielts18_test1_s3']
)

assert.deepStrictEqual(
    ids(buildIntensiveQueueItems({
        catalog,
        listeningTask: ordinaryTask(),
        selectedPracticeList: [{ practice_exercise_id: 'ielts18_test1_s1' }],
        existingTasks: [{
            source_type: 'listening_intensive',
            listening_exercise_id: 'ielts18_test1_s2',
            date: '2026-07-18'
        }],
        date: '2026-07-18'
    })),
    ['ielts18_test1_s3']
)

assert.deepStrictEqual(
    ids(buildIntensiveQueueItems({
        catalog,
        listeningTask: ordinaryTask(),
        selectedPracticeList: [],
        existingTasks: [{
            source_type: 'listening_intensive',
            listening_exercise_id: 'ielts18_test1_s1',
            date: '2026-07-17'
        }],
        date: '2026-07-18'
    })),
    ['ielts18_test1_s1', 'ielts18_test1_s2', 'ielts18_test1_s3']
)

assert.deepStrictEqual(
    findMatchingIntensiveParts(catalog, ordinaryTask({ listening_exercise_id: 'missing_test' })),
    []
)
assert.deepStrictEqual(
    findMatchingIntensiveParts(catalog, ordinaryTask({ listening_section_number: 9 })),
    []
)

assert.deepStrictEqual(
    ids(buildIntensiveQueueItems({
        catalog,
        listeningTask: ordinaryTask({ listening_exercise_id: 'jfdr6_test1' }),
        selectedPracticeList: [],
        existingTasks: [],
        date: '2026-07-18'
    })),
    ['jfdr6_test1_s1', 'jfdr6_test1_s2']
)

console.log('teacher intensive shortcut tests passed')
