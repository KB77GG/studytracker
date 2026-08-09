const { answerSeparators } = require('../../utils/dictation-input-policy.js')

const LETTER_ROWS = [
    ['q', 'w', 'e', 'r', 't', 'y', 'u', 'i', 'o', 'p'],
    ['a', 's', 'd', 'f', 'g', 'h', 'j', 'k', 'l'],
    // The mapped production catalog currently contains the English loanword
    // “fiancé”. Keep its required character available without falling back
    // to a predictive/native keyboard.
    ['z', 'x', 'c', 'v', 'b', 'n', 'm', 'é']
]
const NUMBER_ROW = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '0']

Component({
    properties: {
        answer: { type: String, value: '' },
        safeSeparators: { type: Array, value: null },
        value: { type: String, value: '' },
        status: { type: String, value: 'idle' },
        showValue: { type: Boolean, value: true },
        canConfirm: { type: Boolean, value: false },
        showWrongActions: { type: Boolean, value: false },
        showNext: { type: Boolean, value: false },
        disabled: { type: Boolean, value: false }
    },

    data: {
        letterRows: LETTER_ROWS,
        numberRow: NUMBER_ROW,
        separators: []
    },

    observers: {
        answer(answer) {
            if (!Array.isArray(this.data.safeSeparators)) {
                this.setData({ separators: answerSeparators(answer) })
            }
        },
        safeSeparators(value) {
            this.setData({
                separators: Array.isArray(value) ? answerSeparators(value.join('')) : answerSeparators(this.data.answer)
            })
        }
    },

    methods: {
        emitKey(e) {
            if (this.data.disabled || this.data.showWrongActions || this.data.showNext) return
            this.triggerEvent('key', { key: e.currentTarget.dataset.key })
        },

        emitBackspace() {
            if (this.data.disabled || this.data.showWrongActions || this.data.showNext) return
            this.triggerEvent('backspace')
        },

        emitConfirm() {
            if (this.data.disabled || !this.data.canConfirm) return
            this.triggerEvent('confirm')
        },

        emitRetry() {
            if (this.data.disabled) return
            this.triggerEvent('retry')
        },

        emitSkip() {
            if (this.data.disabled) return
            this.triggerEvent('skip')
        },

        emitNext() {
            if (this.data.disabled) return
            this.triggerEvent('next')
        }
    }
})
