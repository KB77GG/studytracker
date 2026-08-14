const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const test = require('node:test')

const ListeningCloze = require('../static/js/listening-cloze.js')
const listeningDir = path.join(__dirname, '..', 'static', 'listening')

test('all 16 Cambridge IELTS 20 sections satisfy the new cloze and timestamp contract', () => {
    const files = fs.readdirSync(listeningDir)
        .filter(name => /^ielts20_test[1-4]_s[1-4]\.json$/.test(name))
        .sort()
    assert.equal(files.length, 16)

    let totalSegments = 0
    files.forEach(file => {
        const exercise = JSON.parse(fs.readFileSync(path.join(listeningDir, file), 'utf8'))
        assert.match(exercise.audio || '', /^ielts20_test[1-4]_s[1-4]_xdf_20260813\.mp3$/)
        const segments = (exercise.parts || []).flatMap(part => part.segments || [])
        assert.ok(segments.length > 0, `${file} has segments`)
        totalSegments += segments.length

        let previousEnd = 0
        segments.forEach((segment, segmentIndex) => {
            assert.equal(typeof segment.text, 'string', `${file}:${segmentIndex} text`)
            assert.ok(segment.text.trim(), `${file}:${segmentIndex} non-empty text`)
            assert.ok(Number.isFinite(segment.start), `${file}:${segmentIndex} finite start`)
            assert.ok(Number.isFinite(segment.end), `${file}:${segmentIndex} finite end`)
            assert.ok(segment.start >= previousEnd - 0.02, `${file}:${segmentIndex} monotonic timestamp`)
            assert.ok(segment.end > segment.start, `${file}:${segmentIndex} positive duration`)
            previousEnd = segment.end

            const analysed = ListeningCloze.analyseTokens(segment.text)
            const answerable = analysed.filter(token => token.answerable)
            ;['basic', 'standard', 'challenge'].forEach(level => {
                const options = { seed: `${file}:${segmentIndex}:${level}` }
                const first = ListeningCloze.selectHiddenWordIndices(segment.text, level, options)
                const second = ListeningCloze.selectHiddenWordIndices(segment.text, level, options)
                assert.deepEqual(first, second, `${file}:${segmentIndex}:${level} deterministic`)
                first.forEach(index => {
                    const token = analysed.find(item => item.index === index)
                    assert.ok(token && token.answerable, `${file}:${segmentIndex}:${level}:${index} answerable`)
                    assert.equal(token.speakerLabel, false, `${file}:${segmentIndex}:${level}:${index} no speaker label`)
                })
                if (answerable.length) assert.ok(first.length > 0, `${file}:${segmentIndex}:${level} has a target`)
            })

            const preferred = analysed.filter(token => token.answerable && !token.hardExcluded)
            if (preferred.length) {
                ;['basic', 'standard'].forEach(level => {
                    const selected = ListeningCloze.selectHiddenWordIndices(segment.text, level, {
                        seed: `${file}:${segmentIndex}:${level}`
                    })
                    selected.forEach(index => {
                        const token = analysed.find(item => item.index === index)
                        assert.equal(token.hardExcluded, false,
                            `${file}:${segmentIndex}:${level} excludes greetings/unspelled names`)
                    })
                })
            }
        })
    })

    assert.ok(totalSegments >= 500, `expected full-book coverage, got ${totalSegments} segments`)
})
