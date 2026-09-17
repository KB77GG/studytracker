const assert = require('node:assert/strict')
const test = require('node:test')

const clipPlayer = require('../static/js/listening_clip_player.js')

class FakeAudio {
  constructor () {
    this.currentTime = 0
    this.duration = 120
    this.readyState = 1
    this.listeners = new Map()
    this.pauseCount = 0
    this.playCount = 0
  }

  addEventListener (name, callback, options = {}) {
    const rows = this.listeners.get(name) || []
    rows.push({ callback, once: Boolean(options.once) })
    this.listeners.set(name, rows)
  }

  dispatch (name) {
    const rows = [...(this.listeners.get(name) || [])]
    this.listeners.set(name, rows.filter(row => !row.once))
    rows.forEach(row => row.callback())
  }

  pause () { this.pauseCount += 1 }
  play () { this.playCount += 1; return Promise.resolve() }
}

test('validates finite in-range windows and the media version duration', () => {
  assert.deepEqual(
    clipPlayer.validateWindow({ start: 10, end: 20, duration: 30 }),
    { ok: true, start: 10, end: 20 }
  )
  assert.equal(clipPlayer.validateWindow({ start: 20, end: 10, duration: 30 }).reason, 'invalid_window')
  assert.equal(clipPlayer.validateWindow({ start: 10, end: 40, duration: 30 }).reason, 'window_out_of_range')
  assert.equal(
    clipPlayer.validateWindow({ start: 10, end: 20, duration: 30, expectedDuration: 40 }).reason,
    'audio_version_mismatch'
  )
})

test('bounded playback seeks after metadata and stops at the declared end', () => {
  const audio = new FakeAudio()
  const selected = []
  const statuses = []
  const controller = clipPlayer.create({
    audio,
    selectSection: (index, preserve) => selected.push([index, preserve]),
    onStatus: (message, tone) => statuses.push([message, tone])
  })

  controller.playWindow({ sectionIndex: 2, start: 18, end: 24, label: '题组' })
  assert.equal(audio.currentTime, 18)
  assert.equal(audio.playCount, 1)
  assert.deepEqual(selected, [[2, true]])
  assert.equal(controller.state().boundary.end, 24)

  audio.currentTime = 24
  audio.dispatch('timeupdate')
  assert.equal(controller.state().boundary, null)
  assert.ok(audio.pauseCount >= 2)
  assert.match(statuses.at(-1)[0], /播放完毕/)
})

test('a stale loadedmetadata event cannot start an older section request', () => {
  const audio = new FakeAudio()
  audio.readyState = 0
  const selected = []
  const controller = clipPlayer.create({
    audio,
    selectSection: index => selected.push(index)
  })

  controller.playWindow({ sectionIndex: 0, start: 10, end: 20 })
  controller.playWindow({ sectionIndex: 1, start: 40, end: 50 })
  audio.readyState = 1
  audio.dispatch('loadedmetadata')

  assert.deepEqual(selected, [0, 1])
  assert.equal(audio.currentTime, 40)
  assert.equal(audio.playCount, 1)
  assert.equal(controller.state().boundary.end, 50)
})

test('invalid runtime metadata falls back to one full Section without overlap', () => {
  const audio = new FakeAudio()
  audio.duration = 30
  const selected = []
  const statuses = []
  const controller = clipPlayer.create({
    audio,
    selectSection: index => selected.push(index),
    onStatus: (message, tone) => statuses.push([message, tone])
  })

  controller.playWindow({ sectionIndex: 3, start: 80, end: 90 })

  assert.deepEqual(selected, [3, 3])
  assert.equal(audio.currentTime, 0)
  assert.equal(audio.playCount, 1)
  assert.equal(controller.state().boundary, null)
  assert.match(statuses.at(-1)[0], /回退播放完整 Section/)
  assert.equal(statuses.at(-1)[1], 'warn')
})

test('cancel invalidates pending metadata and pauses the old audio', () => {
  const audio = new FakeAudio()
  audio.readyState = 0
  const controller = clipPlayer.create({ audio, selectSection: () => {} })

  controller.playFrom({ sectionIndex: 0, start: 9 })
  controller.cancel({ pauseAudio: true })
  audio.readyState = 1
  audio.dispatch('loadedmetadata')

  assert.equal(audio.playCount, 0)
  assert.equal(controller.state().boundary, null)
  assert.ok(audio.pauseCount >= 2)
})

test('unbounded transcript seek still validates the expected media version', () => {
  const audio = new FakeAudio()
  audio.duration = 90
  const selected = []
  const statuses = []
  const controller = clipPlayer.create({
    audio,
    selectSection: index => selected.push(index),
    onStatus: (message, tone) => statuses.push([message, tone])
  })

  controller.playFrom({ sectionIndex: 2, start: 25, expectedDuration: 120 })

  assert.deepEqual(selected, [2, 2])
  assert.equal(audio.currentTime, 0)
  assert.equal(audio.playCount, 1)
  assert.match(statuses.at(-1)[0], /回退播放完整 Section/)
})
