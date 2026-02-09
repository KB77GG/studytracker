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
    isRecording: false,
    recordStatus: '',
    recordFormat: 'aac',
    recordFallbackTried: false,
    uploadingAudio: false,
    transcribingAudio: false,
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
    this.setupRecorder()
    this.loadAssigned()
  },

  setupRecorder() {
    this.recorderManager = wx.getRecorderManager()
    this.recorderManager.onStart(() => {
      this.setData({ isRecording: true, recordStatus: '录音中...' })
    })
    this.recorderManager.onStop((res) => {
      const tempFilePath = res && res.tempFilePath
      this.setData({ isRecording: false, recordStatus: '录音完成，处理中...' })
      if (tempFilePath) {
        this.handleAudioFile(tempFilePath)
      } else {
        this.setData({ recordStatus: '录音失败，请重试' })
        wx.showToast({ title: '录音失败', icon: 'none' })
      }
    })
    this.recorderManager.onError((err) => {
      const errMsg = err && err.errMsg ? String(err.errMsg) : ''
      if (!this.data.recordFallbackTried) {
        const nextFormat = this.data.recordFormat === 'aac' ? 'mp3' : 'aac'
        this.setData({
          isRecording: false,
          recordFormat: nextFormat,
          recordFallbackTried: true,
          recordStatus: '录音失败，已切换兼容模式'
        })
        wx.showToast({ title: '录音失败，已切换格式', icon: 'none' })
        return
      }
      this.setData({ isRecording: false, recordStatus: '录音失败，请重试' })
      wx.showToast({ title: errMsg || '录音失败', icon: 'none' })
    })
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

  async submitEval(e) {
    const auto = e === true
    if (!this.data.answerText) {
      if (!auto) wx.showToast({ title: '请先输入回答', icon: 'none' })
      return
    }
    if (!this.data.questionText) {
      if (!auto) wx.showToast({ title: '请先获取题目', icon: 'none' })
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
  },

  toggleRecord() {
    if (this.data.isRecording) {
      this.stopRecord()
    } else {
      this.startRecord()
    }
  },

  startRecord() {
    if (this.data.isRecording) return
    wx.getSetting({
      success: (res) => {
        if (res.authSetting && res.authSetting['scope.record']) {
          this.beginRecord()
        } else {
          wx.authorize({
            scope: 'scope.record',
            success: () => this.beginRecord(),
            fail: () => {
              wx.showModal({
                title: '需要麦克风权限',
                content: '请在设置中开启麦克风权限后再使用录音',
                showCancel: false,
                success: () => wx.openSetting()
              })
            }
          })
        }
      },
      fail: () => {
        wx.showToast({ title: '无法获取权限', icon: 'none' })
      }
    })
  },

  beginRecord() {
    this.setData({ recordStatus: '准备录音...', result: null })
    this.recorderManager.start({
      duration: 120000,
      format: this.data.recordFormat
    })
  },

  stopRecord() {
    if (!this.data.isRecording) return
    this.recorderManager.stop()
  },

  async handleAudioFile(tempFilePath) {
    this.setData({ uploadingAudio: true, transcribingAudio: false })
    let uploadedUrl = ''
    try {
      uploadedUrl = await this.uploadAudio(tempFilePath)
    } catch (e) {
      this.setData({ uploadingAudio: false, recordStatus: '上传失败，请重试' })
      wx.showToast({ title: '上传失败', icon: 'none' })
      return
    }
    this.setData({ uploadingAudio: false, transcribingAudio: true })

    try {
      const res = await request('/miniprogram/speaking/transcribe', {
        method: 'POST',
        data: { audio_url: uploadedUrl }
      })
      if (!res.ok) {
        wx.showToast({ title: res.error || '转写失败', icon: 'none' })
        this.setData({ recordStatus: '转写失败，请重试' })
        return
      }
      const transcript = res.transcript || ''
      this.setData({ answerText: transcript, recordStatus: transcript ? '转写完成' : '未识别到内容' })

      if (!transcript) {
        wx.showToast({ title: '未识别到内容', icon: 'none' })
        return
      }

      if (!this.data.questionText) {
        await this.nextQuestion()
      }
      await this.submitEval(true)
    } catch (e) {
      wx.showToast({ title: '转写失败', icon: 'none' })
      this.setData({ recordStatus: '转写失败，请重试' })
    } finally {
      this.setData({ transcribingAudio: false })
    }
  },

  uploadAudio(tempFilePath) {
    return new Promise((resolve, reject) => {
      const baseUrl = getApp().globalData.baseUrl
      let token = getApp().globalData.token || wx.getStorageSync('token')
      const header = {}
      if (token) {
        header['Authorization'] = `Bearer ${token}`
      }

      wx.uploadFile({
        url: `${baseUrl}/miniprogram/upload`,
        filePath: tempFilePath,
        name: 'file',
        header,
        formData: { filename: 'hammer_recording.mp3' },
        success: (res) => {
          try {
            const data = JSON.parse(res.data || '{}')
            if (data.ok && data.url) {
              resolve(data.url)
            } else {
              reject(new Error(data.error || 'upload_failed'))
            }
          } catch (err) {
            reject(err)
          }
        },
        fail: (err) => reject(err)
      })
    })
  }
})
