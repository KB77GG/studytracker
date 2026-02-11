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
    messages: [],
    currentSessionId: null,
    isRecording: false,
    recordStatus: '',
    recordFormats: ['aac', 'mp3', 'wav'],
    recordFormatIndex: 0,
    uploadingAudio: false,
    transcribingAudio: false,
    ttsLoading: false,
    ttsPlaying: false,
    ttsText: '',
    ttsUrl: '',
    lastAudioUrl: '',
    lastAudioMetrics: null,
    lastAsrModel: '',
    lastAsrTaskId: '',
    lastTranscriptionUrl: '',
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
    this.setupAudioPlayer()
    this.loadAssigned()
  },

  setupAudioPlayer() {
    this.audioPlayer = wx.createInnerAudioContext()
    this.audioPlayer.obeyMuteSwitch = false
    this.audioPlayer.onEnded(() => {
      this.setData({ ttsPlaying: false })
    })
    this.audioPlayer.onError(() => {
      this.setData({ ttsPlaying: false })
      wx.showToast({ title: '播放失败', icon: 'none' })
    })
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
      this.setData({ isRecording: false })

      wx.getSetting({
        success: (res) => {
          if (!res.authSetting || !res.authSetting['scope.record']) {
            wx.showModal({
              title: '需要麦克风权限',
              content: '请在设置中开启麦克风权限后再使用录音',
              showCancel: false,
              success: () => wx.openSetting()
            })
            this.setData({ recordStatus: '录音失败：未授权麦克风' })
            return
          }

          if (this.data.recordFormatIndex < this.data.recordFormats.length - 1) {
            const nextIndex = this.data.recordFormatIndex + 1
            this.setData({
              recordFormatIndex: nextIndex,
              recordStatus: '录音失败，已切换格式请重试'
            })
            wx.showToast({ title: '录音失败，已切换格式', icon: 'none' })
            return
          }

          this.setData({ recordStatus: `录音失败：${errMsg || '请重试'}` })
          wx.showToast({ title: errMsg || '录音失败', icon: 'none' })
        },
        fail: () => {
          this.setData({ recordStatus: `录音失败：${errMsg || '请重试'}` })
          wx.showToast({ title: errMsg || '录音失败', icon: 'none' })
        }
      })
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
    this.setData({
      currentPart: part,
      result: null,
      messages: [],
      currentSessionId: null,
      answerText: '',
      lastAudioUrl: '',
      lastAudioMetrics: null,
      lastAsrModel: '',
      lastAsrTaskId: '',
      lastTranscriptionUrl: ''
    })
    this.nextQuestion()
  },

  switchSource(e) {
    const mode = e.currentTarget.dataset.mode
    if (!mode || mode === this.data.sourceMode) return
    this.setData({
      sourceMode: mode,
      messages: [],
      currentSessionId: null,
      answerText: '',
      lastAudioUrl: '',
      lastAudioMetrics: null,
      lastAsrModel: '',
      lastAsrTaskId: '',
      lastTranscriptionUrl: ''
    })
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
    this.setData({
      loadingQuestion: true,
      result: null,
      messages: [],
      currentSessionId: null,
      answerText: '',
      lastAudioUrl: '',
      lastAudioMetrics: null,
      lastAsrModel: '',
      lastAsrTaskId: '',
      lastTranscriptionUrl: ''
    })
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
        await this.createSession('assigned')
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
        await this.createSession('random')
        return
      }
      wx.showToast({ title: '暂无题目', icon: 'none' })
    } catch (e) {
      wx.showToast({ title: '获取题目失败', icon: 'none' })
    }
    this.setData({ loadingQuestion: false })
  },

  async createSession(source) {
    const question = (this.data.questionText || '').trim()
    if (!question) return
    const payload = {
      part: this.data.currentPart,
      question,
      question_type: this.data.questionType,
      source: source || this.data.sourceMode
    }
    if (this.data.currentPart !== 'Part1' && this.data.selectedFramework) {
      payload.part2_topic = this.data.selectedFramework
    }

    try {
      const res = await request('/miniprogram/speaking/session', {
        method: 'POST',
        data: payload
      })
      if (res.ok) {
        const messages = Array.isArray(res.messages) ? res.messages : []
        this.setData({
          currentSessionId: res.session_id || null,
          messages: messages.length ? messages : [{ role: 'system', content: question }]
        })
      } else {
        this.setData({ messages: [{ role: 'system', content: question }] })
      }
    } catch (e) {
      this.setData({ messages: [{ role: 'system', content: question }] })
    }
  },

  handleAnswerInput(e) {
    this.setData({
      answerText: e.detail.value,
      lastAudioUrl: '',
      lastAudioMetrics: null,
      lastAsrModel: '',
      lastAsrTaskId: '',
      lastTranscriptionUrl: ''
    })
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
      transcript: this.data.answerText,
      session_id: this.data.currentSessionId
    }
    if (this.data.lastAudioUrl) payload.audio_url = this.data.lastAudioUrl
    if (this.data.lastAudioMetrics) payload.audio_metrics = this.data.lastAudioMetrics
    if (this.data.lastAsrModel) payload.asr_model = this.data.lastAsrModel
    if (this.data.lastAsrTaskId) payload.asr_task_id = this.data.lastAsrTaskId
    if (this.data.lastTranscriptionUrl) payload.transcription_url = this.data.lastTranscriptionUrl

    if (this.data.currentPart !== 'Part1' && this.data.selectedFramework) {
      payload.part2_topic = this.data.selectedFramework
    }

    if (!payload.session_id) {
      await this.createSession(this.data.sourceMode)
      payload.session_id = this.data.currentSessionId
    }

    this.setData({ loadingEval: true })
    try {
      const res = await request('/miniprogram/speaking/evaluate', {
        method: 'POST',
        data: payload
      })
      if (res.ok && res.result) {
        const normalized = this.normalizeResult(res.result)
        const messages = this.data.messages.slice()
        messages.push({
          role: 'user',
          content: this.data.answerText,
          audio_url: this.data.lastAudioUrl || '',
          meta: { audio_metrics: this.data.lastAudioMetrics || null }
        })
        messages.push({ role: 'assistant', result: normalized })
        this.setData({ result: normalized, messages })
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
    const scores = data.scores || {}
    const criteria = data.criteria_feedback || {}
    const fluency = criteria.fluency_coherence || {}
    const lexical = criteria.lexical_resource || {}
    const grammar = criteria.grammar_range_accuracy || {}
    const pronunciation = criteria.pronunciation || {}
    const logicFramework = fluency.logic_framework || {}
    const logic = data.logic_outline || {}
    const rewrite = data.rewrite_high_band || {}
    const sentenceFeedback = Array.isArray(grammar.sentence_corrections)
      ? grammar.sentence_corrections
      : Array.isArray(data.sentence_feedback)
      ? data.sentence_feedback
      : []
    const chineseStyleCorrection = Array.isArray(lexical.expression_corrections)
      ? lexical.expression_corrections
      : Array.isArray(data.chinese_style_correction)
      ? data.chinese_style_correction
      : []
    const lexicalUpgrade = Array.isArray(lexical.vocabulary_upgrades)
      ? lexical.vocabulary_upgrades.map(item => ({
        from: item.from || '',
        to: Array.isArray(item.to) ? item.to : item.to ? [item.to] : [],
        constraint: item.usage_note || item.constraint || ''
      }))
      : Array.isArray(data.lexical_upgrade)
      ? data.lexical_upgrade
      : []

    return {
      scores: {
        fluency_coherence: Number(scores.fluency_coherence || fluency.band || 0),
        lexical_resource: Number(scores.lexical_resource || lexical.band || 0),
        grammar_range_accuracy: Number(scores.grammar_range_accuracy || grammar.band || 0),
        pronunciation: Number(scores.pronunciation || pronunciation.band || 0),
        overall: Number(scores.overall || 0)
      },
      criteria_feedback: {
        fluency_coherence: {
          band: Number(fluency.band || scores.fluency_coherence || 0),
          plus: Array.isArray(fluency.plus) ? fluency.plus : [],
          minus: Array.isArray(fluency.minus) ? fluency.minus : [],
          logic_framework: {
            outline_zh: Array.isArray(logicFramework.outline_zh) ? logicFramework.outline_zh : [],
            outline_en: Array.isArray(logicFramework.outline_en) ? logicFramework.outline_en : [],
            upgrade_tips: Array.isArray(logicFramework.upgrade_tips) ? logicFramework.upgrade_tips : []
          }
        },
        lexical_resource: {
          band: Number(lexical.band || scores.lexical_resource || 0),
          plus: Array.isArray(lexical.plus) ? lexical.plus : [],
          minus: Array.isArray(lexical.minus) ? lexical.minus : []
        },
        grammar_range_accuracy: {
          band: Number(grammar.band || scores.grammar_range_accuracy || 0),
          plus: Array.isArray(grammar.plus) ? grammar.plus : [],
          minus: Array.isArray(grammar.minus) ? grammar.minus : []
        },
        pronunciation: {
          band: Number(pronunciation.band || scores.pronunciation || 0),
          plus: Array.isArray(pronunciation.plus) ? pronunciation.plus : [],
          minus: Array.isArray(pronunciation.minus) ? pronunciation.minus : [],
          audio_observations: Array.isArray(pronunciation.audio_observations) ? pronunciation.audio_observations : [],
          confidence: pronunciation.confidence || '',
          limitation_note: pronunciation.limitation_note || ''
        }
      },
      logic_outline: {
        zh: Array.isArray(logicFramework.outline_zh)
          ? logicFramework.outline_zh
          : Array.isArray(logic.zh)
          ? logic.zh
          : [],
        en: Array.isArray(logicFramework.outline_en)
          ? logicFramework.outline_en
          : Array.isArray(logic.en)
          ? logic.en
          : []
      },
      rewrite_high_band: {
        paragraph: rewrite.paragraph || rewrite.rewrite || '',
        logic_tips: Array.isArray(rewrite.logic_tips)
          ? rewrite.logic_tips
          : Array.isArray(logicFramework.upgrade_tips)
          ? logicFramework.upgrade_tips
          : []
      },
      sentence_feedback: sentenceFeedback,
      chinese_style_correction: chineseStyleCorrection,
      lexical_upgrade: lexicalUpgrade,
      next_step: Array.isArray(data.next_step) ? data.next_step : []
    }
  },

  async playRewriteAudio(e) {
    const text = e && e.currentTarget && e.currentTarget.dataset ? e.currentTarget.dataset.text : ''
    const paragraph = text || this.data.result?.rewrite_high_band?.paragraph || ''
    if (!paragraph) {
      wx.showToast({ title: '暂无改写内容', icon: 'none' })
      return
    }

    if (this.data.ttsLoading) return
    if (this.data.ttsPlaying) {
      try {
        this.audioPlayer.stop()
      } catch (e) {}
      this.setData({ ttsPlaying: false })
    }

    if (paragraph === this.data.ttsText && this.data.ttsUrl) {
      this.playAudioUrl(this.data.ttsUrl, { trackTts: true })
      return
    }

    this.setData({ ttsLoading: true })
    try {
      const res = await request('/miniprogram/speaking/tts', {
        method: 'POST',
        data: { text: paragraph }
      })
      if (!res.ok || !res.audio_url) {
        wx.showToast({ title: res.error || '获取音频失败', icon: 'none' })
        return
      }
      this.setData({ ttsText: paragraph, ttsUrl: res.audio_url })
      this.playAudioUrl(res.audio_url, { trackTts: true })
    } catch (e) {
      wx.showToast({ title: '获取音频失败', icon: 'none' })
    } finally {
      this.setData({ ttsLoading: false })
    }
  },

  playMessageAudio(e) {
    const audioUrl = e && e.currentTarget && e.currentTarget.dataset ? e.currentTarget.dataset.url : ''
    if (!audioUrl) {
      wx.showToast({ title: '暂无录音', icon: 'none' })
      return
    }
    this.playAudioUrl(audioUrl, { trackTts: false })
  },

  playAudioUrl(audioUrl, options = {}) {
    const trackTts = !!options.trackTts
    const baseUrl = getApp().globalData.baseUrl || ''
    const rootUrl = baseUrl.replace(/\/api\/?$/, '')
    const finalUrl = audioUrl.startsWith('http') ? audioUrl : `${rootUrl}${audioUrl}`
    this.audioPlayer.src = finalUrl
    this.audioPlayer.play()
    this.setData({ ttsPlaying: trackTts })
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
    const format = this.data.recordFormats[this.data.recordFormatIndex] || 'aac'
    this.recorderManager.start({
      duration: 120000,
      format
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
      this.setData({
        answerText: transcript,
        recordStatus: transcript ? '转写完成' : '未识别到内容',
        lastAudioUrl: uploadedUrl,
        lastAudioMetrics: res.audio_metrics || null,
        lastAsrModel: res.model || '',
        lastAsrTaskId: res.task_id || '',
        lastTranscriptionUrl: res.transcription_url || ''
      })

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
