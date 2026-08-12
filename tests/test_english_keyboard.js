const assert = require('assert')
const path = require('path')

let definition = null
global.Component = (value) => {
    definition = value
}

require(path.join(__dirname, '../miniprogram/components/english-keyboard/index.js'))
assert(definition, 'english keyboard component must register itself')

function emittedFor(data) {
    const emitted = []
    definition.methods.emitConfirm.call({
        data,
        triggerEvent(name) { emitted.push(name) }
    })
    return emitted
}

assert.deepStrictEqual(
    emittedFor({ disabled: false, canConfirm: false, value: 'saving' }),
    ['confirm'],
    'a visible non-empty answer must submit even if the redundant Boolean binding is stale'
)
assert.deepStrictEqual(emittedFor({ disabled: false, canConfirm: true, value: '   ' }), [])
assert.deepStrictEqual(emittedFor({ disabled: true, canConfirm: true, value: 'saving' }), [])

console.log('english keyboard confirm tests passed')
