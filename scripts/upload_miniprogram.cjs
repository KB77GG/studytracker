#!/usr/bin/env node

const fs = require('fs')
const path = require('path')
const { execSync } = require('child_process')
const ci = require('miniprogram-ci')

const repoRoot = path.resolve(__dirname, '..')
const defaultProjectPath = path.join(repoRoot, 'miniprogram')
const packageJson = readJson(path.join(repoRoot, 'package.json'))

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, 'utf8'))
}

function parseArgs(argv) {
  const args = {
    command: 'upload',
    dryRun: false
  }
  const rest = [...argv]
  if (rest[0] && !rest[0].startsWith('-')) {
    args.command = rest.shift()
  }
  for (let index = 0; index < rest.length; index += 1) {
    const item = rest[index]
    if (!item.startsWith('--')) continue
    const key = item.slice(2)
    if (key === 'dry-run') {
      args.dryRun = true
      continue
    }
    const next = rest[index + 1]
    if (!next || next.startsWith('--')) {
      args[key] = true
      continue
    }
    args[key] = next
    index += 1
  }
  return args
}

function getEnv(...names) {
  for (const name of names) {
    const value = process.env[name]
    if (value && String(value).trim()) return String(value).trim()
  }
  return ''
}

function resolvePath(value) {
  if (!value) return ''
  return path.isAbsolute(value) ? value : path.resolve(repoRoot, value)
}

function normalizePrivateKey(value) {
  if (!value) return ''
  const decoded = value.includes('\\n') ? value.replace(/\\n/g, '\n') : value
  return decoded.trim()
}

function readPrivateKeyBase64(value) {
  if (!value) return ''
  return Buffer.from(value, 'base64').toString('utf8').trim()
}

function gitValue(command, fallback = '') {
  try {
    return execSync(command, { cwd: repoRoot, encoding: 'utf8', stdio: ['ignore', 'pipe', 'ignore'] }).trim()
  } catch (error) {
    return fallback
  }
}

function defaultVersion() {
  const now = new Date()
  const yy = String(now.getFullYear()).slice(-2)
  const mm = String(now.getMonth() + 1).padStart(2, '0')
  const dd = String(now.getDate()).padStart(2, '0')
  const hh = String(now.getHours()).padStart(2, '0')
  const min = String(now.getMinutes()).padStart(2, '0')
  const base = packageJson.version || '0.1.0'
  const prefix = base.split('.').slice(0, 2).join('.') || '0.1'
  return `${prefix}.${yy}${mm}${dd}${hh}${min}`
}

function defaultDesc() {
  const subject = gitValue('git log -1 --pretty=%s', 'manual upload')
  const shortSha = gitValue('git rev-parse --short HEAD')
  return [subject, shortSha && `(${shortSha})`].filter(Boolean).join(' ')
}

function buildProject(options) {
  const projectPath = resolvePath(
    options['project-path'] || getEnv('WECHAT_MP_PROJECT_PATH', 'MINIPROGRAM_PROJECT_PATH') || defaultProjectPath
  )
  const projectConfigPath = path.join(projectPath, 'project.config.json')
  if (!fs.existsSync(projectConfigPath)) {
    throw new Error(`project.config.json not found under ${projectPath}`)
  }

  const projectConfig = readJson(projectConfigPath)
  const appid = options.appid || getEnv('WECHAT_MP_APPID', 'MINIPROGRAM_APPID') || projectConfig.appid
  const privateKeyPath = resolvePath(
    options['key-path'] || getEnv('WECHAT_MP_PRIVATE_KEY_PATH', 'MINIPROGRAM_PRIVATE_KEY_PATH')
  )
  const privateKey = normalizePrivateKey(
    options.key
      || getEnv('WECHAT_MP_PRIVATE_KEY', 'MINIPROGRAM_PRIVATE_KEY')
      || readPrivateKeyBase64(getEnv('WECHAT_MP_PRIVATE_KEY_BASE64', 'MINIPROGRAM_PRIVATE_KEY_BASE64'))
  )

  if (!appid) {
    throw new Error('Missing appid. Set WECHAT_MP_APPID or miniprogram/project.config.json appid.')
  }
  if (!privateKey && !privateKeyPath) {
    throw new Error(
      'Missing upload key. Set WECHAT_MP_PRIVATE_KEY, WECHAT_MP_PRIVATE_KEY_BASE64, or WECHAT_MP_PRIVATE_KEY_PATH.'
    )
  }
  if (privateKeyPath && !fs.existsSync(privateKeyPath)) {
    throw new Error(`Upload key file not found: ${privateKeyPath}`)
  }

  return {
    appid,
    projectPath,
    project: new ci.Project({
      appid,
      type: 'miniProgram',
      projectPath,
      privateKey: privateKey || undefined,
      privateKeyPath: privateKey ? undefined : privateKeyPath,
      ignores: [
        'node_modules/**/*',
        'private.*.key',
        '*.key',
        '.env',
        '.env.*'
      ]
    })
  }
}

async function run() {
  const options = parseArgs(process.argv.slice(2))
  const command = options.command
  if (!['upload', 'preview'].includes(command)) {
    throw new Error(`Unsupported command: ${command}. Use upload or preview.`)
  }

  const { appid, projectPath, project } = buildProject(options)
  const robot = Number(options.robot || getEnv('WECHAT_MP_ROBOT', 'MINIPROGRAM_ROBOT') || 1)
  const desc = String(options.desc || getEnv('WECHAT_MP_DESC', 'MINIPROGRAM_DESC') || defaultDesc()).slice(0, 100)
  const setting = { useProjectConfig: true }

  if (command === 'upload') {
    const version = String(options.version || getEnv('WECHAT_MP_VERSION', 'MINIPROGRAM_VERSION') || defaultVersion())
    console.log(`[miniprogram-ci] upload appid=${appid} project=${projectPath} version=${version} robot=${robot}`)
    console.log(`[miniprogram-ci] desc=${desc}`)
    if (options.dryRun) return
    const result = await ci.upload({
      project,
      version,
      desc,
      robot,
      setting,
      onProgressUpdate: console.log
    })
    console.log(JSON.stringify(result, null, 2))
    return
  }

  const outputDest = resolvePath(options['qrcode-output'] || getEnv('WECHAT_MP_QRCODE_OUTPUT') || 'tmp/miniprogram-preview.jpg')
  fs.mkdirSync(path.dirname(outputDest), { recursive: true })
  console.log(`[miniprogram-ci] preview appid=${appid} project=${projectPath} output=${outputDest} robot=${robot}`)
  if (options.dryRun) return
  const result = await ci.preview({
    project,
    desc,
    robot,
    setting,
    qrcodeFormat: 'image',
    qrcodeOutputDest: outputDest,
    onProgressUpdate: console.log
  })
  console.log(JSON.stringify(result, null, 2))
}

run().catch((error) => {
  console.error(`[miniprogram-ci] ${error.message}`)
  process.exit(1)
})
