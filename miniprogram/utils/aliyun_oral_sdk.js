function guid() {
  const hex = '0123456789abcdef'
  let out = ''
  for (let i = 0; i < 32; i += 1) {
    out += hex[Math.floor(Math.random() * 16)]
  }
  return out
}

function chooseCoreType(part) {
  if (part === 'Part1') return 'en.sent.score'
  return 'en.pred.score'
}

function extractRecordIds(payload, fallbackId) {
  const ids = []
  const walk = (node) => {
    if (!node) return
    if (Array.isArray(node)) {
      node.forEach(walk)
      return
    }
    if (typeof node === 'object') {
      Object.keys(node).forEach((key) => {
        const value = node[key]
        const low = key.toLowerCase()
        if (
          (low.includes('record') || low === 'request_id' || low === 'requestid') &&
          (typeof value === 'string' || typeof value === 'number')
        ) {
          const id = String(value).trim()
          if (id) ids.push(id)
        } else {
          walk(value)
        }
      })
    }
  }
  walk(payload)
  if (!ids.length && fallbackId) ids.push(fallbackId)
  return [...new Set(ids)]
}

function evaluate(params = {}) {
  const warrantId = String(params.warrantId || '').trim()
  const appId = String(params.appId || '').trim()
  const tempFilePath = String(params.tempFilePath || '').trim()
  const transcript = String(params.transcript || '').trim()
  const part = String(params.part || 'Part1')
  const coreType = chooseCoreType(part)

  if (!warrantId) return Promise.resolve({ ok: false, error: 'missing_warrant_id' })
  if (!appId) return Promise.resolve({ ok: false, error: 'missing_oral_appid' })
  if (!tempFilePath) return Promise.resolve({ ok: false, error: 'missing_temp_file_path' })
  if (!transcript) return Promise.resolve({ ok: false, error: 'missing_ref_text' })

  const connectId = guid()
  const requestId = guid()
  const requestBody = {
    coreType,
    refText: transcript,
    request_id: requestId
  }
  const text = {
    connect: {
      cmd: 'connect',
      param: {
        sdk: {
          version: 20200903,
          sdk_version: 'v0.0.1',
          arch: 'x86_64',
          source: 8,
          protocol: 2
        },
        app: {
          userId: 'student',
          connect_id: connectId,
          sig: 'default',
          timestamp: `${Date.now()}`,
          applicationId: appId,
          warrantId
        }
      }
    },
    start: {
      cmd: 'start',
      param: {
        app: {
          userId: 'student',
          connect_id: connectId,
          sig: 'default',
          timestamp: `${Date.now()}`,
          applicationId: appId,
          warrantId
        },
        audio: {
          sampleRate: 16000,
          channel: 1,
          sampleBytes: 2,
          audioType: 'mp3'
        },
        request: requestBody
      }
    }
  }

  const url = `https://api.cloud.ssapi.cn/${coreType}?appkey=${encodeURIComponent(appId)}&connect_id=${connectId}&request_id=${requestId}&warrant_id=${encodeURIComponent(warrantId)}`

  return new Promise((resolve) => {
    wx.uploadFile({
      filePath: tempFilePath,
      name: 'audio',
      url,
      timeout: 30000,
      header: {
        'Request-Index': 0
      },
      formData: {
        text: JSON.stringify(text)
      },
      success: (res) => {
        let parsed = null
        try {
          parsed = JSON.parse(res.data || '{}')
        } catch (e) {
          resolve({ ok: false, error: 'oral_sdk_invalid_json', details: res.data || '' })
          return
        }
        if (res.statusCode !== 200) {
          resolve({ ok: false, error: 'oral_sdk_http_error', status: res.statusCode, details: parsed })
          return
        }
        resolve({
          ok: true,
          data: parsed,
          recordIds: extractRecordIds(parsed, requestId)
        })
      },
      fail: (err) => {
        resolve({ ok: false, error: 'oral_sdk_upload_failed', details: err })
      }
    })
  })
}

module.exports = {
  evaluate
}
