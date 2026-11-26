# 九分学长官方客户端会话生命周期静态调查

调查时间：2026-11-26。实现树 `/Users/zhouxin/Desktop/studytracker/.tmp/exam-sprint-repair-20261126`，分支 `codex/exam-sprint-repair-20261126`，基线 `f81a5e4a`。本报告记录安装包内可复核的客户端代码及独立续期模块的离线实现；本子任务未访问源站、登录或交卷，未改变 runtime 或客户端文件。

## 结论

本机安装的 **0.9.20-rc.1** 官方客户端确实实现了会话续期：正常流程向 `POST https://www.9fnnn.com/api/user-auth/v1/session/renew` 发送当前 token；成功后保存服务端返回的新 token 和同一用户对象。它不是独立 `refresh_token` 换 token 的实现。源码只能证明客户端覆盖本地 token，**不能证明新 token 会立即撤销服务器上的旧 token**。

这个流程**不能证明已经返回 401 的旧 token 仍可续期**。客户端对续期请求的 HTTP 401/403 或业务错误码 401/403/10401/10403 执行清除登录状态；其正常恢复路径是重新登录。本次未调用该端点，源站是否存在过期宽限期、具体 token 有效期和服务器撤销策略均未验证。

客户端续期会轮换本地 `localStorage` 的 token。独立任务此前保存的会话副本不会因为客户端正常续期而自动更新；因此一个曾经有效的副本不能被当作永久凭据。此为基于客户端保存流程的推论，未读取或比对任何真实 token。

## 可复核的实现

所有文件均位于 `/Applications/九分学长考雅机考平台.app/Contents/Resources/app.asar`。下列偏移是 **Python UTF-8 解码字符串的 0-based 字符偏移**，不是 ASAR 文件偏移；压缩后的 renderer 内容集中在第 2 行，故同时给出函数名和偏移。

| 文件／定位 | 代码行为 |
|---|---|
| `dist/assets/index-DTVCV1yT.js`，`renewUserAuthSession()`，字符 116574 | 调用 `/user-auth/v1/session/renew`，POST，空 JSON 对象，认证服务 base URL，10 秒超时。 |
| 同文件，`class sC`／`request()`，字符 113740 | 从 `localStorage` 的 `token` 键取当前值，使用自定义 **`token` 请求头**。请求使用 JSON、`credentials: "omit"`；没有 Cookie 或 Bearer 形式的续期要求。续期端点不在跳过鉴权的登录接口集合中。 |
| 同文件，`function zo()`，字符 111339 | 成功结果支持 `token`／`accessToken`／`studentToken` 字段，以及 `user`／`wxUser`／`student`／`userInfo` 用户对象；缺少 token 或有效 owner 则报错。续期时新旧 owner 必须一致，否则 `AUTH_IDENTITY_CONFLICT`。通过后覆盖 `localStorage.token` 和 `localStorage.user`，发出身份变化事件。 |
| 同文件，`function Jn()`，字符 108302；`Nn()`、`yn()`、`id()` 紧随 | 对 generation、identityGeneration、token、owner 做异步响应归属检查，避免过时登录／续期响应覆盖已切换会话。续期保留身份代次，普通登录改变身份代次。 |
| 同文件，`async function uC()`，字符 117729 | 没有 token 时跳过；同一会话的并发续期复用 Promise；尝试冷却 **10 秒**、失败冷却 **30 秒**、成功冷却 **300 秒**。这些是请求节流窗口，**不是 token TTL**。 |
| 同文件，`async function cC()`，字符 118198；`function dC()`，字符 118589 | 成功则按 `renew: true` 保存新会话。认证失效则清除；其他故障返回可恢复失败，保留现有会话，受失败冷却约束。 |
| 同文件，App setup，字符 147022 起；`s("app-mounted")`，字符 147791 | 在 App 挂载、`window` 的 `focus` 事件、`document` 从隐藏变为可见时尝试续期；卸载时移除监听。此处没有持续每 5 分钟运行的定时器。 |
| 同文件，`emitTokenExpired()`，字符 109523 | 在会话归属仍有效时移除 `token`、`user`，触发 `token_expired`／`xxgg-auth-expired`。目录页切换为未登录；考试页保留未提交答案，不强制离开；其他页返回目录。 |
| `dist-electron/preload/index.cjs`，`function P()` 字符 948；`__APP_CONFIG__` 字符 1191 | 默认选择 online 配置，认证服务地址为 `https://www.9fnnn.com/api`；存在明确环境变量覆盖能力，本次未读取进程环境，也未声称实机运行时不存在覆盖。 |
| `dist-electron/main/index.js`，第 1712–1718 行 | 默认 `userData` 为 `app.getPath("appData")/xxgg-electron`，通过 `setPath("userData", ...)` 设定。打包版本不应用开发 smoke 隔离路径。 |

登录请求另有微信网页登录和邮箱验证码登录路径，登录成功也使用上述 `zo()` 保存服务端会话；没有依据从密码、验证码或其他账户入口自动恢复。本次不调用、不模拟这些入口。

在业务 bundle 内未发现独立 refresh token 参数、JWT `exp` 解码或确定的过期时间计算。主进程源码唯一 `refresh_token` 命中位于第 1725 行起的日志敏感字段脱敏正则，**不能把它当作存在 refresh-token 机制的证据**。

## 响应字段与独立续期模块

`request()` 在 HTTP 成功且内容类型为 JSON 后，仅接受外层 `code === "200" || code === 200`，返回该封套的 `data`。随后 `zo(e)` 取 `e?.data || e || {}`；因此明确支持解包一次后的平铺会话对象，以及再包一层 `data` 的对象。它依次读取 `token || accessToken || studentToken` 和 `user || wxUser || student || userInfo`。身份提取 `Hp()` 将对象中的 `userId`、`id` 转为字符串，两者均非空却不一致时拒绝；正常续期必须与请求开始时的 owner 相同。这是源码支持的有限结构，不代表本子任务已经通过网络确认服务器当前选择哪个别名。

本次新增 `services/ninefen_auth.py`，提供 `renew_session_file(explicit_path, *, now=None)`：

- 显式会话文件最小格式为 `{ "token": "<private>", "owner": "<private>" }`，只由已授权正常登录流程建立 owner 绑定；不读取 profile 或推测账号。父目录必须属于当前用户且 mode 700，文件必须为当前用户的 mode 600 单链接普通文件，拒绝符号链接。续期锁采用同目录受限文件。
- 只发上述固定 HTTPS 端点的单次 POST `{}`，`token` 请求头、10 秒超时，不使用 Cookie、环境代理凭据、重定向或盲重试。响应有大小、JSON 重复字段、token 字符和同身份检查；官方明确的别名若冲突则拒绝。
- 成功原子替换 token 并保存整数 `renewed_at`，返回只有 `status`、时间和 `durability_confirmed` 的结果，不保存响应用户对象。成功后 24 小时内跳过；**失败尝试的每日限制由 runner 负责**。
- 认证拒绝抛 `AuthenticationRejected`；其他错误为 `RenewalError`。可记录的属性仅受限 `http_status` 与枚举 `reason_code`（`renewal_failed`／`owner_missing`／`owner_mismatch`），不输出源站正文或用户信息。
- 写入或原子替换失败时保持原会话；并发会话变化时拒绝覆盖。原子替换完成后若仅目录 fsync 失败，返回 `status: renewed, durability_confirmed: false`，明确为已经提交的新会话，不回滚、不当作可重试失败。网络中断是否已在服务器轮换 token 仍未知，故一律不重发 POST。

`tests/test_ninefen_auth.py` 仅用合成 token、合成 owner 和假 HTTP，未请求源站。验证命令：

```bash
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -B -m unittest discover -s tests -p test_ninefen_auth.py -v
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -m ruff check services/ninefen_auth.py tests/test_ninefen_auth.py
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -m black --check services/ninefen_auth.py tests/test_ninefen_auth.py
```

最终结果见本报告末尾的验证记录；所有测试都在隔离工作树执行。

## 文件身份与复现

`Info.plist` 的版本以及 ASAR 中 `package.json` 的版本均为 `0.9.20-rc.1`；bundle ID 为 `com.9fnnn.ielts`，package name 为 `xxgg-ielts`。

| ASAR 内路径 | SHA-256 |
|---|---|
| `dist/assets/index-DTVCV1yT.js` | `ca9ad56af1c886b3cac97f1053145cd16d17a2bc74fce4014825132d10077009` |
| `dist-electron/preload/index.cjs` | `35512177144f54db6b197e4108ac0b0f13292a842f3c22d8d0ab9ef9f94ef0b1` |
| `dist-electron/main/index.js` | `6ce4a5e903012819493781747fc99b434f8cec6d6edf833a01e7fe550f72fe81` |

复现只读取安装包静态文件，并只输出文件哈希及符号位置，不读取任何 profile 内容：

```bash
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -B - <<'PY'
import hashlib, json, struct
from pathlib import Path
p = Path('/Applications/九分学长考雅机考平台.app/Contents/Resources/app.asar')
markers = {
    'dist/assets/index-DTVCV1yT.js': [
        'function Jn()', 'emitTokenExpired(t)', 'function zo(', 'class sC',
        'async renewUserAuthSession()', 'async function uC(',
        'async function cC(', 'function dC(', 's("app-mounted")',
    ],
    'dist-electron/preload/index.cjs': ['function P()', '__APP_CONFIG__'],
    'dist-electron/main/index.js': ['const xr =', 'w.setPath("userData"', 'function be(e)'],
}
with p.open('rb') as f:
    _, header_size, _, json_size = struct.unpack('<4I', f.read(16))
    tree = json.loads(f.read(json_size))
    for name, terms in markers.items():
        entry = tree
        for component in name.split('/'):
            entry = entry['files'][component]
        f.seek(8 + header_size + int(entry['offset']))
        raw = f.read(entry['size'])
        source = raw.decode('utf-8')
        print(json.dumps({
            'file': name, 'sha256': hashlib.sha256(raw).hexdigest(),
            'markers': [{'name': term, 'char_offset': source.find(term)} for term in terms],
        }, ensure_ascii=False))
PY
```

## 本次边界与交接

- 没有打开 `~/Library/Application Support/xxgg-electron` 内的任何文件，包括 Local Storage、Cookie、IndexedDB、日志或数据库；没有读取、打印或复制真实会话、邮箱、密码、验证码或账号信息。
- 没有网络请求、登录、续期、交卷、启动应用或修改运行状态。本报告没有验证续期端点的实际 HTTP 结果。
- 工作树开工状态已有未跟踪 `docs/reviews/exam-sprint-repair-20261126/` 与 `instance/`，均来自 root 的本轮修复工作；本子任务仅新增本报告、`services/ninefen_auth.py` 和 `tests/test_ninefen_auth.py`，未覆盖其他 agent 改动，未 commit/push/deploy。root／其他 agent 的 runner、session、sync、installer 和诊断改动由 root 汇总，不属于本子任务上线结果。
- 下一步由 root 在用户正常登录后，按已授权范围核验新会话与正常续期行为；若实现自动续期，应保持同一身份校验、原子保存、并发隔离、发布失败保留原题单及 401 停止自动重试的边界，不能把登录重试或重新交卷混入续期。
- root 负责合并本报告事实到 `docs/CODEX_HANDOFF.md`／`docs/WORKLOG.md`；当前报告仅本机共享文件可见。

### 最终离线验证（2026-11-26）

- 上述 unittest 命令：**22 tests，全部通过**。包括固定 URL／空 POST／10 秒、官方支持字段别名、跨 owner 和冲突字段拒绝、认证拒绝独立类型、不重试任何 POST、响应大小和 JSON 校验、目录／文件权限及所有者、符号链接／硬链接／FIFO、并发锁及替换检查、写入失败保留原文件、目录持久化失败状态、24 小时成功冷却、安全错误枚举。
- 上述 Ruff、Black 检查：通过。
- 使用 `ast.parse(source, filename=path, feature_version=(3, 10))` 解析新增两个 Python 文件：通过，未导入 app/config/DB。
- 另一子 agent 独立只读 review 未发现阻断项；其目录 fsync 可靠性建议已落实并补专门测试。真实在线续期与 runner／调度接入由 root 及其指定 agent 另行验证，不包含在本子任务的离线通过结论中。
