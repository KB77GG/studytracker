const app = getApp()
const { request } = require('../../../../utils/request.js')

Page({
    data: {
        taskId: null,
        token: '',
        loading: true,
        submitting: false,
        task: {},
        test: {},
        passages: [],
        passageTabs: [],
        passageNumber: null,
        passageLocked: false,
        activePassageIndex: 0,
        activePassage: null,
        activeGroups: [],
        answers: {},
        answerUnits: [],
        startedAt: 0,
        progress: {
            answeredCount: 0,
            totalCount: 0,
            percent: 0
        },
        submitted: false,
        result: null,
        submission: null,
        resultDisplay: null,
        resultMap: {},
        wrongKeys: [],
        retryingWrong: false
    },

    onLoad(options) {
        const taskId = parseInt(options.taskId, 10)
        const token = options.token ? decodeURIComponent(options.token) : ''
        const initialPassage = options.passage ? parseInt(options.passage, 10) : null
        this.initialPassage = initialPassage
        this.setData({
            taskId,
            token,
            startedAt: Date.now()
        })
        this.fetchReadingTask()
    },

    async fetchReadingTask() {
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
                `/miniprogram/student/reading/cambridge/${this.data.taskId}?token=${encodeURIComponent(token)}`,
                { timeout: 90000 }
            )
            if (!res.ok) {
                wx.showModal({
                    title: '加载失败',
                    content: res.error === 'invalid_token' ? '任务令牌已失效，请回到首页重新打开。' : '阅读任务加载失败。',
                    showCancel: false
                })
                return
            }

            const test = res.test || {}
            const passages = test.passages || []
            const passageNumber = res.passage_number || null
            const preferredPassage = passageNumber || this.initialPassage
            let activeIndex = 0
            if (preferredPassage) {
                const found = passages.findIndex(passage => Number(passage.passage_number) === Number(preferredPassage))
                activeIndex = found >= 0 ? found : 0
            }
            const answerUnits = this.buildAnswerUnits(passages)
            const submission = res.submission || null
            const loadedAnswers = this.normalizeAnswerMap(submission && submission.answers)
            const reviewState = this.buildReviewState(submission, null)
            const progress = this.buildProgress(loadedAnswers, answerUnits)

            this.setData({
                task: res.task || {},
                test,
                passages,
                passageTabs: passages.map(passage => ({
                    passageIndex: passage.passage_index,
                    passageNumber: passage.passage_number,
                    title: `P${passage.passage_number}`
                })),
                passageNumber,
                passageLocked: !!passageNumber || passages.length <= 1,
                answerUnits,
                answers: loadedAnswers,
                progress,
                submission,
                submitted: !!submission,
                resultMap: reviewState.resultMap,
                wrongKeys: reviewState.wrongKeys,
                retryingWrong: false,
                resultDisplay: this.buildResultDisplay(submission, null),
                loading: false
            }, () => {
                this.selectPassage(activeIndex, false)
            })
        } catch (err) {
            console.error('fetch cambridge reading failed', err)
            wx.showToast({ title: '网络错误', icon: 'none' })
        } finally {
            wx.hideLoading()
        }
    },

    async ensureTaskToken() {
        if (this.data.token) return this.data.token
        const detail = await request(`/miniprogram/student/tasks/${this.data.taskId}`)
        if (detail.ok && detail.task && detail.task.reading_token) {
            this.setData({ token: detail.task.reading_token })
            return detail.task.reading_token
        }
        return ''
    },

    selectPassage(index, scrollTop = true) {
        const passages = this.data.passages || []
        const passage = passages[index]
        if (!passage) return
        const groups = this.applyAnswerState(
            this.buildGroups(passage),
            this.data.answers,
            this.data.resultMap,
            this.data.submitted
        )
        this.setData({
            activePassageIndex: index,
            activePassage: passage,
            activeGroups: groups
        })
        if (scrollTop) {
            wx.pageScrollTo({ scrollTop: 0, duration: 180 })
        }
    },

    onPassageTap(e) {
        const index = Number(e.currentTarget.dataset.index || 0)
        if (index === this.data.activePassageIndex) return
        this.selectPassage(index)
    },

    buildGroups(passage) {
        return (passage.groups || []).map((group, groupIndex) => {
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
            const renderQuestions = questions.filter(question => !renderedKeys[question.key])
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
                showOptionBank: !!(((group.collect_option || {}).list || []).length),
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
            control = question.is_multi_answer ? 'checkbox' : 'radio'
            sourceOptions = ownOptions
        } else if (bankOptions.length) {
            control = question.is_multi_answer ? 'checkbox' : 'select'
            sourceOptions = bankOptions
        }
        const decorated = {
            key,
            number: question.number,
            title: question.title || '',
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
            const displayContent = this.stripOptionKeyPrefix(value, content)
            return {
                value,
                label: displayContent ? `${value}. ${displayContent}` : value,
                checked: false
            }
        }).filter(option => option.value)
    },

    stripOptionKeyPrefix(key, text) {
        const escaped = String(key || '').replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
        return String(text || '').trim().replace(new RegExp(`^\\s*${escaped}\\s*[.．、)]\\s*`, 'i'), '')
    },

    splitQuestionTitle(question) {
        const raw = question.title || ''
        if (!raw) return []
        const canInline = question.control === 'text' || question.control === 'select'
        const parts = []
        let last = 0
        let found = false
        raw.replace(/【\s*】/g, (match, offset) => {
            const before = raw.slice(last, offset)
            if (before) parts.push(this.textChunk(before, `${question.key}_${parts.length}`))
            if (canInline) {
                parts.push({
                    kind: 'blank',
                    chunkKey: `${question.key}_blank_${parts.length}`,
                    question
                })
                question.showControl = false
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
                    question: inlineQuestion
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

    textChunk(text, key) {
        return {
            kind: 'text',
            chunkKey: key,
            html: this.richText(text)
        }
    },

    richText(value) {
        return String(value || '')
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

    applyAnswerState(groups, answers, resultMap = this.data.resultMap, submitted = this.data.submitted) {
        return (groups || []).map(group => {
            const nextGroup = { ...group }
            nextGroup.questions = (nextGroup.questions || []).map(question => (
                this.decorateChoiceState(question, answers[question.key], resultMap[question.key], submitted)
            ))
            nextGroup.collectChunks = this.decorateChunks(nextGroup.collectChunks, answers, resultMap, submitted)
            nextGroup.tableRows = (nextGroup.tableRows || []).map(row => ({
                ...row,
                cells: (row.cells || []).map(cell => ({
                    ...cell,
                    chunks: this.decorateChunks(cell.chunks, answers, resultMap, submitted)
                }))
            }))
            return nextGroup
        })
    },

    decorateChunks(chunks, answers, resultMap = this.data.resultMap, submitted = this.data.submitted) {
        return (chunks || []).map(chunk => {
            if (chunk.kind !== 'blank' || !chunk.question) return chunk
            return {
                ...chunk,
                question: this.decorateChoiceState(
                    chunk.question,
                    answers[chunk.question.key],
                    resultMap[chunk.question.key],
                    submitted
                )
            }
        })
    },

    decorateChoiceState(question, value, resultRow = null, submitted = this.data.submitted) {
        const values = this.splitAnswerValue(value)
        const correctValues = resultRow ? this.splitAnswerValue(resultRow.answer) : []
        const options = (question.options || []).map(option => ({
            ...option,
            checked: values.indexOf(option.value) >= 0,
            isCorrectOption: !!(submitted && resultRow && correctValues.indexOf(option.value) >= 0),
            isUserWrong: !!(submitted && resultRow && !resultRow.correct && values.indexOf(option.value) >= 0)
        }))
        const selected = options.filter(option => option.checked).map(option => option.label)
        const reviewClass = submitted && resultRow ? (resultRow.correct ? 'correct' : 'wrong') : ''
        return {
            ...question,
            options,
            selectedLabel: selected.join('，'),
            reviewClass,
            reviewAnswerText: submitted && resultRow ? this.formatAnswerText(resultRow.answer) : ''
        }
    },

    splitAnswerValue(value) {
        return String(value || '').split(',').map(item => item.trim()).filter(Boolean)
    },

    formatAnswerText(value) {
        return String(value || '').trim()
    },

    normalizeAnswerMap(answers) {
        const normalized = {}
        Object.keys(answers || {}).forEach(key => {
            const value = answers[key]
            if (value !== undefined && value !== null && String(value).trim()) {
                normalized[String(key)] = String(value).trim()
            }
        })
        return normalized
    },

    buildReviewState(submission, result) {
        const source = (submission && Array.isArray(submission.results) && submission.results.length)
            ? submission
            : (result || submission || {})
        const rows = Array.isArray(source.results) ? source.results : []
        const resultMap = {}
        const wrongKeys = []
        rows.forEach(row => {
            const ids = (row.ids || []).map(id => String(id))
            const key = ids.join(',')
            if (!key) return
            const normalized = {
                ...row,
                ids,
                key,
                answer: this.formatAnswerText(row.answer),
                value: String(row.value || ''),
                correct: !!row.correct
            }
            resultMap[key] = normalized
            ids.forEach(id => {
                resultMap[id] = normalized
            })
            if (!normalized.correct) {
                wrongKeys.push(key)
            }
        })
        return {
            resultMap,
            wrongKeys: Array.from(new Set(wrongKeys))
        }
    },

    buildAnswerUnits(passages) {
        const units = []
        ;(passages || []).forEach(passage => {
            ;(passage.groups || []).forEach(group => {
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
            data.activeGroups = this.applyAnswerState(
                this.buildGroups(this.data.activePassage),
                answers,
                this.data.resultMap,
                this.data.submitted
            )
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
            if (this.data.passageNumber) {
                body.passage_number = this.data.passageNumber
            }
            const res = await request(`/reading/test/${encodeURIComponent(this.data.test.id)}/submit`, {
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
            const submission = res.submission || null
            const loadedAnswers = this.normalizeAnswerMap((submission && submission.answers) || this.data.answers)
            const reviewState = this.buildReviewState(submission, res.result)
            const activeGroups = this.data.activePassage
                ? this.applyAnswerState(this.buildGroups(this.data.activePassage), loadedAnswers, reviewState.resultMap, true)
                : this.data.activeGroups
            this.setData({
                submitted: true,
                result: res.result || null,
                submission,
                answers: loadedAnswers,
                progress: this.buildProgress(loadedAnswers),
                resultMap: reviewState.resultMap,
                wrongKeys: reviewState.wrongKeys,
                retryingWrong: false,
                activeGroups,
                resultDisplay: this.buildResultDisplay(submission, res.result)
            })
            wx.pageScrollTo({ scrollTop: 0, duration: 180 })
            wx.showToast({ title: '已提交', icon: 'success' })
        } catch (err) {
            console.error('submit cambridge reading failed', err)
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

    redoWrong() {
        const wrongKeys = this.data.wrongKeys || []
        if (!wrongKeys.length) {
            wx.showToast({ title: '没有错题', icon: 'none' })
            return
        }
        const answers = { ...this.data.answers }
        wrongKeys.forEach(key => {
            delete answers[key]
            const row = this.data.resultMap[key]
            ;(row && row.ids ? row.ids : []).forEach(id => {
                delete answers[String(id)]
            })
        })
        const targetIndex = this.findPassageIndexForKey(wrongKeys[0])
        this.setData({
            answers,
            progress: this.buildProgress(answers),
            submitted: false,
            result: null,
            submission: null,
            resultDisplay: null,
            resultMap: {},
            wrongKeys: [],
            retryingWrong: true,
            startedAt: Date.now()
        }, () => {
            this.selectPassage(targetIndex >= 0 ? targetIndex : this.data.activePassageIndex, false)
            wx.pageScrollTo({ scrollTop: 0, duration: 180 })
            wx.showToast({ title: '已进入错题重做', icon: 'none' })
        })
    },

    findPassageIndexForKey(targetKey) {
        const target = String(targetKey || '')
        const passages = this.data.passages || []
        for (let passageIndex = 0; passageIndex < passages.length; passageIndex += 1) {
            for (const group of passages[passageIndex].groups || []) {
                for (const question of group.questions || []) {
                    const key = String(question.id || question.number)
                    if (key === target || target.split(',').indexOf(key) >= 0) {
                        return passageIndex
                    }
                }
            }
        }
        return -1
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
    }
})
