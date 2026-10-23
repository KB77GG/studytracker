const assert = require('node:assert/strict')
const fs = require('node:fs')
const path = require('node:path')
const vm = require('node:vm')
const test = require('node:test')

const template = fs.readFileSync(path.join(__dirname, '../templates/tasks.html'), 'utf8')
const source = template.slice(
    template.indexOf('function updateDictationRangeSuggestion('),
    template.indexOf('// Rest of existing JavaScript')
)

function renderHint(hint, value = '144', autofill = '1') {
    const hintEl = { textContent: '' }
    const startInput = { value, dataset: { autofill } }
    const elements = {
        'dictation-range-hint': hintEl,
        taskStudent: { value: 'synthetic student' },
        material_id: { value: 'dictation-8' }
    }
    const context = {
        document: {
            getElementById: id => elements[id],
            getElementsByName: name => [name === 'dictation_word_start' ? startInput : {}]
        },
        dictationRangeHints: { 'synthetic student': { '8': hint } }
    }
    vm.runInNewContext(`${source}\nupdateDictationRangeSuggestion()`, context)
    return { hintEl, startInput }
}

test('book-end hint clears an automatically filled invalid next start', () => {
    const { hintEl, startInput } = renderHint({ start: 120, end: 143, exhausted: true, next_start: null })
    assert.match(hintEl.textContent, /已到词书末尾/)
    assert.doesNotMatch(hintEl.textContent, /建议起始/)
    assert.equal(startInput.value, '')
})

test('book-end hint preserves a manually chosen review range', () => {
    const { startInput } = renderHint({ start: 120, end: 143, exhausted: true }, '10', '0')
    assert.equal(startInput.value, '10')
})

test('a real next word remains available for automatic continuation', () => {
    const { hintEl, startInput } = renderHint({ start: 1, end: 30, next_start: 31, exhausted: false }, '', '0')
    assert.match(hintEl.textContent, /建议起始：31/)
    assert.equal(startInput.value, 31)
})
