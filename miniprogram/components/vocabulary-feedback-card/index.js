Component({
    properties: {
        feedback: { type: Object, value: null },
        audioState: { type: String, value: 'idle' }
    },

    methods: {
        replay() {
            if (!this.data.feedback || !this.data.feedback.audio_tts_url) return
            this.triggerEvent('replay')
        }
    }
})
