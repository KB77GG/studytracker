const { request } = require('../../../utils/request.js')

Page({
  data: {
    currentPart: 'Part1',
    sourceMode: 'assigned',
    assignedQuestions: [],
    assignedCount: 0,
    assignedIndex: 0,
    questionText: '',
    questionMeta: '',
    questionType: '',
    answerText: '',
    loadingQuestion: false,
    loadingEval: false,
    result: null,
    part2Options: [
      { value: '', label: '不指定' },
      { value: 'person_place', label: '人物/地点' },
      { value: 'object_concrete', label: '具体物品' },
      { value: 'object_abstract', label: '抽象物品/知识技能' },
      { value: 'storyline', label: '叙述故事' }
    ],
    selectedFramework: '',
    selectedFrameworkLabel: '不指定'
  },

  onLoad() {
    this.loadAssigned()
  },

  async loadAssigned() {
    try {
      const res = await request('/miniprogram/speaking/assigned')
      if (res.ok && Array.isArray(res.tasks)) {
        const questions = []
        res.tasks.forEach(task => {
          const material = task.material || {}
          const list = material.questions || []
          list.forEach(q => {
            questions.push({
              id: q.id,
              type: q.type,
              content: q.content,
              materialTitle: material.title,
              materialType: material.type,
              taskId: task.task_id
            })
          })
        })
        this.setData({
          assignedQuestions: questions,
          assignedCount: questions.length,
          sourceMode: questions.length ? 'assigned' : 'random'
        })
      } else {
        this.setData({ assignedQuestions: [], assignedCount: 0, sourceMode: 'random' })
      }
    } catch (e) {
      this.setData({ assignedQuestions: [], assignedCount: 0, sourceMode: 'random' })
    }

    if (!this.data.questionText) {
      this.nextQuestion()
    }
  },

  switchPart(e) {
    const part = e.currentTarget.dataset.part
    if (!part || part === this.data.currentPart) return
    this.setData({ currentPart: part, result: null })
    this.nextQuestion()
  },

  switchSource(e) {
    const mode = e.currentTarget.dataset.mode
    if (!mode || mode === this.data.sourceMode) return
    this.setData({ sourceMode: mode })
    this.nextQuestion()
  },

  handleFrameworkChange(e) {
    const idx = Number(e.detail.value)
    const option = this.data.part2Options[idx]
    this.setData({
      selectedFramework: option.value,
      selectedFrameworkLabel: option.label
    })
  },

  async nextQuestion() {
    this.setData({ loadingQuestion: true, result: null })
    const part = this.data.currentPart
    const useAssigned = this.data.sourceMode === 'assigned'

    if (useAssigned) {
      const filtered = this.filterAssignedByPart(part)
      if (filtered.length > 0) {
        const index = this.data.assignedIndex % filtered.length
        const item = filtered[index]
        this.setData({
          questionText: item.content,
          questionMeta: `已布置 · ${item.materialTitle || '题库'}`,
          questionType: item.type,
          assignedIndex: index + 1,
          loadingQuestion: false
        })
        return
      }
      this.setData({ sourceMode: 'random' })
    }

    await this.loadRandomQuestion(part)
  },

  filterAssignedByPart(part) {
    const list = this.data.assignedQuestions || []
    if (part === 'Part1') {
      return list.filter(q => q.type === 'speaking_part1')
    }
    if (part === 'Part2') {
      return list.filter(q => q.type === 'speaking_part2' || q.type === 'speaking_part2_3')
    }
    return list.filter(q => q.type === 'speaking_part2_3')
  },

  async loadRandomQuestion(part) {
    try {
      const res = await request(`/miniprogram/speaking/random?part=${part}`)
      if (res.ok && res.question) {
        this.setData({
          questionText: res.question.content,
          questionMeta: '随机题',
          questionType: res.question.type,
          loadingQuestion: false
        })
        return
      }
      wx.showToast({ title: '暂无题目', icon: 'none' })
    } catch (e) {
      wx.showToast({ title: '获取题目失败', icon: 'none' })
    }
    this.setData({ loadingQuestion: false })
  },

  handleAnswerInput(e) {
    this.setData({ answerText: e.detail.value })
  },

  async submitEval() {
    if (!this.data.answerText) {
      wx.showToast({ title: '请先输入回答', icon: 'none' })
      return
    }
    if (!this.data.questionText) {
      wx.showToast({ title: '请先获取题目', icon: 'none' })
      return
    }

    const payload = {
      part: this.data.currentPart,
      question: this.data.questionText,
      transcript: this.data.answerText
    }

    if (this.data.currentPart !== 'Part1' && this.data.selectedFramework) {
      payload.part2_topic = this.data.selectedFramework
    }

    this.setData({ loadingEval: true })
    try {
      const res = await request('/miniprogram/speaking/evaluate', {
        method: 'POST',
        data: payload
      })
      if (res.ok && res.result) {
        const normalized = this.normalizeResult(res.result)
        this.setData({ result: normalized })
      } else {
        wx.showToast({ title: res.error || '评估失败', icon: 'none' })
      }
    } catch (e) {
      wx.showToast({ title: '评估失败', icon: 'none' })
    }
    this.setData({ loadingEval: false })
  },

  normalizeResult(result) {
    const data = result || {}
    const logic = data.logic_outline || {}
    const rewrite = data.rewrite_high_band || {}
    return {
      logic_outline: {
        zh: Array.isArray(logic.zh) ? logic.zh : [],
        en: Array.isArray(logic.en) ? logic.en : []
      },
      rewrite_high_band: {
        paragraph: rewrite.paragraph || rewrite.rewrite || '',
        logic_tips: Array.isArray(rewrite.logic_tips) ? rewrite.logic_tips : []
      },
      sentence_feedback: Array.isArray(data.sentence_feedback) ? data.sentence_feedback : [],
      chinese_style_correction: Array.isArray(data.chinese_style_correction) ? data.chinese_style_correction : [],
      lexical_upgrade: Array.isArray(data.lexical_upgrade) ? data.lexical_upgrade : []
    }
  }
})
