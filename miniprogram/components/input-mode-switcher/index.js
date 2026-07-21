Component({
    properties: {
        value: { type: String, value: 'strict' },
        allowed: { type: Boolean, value: false }
    },
    methods: {
        choose(e) {
            if (!this.data.allowed) return
            const mode = e.currentTarget.dataset.mode
            if (!mode || mode === this.data.value) return
            this.triggerEvent('change', { mode })
        }
    }
})
