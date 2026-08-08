# 托福模考流程 spec（2026 自适应格式）

> 来源：对 wofo.cc 前端公开 bundle 的流程结构分析（只取流程/计时/状态机，不含任何题目内容）。
> 目的：在 studytracker 里实现自己的模考引擎，题目用本仓库自有题库。

## 1. 总体结构

四个 section，固定顺序：

```
Reading → Listening → Writing → Speaking
```

其中 **Reading 和 Listening 是两模块自适应**（m1 → 服务端判分 → m2 走 easy 或 hard 分支）。
Speaking 和 Writing 不自适应，题目固定。

支持两种入口：

| 入口 | 说明 |
|---|---|
| 完整模考 | 四个 section 全走 |
| 单项模考 | 只走一个 section，URL 带 `?sections=reading\|listening\|speaking\|writing` |

## 2. 路由

```
/toefl/mock                       列表页（分页）
/toefl/mock/{testId}              完整模考
/toefl/mock/{testId}?sections=X   单项
/toefl/mock/{testId}?attemptId=Y  恢复某次作答
/toefl/mock/{testId}?returnTo=Z   结束后跳回
```

## 3. 后端接口（对应关系）

| 时机 | 接口 | 说明 |
|---|---|---|
| 进入考试 | `GET  /api/toefl/tests/{testId}/definition` | 拉整卷定义（分段、题目、音频、计时） |
| 开始 | `POST /api/toefl/attempts/start` | 建 attempt，返回 attemptId |
| 每题作答 | `POST /api/toefl/responses` | 增量提交单题答案 |
| 口语录音 | `POST /api/toefl/recordings` | 上传音频 |
| M1 结束 | `POST /api/toefl/attempts/{id}/route-m2` | body `{section, forceMode}`，**服务端决定 m2 难度** |
| 断线恢复 | `GET  /api/toefl/attempts/{id}/resume` | 恢复到中断处 |
| 进度同步 | `GET/PUT /api/toefl/attempts/{id}/state` | 当前 phase / 剩余时间 |
| 交卷 | `POST /api/toefl/attempts/{id}/complete` | |
| 出分 | `GET  /api/toefl/attempts/{id}/report` | 成绩报告 |

**关键设计点**：自适应难度判定放服务端。客户端只在 M1 结束时通知"这个 section 的 m1 做完了"，
拿回 m2 该走哪条分支。`forceMode` 是调试后门（URL `?force=easy|hard`，存 sessionStorage），
生产判分逻辑不下发到前端——这点值得照抄，否则学生能从前端看出自己 M1 考砸了。

## 4. Phase 状态机

### Reading

```
reading-section-intro          section 说明
  ↓
reading-email                  Module 1：邮件题
reading-email-v2
reading-fill-in-blank          填空
reading-academic-passage       学术阅读
reading-academic-highlight     句子高亮题
  ↓
reading-end-module1            ← 触发 POST route-m2
  ↓
reading-module2-intro
  ↓
（m2 题目，easy 或 hard 分支）
  ↓
reading-end-section
```

**计时**（从 bundle 里读到的实际常量）：

| 阶段 | 秒 | 分钟 |
|---|---|---|
| `readingM1Seconds` | 1080 | 18 |
| `readingM2Seconds` | 540 | 9 |

### Listening

```
listening-section-intro / listening-task-intro
  ↓
listening-announcement-1       通知类音频
listening-conversation         对话
listening-conversation-2
listening-q1 … listening-q18   Module 1，18 题
  ↓
listening-end-module-1         ← 触发 POST route-m2
  ↓
listening-transition-2
listening-m2-announcement
listening-m2-conversation
listening-m2-talk
listening-m2-q1 … listening-m2-q16   Module 2，16 题
  ↓
listening-end-section
```

M1/M2 题量由套题 definition 决定。运行时按 ETS 2026 技术规格显示服务端权威 Module 倒计时：
M1 18 分钟；当前唯一可核对的 Default M2 使用 OG 线性练习的 9 分钟。正式考试的 M2 会随
lower/upper 路由在 7–11 分钟之间变化。音频仍只能播放一次，且不可回退。

### Speaking

2026 新题型，两类任务：

```
speaking-section-intro
  ↓
volume-record-section          麦克风音量测试
volume-record-instruction
  ↓
speaking-listen-repeat-intro   Listen and Repeat
speaking-listen-repeat-scenario
  ↓
speaking-take-interview-intro  Take an Interview
speaking-interview-scenario
  ↓
speaking-q1 → speaking-q1-stop
speaking-q2 → speaking-q2-stop
…
speaking-q11 → speaking-q11-stop     共 11 题
  ↓
speaking-end / speaking-end-session
```

每题是 `qN` → `qN-stop` 一对：`qN` 期间录音，`qN-stop` 强制停止。
准备/作答时长按题来自 definition，不是全局常量。

**麦克风音量测试是独立 phase**，在正式题目前——这个别省，学生录不上音是最常见的模考事故。

#### StudyTracker 已落地的 2026 Speaking 时间定义

三套首发真题统一把时间写入各题 definition，而不是由前端猜测：

| 任务 | 题数 | 准备 | 每题作答 |
|---|---:|---:|---:|
| Listen and Repeat | 7 | 0 秒 | 12 秒 |
| Take an Interview | 4 | 0 秒 | 45 秒 |

- Speaking 两个服务端 phase 为 180 秒 + 300 秒，合计 480 秒（8 分钟）。
- ETS 对 Listen and Repeat 给出 8–12 秒范围；系统采用 12 秒上限，避免把未公开的逐题差异猜成更短时长。
- 每题音频范围由原 MP3 的逐词转写时间戳生成；Q1/Q8 的范围包含相应任务说明与场景，之后只播放当前题 cue。
- 用户点击一次开始本题后，流程固定为：播放一次 → 自动开始录音 → 到时强制停止 → 上传成功 → 自动进入下一题。
- 正式模式服务端拒绝超出题级时长容差的录音、跨题上传和第二次录音；preview 才允许重试。

时间依据：
[ETS TOEFL iBT Test Overview](https://www.ets.org/pdfs/toefl/toefl-ibt-test-overview.pdf)；
[ETS TOEFL iBT Test Specifications (2026)](https://www.ets.org/content/dam/ets-org/pdfs/toefl/toefl-ibt-test-specifications-2026.pdf)。

### Writing

```
writing-section
  ↓
writing-build-sentence-intro
writing-build-sentence-q1 … q10     Build a Sentence，10 题
  ↓
writing-email-intro
writing-email-q1                    Write an Email
writing-q1-time-remaining
  ↓
writing-academic-discussion-intro
writing-academic-discussion-q2      Academic Discussion
writing-q2-time-remaining
  ↓
writing-end
```

**计时**：

| 阶段 | 秒 | 分钟 |
|---|---|---|
| `writingBuildSentenceSeconds` | 360 | 6 |
| `writingQ1Seconds`（Email） | 420 | 7 |
| `writingQ2Seconds`（Academic Discussion） | 600 | 10 |

### 全局收尾

```
finished / completed → 报告页
```

## 5. 计时器实现

前端同时展示阶段/题级倒计时，统一在一个 `setInterval(…, 1000)` 里递减，各自到 0 停：

1. section 总时限
2. 当前题时限
3. 口语准备时间
4. 口语作答时间
5. 写作单题时限

一个 interval 驱动全部计时器，避免多 timer 漂移。阶段说明、Module 过渡和 Speaking 麦克风检查
不消耗作答时间；学生点击“开始本阶段”后，服务端才启动该阶段权威时钟。

**必须补的点**：前端倒计时只是显示。剩余时间要通过 `PUT /attempts/{id}/state` 同步到服务端，
交卷时以服务端时间为准，否则学生改本地时钟就能作弊。

## 6. 断线恢复

`GET /api/toefl/attempts/{id}/resume` + `?attemptId=` URL 参数。
恢复粒度是 phase 级：记当前 phase id + 该 phase 剩余秒数。

已作答的题通过 `POST /api/toefl/responses` 增量落库，所以恢复时答案不丢——
**不要等到交卷才批量提交**。

## 7. 在 studytracker 落地的建议

按 CLAUDE.md 的约定：

- 新建蓝图 `api/toefl_mock.py`，别塞 `app.py` / `api/miniprogram.py`
- 判分、自适应分流抽成独立 service 模块，路由只做收参数 → 调逻辑 → 返响应
- 数据模型：`MockTest`（卷）/ `MockAttempt`（作答）/ `MockResponse`（单题）/ `MockReport`（报告）
- 自适应阈值先用简单规则：M1 正确率 ≥ 阈值 → hard，否则 easy。阈值放配置，别硬编码
- 题目来源用本仓库已有的 `static/reading_tests/*.json`，格式对不上就写个适配层

### 待定（需要你决定）

1. **自适应阈值**具体定多少（wofo 放服务端，看不到）
2. **计分映射**：raw → scaled 的换算表
3. Listening 使用服务端 Module 倒计时并保持音频单次播放；Speaking 时间按上方 2026 定义落地并由 release gate 校验

---

*生成于 2026-07-26。流程结构来自公开前端资源分析，不含 wofo 的题目内容。*
