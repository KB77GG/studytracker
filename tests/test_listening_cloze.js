const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')

const web = require('../static/js/listening-cloze.js')
const mini = require('../miniprogram/utils/listening-cloze.js')
const fixturePath = path.join(__dirname, 'fixtures', 'listening_cloze_contract.json')
const fixtures = JSON.parse(fs.readFileSync(fixturePath, 'utf8'))

const LEVELS = ['basic', 'standard', 'challenge']

test('web and mini-program selectors satisfy the shared listening cloze contract', () => {
    fixtures.filter(sample => sample.expected).forEach(sample => {
        LEVELS.forEach(level => {
            const options = { seed: sample.seed }
            const webIndices = web.selectHiddenWordIndices(sample.text, level, options)
            const miniIndices = mini.selectHiddenWordIndices(sample.text, level, options)
            assert.deepEqual(webIndices, sample.expected[level], `${sample.name} web ${level}`)
            assert.deepEqual(miniIndices, sample.expected[level], `${sample.name} mini ${level}`)
            assert.deepEqual(webIndices, miniIndices, `${sample.name} contract ${level}`)
        })
    })
})

test('hard exclusions apply by default while empty-safe fallback remains answerable', () => {
    const greeting = fixtures.find(sample => sample.name === 'speaker-label-and-greeting')
    const named = fixtures.find(sample => sample.name === 'unspelled-name-and-time')
    ;[greeting, named].forEach(sample => {
        Object.entries(sample.notSelected).forEach(([level, forbidden]) => {
            const selected = web.selectHiddenWordIndices(sample.text, level, { seed: sample.seed })
            forbidden.forEach(index => assert.ok(!selected.includes(index), `${sample.name}:${level}:${index}`))
        })
    })
    const challenge = web.selectHiddenWordIndices(greeting.text, 'challenge', { seed: greeting.seed })
    assert.ok(!challenge.includes(0), 'speaker label is never a challenge answer')
    assert.deepEqual(web.selectHiddenWordIndices('Yes.', 'standard'), [0])
    assert.deepEqual(web.selectHiddenWordIndices('...', 'standard'), [])
})

test('contextual acknowledgements and spelling evidence do not over-exclude content or names', () => {
    const sample = fixtures.find(item => item.name === 'contextual-response-and-spelling-scope')
    const content = web.analyseTokens(sample.contentText)
    sample.contentWords.forEach(word => {
        const token = content.find(item => item.normalized === word)
        assert.equal(token.filler, false, `${word} remains content in context`)
        assert.equal(token.hardExcluded, false, `${word} remains selectable in context`)
    })

    const response = web.analyseTokens(sample.responseText)
        .find(item => item.normalized === sample.responseWord)
    assert.equal(response.filler, true, 'response-like right is still excluded')

    const spelling = web.analyseTokens(sample.spellingText)
    const spellingTarget = spelling.find(item => item.normalized === sample.spellingTarget)
    const unspelledName = spelling.find(item => item.normalized === sample.unspelledName)
    assert.equal(spellingTarget.spelling, true)
    assert.equal(spellingTarget.name, false)
    assert.equal(unspelledName.name, true, 'whole-sentence spelling evidence cannot unlock another name')
    const upperSpelling = web.analyseTokens(sample.uppercaseSpellingText)
    const upperTarget = upperSpelling.find(item => item.normalized === sample.uppercaseSpellingTarget)
    const upperUnspelled = upperSpelling.find(item => item.normalized === sample.uppercaseUnspelledName)
    assert.equal(upperTarget.spelling, true)
    assert.equal(upperTarget.name, false)
    assert.equal(upperUnspelled.name, true, 'uppercase spelling evidence stays token-scoped')
    const separateLetters = web.analyseTokens('WOMAN: The code is A U D L E Y.')
        .filter(item => /^[AUDLEY]$/.test(item.display) && item.index >= 4)
    assert.equal(separateLetters.length, 6)
    assert.equal(separateLetters.every(item => item.spelling && !item.name), true,
        'a spaced letter run is treated as explicit spelling information')
    const whitelisted = web.analyseTokens('MAN: Meet Daniel at seven.', {
        properNounWhitelist: ['Daniel']
    }).find(item => item.normalized === 'daniel')
    assert.equal(whitelisted.name, false, 'proper-name whitelist remains configurable')
    assert.deepEqual(mini.analyseTokens(sample.spellingText), spelling, 'mini spelling contract')
})

test('difficulty boundaries are deterministic and basic/standard avoid meaningless adjacency', () => {
    const long = fixtures.find(sample => sample.name === 'long-time-boundary')
    assert.equal(web.getTargetCount('basic', 8), 1)
    assert.equal(web.getTargetCount('basic', 9), 2)
    assert.equal(web.getTargetCount('standard', 2), 2)
    assert.equal(web.getTargetCount('standard', 8), 3)
    assert.equal(web.getTargetCount('standard', 15), 4)
    assert.deepEqual(
        web.selectHiddenWordIndices(long.text, 'standard', { seed: long.seed }),
        web.selectHiddenWordIndices(long.text, 'standard', { seed: long.seed })
    )

    const analysed = web.analyseTokens(long.text)
    const standard = web.selectHiddenWordIndices(long.text, 'standard', { seed: long.seed })
    for (let index = 1; index < standard.length; index += 1) {
        if (standard[index] - standard[index - 1] !== 1) continue
        const left = analysed.find(token => token.index === standard[index - 1])
        const right = analysed.find(token => token.index === standard[index])
        assert.equal(left.highValue && right.highValue, true)
    }
})

test('challenge mode keeps numeric word indices and per-word compatible answers', () => {
    const text = "WOMAN: I don't need twenty-one pounds."
    const hidden = web.selectHiddenWordIndices(text, 'challenge', { seed: 'challenge' })
    assert.deepEqual(hidden, [1, 2, 3, 4, 5])
    assert.equal(hidden.every(Number.isInteger), true)

    const answers = web.splitChallengeAnswers("I don't need twenty-one pounds", hidden.length)
    assert.equal(Array.isArray(answers), true)
    assert.equal(answers.length, hidden.length)
    const grade = web.gradeAnswers(text, hidden, answers)
    assert.equal(grade.correctWords, hidden.length)
    assert.equal(grade.accuracy, 100)
    assert.equal(grade.results[1].answer, "don't")
    assert.equal(grade.results[3].answer, 'twenty-one')
})

test('challenge mode penalizes every extra supplied word and keeps one-decimal scores', () => {
    const text = 'WOMAN: I need a table.'
    const hidden = [1, 2, 3, 4]
    const answers = web.splitChallengeAnswers('I need a table please', hidden.length)
    assert.equal(answers.length, 5, 'extra input is retained for grading')
    const webGrade = web.gradeAnswers(text, hidden, answers)
    const miniGrade = mini.gradeAnswers(text, hidden, answers)
    assert.equal(webGrade.correctWords, 4)
    assert.equal(webGrade.totalWords, 5)
    assert.equal(webGrade.accuracy, 80)
    assert.equal(webGrade.results.at(-1).isExtra, true)
    assert.equal(webGrade.results.at(-1).rawAnswer, 'please')
    assert.deepEqual(miniGrade, webGrade)

    const decimal = web.gradeAnswers('MAN: red blue green.', [1, 2, 3], ['red', 'wrong', 'green'])
    assert.equal(decimal.accuracy, 66.7)
})

test('legacy coordinate bases and new canonical web submissions remain compatible', () => {
    const legacy = fixtures.find(sample => sample.name === 'legacy-coordinate-bases')
    ;['legacyWeb', 'legacyMini', 'newCanonical'].forEach(key => {
        const saved = legacy[key]
        const webGrade = web.gradeAnswers(saved.segmentText, saved.hiddenWordIndices, saved.answers)
        const miniGrade = mini.gradeAnswers(saved.segmentText, saved.hiddenWordIndices, saved.answers)
        assert.deepEqual(webGrade.results.map(result => result.wordIndex), saved.hiddenWordIndices, key)
        assert.deepEqual(webGrade.results.map(result => result.answer), saved.expectedWords, key)
        assert.deepEqual(miniGrade, webGrade, `${key} contract`)
    })

    const newSaved = legacy.newCanonical
    const oldMiniCompatible = mini.gradeAnswers(
        newSaved.segmentText,
        newSaved.hiddenWordIndices,
        newSaved.answers
    )
    assert.equal(oldMiniCompatible.accuracy, 100)
})

test('saved progress infers challenge only from complete spoken-token coverage', () => {
    const sample = fixtures.find(item => item.name === 'saved-level-inference')
    ;['newChallenge', 'legacySixtyPercent', 'legacyFiftyPercent'].forEach(key => {
        const progress = sample[key]
        const webLevel = web.inferSavedDictationLevel(progress.segment_text, progress)
        const miniLevel = mini.inferSavedDictationLevel(progress.segment_text, progress)
        assert.equal(webLevel, progress.expectedLevel, `${key} web level`)
        assert.equal(miniLevel, progress.expectedLevel, `${key} mini level`)
    })
})

test('client integrations retain the empty-answer guard and frozen saved-level path', () => {
    const webPlayer = fs.readFileSync(path.join(__dirname, '..', 'templates', 'listening', 'player.html'), 'utf8')
    const miniPlayer = fs.readFileSync(path.join(__dirname, '..', 'miniprogram', 'pages', 'student', 'listening', 'practice', 'index.js'), 'utf8')
    assert.match(webPlayer, /请至少填写一个听写词，再提交/)
    assert.match(webPlayer, /请先输入整句或意群，再提交/)
    assert.match(webPlayer, /inferSavedDictationLevel\(sourceText \|\| savedProgress\.segment_text/)
    assert.match(webPlayer, /isDictationLevelFrozen\(context\.segGlobalIdx, context\.savedProgress\)/)
    assert.match(webPlayer, /clearFreeDictationTransientState\(\)/)
    assert.match(webPlayer, /markFirstAttemptSavePending\(context, grade, answers\)/)
    assert.match(miniPlayer, /请至少填写一个听写词，再提交首答/)
    assert.match(miniPlayer, /请先输入整句或意群，再提交首答/)
    assert.match(miniPlayer, /ListeningCloze\.inferSavedDictationLevel\(sourceText, progress\)/)
    assert.match(miniPlayer, /isDictationLevelFrozen\(currentSegment, progress\)/)
})

test('free-progress reset opens a fresh first-attempt gate without touching task state', () => {
    const containers = {
        dictationStartedSegments: new Set(['0']),
        correctionSegments: new Set(['0']),
        firstAttemptGates: new Map([['0', web.createFirstAttemptGate(false)]]),
        dictationDrafts: new Map([['0:standard', ['need']]]),
        dictationLevelsBySegment: new Map([['0', 'standard']]),
        pendingFirstAttempts: new Map([['0', { grade: { accuracy: 0 } }]])
    }
    containers.firstAttemptGates.get('0').beginFirstAttempt()
    assert.equal(web.clearFreePracticeTransientState(containers, true), false)
    assert.equal(containers.firstAttemptGates.get('0').beginFirstAttempt(), false, 'task state stays closed')

    assert.equal(web.clearFreePracticeTransientState(containers, false), true)
    Object.values(containers).forEach(collection => assert.equal(collection.size, 0))
    const newGate = web.createFirstAttemptGate(false)
    containers.firstAttemptGates.set('0', newGate)
    assert.equal(newGate.beginFirstAttempt(), true, 'reset creates a postable fresh first attempt')
    assert.deepEqual(
        mini.clearFreePracticeTransientState({
            dictationStartedSegments: new Set(['0']),
            correctionSegments: new Set(['0']),
            firstAttemptGates: new Map([['0', mini.createFirstAttemptGate(true)]]),
            dictationDrafts: new Map([['0', ['need']]]),
            dictationLevelsBySegment: new Map([['0', 'standard']]),
            pendingFirstAttempts: new Map([['0', {}]])
        }),
        true,
        'mini copy keeps the same transient-reset contract'
    )
})

test('correction never opens another post', () => {

    const gate = web.createFirstAttemptGate(false)
    let posts = 0
    if (gate.beginFirstAttempt()) posts += 1
    if (gate.beginFirstAttempt()) posts += 1
    assert.equal(posts, 1)
    assert.equal(gate.enterCorrection(), true)
    assert.equal(gate.isCorrection(), true)
    assert.equal(gate.canPost(), false)
})
