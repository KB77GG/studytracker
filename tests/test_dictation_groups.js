const assert = require('assert')
const {
    buildFixedGroupSizes,
    buildGroupPlans,
    findGroupIndex,
    groupBounds,
    normalizeGroupSizes
} = require('../miniprogram/utils/dictation-groups.js')

assert.deepStrictEqual(buildFixedGroupSizes(50, 20), [20, 30])
assert.deepStrictEqual(buildFixedGroupSizes(50, 25), [25, 25])
assert.deepStrictEqual(buildFixedGroupSizes(50, 10), [10, 10, 10, 10, 10])
assert.deepStrictEqual(normalizeGroupSizes([20, 30], 50), [20, 30])
assert.deepStrictEqual(normalizeGroupSizes([20, 20], 50), [50])
assert.deepStrictEqual(
    groupBounds([20, 30], 1),
    { groupIndex: 1, start: 20, end: 50, size: 30 }
)
assert.strictEqual(findGroupIndex([20, 30], 19), 0)
assert.strictEqual(findGroupIndex([20, 30], 20), 1)

const plans = buildGroupPlans(50)
assert(plans.some(plan => plan.key === '20_30' && plan.recommended))
assert(plans.some(plan => plan.key === '25_25'))

let practiceDefinition = null
global.getApp = () => ({ globalData: {} })
global.Page = definition => { practiceDefinition = definition }
global.wx = {}
require('../miniprogram/pages/student/dictation/practice/index.js')

const page = Object.assign({}, practiceDefinition)
page.data = Object.assign({}, practiceDefinition.data, {
    totalWords: 50,
    correctCount: 15,
    wrongWordsDetail: [{}, {}, {}, {}, {}],
    groupCorrectStart: 0,
    groupWrongStart: 0
})
page.setData = function (patch, callback) {
    Object.assign(this.data, patch)
    if (callback) callback()
}
page.pauseTimer = () => {}
page.stopTicker = () => {}
let savedCheckpoint = null
page.saveProgress = (index, extra) => { savedCheckpoint = { index, extra } }

page.activateGroup([20, 30], 0, { correctStart: 0, wrongStart: 0 })
assert.strictEqual(page.data.groupStart, 0)
assert.strictEqual(page.data.groupEnd, 20)
assert.strictEqual(page.data.hasMoreGroups, true)

page.finishCurrentGroup()
assert.strictEqual(page.data.phase, 'group_summary')
assert.strictEqual(page.data.groupSummaryInfo.total, 20)
assert.strictEqual(page.data.groupSummaryInfo.nextCount, 30)
assert.deepStrictEqual(savedCheckpoint.extra, {
    awaitingNextGroup: true,
    resumePhase: 'group_summary'
})

let familiarizationStarted = false
page.enterFamiliarization = () => { familiarizationStarted = true }
page.continueNextGroup()
assert.strictEqual(page.data.currentGroupIndex, 1)
assert.strictEqual(page.data.groupStart, 20)
assert.strictEqual(page.data.groupEnd, 50)
assert.strictEqual(page.data.hasMoreGroups, false)
assert.strictEqual(familiarizationStarted, true)
