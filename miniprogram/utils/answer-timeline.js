// 作答过程记录：记下本次作答中每道题的作答时刻、离开/回到页面的时刻，
// 交卷时随答案一起提交，供老师在后台判断是否异常作答。
// 只记录时间与题号，不记录任何答案内容；不影响判分和提交。
//
// 用法（页面里）：
//   onLoad:  this.answerTimeline = createAnswerTimeline({ mode })
//   onShow / onHide: this.answerTimeline.markShown() / markHidden()
//   作答时:  this.answerTimeline.recordAnswer(questionKey)
//   交卷时:  data.integrity = this.answerTimeline.snapshot()
//   重做时:  this.answerTimeline.reset(mode)

const TIMELINE_VERSION = 1
const MAX_EVENTS = 800
// 同一道题连续输入（例如填空逐字输入）在这个时间窗内合并成一次作答
const COALESCE_MS = 4000
const MODES = ['practice', 'redo_wrong', 'redo_all']

function normalizeMode(mode) {
    return MODES.indexOf(mode) >= 0 ? mode : 'practice'
}

function createAnswerTimeline(options = {}) {
    const now = typeof options.now === 'function' ? options.now : () => Date.now()
    let startedAt = now()
    let mode = normalizeMode(options.mode)
    let events = []
    let hidden = false

    function offset() {
        return Math.max(0, Math.round(now() - startedAt))
    }

    function push(event) {
        if (events.length >= MAX_EVENTS) return
        events.push(event)
    }

    return {
        recordAnswer(key) {
            const questionKey = String(key === undefined || key === null ? '' : key).trim()
            if (!questionKey) return
            const at = offset()
            const last = events[events.length - 1]
            if (last && last[1] === 'a' && last[2] === questionKey && at - last[0] <= COALESCE_MS) {
                last[0] = at
                return
            }
            push([at, 'a', questionKey])
        },

        markHidden() {
            if (hidden) return
            hidden = true
            push([offset(), 'h'])
        },

        markShown() {
            if (!hidden) return
            hidden = false
            push([offset(), 's'])
        },

        reset(nextMode) {
            startedAt = now()
            mode = normalizeMode(nextMode)
            events = []
            hidden = false
        },

        snapshot() {
            return {
                v: TIMELINE_VERSION,
                mode,
                submitted_offset_ms: offset(),
                events: events.map(event => event.slice())
            }
        }
    }
}

module.exports = {
    createAnswerTimeline,
    COALESCE_MS,
    MAX_EVENTS
}
