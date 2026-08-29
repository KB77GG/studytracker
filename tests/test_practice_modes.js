const assert = require('node:assert/strict')
const test = require('node:test')

const modes = require('../static/js/practice_modes.js')

test('exactly one explicit mode flag must be active', () => {
  assert.equal(modes.resolve({ simulationMode: true }), 'simulation')
  assert.equal(modes.resolve({ practiceMode: true }), 'practice')
  assert.equal(modes.resolve({ intensiveListeningMode: true }), 'intensiveListening')
  assert.equal(modes.resolve({ reviewMode: true }), 'review')
  assert.throws(() => modes.resolve({}), /Exactly one/)
  assert.throws(() => modes.resolve({ simulationMode: true, reviewMode: true }), /Exactly one/)
})

test('simulation denies training and scoring capabilities by default', () => {
  const caps = modes.capabilities('simulation')
  assert.equal(caps.simulationMode, true)
  assert.equal(caps.canFlagQuestions, true)
  assert.equal(caps.requiresAudioPreflight, true)
  assert.equal(caps.usesServerDeadline, true)
  for (const capability of [
    'canPauseAudio',
    'canSeekAudio',
    'canReplayAudio',
    'canChangePlaybackRate',
    'canShowTranscript',
    'canShowAnalysis',
    'canShowCorrectness',
    'canUseQuestionNotes',
    'canUseMapZoom',
    'canUseReadingStudy',
    'canSubmitForScoring',
    'canResetAnswers',
    'showAnsweredSummary',
    'showPracticeScorePanel'
  ]) assert.equal(caps[capability], false, capability)
})

test('practice, intensive listening and review expose different capabilities', () => {
  const practice = modes.capabilities('practice')
  const intensive = modes.capabilities('intensiveListening')
  const review = modes.capabilities('review')

  assert.equal(practice.canSubmitForScoring, true)
  assert.equal(practice.canShowCorrectness, false)
  assert.equal(practice.canUseTrainingViews, false)
  assert.equal(intensive.canChangePlaybackRate, true)
  assert.equal(intensive.canShowTranscript, true)
  assert.equal(review.canShowCorrectness, true)
  assert.equal(review.canSubmitForScoring, false)
})

test('apply hides nodes whose capability is denied', () => {
  const nodes = [
    { dataset: { capability: 'canUseMapZoom' }, hidden: false, disabled: false, setAttribute(name, value) { this[name] = value } },
    { dataset: { capability: 'canFlagQuestions' }, hidden: false, disabled: false, setAttribute(name, value) { this[name] = value } }
  ]
  const documentElement = { dataset: {} }
  const body = { dataset: {} }
  const fakeDocument = {
    nodeType: 9,
    documentElement,
    body,
    querySelectorAll: () => nodes
  }

  modes.apply(fakeDocument, 'simulation')
  assert.equal(nodes[0].hidden, true)
  assert.equal(nodes[0].disabled, true)
  assert.equal(nodes[1].hidden, false)
  assert.equal(nodes[1].disabled, false)
  assert.equal(documentElement.dataset.experienceMode, 'simulation')
  assert.equal(body.dataset.experienceMode, 'simulation')
})
