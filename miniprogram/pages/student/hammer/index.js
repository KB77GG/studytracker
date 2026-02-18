const { request } = require('../../../utils/request.js')
const oralSdkBridge = require('../../../utils/aliyun_oral_sdk.js')

const WAVE_BAR_COUNT = 64

function buildWaveBars(active = false) {
  const min = active ? 10 : 6
  const max = active ? 30 : 10
  return Array.from({ length: WAVE_BAR_COUNT }, () => Math.floor(Math.random() * (max - min + 1)) + min)
}

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
    chatScrollTop: 0,
    currentSessionId: null,
    isRecording: false,
    recordBusy: false,
    discardNextRecording: false,
    recordStatus: '',
    recordFormats: ['mp3', 'wav', 'aac'],
    recordFormatIndex: 0,
    uploadingAudio: false,
    transcribingAudio: false,
    ttsLoading: false,
    ttsPlaying: false,
    ttsText: '',
    ttsUrl: '',
    inputMode: 'standard',
    oralModeOptions: [
      { value: 'standard', label: '标准评估' },
      { value: 'oral_sdk', label: '发音增强(beta)' }
    ],
    oralWarrantId: '',
    oralAppId: '',
    oralWarrantExpire: '',
    oralWarrantLoading: false,
    oralEngineStatus: '',
    lastOralEvaluation: null,
    lastOralWarrantId: '',
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
    selectedFrameworkLabel: '不指定',
    sessionDrawerOpen: false,
    sessionLoading: false,
    sessionLoadingDetail: false,
    sessionList: [],
    activeSessionId: null,
    voiceUiMode: 'idle',
    recordDurationSec: 0,
    recordTimerLabel: '00:00',
    waveBars: buildWaveBars(false)
  },

  onLoad() {
    this.setupRecorder()
    this.setupAudioPlayer()
    this.loadAssigned()
    this.loadSessionList(true)
  },

  onShow() {
    if (typeof this.getTabBar === 'function' && this.getTabBar()) {
      this.getTabBar().setData({ selected: 2 })
    }
    this.loadSessionList(true)
  },

  onHide() {
    this.cleanupRecordAndAudio()
  },

  onUnload() {
    this.cleanupRecordAndAudio()
  },

  cleanupRecordAndAudio() {
    this.stopRecordingTicker()
    try {
      if (this.data.isRecording && this.recorderManager) {
        this.setData({ discardNextRecording: true, recordBusy: true, recordStatus: '已停止录音' })
        this.recorderManager.stop()
      }
    } catch (e) {}
    try {
      if (this.audioPlayer) this.audioPlayer.stop()
    } catch (e) {}
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
      this.startRecordingTicker()
      this.setData({
        isRecording: true,
        recordBusy: false,
        voiceUiMode: 'recording',
        recordStatus: '录音中...'
      })
    })
    this.recorderManager.onStop((res) => {
      const tempFilePath = res && res.tempFilePath
      const shouldDiscard = !!this.data.discardNextRecording
      this.stopRecordingTicker()
      this.setData({
        isRecording: false,
        recordBusy: false,
        voiceUiMode: 'idle',
        recordDurationSec: 0,
        recordTimerLabel: '00:00',
        waveBars: buildWaveBars(false),
        discardNextRecording: false,
        recordStatus: shouldDiscard ? '已取消本次录音，可重新练习' : '录音完成，处理中...'
      })
      if (shouldDiscard) return
      if (tempFilePath) {
        this.handleAudioFile(tempFilePath)
      } else {
        this.setData({ recordStatus: '录音失败，请重试' })
        wx.showToast({ title: '录音失败', icon: 'none' })
      }
    })
    this.recorderManager.onError((err) => {
      const errMsg = err && err.errMsg ? String(err.errMsg) : ''
      this.stopRecordingTicker()
      this.setData({
        isRecording: false,
        recordBusy: false,
        discardNextRecording: false,
        voiceUiMode: 'idle',
        recordDurationSec: 0,
        recordTimerLabel: '00:00',
        waveBars: buildWaveBars(false)
      })
      if (errMsg.includes('is recording or paused')) {
        this.setData({ recordStatus: '检测到录音未结束，请先点“停止录音”' })
        return
      }

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

  resetAnswerArtifacts() {
    return {
      lastAudioUrl: '',
      lastAudioMetrics: null,
      lastAsrModel: '',
      lastAsrTaskId: '',
      lastTranscriptionUrl: '',
      lastOralEvaluation: null,
      lastOralWarrantId: '',
      oralEngineStatus: ''
    }
  },

  scrollChatToBottom() {
    this.setData({ chatScrollTop: this.data.chatScrollTop + 100000 })
  },

  formatSessionDate(iso) {
    if (!iso) return ''
    const text = String(iso).replace('T', ' ').replace('Z', '')
    return text.slice(0, 16)
  },

  normalizeSessionItem(item = {}) {
    const question = String(item.question || '').trim()
    return {
      id: Number(item.id || 0),
      part: item.part || 'Part1',
      question,
      source: item.source || 'random',
      createdAt: item.created_at || '',
      createdLabel: this.formatSessionDate(item.created_at),
      preview: question.length > 42 ? `${question.slice(0, 42)}...` : question
    }
  },

  async loadSessionList(silent = false) {
    if (!silent) this.setData({ sessionLoading: true })
    try {
      const res = await request('/miniprogram/speaking/sessions?limit=30')
      if (res.ok && Array.isArray(res.sessions)) {
        this.setData({
          sessionList: res.sessions.map(item => this.normalizeSessionItem(item))
        })
      } else if (!silent) {
        wx.showToast({ title: res.error || '加载会话失败', icon: 'none' })
      }
    } catch (e) {
      if (!silent) wx.showToast({ title: '加载会话失败', icon: 'none' })
    } finally {
      if (!silent) this.setData({ sessionLoading: false })
    }
  },

  openSessionDrawer() {
    this.setData({ sessionDrawerOpen: true })
    this.loadSessionList()
  },

  closeSessionDrawer() {
    this.setData({ sessionDrawerOpen: false })
  },

  async startNewSession() {
    this.closeSessionDrawer()
    this.setData({
      currentSessionId: null,
      activeSessionId: null,
      messages: [],
      answerText: '',
      result: null,
      ...this.resetAnswerArtifacts()
    })
    await this.nextQuestion()
    await this.loadSessionList(true)
  },

  async openSessionFromList(e) {
    const sessionId = Number(e.currentTarget.dataset.id || 0)
    if (!sessionId || this.data.sessionLoadingDetail) return
    const item = (this.data.sessionList || []).find(x => Number(x.id) === sessionId)
    this.setData({ sessionLoadingDetail: true })
    try {
      const res = await request(`/miniprogram/speaking/session/${sessionId}`)
      if (!res.ok || !res.session) {
        wx.showToast({ title: res.error || '加载记录失败', icon: 'none' })
        return
      }
      const session = res.session || {}
      const rawMessages = Array.isArray(res.messages) ? res.messages : []
      const messages = rawMessages.map((msg) => {
        const role = msg.role || 'assistant'
        if (role === 'assistant') {
          const rawResult = msg.result && typeof msg.result === 'object' ? msg.result : null
          return {
            role: 'assistant',
            result: rawResult ? this.normalizeResult(rawResult) : null
          }
        }
        if (role === 'user') {
          return {
            role: 'user',
            content: msg.content || '',
            audio_url: msg.audio_url || '',
            meta: msg.meta || {}
          }
        }
        return {
          role: 'system',
          content: msg.content || session.question || this.data.questionText || ''
        }
      })

      this.setData({
        currentSessionId: session.id,
        activeSessionId: session.id,
        currentPart: session.part || this.data.currentPart,
        questionText: session.question || this.data.questionText,
        questionType: session.question_type || this.data.questionType,
        questionMeta: `历史记录 · ${(item && item.createdLabel) || this.formatSessionDate(session.created_at || '') || '会话'}`,
        sourceMode: session.source || this.data.sourceMode,
        selectedFramework: session.part2_topic || '',
        selectedFrameworkLabel: this.getFrameworkLabel(session.part2_topic || ''),
        messages: messages.length ? messages : [{ role: 'system', content: session.question || '' }],
        answerText: '',
        result: null,
        ...this.resetAnswerArtifacts()
      })
      this.closeSessionDrawer()
      this.scrollChatToBottom()
    } catch (e) {
      wx.showToast({ title: '加载记录失败', icon: 'none' })
    } finally {
      this.setData({ sessionLoadingDetail: false })
    }
  },

  getFrameworkLabel(value) {
    const found = (this.data.part2Options || []).find(item => item.value === value)
    return found ? found.label : '不指定'
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
      activeSessionId: null,
      answerText: '',
      ...this.resetAnswerArtifacts()
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
      activeSessionId: null,
      answerText: '',
      ...this.resetAnswerArtifacts()
    })
    this.nextQuestion()
  },

  async switchInputMode(e) {
    const mode = e.currentTarget.dataset.mode
    if (!mode || mode === this.data.inputMode) return
    this.setData({
      inputMode: mode,
      ...this.resetAnswerArtifacts()
    })
    if (mode === 'oral_sdk') {
      await this.ensureOralWarrant()
    }
  },

  async toggleComposerOralMode() {
    const mode = this.data.inputMode === 'oral_sdk' ? 'standard' : 'oral_sdk'
    if (mode === 'oral_sdk') {
      this.setData({
        inputMode: mode,
        ...this.resetAnswerArtifacts()
      })
      await this.ensureOralWarrant()
      return
    }
    this.setData({
      inputMode: mode,
      ...this.resetAnswerArtifacts(),
      oralEngineStatus: ''
    })
  },

  async ensureOralWarrant(force = false) {
    if (this.data.inputMode !== 'oral_sdk') return true
    if (!force && this.data.oralWarrantId && this.data.oralAppId) return true
    if (this.data.oralWarrantLoading) return false
    this.setData({ oralWarrantLoading: true, oralEngineStatus: '正在获取口语凭证...' })
    try {
      const res = await request('/miniprogram/speaking/oral/warrant')
      if (!res.ok || !res.warrant_id) {
        this.setData({ oralEngineStatus: `口语凭证失败：${res.error || '请稍后重试'}` })
        return false
      }
      this.setData({
        oralWarrantId: res.warrant_id,
        oralAppId: res.appid || '',
        oralWarrantExpire: res.warrant_available || '',
        oralEngineStatus: '口语凭证已就绪'
      })
      return true
    } catch (e) {
      this.setData({ oralEngineStatus: '口语凭证失败：网络异常' })
      return false
    } finally {
      this.setData({ oralWarrantLoading: false })
    }
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
      activeSessionId: null,
      answerText: '',
      ...this.resetAnswerArtifacts()
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
          activeSessionId: res.session_id || null,
          messages: messages.length ? messages : [{ role: 'system', content: question }]
        })
        this.scrollChatToBottom()
        this.loadSessionList(true)
      } else {
        this.setData({ messages: [{ role: 'system', content: question }] })
        this.scrollChatToBottom()
      }
    } catch (e) {
      this.setData({ messages: [{ role: 'system', content: question }] })
      this.scrollChatToBottom()
    }
  },

  handleAnswerInput(e) {
    this.setData({
      answerText: e.detail.value,
      ...this.resetAnswerArtifacts()
    })
  },

  reuseUserMessage(e) {
    const text = (e.currentTarget.dataset.content || '').trim()
    if (!text) return
    this.setData({ answerText: text })
    wx.showToast({ title: '已填入输入框', icon: 'none' })
  },

  deleteMessageLocal(e) {
    const index = Number(e.currentTarget.dataset.index)
    const list = this.data.messages || []
    if (Number.isNaN(index) || index < 0 || index >= list.length) return
    if ((list[index] || {}).role === 'system') return
    const messages = list.slice(0, index).concat(list.slice(index + 1))
    this.setData({ messages })
  },

  favoriteAssistantMessage(e) {
    const index = Number(e.currentTarget.dataset.index)
    const list = this.data.messages || []
    const msg = list[index]
    if (!msg || msg.role !== 'assistant' || !msg.result) return
    const favorites = wx.getStorageSync('hammer_feedback_favorites') || []
    favorites.unshift({
      createdAt: Date.now(),
      question: this.data.questionText || '',
      part: this.data.currentPart,
      result: msg.result
    })
    wx.setStorageSync('hammer_feedback_favorites', favorites.slice(0, 80))
    wx.showToast({ title: '已收藏', icon: 'success' })
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
    if (this.data.lastOralEvaluation) payload.oral_evaluation = this.data.lastOralEvaluation
    if (this.data.lastOralWarrantId) payload.oral_warrant_id = this.data.lastOralWarrantId

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
        data: payload,
        timeout: 70000
      })
      if (res.ok && res.result) {
        const normalized = this.normalizeResult(res.result)
        const messages = this.data.messages.slice()
        messages.push({
          role: 'user',
          content: this.data.answerText,
          audio_url: this.data.lastAudioUrl || '',
          meta: {
            audio_metrics: this.data.lastAudioMetrics || null,
            oral_evaluation: this.data.lastOralEvaluation || null
          }
        })
        messages.push({ role: 'assistant', result: normalized })
        this.setData({ result: normalized, messages })
        this.scrollChatToBottom()
        this.loadSessionList(true)
      } else {
        const err = res.error || '评估失败'
        const msg = err === 'deepseek_request_failed'
          ? '评估超时，请稍后重试'
          : err === 'deepseek_http_error'
          ? '评估服务繁忙，请稍后重试'
          : err
        wx.showToast({ title: msg, icon: 'none' })
      }
    } catch (e) {
      wx.showToast({ title: '网络异常，请重试', icon: 'none' })
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

  async runOralEnhancement(params) {
    if (this.data.inputMode !== 'oral_sdk') return null

    const ready = await this.ensureOralWarrant()
    if (!ready || !this.data.oralWarrantId) {
      return { ok: false, error: 'missing_warrant_id' }
    }

    if (!oralSdkBridge || typeof oralSdkBridge.evaluate !== 'function') {
      return { ok: false, error: 'oral_sdk_bridge_missing' }
    }

    const sdkPayload = {
      warrantId: this.data.oralWarrantId,
      appId: this.data.oralAppId || '',
      question: this.data.questionText,
      transcript: params.transcript || '',
      tempFilePath: params.tempFilePath || '',
      audioUrl: params.audioUrl || '',
      part: this.data.currentPart
    }

    try {
      const sdkRes = await oralSdkBridge.evaluate(sdkPayload)
      if (!sdkRes || !sdkRes.ok) {
        return { ok: false, error: (sdkRes && sdkRes.error) || 'oral_sdk_eval_failed' }
      }

      const oralEvaluation = (sdkRes.data && typeof sdkRes.data === 'object') ? sdkRes.data : {}
      if (Array.isArray(sdkRes.recordIds) && sdkRes.recordIds.length) {
        const serverRes = await request('/miniprogram/speaking/oral/task', {
          method: 'POST',
          data: {
            warrant_id: this.data.oralWarrantId,
            record_ids: sdkRes.recordIds
          }
        })
        if (serverRes.ok) {
          return {
            ok: true,
            evaluation: {
              taskid: serverRes.taskid,
              status: serverRes.status,
              result: serverRes.result || {},
              raw: serverRes.raw || {},
              source: 'aliyun_oral_task'
            }
          }
        }
      }

      return { ok: true, evaluation: oralEvaluation }
    } catch (e) {
      return { ok: false, error: 'oral_sdk_eval_failed' }
    }
  },

  startRecord() {
    if (this.data.isRecording || this.data.recordBusy || this.data.uploadingAudio || this.data.transcribingAudio) {
      return
    }
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

  onMicTap() {
    this.startRecord()
  },

  beginRecord() {
    this.setData({
      recordStatus: '准备录音...',
      result: null,
      recordBusy: true,
      discardNextRecording: false
    })
    const format = this.data.recordFormats[this.data.recordFormatIndex] || 'aac'
    try {
      this.recorderManager.start({
        duration: 120000,
        format
      })
    } catch (e) {
      this.setData({ recordBusy: false, recordStatus: '启动录音失败，请重试' })
      wx.showToast({ title: '启动录音失败', icon: 'none' })
    }
  },

  handleRecordCancel() {
    if (!this.data.isRecording || this.data.recordBusy) return
    this.setData({
      discardNextRecording: true,
      recordStatus: '已取消录音'
    })
    this.stopRecord()
  },

  handleRecordConfirm() {
    if (!this.data.isRecording || this.data.recordBusy) return
    this.stopRecord()
  },

  stopRecord() {
    if (!this.data.isRecording || this.data.recordBusy) return
    this.setData({ recordBusy: true, recordStatus: '停止录音中...' })
    try {
      this.recorderManager.stop()
    } catch (e) {
      this.setData({ recordBusy: false, isRecording: false, recordStatus: '停止录音失败，请重试' })
      wx.showToast({ title: '停止录音失败', icon: 'none' })
    }
  },

  retryRecord() {
    if (this.data.isRecording) {
      this.setData({ discardNextRecording: true })
      this.stopRecord()
    }
    this.stopRecordingTicker()
    this.setData({
      answerText: '',
      result: null,
      voiceUiMode: 'idle',
      recordDurationSec: 0,
      recordTimerLabel: '00:00',
      waveBars: buildWaveBars(false),
      recordBusy: false,
      recordStatus: '已清空，可重新录音',
      ...this.resetAnswerArtifacts()
    })
  },

  formatRecordTimer(totalSec = 0) {
    const mm = String(Math.floor(totalSec / 60)).padStart(2, '0')
    const ss = String(totalSec % 60).padStart(2, '0')
    return `${mm}:${ss}`
  },

  startRecordingTicker() {
    this.stopRecordingTicker()
    this.waveTimer = setInterval(() => {
      this.setData({
        waveBars: buildWaveBars(true)
      })
    }, 180)
    this.durationTimer = setInterval(() => {
      const nextSec = this.data.recordDurationSec + 1
      this.setData({
        recordDurationSec: nextSec,
        recordTimerLabel: this.formatRecordTimer(nextSec)
      })
    }, 1000)
  },

  stopRecordingTicker() {
    if (this.waveTimer) {
      clearInterval(this.waveTimer)
      this.waveTimer = null
    }
    if (this.durationTimer) {
      clearInterval(this.durationTimer)
      this.durationTimer = null
    }
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
        lastTranscriptionUrl: res.transcription_url || '',
        lastOralEvaluation: null,
        lastOralWarrantId: ''
      })

      if (!transcript) {
        wx.showToast({ title: '未识别到内容', icon: 'none' })
        return
      }

      if (this.data.inputMode === 'oral_sdk') {
        this.setData({ oralEngineStatus: '正在进行发音增强评测...' })
        const oralRes = await this.runOralEnhancement({
          transcript,
          tempFilePath,
          audioUrl: uploadedUrl
        })
        if (oralRes && oralRes.ok) {
          this.setData({
            lastOralEvaluation: oralRes.evaluation || null,
            lastOralWarrantId: this.data.oralWarrantId,
            oralEngineStatus: '发音增强评测完成'
          })
        } else {
          const err = oralRes && oralRes.error ? oralRes.error : '未启用SDK'
          this.setData({
            lastOralEvaluation: null,
            oralEngineStatus: `发音增强未完成：${err}（已回退标准评估）`,
            inputMode: 'standard'
          })
        }
      }

      if (!this.data.questionText) {
        await this.nextQuestion()
      }
      this.setData({ recordStatus: '转写完成，可点击发送评估' })
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
