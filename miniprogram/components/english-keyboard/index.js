const { answerSeparators } = require('../../utils/dictation-input-policy.js')

const LETTER_ROWS = [
    ['Q', 'W', 'E', 'R', 'T', 'Y', 'U', 'I', 'O', 'P'],
    ['A', 'S', 'D', 'F', 'G', 'H', 'J', 'K', 'L'],
    ['Z', 'X', 'C', 'V', 'B', 'N', 'M']
]

Component({
    properties: {
        answer: { type: String, value: '' },
        value: { type: String, value: '' },
        status: { type: String, value: 'idle' },
        canConfirm: { type: Boolean, value: false },
        showWrongActions: { type: Boolean, value: false },
        showNext: { type: Boolean, value: false },
        disabled: { type: Boolean, value: false }
    },

    data: {
        letterRows: LETTER_ROWS,
        separators: []
    },

    observers: {
        answer(answer) {
            this.setData({ separators: answerSeparators(answer) })
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
