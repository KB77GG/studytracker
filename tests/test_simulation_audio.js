const assert = require('node:assert/strict')
const test = require('node:test')

const simulationAudio = require('../static/js/simulation_audio.js')

class FakeMedia {
  constructor(duration = 30) {
    this.duration = duration
    this.readyState = 0
    this.currentTime = 0
    this.playbackRate = 1
    this.volume = 1
    this.ended = false
    this.listeners = new Map()
    this.playCalls = 0
  }

  addEventListener(name, callback) {
    if (!this.listeners.has(name)) this.listeners.set(name, new Set())
    this.listeners.get(name).add(callback)
  }

  removeEventListener(name, callback) {
    this.listeners.get(name)?.delete(callback)
  }

  emit(name) {
    for (const callback of this.listeners.get(name) || []) callback({ type: name })
  }

  load() {
    this.readyState = 1
    queueMicrotask(() => this.emit('loadedmetadata'))
  }

  play() {
    this.playCalls += 1
    return Promise.resolve()
  }
}

test('preflight rejects a zero-duration resource and records valid durations', async () => {
  const durations = [12, 18]
  const rows = await simulationAudio.preflightResources(
    [{ url: '/a.mp3' }, { url: '/b.mp3' }],
    { createMedia: () => new FakeMedia(durations.shift()) }
  )
  assert.deepEqual(rows.map(row => row.duration), [12, 18])

  await assert.rejects(
    simulationAudio.preflightResources([{ url: '/bad.mp3' }], { createMedia: () => new FakeMedia(0) }),
    /invalid_audio_duration/
  )
})

test('server start time maps refresh recovery to the real playlist position', () => {
  assert.deepEqual(
    simulationAudio.timelinePosition([30, 40, 50], 1_000, 46_000),
    { complete: false, sectionIndex: 1, offsetSeconds: 15 }
  )
  assert.equal(simulationAudio.timelinePosition([30, 40], 1_000, 90_000).complete, true)
})

test('locked playlist keeps one media node, rejects seeking and advances only on ended', async () => {
  const audio = new FakeMedia(30)
  const sections = []
  const playlist = simulationAudio.createLockedPlaylist({
    audio,
    resources: [{ url: '/a.mp3' }, { url: '/b.mp3' }],
    onSectionChange: index => sections.push(index)
  })

  assert.equal(await playlist.loadSection(0, 7), true)
  assert.equal(audio.currentTime, 7)
  audio.currentTime = 8
  audio.emit('timeupdate')
  audio.currentTime = 2
  audio.emit('seeking')
  assert.equal(audio.currentTime, 8)

  audio.playbackRate = 1.5
  audio.emit('ratechange')
  assert.equal(audio.playbackRate, 1)

  audio.emit('pause')
  assert.equal(audio.playCalls, 2)

  audio.duration = 40
  audio.emit('ended')
  await new Promise(resolve => setImmediate(resolve))
  assert.deepEqual(sections, [0, 1])
  assert.equal(playlist.snapshot().mediaElementMounts, 1)
})
