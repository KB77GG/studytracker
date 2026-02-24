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
    canSend: false,
    loadingQuestion: false,
    loadingEval: false,
    result: null,
    messages: [],
    chatScrollTop: 0,
    showMoreMenu: false,
    showModeSheet: false,
    showQuickActions: false,
    showContextMenu: false,
    contextMenuTargetId: '',
    contextMenuItems: [],
    sheetTouchStartY: 0,
    topicTitle: '',
    topicSubtitle: '',
    topicPromptLine: '',
    topicCueLines: [],
    topicCuePreview: [],
    topicBodyLines: [],
    topicBodyPreview: [],
    topicExpanded: false,
    topicQuestionsAll: [],
    topicQuestionsPreview: [],
    part3Expanded: false,
    isNearBottom: true,
    showToBottom: false,
    keyboardHeight: 0,
    scrollAnchorId: 'chat-anchor',
    composerTransform: 'translateY(0px)',
    toBottomTransform: 'translateY(0px)',
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
    linkedPart23: null,
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
    this.syncKeyboardShift(0)
    this.measureMessageScrollHeight()
    this.loadSessionList(true)
  },

  onReady() {
    this.measureMessageScrollHeight()
  },

  onHide() {
    this.setData({
      showMoreMenu: false,
      showModeSheet: false,
      showQuickActions: false,
      showContextMenu: false
    })
    this.cleanupRecordAndAudio()
  },

  onUnload() {
    this.cleanupRecordAndAudio()
  },

  cleanupRecordAndAudio() {
    this.stopRecordingTicker()
    this.clearRecordStopGuard()
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
      this.clearRecordStopGuard()
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
      this.clearRecordStopGuard()
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

  makeMessageId(prefix = 'msg') {
    return `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`
  },

  createMessage(role, extra = {}) {
    return Object.assign(
      {
        id: this.makeMessageId(role),
        role,
        type: 'text',
        content: '',
        status: 'sent',
        time: Date.now()
      },
      extra
    )
  },

  appendMessage(msg, forceScroll = false) {
    const messages = (this.data.messages || []).concat([msg])
    this.setData({ messages }, () => {
      this.maybeScrollToBottom(forceScroll)
    })
  },

  appendSystemMessage(content) {
    const text = String(content || '').trim()
    if (!text) return
    this.appendMessage(
      this.createMessage('system', {
        type: 'tips',
        content: text
      })
    )
  },

  updateMessageStatus(messageId, status, errorText = '') {
    const next = (this.data.messages || []).map((item) => {
      if (item.id !== messageId) return item
      return Object.assign({}, item, {
        status,
        errorText: status === 'failed' ? (errorText || '发送失败') : ''
      })
    })
    this.setData({ messages: next })
  },

  maybeScrollToBottom(force = false) {
    if (!force && !this.data.isNearBottom) {
      this.setData({ showToBottom: true })
      return
    }
    this.scrollChatToBottom()
  },

  refreshTopicPresentation() {
    const displayQuestion = this.getDisplayQuestion(
      this.data.questionText,
      this.data.currentPart,
      this.data.questionType
    )
    const lines = String(displayQuestion || '')
      .split('\n')
      .map((line) => line.trim())
      .filter(Boolean)

    if (!lines.length) {
      this.setData({
        topicTitle: '',
        topicSubtitle: '',
        topicPromptLine: '',
        topicCueLines: [],
        topicCuePreview: [],
        topicBodyLines: [],
        topicBodyPreview: [],
        topicExpanded: false,
        topicQuestionsAll: [],
        topicQuestionsPreview: [],
        part3Expanded: false
      })
      return
    }

    if (this.data.currentPart === 'Part3') {
      const stripped = lines.filter((line) => !/^part\s*3\b/i.test(line))
      const normalized = stripped.map((line) => line.replace(/^[•*\-\u2022]\s*/, '').trim()).filter(Boolean)
      this.setData({
        topicTitle: 'Part 3 深入讨论',
        topicSubtitle: this.data.questionMeta || '',
        topicPromptLine: '',
        topicCueLines: [],
        topicCuePreview: [],
        topicBodyLines: [],
        topicBodyPreview: [],
        topicExpanded: false,
        topicQuestionsAll: normalized,
        topicQuestionsPreview: normalized.slice(0, 2),
        part3Expanded: false
      })
      return
    }

    const title = lines[0]
    const body = lines
      .slice(1)
      .map((line) => line.replace(/^[•*\-\u2022]\s*/, '').trim())
      .filter(Boolean)

    let promptLine = ''
    let cueLines = []
    if (body.length === 1) {
      promptLine = body[0]
    } else if (body.length > 1) {
      const first = body[0]
      const lower = first.toLowerCase()
      const looksLikePrompt =
        /you should say|you should explain|you should mention|you should include|describe|talk about|please|请|你应/.test(lower) ||
        /[:：]$/.test(first)
      if (looksLikePrompt) {
        promptLine = first
        cueLines = body.slice(1)
      } else {
        cueLines = body
      }
    }

    this.setData({
      topicTitle: title,
      topicSubtitle: this.data.questionMeta || '',
      topicPromptLine: promptLine,
      topicCueLines: cueLines,
      topicCuePreview: cueLines.slice(0, 3),
      topicBodyLines: body,
      topicBodyPreview: body.slice(0, 2),
      topicExpanded: false,
      topicQuestionsAll: [],
      topicQuestionsPreview: [],
      part3Expanded: false
    })
  },

  syncKeyboardShift(height = 0) {
    const px = Number(height) || 0
    this.setData({
      keyboardHeight: px,
      composerTransform: `translateY(-${px}px)`,
      toBottomTransform: `translateY(-${px}px)`
    })
  },

  closeTransientPanels() {
    if (!this.data.showMoreMenu && !this.data.showQuickActions && !this.data.showContextMenu) return
    this.setData({
      showMoreMenu: false,
      showQuickActions: false,
      showContextMenu: false
    })
  },

  noop() {},

  measureMessageScrollHeight() {
    wx.createSelectorQuery()
      .in(this)
      .select('.message-scroll')
      .boundingClientRect((rect) => {
        if (!rect || !rect.height) return
        this.messageScrollClientHeight = rect.height
      })
      .exec()
  },

  scrollChatToBottom() {
    this.setData({
      chatScrollTop: this.data.chatScrollTop + 100000,
      isNearBottom: true,
      showToBottom: false
    })
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

  splitPart23Question(text) {
    const raw = String(text || '').replace(/\r\n/g, '\n').trim()
    if (!raw) return { part2: '', part3: '' }
    const lines = raw.split('\n')
    const part3Index = lines.findIndex((line) => /^part\s*3\b/i.test(line.trim()))
    if (part3Index < 0) {
      return { part2: raw, part3: '' }
    }
    const part2 = lines.slice(0, part3Index).join('\n').trim()
    const part3 = lines.slice(part3Index + 1).join('\n').trim()
    return { part2, part3 }
  },

  getDisplayQuestion(text, part, questionType) {
    const raw = String(text || '').trim()
    if (!raw) return ''
    if (questionType !== 'speaking_part2_3') return raw
    const sections = this.splitPart23Question(raw)
    if (part === 'Part2') {
      return sections.part2 || raw
    }
    if (part === 'Part3') {
      return sections.part3 ? `Part 3\n${sections.part3}` : raw
    }
    return raw
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
    this.setData({
      sessionDrawerOpen: true,
      showMoreMenu: false,
      showModeSheet: false,
      showQuickActions: false,
      showContextMenu: false
    })
    this.loadSessionList()
  },

  closeSessionDrawer() {
    this.setData({ sessionDrawerOpen: false })
  },

  toggleMoreMenu() {
    this.setData({
      showMoreMenu: !this.data.showMoreMenu,
      showModeSheet: false,
      showContextMenu: false
    })
  },

  openModeSheet() {
    this.setData({
      showModeSheet: true,
      showMoreMenu: false,
      showQuickActions: false,
      showContextMenu: false
    })
  },

  closeModeSheet() {
    this.setData({ showModeSheet: false })
  },

  onSheetTouchStart(e) {
    const touch = e.changedTouches && e.changedTouches[0]
    if (!touch) return
    this.setData({ sheetTouchStartY: touch.clientY })
  },

  onSheetTouchEnd(e) {
    const touch = e.changedTouches && e.changedTouches[0]
    if (!touch) return
    const delta = touch.clientY - (this.data.sheetTouchStartY || 0)
    if (delta > 80) this.closeModeSheet()
  },

  handleMoreAction(e) {
    const action = e.currentTarget.dataset.action
    this.setData({ showMoreMenu: false })
    if (action === 'history') {
      this.openSessionDrawer()
      return
    }
    if (action === 'new') {
      this.startNewSession()
      return
    }
    if (action === 'help') {
      wx.showModal({
        title: '口语对练使用说明',
        content: '先选择 Part 和题源，作答后点击发送获得评分反馈。长按消息可复制或删除。',
        showCancel: false
      })
    }
  },

  async startNewSession() {
    this.closeSessionDrawer()
    this.setData({
      currentSessionId: null,
      activeSessionId: null,
      linkedPart23: null,
      messages: [],
      answerText: '',
      canSend: false,
      result: null,
      showModeSheet: false,
      showQuickActions: false,
      showMoreMenu: false,
      showContextMenu: false,
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
      const sessionPart = session.part || this.data.currentPart
      const sessionQuestionType = session.question_type || this.data.questionType
      const sessionQuestion = session.question || this.data.questionText || ''
      const rawMessages = Array.isArray(res.messages) ? res.messages : []
      const displayQuestion = this.getDisplayQuestion(
        sessionQuestion,
        sessionPart,
        sessionQuestionType
      )
      const messages = rawMessages.map((msg) => {
        const role = msg.role || 'assistant'
        if (role === 'assistant') {
          const rawResult = msg.result && typeof msg.result === 'object' ? msg.result : null
          return this.createMessage('assistant', {
            result: rawResult ? this.normalizeResult(rawResult) : null
          })
        }
        if (role === 'user') {
          return this.createMessage('user', {
            content: msg.content || '',
            audio_url: msg.audio_url || '',
            meta: msg.meta || {},
            status: 'sent'
          })
        }
        const sys = this.getDisplayQuestion(msg.content || '', sessionPart, sessionQuestionType)
        if (sys && sys.trim() === displayQuestion.trim()) return null
        return this.createMessage('system', {
          type: 'tips',
          content: sys || '已加载历史会话'
        })
      }).filter(Boolean)

      this.setData({
        currentSessionId: session.id,
        activeSessionId: session.id,
        currentPart: session.part || this.data.currentPart,
        questionText: sessionQuestion,
        questionType: sessionQuestionType,
        questionMeta: `历史记录 · ${(item && item.createdLabel) || this.formatSessionDate(session.created_at || '') || '会话'}`,
        sourceMode: session.source || this.data.sourceMode,
        selectedFramework: session.part2_topic || '',
        selectedFrameworkLabel: this.getFrameworkLabel(session.part2_topic || ''),
        messages,
        answerText: '',
        canSend: false,
        result: null,
        showModeSheet: false,
        showQuickActions: false,
        showMoreMenu: false,
        showContextMenu: false,
        linkedPart23: (session.question_type === 'speaking_part2_3')
          ? {
              questionText: session.question || '',
              questionType: session.question_type || '',
              questionMeta: `历史记录 · ${(item && item.createdLabel) || this.formatSessionDate(session.created_at || '') || '会话'}`,
              sourceMode: session.source || this.data.sourceMode
            }
          : null,
        ...this.resetAnswerArtifacts()
      }, () => {
        this.refreshTopicPresentation()
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
    const isPart23Switch =
      (this.data.currentPart === 'Part2' || this.data.currentPart === 'Part3') &&
      (part === 'Part2' || part === 'Part3')
    const linked = this.data.linkedPart23
    if (isPart23Switch && linked && linked.questionText) {
      this.setData({
        currentPart: part,
        result: null,
        messages: [],
        currentSessionId: null,
        activeSessionId: null,
        answerText: '',
        canSend: false,
        questionText: linked.questionText,
        questionMeta: linked.questionMeta || this.data.questionMeta,
        questionType: linked.questionType || 'speaking_part2_3',
        showModeSheet: false,
        part3Expanded: false,
        topicExpanded: false,
        ...this.resetAnswerArtifacts()
      }, () => {
        this.refreshTopicPresentation()
      })
      this.createSession(linked.sourceMode || this.data.sourceMode)
      return
    }
    this.setData({
      currentPart: part,
      result: null,
      messages: [],
      currentSessionId: null,
      activeSessionId: null,
      linkedPart23: null,
      answerText: '',
      canSend: false,
      showModeSheet: false,
      part3Expanded: false,
      topicExpanded: false,
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
      linkedPart23: null,
      answerText: '',
      canSend: false,
      showModeSheet: false,
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

  handleFrameworkTagTap(e) {
    const value = e.currentTarget.dataset.value || ''
    const nextValue = this.data.selectedFramework === value ? '' : value
    this.setData({
      selectedFramework: nextValue,
      selectedFrameworkLabel: this.getFrameworkLabel(nextValue)
    })
  },

  async nextQuestion() {
    this.setData({
      loadingQuestion: true,
      result: null,
      messages: [],
      currentSessionId: null,
      activeSessionId: null,
      linkedPart23: null,
      answerText: '',
      canSend: false,
      showModeSheet: false,
      showMoreMenu: false,
      showQuickActions: false,
      showContextMenu: false,
      part3Expanded: false,
      topicExpanded: false,
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
          linkedPart23: (item.type === 'speaking_part2_3')
            ? {
                questionText: item.content,
                questionType: item.type,
                questionMeta: `已布置 · ${item.materialTitle || '题库'}`,
                sourceMode: 'assigned'
              }
            : null,
          assignedIndex: index + 1,
          loadingQuestion: false
        }, () => {
          this.refreshTopicPresentation()
        })
        await this.createSession('assigned')
        this.appendSystemMessage('已切换新题，可直接作答 ✓')
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
      return list.filter((q) => {
        if (q.type === 'speaking_part2') return true
        if (q.type !== 'speaking_part2_3') return false
        const sections = this.splitPart23Question(q.content || '')
        return !!sections.part2
      })
    }
    return list.filter(q => q.type === 'speaking_part2_3')
  },

  async loadRandomQuestion(part, retry = 0) {
    try {
      const res = await request(`/miniprogram/speaking/random?part=${part}`)
      if (res.ok && res.question) {
        const isInvalidPart2Card =
          part === 'Part2' &&
          res.question.type === 'speaking_part2_3' &&
          !this.splitPart23Question(res.question.content || '').part2
        if (isInvalidPart2Card && retry < 5) {
          return this.loadRandomQuestion(part, retry + 1)
        }
        this.setData({
          questionText: res.question.content,
          questionMeta: '随机题',
          questionType: res.question.type,
          linkedPart23: (res.question.type === 'speaking_part2_3')
            ? {
                questionText: res.question.content,
                questionType: res.question.type,
                questionMeta: '随机题',
                sourceMode: 'random'
              }
            : null,
          loadingQuestion: false
        }, () => {
          this.refreshTopicPresentation()
        })
        await this.createSession('random')
        this.appendSystemMessage('已切换新题，可直接作答 ✓')
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
    const displayQuestion = this.getDisplayQuestion(
      question,
      this.data.currentPart,
      this.data.questionType
    )
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
        this.setData({
          currentSessionId: res.session_id || null,
          activeSessionId: res.session_id || null
        })
        this.loadSessionList(true)
      } else if (!this.data.messages.length) {
        this.setData({
          messages: [
            this.createMessage('system', {
              type: 'tips',
              content: displayQuestion
            })
          ]
        })
      }
    } catch (e) {
      if (!this.data.messages.length) {
        this.setData({
          messages: [
            this.createMessage('system', {
              type: 'tips',
              content: this.getDisplayQuestion(question, this.data.currentPart, this.data.questionType)
            })
          ]
        })
      }
    }
  },

  handleAnswerInput(e) {
    const value = e.detail.value || ''
    this.setData({
      answerText: value,
      canSend: !!String(value).trim(),
      ...this.resetAnswerArtifacts()
    })
  },

  onComposerFocus(e) {
    if (e && e.detail && typeof e.detail.height === 'number') {
      this.syncKeyboardShift(e.detail.height)
    }
  },

  onComposerBlur() {
    this.syncKeyboardShift(0)
  },

  onComposerKeyboardHeightChange(e) {
    const height = e && e.detail ? Number(e.detail.height || 0) : 0
    this.syncKeyboardShift(height)
  },

  reuseUserMessage(e) {
    const text = (e.currentTarget.dataset.content || '').trim()
    if (!text) return
    this.setData({ answerText: text, canSend: true })
    wx.showToast({ title: '已填入输入框', icon: 'none' })
  },

  deleteMessageLocal(e) {
    const list = this.data.messages || []
    const msgId = e.currentTarget.dataset.id
    let index = -1
    if (msgId) {
      index = list.findIndex((item) => item.id === msgId)
    } else {
      index = Number(e.currentTarget.dataset.index)
    }
    if (Number.isNaN(index) || index < 0 || index >= list.length) return
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

  toggleQuickActions() {
    this.setData({
      showQuickActions: !this.data.showQuickActions,
      showMoreMenu: false,
      showContextMenu: false
    })
  },

  handleQuickActionTap(e) {
    const action = e.currentTarget.dataset.action
    if (!action) return
    if (action === 'toggle_oral') {
      this.toggleComposerOralMode()
      this.setData({ showQuickActions: false })
      return
    }

    let snippet = ''
    if (action === 'framework_person') {
      snippet = 'When it comes to this person, I would like to say...'
    } else if (action === 'framework_place') {
      snippet = 'As for this place, what impressed me most is...'
    } else if (action === 'high_band') {
      snippet = 'From my perspective, one compelling reason is that...'
    } else if (action === 'followup') {
      snippet = '请基于我的答案继续追问一个问题。'
    } else if (action === 'proofread') {
      snippet = '请帮我做句子纠错并给一个更高分版本。'
    }

    if (snippet) {
      const joined = this.data.answerText ? `${this.data.answerText}\n${snippet}` : snippet
      this.setData({ answerText: joined, canSend: !!String(joined).trim() })
    }
    this.setData({ showQuickActions: false })
  },

  togglePart3Expand() {
    this.setData({ part3Expanded: !this.data.part3Expanded })
  },

  toggleTopicExpand() {
    this.setData({ topicExpanded: !this.data.topicExpanded })
  },

  onMessageScroll(e) {
    const detail = e.detail || {}
    const top = Number(detail.scrollTop || 0)
    const height = Number(detail.scrollHeight || 0)
    const client = Number(detail.clientHeight || this.messageScrollClientHeight || 0)
    if (!this.messageScrollClientHeight) this.measureMessageScrollHeight()
    if (!client || !height) return
    const nearBottom = height - (top + client) < 120
    this.setData({
      isNearBottom: nearBottom,
      showToBottom: !nearBottom
    })
  },

  scrollToBottom() {
    this.scrollChatToBottom()
  },

  async handleMessageLongPress(e) {
    const msgId = e.currentTarget.dataset.id
    const index = (this.data.messages || []).findIndex((item) => item.id === msgId)
    if (index < 0) return
    const message = this.data.messages[index]
    const items = [
      { action: 'copy', label: '复制', icon: '/assets/icons/copy.svg' },
      { action: 'delete', label: '删除', icon: '/assets/icons/trash.svg' }
    ]
    if (message.role === 'assistant') {
      items.push(
        { action: 'correct', label: '纠错（占位）', icon: '/assets/icons/retry.svg' },
        { action: 'polish', label: '润色（占位）', icon: '/assets/icons/retry.svg' }
      )
    }
    if (message.role === 'user' && message.status === 'failed') {
      items.push({ action: 'retry', label: '重试', icon: '/assets/icons/retry.svg' })
    }
    this.setData({
      showContextMenu: true,
      contextMenuTargetId: msgId,
      contextMenuItems: items
    })
  },

  closeContextMenu() {
    if (!this.data.showContextMenu) return
    this.setData({ showContextMenu: false, contextMenuTargetId: '', contextMenuItems: [] })
  },

  async handleContextMenuAction(e) {
    const action = e.currentTarget.dataset.action
    const targetId = this.data.contextMenuTargetId
    this.closeContextMenu()
    if (!action || !targetId) return
    const list = this.data.messages || []
    const index = list.findIndex((item) => item.id === targetId)
    if (index < 0) return
    const message = list[index]
    if (action === 'copy') {
      const text = message.content || this.extractAssistantText(message.result)
      if (!text) return
      wx.setClipboardData({ data: text })
      return
    }
    if (action === 'delete') {
      const next = list.slice()
      next.splice(index, 1)
      this.setData({ messages: next })
      return
    }
    if (action === 'retry') {
      await this.retryMessageEval({ currentTarget: { dataset: { id: targetId } } })
      return
    }
    wx.showToast({ title: '功能占位，后续可接入', icon: 'none' })
  },

  extractAssistantText(result) {
    if (!result) return ''
    const lines = []
    if (result.rewrite_high_band && result.rewrite_high_band.paragraph) {
      lines.push(result.rewrite_high_band.paragraph)
    }
    if (Array.isArray(result.next_step) && result.next_step.length) {
      lines.push(`建议：${result.next_step.join('；')}`)
    }
    return lines.join('\n')
  },

  buildEvalPayload(transcript, sessionId = null, extra = {}) {
    const payload = {
      part: this.data.currentPart,
      question: this.data.questionText,
      transcript,
      session_id: sessionId || this.data.currentSessionId
    }
    if (this.data.currentPart !== 'Part1' && this.data.selectedFramework) {
      payload.part2_topic = this.data.selectedFramework
    }
    if (extra.audio_url || this.data.lastAudioUrl) payload.audio_url = extra.audio_url || this.data.lastAudioUrl
    if (extra.audio_metrics || this.data.lastAudioMetrics) payload.audio_metrics = extra.audio_metrics || this.data.lastAudioMetrics
    if (extra.asr_model || this.data.lastAsrModel) payload.asr_model = extra.asr_model || this.data.lastAsrModel
    if (extra.asr_task_id || this.data.lastAsrTaskId) payload.asr_task_id = extra.asr_task_id || this.data.lastAsrTaskId
    if (extra.transcription_url || this.data.lastTranscriptionUrl) payload.transcription_url = extra.transcription_url || this.data.lastTranscriptionUrl
    if (extra.oral_evaluation || this.data.lastOralEvaluation) payload.oral_evaluation = extra.oral_evaluation || this.data.lastOralEvaluation
    if (extra.oral_warrant_id || this.data.lastOralWarrantId) payload.oral_warrant_id = extra.oral_warrant_id || this.data.lastOralWarrantId
    return payload
  },

  mapEvalError(errorCode = '') {
    if (errorCode === 'deepseek_request_failed') return '评估超时，请稍后重试'
    if (errorCode === 'deepseek_http_error') return '评估服务繁忙，请稍后重试'
    if (errorCode === 'missing_deepseek_key') return '评估服务未配置'
    return errorCode || '评估失败'
  },

  async ensureSessionExists() {
    if (this.data.currentSessionId) return this.data.currentSessionId
    await this.createSession(this.data.sourceMode)
    return this.data.currentSessionId
  },

  async performEvalForMessage(messageId, payload) {
    this.setData({ loadingEval: true })
    try {
      const res = await request('/miniprogram/speaking/evaluate', {
        method: 'POST',
        data: payload,
        timeout: 70000
      })
      if (!res.ok || !res.result) {
        const errText = this.mapEvalError(res.error || '评估失败')
        this.updateMessageStatus(messageId, 'failed', errText)
        wx.showToast({ title: errText, icon: 'none' })
        return false
      }

      const normalized = this.normalizeResult(res.result)
      this.updateMessageStatus(messageId, 'sent')
      this.appendMessage(this.createMessage('assistant', { result: normalized }))
      this.setData({
        result: normalized,
        ...this.resetAnswerArtifacts()
      })
      this.loadSessionList(true)
      return true
    } catch (e) {
      this.updateMessageStatus(messageId, 'failed', '网络异常，请重试')
      wx.showToast({ title: '网络异常，请重试', icon: 'none' })
      return false
    } finally {
      this.setData({ loadingEval: false })
    }
  },

  async submitEval(e) {
    if (this.data.loadingEval) return
    const transcript = (this.data.answerText || '').trim()
    const auto = e === true
    if (!transcript) {
      if (!auto) wx.showToast({ title: '请先输入回答', icon: 'none' })
      return
    }
    if (!this.data.questionText) {
      if (!auto) wx.showToast({ title: '请先获取题目', icon: 'none' })
      return
    }

    const snapshot = {
      audio_url: this.data.lastAudioUrl || '',
      audio_metrics: this.data.lastAudioMetrics || null,
      asr_model: this.data.lastAsrModel || '',
      asr_task_id: this.data.lastAsrTaskId || '',
      transcription_url: this.data.lastTranscriptionUrl || '',
      oral_evaluation: this.data.lastOralEvaluation || null,
      oral_warrant_id: this.data.lastOralWarrantId || ''
    }
    const userMessageId = this.makeMessageId('user')
    this.appendMessage(
      this.createMessage('user', {
        id: userMessageId,
        content: transcript,
        status: 'sending',
        audio_url: snapshot.audio_url,
        meta: snapshot
      }),
      true
    )
    this.setData({ answerText: '', canSend: false, showQuickActions: false })

    const sessionId = await this.ensureSessionExists()
    if (!sessionId) {
      this.updateMessageStatus(userMessageId, 'failed', '会话初始化失败，请重试')
      wx.showToast({ title: '会话初始化失败', icon: 'none' })
      return
    }

    const payload = this.buildEvalPayload(transcript, sessionId, snapshot)
    await this.performEvalForMessage(userMessageId, payload)
  },

  async retryMessageEval(e) {
    if (this.data.loadingEval) return
    const msgId = e.currentTarget.dataset.id
    const msg = (this.data.messages || []).find((item) => item.id === msgId)
    if (!msg || msg.role !== 'user') return
    const transcript = (msg.content || '').trim()
    if (!transcript) return
    this.updateMessageStatus(msg.id, 'sending')
    const sessionId = this.data.currentSessionId || await this.ensureSessionExists()
    if (!sessionId) {
      this.updateMessageStatus(msg.id, 'failed', '会话初始化失败，请重试')
      wx.showToast({ title: '会话初始化失败', icon: 'none' })
      return
    }
    const payload = this.buildEvalPayload(transcript, sessionId, msg.meta || {})
    await this.performEvalForMessage(msg.id, payload)
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
    const nextStepList = Array.isArray(data.next_step) ? data.next_step : []
    const summaryPool = []
    if (Array.isArray(fluency.plus) && fluency.plus[0]) summaryPool.push(fluency.plus[0])
    if (Array.isArray(lexical.plus) && lexical.plus[0]) summaryPool.push(lexical.plus[0])
    if (Array.isArray(grammar.plus) && grammar.plus[0]) summaryPool.push(grammar.plus[0])
    if (nextStepList[0]) summaryPool.push(`建议：${nextStepList[0]}`)
    const summaryText = summaryPool.join(' ').trim()

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
      next_step: nextStepList,
      summary_text: summaryText
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
    this.setData({ showQuickActions: false, showMoreMenu: false, showContextMenu: false })
    if (this.data.recordBusy && !this.data.isRecording && !this.data.uploadingAudio && !this.data.transcribingAudio) {
      this.setData({ recordBusy: false })
    }
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
    this.startRecordStopGuard()
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
      canSend: false,
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

  startRecordStopGuard() {
    this.clearRecordStopGuard()
    this.recordStopGuard = setTimeout(() => {
      if (this.data.isRecording || this.data.recordBusy) {
        this.stopRecordingTicker()
        this.setData({
          isRecording: false,
          recordBusy: false,
          voiceUiMode: 'idle',
          recordDurationSec: 0,
          recordTimerLabel: '00:00',
          waveBars: buildWaveBars(false),
          recordStatus: '录音已结束，可再次点击麦克风录音'
        })
      }
    }, 5000)
  },

  clearRecordStopGuard() {
    if (this.recordStopGuard) {
      clearTimeout(this.recordStopGuard)
      this.recordStopGuard = null
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
        canSend: !!String(transcript).trim(),
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
