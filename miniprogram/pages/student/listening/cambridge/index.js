const app = getApp()
const { request } = require('../../../../utils/request.js')

const SPEED_OPTIONS = [
    { label: '0.75x', value: 0.75 },
    { label: '1.0x', value: 1 },
    { label: '1.25x', value: 1.25 }
]

Page({
    data: {
        taskId: null,
        token: '',
        loading: true,
        submitting: false,
        task: {},
        test: {},
        sections: [],
        sectionTabs: [],
        sectionNumber: null,
        sectionLocked: false,
        activeSectionIndex: 0,
        activeSection: null,
        activeGroups: [],
        answers: {},
        answerUnits: [],
        audioBaseUrl: '',
        audioReady: false,
        audioPlaying: false,
        currentTimeText: '00:00',
        durationText: '00:00',
        speedOptions: SPEED_OPTIONS,
        speedIndex: 1,
        startedAt: 0,
        progress: {
            answeredCount: 0,
            totalCount: 0,
            percent: 0
        },
        submitted: false,
        result: null,
        submission: null,
        resultDisplay: null
    },

    onLoad(options) {
        const taskId = parseInt(options.taskId, 10)
        const token = options.token ? decodeURIComponent(options.token) : ''
        const initialSection = options.section ? parseInt(options.section, 10) : null
        this.initialSection = initialSection
        this.setData({
            taskId,
            token,
            startedAt: Date.now()
        })
        this.fetchCambridgeTask()
    },

    onHide() {
        this.pauseAudio()
    },

    onUnload() {
        this.destroyAudio()
    },

    async fetchCambridgeTask() {
        wx.showLoading({ title: '加载中...' })
        try {
            const token = await this.ensureTaskToken()
            if (!token) {
                wx.showModal({
                    title: '无法打开任务',
                    content: '任务缺少访问令牌，请从首页重新打开。',
                    showCancel: false
                })
                return
            }
            const res = await request(
                `/miniprogram/student/listening/cambridge/${this.data.taskId}?token=${encodeURIComponent(token)}&render=rich_v2`,
                { timeout: 90000 }
            )
            if (!res.ok) {
                wx.showModal({
                    title: '加载失败',
                    content: res.error === 'invalid_token' ? '任务令牌已失效，请回到首页重新打开。' : '剑雅听力任务加载失败。',
                    showCancel: false
                })
                return
            }

            const test = res.test || {}
            const sections = test.sections || []
            const sectionNumber = res.section_number || null
            const preferredSection = sectionNumber || this.initialSection
            let activeIndex = 0
            if (preferredSection) {
                const found = sections.findIndex(section => Number(section.section_number) === Number(preferredSection))
                activeIndex = found >= 0 ? found : 0
            }
            const answerUnits = this.buildAnswerUnits(sections)
            const progress = this.buildProgress({}, answerUnits)

            this.setData({
                task: res.task || {},
                test,
                sections,
                sectionTabs: sections.map(section => ({
                    sectionIndex: section.section_index,
                    sectionNumber: section.section_number,
                    title: `S${section.section_number}`
                })),
                sectionNumber,
                sectionLocked: !!sectionNumber || sections.length <= 1,
                audioBaseUrl: res.audio_base_url || `${this.getRootUrl()}/static/listening/`,
                answerUnits,
                progress,
                submission: res.submission || null,
                submitted: !!res.submission,
                resultDisplay: this.buildResultDisplay(res.submission, null),
                loading: false
            })
            this.selectSection(activeIndex, false)
        } catch (err) {
            console.error('fetch cambridge listening failed', err)
            wx.showToast({ title: '网络错误', icon: 'none' })
        } finally {
            wx.hideLoading()
        }
    },

    async ensureTaskToken() {
        if (this.data.token) return this.data.token
        const detail = await request(`/miniprogram/student/tasks/${this.data.taskId}`)
        if (detail.ok && detail.task && detail.task.listening_token) {
            this.setData({ token: detail.task.listening_token })
            return detail.task.listening_token
        }
        return ''
    },

    getRootUrl() {
        return (app.globalData.baseUrl || '').replace(/\/api\/?$/, '')
    },

    initAudio() {
        wx.setInnerAudioOption({
            obeyMuteSwitch: false,
            speakerOn: true
        })
        this.audioCtx = wx.createInnerAudioContext()
        this.audioCtx.obeyMuteSwitch = false
        this.audioCtx.autoplay = false
        this.audioCtx.playbackRate = this.data.speedOptions[this.data.speedIndex].value
        this.audioCtx.onCanplay(() => {
            this.setData({ audioReady: true })
        })
        this.audioCtx.onPlay(() => {
            this.setData({ audioPlaying: true })
        })
        this.audioCtx.onPause(() => {
            this.setData({ audioPlaying: false })
        })
        this.audioCtx.onStop(() => {
            this.setData({ audioPlaying: false })
        })
        this.audioCtx.onEnded(() => {
            this.setData({ audioPlaying: false })
        })
        this.audioCtx.onTimeUpdate(() => {
            const current = this.audioCtx.currentTime || 0
            const duration = this.audioCtx.duration || 0
            this.setData({
                currentTimeText: this.formatTime(current),
                durationText: this.formatTime(duration)
            })
        })
        this.audioCtx.onError((err) => {
            console.error('cambridge audio error', err)
            this.setData({ audioReady: false, audioPlaying: false })
            wx.showToast({ title: '音频加载失败，可先答题', icon: 'none' })
        })
    },

    destroyAudio() {
        if (!this.audioCtx) return
        try {
            this.audioCtx.stop()
            this.audioCtx.destroy()
        } catch (err) {
            console.warn('destroy audio failed', err)
        }
        this.audioCtx = null
    },

    resetAudio(section) {
        this.destroyAudio()
        this.initAudio()
        const audio = section && section.audio ? section.audio : ''
        if (audio) {
            const base = this.data.audioBaseUrl.endsWith('/') ? this.data.audioBaseUrl : `${this.data.audioBaseUrl}/`
            this.audioCtx.src = `${base}${audio}`
        }
        this.setData({
            audioReady: false,
            audioPlaying: false,
            currentTimeText: '00:00',
            durationText: '00:00'
        })
    },

    selectSection(index, scrollTop = true) {
        const sections = this.data.sections || []
        const section = sections[index]
        if (!section) return
        const groups = this.applyAnswerState(this.buildGroups(section), this.data.answers)
        this.setData({
            activeSectionIndex: index,
            activeSection: section,
            activeGroups: groups
        })
        this.resetAudio(section)
        if (scrollTop) {
            wx.pageScrollTo({ scrollTop: 0, duration: 180 })
        }
    },

    onSectionTap(e) {
        const index = Number(e.currentTarget.dataset.index || 0)
        if (index === this.data.activeSectionIndex) return
        this.selectSection(index)
    },

    buildGroups(section) {
        return (section.groups || []).map((group, groupIndex) => {
            const renderedKeys = {}
            const questions = (group.questions || []).map(question => this.decorateQuestion(question, group))
            const questionMap = {}
            questions.forEach(question => {
                questionMap[String(question.key)] = question
            })
            const tableRows = this.buildTableRows(group, questionMap, renderedKeys)
            const collectChunks = group.collect
                ? this.splitReferenceText(group.collect, questionMap, renderedKeys)
                : []
            const renderQuestions = questions.filter(question => !renderedKeys[question.key] && !group.combined_multi)
            const combined = group.combined_multi ? {
                key: group.combined_key,
                number: (group.combined_numbers || [])[0] || '',
                numbersLabel: (group.combined_numbers || []).join(', '),
                control: 'checkbox',
                options: this.normalizeOptions((group.collect_option || {}).list || []),
                selectedLabel: '',
                checkedMap: {},
                showControl: true
            } : null

            return {
                groupIndex,
                groupId: group.group_id || groupIndex,
                type: group.type,
                titleHtml: this.richText(group.title || ''),
                descHtml: this.richText(group.desc || ''),
                questionTitleHtml: this.richText(group.question_title || ''),
                imageUrl: group.image_url || '',
                collectChunks,
                tableRows,
                optionBank: this.normalizeOptions((group.collect_option || {}).list || []),
                showOptionBank: !!(((group.collect_option || {}).list || []).length && !group.combined_multi),
                combined,
                questions: renderQuestions
            }
        })
    },

    decorateQuestion(question, group) {
        const key = String(question.id || question.number)
        const bankOptions = ((group.collect_option || {}).list || [])
        const ownOptions = question.options || []
        let control = 'text'
        let sourceOptions = []
        if (ownOptions.length) {
            control = question.is_multi_answer || group.type === 9 ? 'checkbox' : 'radio'
            sourceOptions = ownOptions
        } else if (bankOptions.length && group.type !== 2) {
            control = question.is_multi_answer || group.type === 9 ? 'checkbox' : 'select'
            sourceOptions = bankOptions
        }
        const decorated = {
            key,
            number: question.number,
            title: question.title || '',
            start: question.start,
            end: question.end,
            control,
            options: this.normalizeOptions(sourceOptions),
            selectedLabel: '',
            titleChunks: [],
            showControl: true
        }
        decorated.titleChunks = this.splitQuestionTitle(decorated)
        return decorated
    },

    normalizeOptions(options) {
        return (options || []).map(option => {
            const value = String(option.key || option.title || '').trim()
            const content = String(option.text || option.content || '').trim()
            return {
                value,
                label: content ? `${value}. ${content}` : value,
                checked: false
            }
        }).filter(option => option.value)
    },

    splitQuestionTitle(question) {
        const raw = question.title || ''
        if (!raw) return []
        const canInline = question.control === 'text' || question.control === 'select'
        const parts = []
        let last = 0
        let found = false
        raw.replace(/【\s*】|_{3,}/g, (match, offset) => {
            const before = raw.slice(last, offset)
            if (before) parts.push(this.textChunk(before, `${question.key}_${parts.length}`))
            if (canInline) {
                question.showControl = false
                parts.push({
                    kind: 'blank',
                    chunkKey: `${question.key}_blank_${parts.length}`,
                    question: this.inlineQuestionControl(question),
                    showNumber: false
                })
                found = true
            } else {
                parts.push(this.textChunk('____', `${question.key}_blank_text_${parts.length}`))
            }
            last = offset + match.length
            return match
        })
        const tail = raw.slice(last)
        if (tail) parts.push(this.textChunk(tail, `${question.key}_${parts.length}`))
        return found || parts.length ? parts : [this.textChunk(raw, `${question.key}_title`)]
    },

    buildTableRows(group, questionMap, renderedKeys) {
        const table = group.table || {}
        const rows = table.content || []
        return rows.map((row, rowIndex) => ({
            rowKey: `${group.group_id || 'g'}_${rowIndex}`,
            cells: (Array.isArray(row) ? row : [row]).map((cell, cellIndex) => ({
                cellKey: `${group.group_id || 'g'}_${rowIndex}_${cellIndex}`,
                chunks: this.splitReferenceText(String(cell || ''), questionMap, renderedKeys)
            }))
        }))
    },

    splitReferenceText(raw, questionMap, renderedKeys) {
        const chunks = []
        let last = 0
        raw.replace(/\$([^$\s]+)\$/g, (match, id, offset) => {
            const before = raw.slice(last, offset)
            if (before) chunks.push(this.textChunk(before, `text_${chunks.length}_${offset}`))
            const question = questionMap[String(id)]
            if (question && !renderedKeys[question.key]) {
                renderedKeys[question.key] = true
                const inlineQuestion = {
                    ...question,
                    control: question.options.length && question.control !== 'checkbox' ? 'select' : question.control,
                    showControl: false
                }
                chunks.push({
                    kind: 'blank',
                    chunkKey: `blank_${question.key}_${offset}`,
                    question: this.inlineQuestionControl(inlineQuestion),
                    showNumber: true
                })
            } else {
                chunks.push(this.textChunk('____', `ghost_${id}_${offset}`))
            }
            last = offset + match.length
            return match
        })
        const tail = raw.slice(last)
        if (tail) chunks.push(this.textChunk(tail, `text_${chunks.length}_${raw.length}`))
        return chunks
    },

    inlineQuestionControl(question) {
        return {
            key: question.key,
            number: question.number,
            title: question.title || '',
            start: question.start,
            end: question.end,
            control: question.control,
            options: question.options || [],
            selectedLabel: question.selectedLabel || '',
            showControl: false
        }
    },

    textChunk(text, key) {
        return {
            kind: 'text',
            chunkKey: key,
            html: this.richText(text)
        }
    },

    decodeHtmlEntities(value) {
        return String(value || '')
            .replace(/&nbsp;/gi, ' ')
            .replace(/&#160;/gi, ' ')
            .replace(/&amp;/gi, '&')
            .replace(/&lt;/gi, '<')
            .replace(/&gt;/gi, '>')
            .replace(/&quot;/gi, '"')
            .replace(/&#39;/gi, "'")
    },

    richText(value) {
        return this.decodeHtmlEntities(value)
            .replace(/\u00a0/g, ' ')
            .replace(/<\s*divider\s*\/?\s*>/gi, '\n')
            .replace(/<\s*br\s*\/?\s*>/gi, '\n')
            .replace(/[ \t]{3,}/g, '  ')
            .replace(/\n{3,}/g, '\n\n')
            .trim()
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/&lt;b&gt;/g, '<b>')
            .replace(/&lt;\/b&gt;/g, '</b>')
            .replace(/&lt;i&gt;/g, '<i>')
            .replace(/&lt;\/i&gt;/g, '</i>')
            .replace(/&lt;bc&gt;/g, '<b>')
            .replace(/&lt;\/bc&gt;/g, '</b>')
            .replace(/&lt;iu&gt;/g, '<i>')
            .replace(/&lt;\/iu&gt;/g, '</i>')
            .replace(/\n/g, '<br/>')
    },

    applyAnswerState(groups, answers) {
        return (groups || []).map(group => {
            const nextGroup = { ...group }
            if (nextGroup.combined) {
                nextGroup.combined = this.decorateChoiceState(nextGroup.combined, answers[nextGroup.combined.key])
            }
            nextGroup.questions = (nextGroup.questions || []).map(question => (
                this.decorateChoiceState(question, answers[question.key])
            ))
            nextGroup.collectChunks = this.decorateChunks(nextGroup.collectChunks, answers)
            nextGroup.tableRows = (nextGroup.tableRows || []).map(row => ({
                ...row,
                cells: (row.cells || []).map(cell => ({
                    ...cell,
                    chunks: this.decorateChunks(cell.chunks, answers)
                }))
            }))
            return nextGroup
        })
    },

    decorateChunks(chunks, answers) {
        return (chunks || []).map(chunk => {
            if (chunk.kind !== 'blank' || !chunk.question) return chunk
            return {
                ...chunk,
                question: this.decorateChoiceState(chunk.question, answers[chunk.question.key])
            }
        })
    },

    decorateChoiceState(question, value) {
        const values = this.splitAnswerValue(value)
        const options = (question.options || []).map(option => ({
            ...option,
            checked: values.indexOf(option.value) >= 0
        }))
        const selected = options.filter(option => option.checked).map(option => option.label)
        return {
            ...question,
            options,
            selectedLabel: selected.join('，')
        }
    },

    splitAnswerValue(value) {
        return String(value || '').split(',').map(item => item.trim()).filter(Boolean)
    },

    buildAnswerUnits(sections) {
        const units = []
        ;(sections || []).forEach(section => {
            ;(section.groups || []).forEach(group => {
                if (group.combined_multi && group.combined_key) {
                    units.push({
                        key: group.combined_key,
                        marks: Math.max(1, (group.combined_numbers || []).length)
                    })
                    return
                }
                ;(group.questions || []).forEach(question => {
                    units.push({
                        key: String(question.id || question.number),
                        marks: 1
                    })
                })
            })
        })
        return units
    },

    buildProgress(answers, units = this.data.answerUnits) {
        const totalCount = (units || []).reduce((sum, unit) => sum + Number(unit.marks || 1), 0)
        const answeredCount = (units || []).reduce((sum, unit) => {
            return this.isAnswered(answers[unit.key]) ? sum + Number(unit.marks || 1) : sum
        }, 0)
        return {
            answeredCount,
            totalCount,
            percent: totalCount ? Math.round(answeredCount * 100 / totalCount) : 0
        }
    },

    isAnswered(value) {
        return String(value || '').trim().length > 0
    },

    setAnswer(key, value, refreshGroups = false) {
        const answers = { ...this.data.answers }
        const normalized = Array.isArray(value) ? value.join(',') : String(value || '').trim()
        if (normalized) {
            answers[key] = normalized
        } else {
            delete answers[key]
        }
        const data = {
            answers,
            progress: this.buildProgress(answers)
        }
        if (refreshGroups) {
            data.activeGroups = this.applyAnswerState(this.buildGroups(this.data.activeSection), answers)
        }
        this.setData(data)
    },

    onTextInput(e) {
        this.setAnswer(String(e.currentTarget.dataset.key), e.detail.value, false)
    },

    onRadioChange(e) {
        this.setAnswer(String(e.currentTarget.dataset.key), e.detail.value, true)
    },

    onCheckboxChange(e) {
        this.setAnswer(String(e.currentTarget.dataset.key), e.detail.value || [], true)
    },

    onPickerChange(e) {
        const key = String(e.currentTarget.dataset.key)
        const question = this.findQuestionByKey(key)
        const index = Number(e.detail.value || 0)
        const option = question && question.options ? question.options[index] : null
        this.setAnswer(key, option ? option.value : '', true)
    },

    findQuestionByKey(key) {
        for (const group of this.data.activeGroups || []) {
            if (group.combined && group.combined.key === key) return group.combined
            for (const question of group.questions || []) {
                if (question.key === key) return question
            }
            const fromCollect = this.findQuestionInChunks(group.collectChunks, key)
            if (fromCollect) return fromCollect
            for (const row of group.tableRows || []) {
                for (const cell of row.cells || []) {
                    const found = this.findQuestionInChunks(cell.chunks, key)
                    if (found) return found
                }
            }
        }
        return null
    },

    findQuestionInChunks(chunks, key) {
        for (const chunk of chunks || []) {
            if (chunk.kind === 'blank' && chunk.question && chunk.question.key === key) {
                return chunk.question
            }
        }
        return null
    },

    togglePlay() {
        if (!this.audioCtx) return
        if (this.data.audioPlaying) {
            this.pauseAudio()
            return
        }
        try {
            this.audioCtx.playbackRate = this.data.speedOptions[this.data.speedIndex].value
            this.audioCtx.play()
        } catch (err) {
            console.warn('play cambridge audio failed', err)
        }
    },

    pauseAudio() {
        if (!this.audioCtx) return
        try {
            this.audioCtx.pause()
        } catch (err) {
            console.warn('pause cambridge audio failed', err)
        }
    },

    seekAudio(e) {
        if (!this.audioCtx) return
        const offset = Number(e.currentTarget.dataset.offset || 0)
        const target = Math.max(0, Number(this.audioCtx.currentTime || 0) + offset)
        this.audioCtx.seek(target)
    },

    seekToQuestion(e) {
        if (!this.audioCtx) return
        const start = Number(e.currentTarget.dataset.start || 0)
        if (!start) return
        this.audioCtx.seek(Math.max(0, start - 1))
        this.audioCtx.play()
    },

    onSpeedChange(e) {
        const speedIndex = Number(e.detail.value || 0)
        this.setData({ speedIndex })
        if (this.audioCtx) {
            this.audioCtx.playbackRate = this.data.speedOptions[speedIndex].value
        }
    },

    async submitAnswers() {
        if (this.data.submitting) return
        if (this.data.progress.answeredCount < this.data.progress.totalCount) {
            const ok = await this.confirmSubmitPartial()
            if (!ok) return
        }
        this.setData({ submitting: true })
        wx.showLoading({ title: '提交中...' })
        try {
            const duration = Math.max(0, Math.round((Date.now() - this.data.startedAt) / 1000))
            const body = {
                task_id: this.data.taskId,
                token: this.data.token,
                answers: this.data.answers,
                duration_seconds: duration
            }
            if (this.data.sectionNumber) {
                body.section_number = this.data.sectionNumber
            }
            const res = await request(`/listening/test/${encodeURIComponent(this.data.test.id)}/submit`, {
                method: 'POST',
                header: { 'Content-Type': 'application/json' },
                data: body,
                timeout: 90000
            })
            if (!res.ok) {
                wx.showModal({
                    title: '提交失败',
                    content: res.error === 'invalid_token' ? '任务令牌已失效，请从首页重新打开。' : '提交失败，请稍后重试。',
                    showCancel: false
                })
                return
            }
            this.setData({
                submitted: true,
                result: res.result || null,
                submission: res.submission || null,
                resultDisplay: this.buildResultDisplay(res.submission, res.result)
            })
            wx.showToast({ title: '已提交', icon: 'success' })
        } catch (err) {
            console.error('submit cambridge listening failed', err)
            wx.showToast({ title: '网络错误', icon: 'none' })
        } finally {
            wx.hideLoading()
            this.setData({ submitting: false })
        }
    },

    confirmSubmitPartial() {
        return new Promise(resolve => {
            wx.showModal({
                title: '还有题目未答',
                content: `已答 ${this.data.progress.answeredCount}/${this.data.progress.totalCount} 题，确定提交吗？`,
                confirmText: '提交',
                cancelText: '继续答题',
                success: res => resolve(!!res.confirm),
                fail: () => resolve(false)
            })
        })
    },

    goBack() {
        wx.navigateBack()
    },

    buildResultDisplay(submission, result) {
        const source = submission || result
        if (!source) return null
        const correct = source.correct_count !== undefined ? source.correct_count : source.correct
        const total = source.total_count !== undefined ? source.total_count : source.total
        const wrongNumbers = source.wrong_numbers || []
        return {
            correct,
            total,
            accuracy: source.accuracy || 0,
            ieltsScore: source.ielts_score,
            hasWrong: wrongNumbers.length > 0,
            wrongText: wrongNumbers.map(number => `Q${number}`).join('、')
        }
    },

    formatTime(seconds) {
        const safe = Math.max(0, Math.floor(Number(seconds) || 0))
        const mins = Math.floor(safe / 60)
        const secs = safe % 60
        return `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`
    }
})
