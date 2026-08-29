# IELTS 四模式 capability 矩阵

更新日期：2026-08-28
事实基线：[`IELTS_EXPERIENCE_BASELINE.md`](IELTS_EXPERIENCE_BASELINE.md)

## 模式定义

四种模式互斥；任一时刻必须且只能激活一种：

- `simulationMode`：正式模拟考试，最接近 IELTS on Computer。
- `practiceMode`：普通练习，沿用考试题面和导航，轻量增加训练便利。
- `intensiveListeningMode`：精听训练，允许媒体控制与听写工具。
- `reviewMode`：提交后的复盘，只读呈现当次答案、正确答案和解析。

代码不得通过到处散落的 `if (examContext)`、`if (resultMode)` 自行解释功能边界。模式解析和 capability 必须来自共享模块；模板只消费 capability。

## Capability 矩阵

| Capability | Simulation | Practice | Intensive Listening | Review |
|---|---:|---:|---:|---:|
| 保留原题语义结构 | 必须 | 必须 | 相关题面必须 | 必须 |
| 当前/已答/未答题号状态 | 必须 | 必须 | 可选 | 必须 |
| 标记/取消待检查 | 必须 | 必须 | 否 | 否 |
| Previous / Next / 点题跳转 | 必须 | 必须 | 句级导航 | 必须 |
| 修改已填答案 | 提交前允许 | 允许 | 依训练任务 | 否 |
| 自动保存答案 | 必须 | 必须 | 必须 | 不适用 |
| 服务端截止时间倒计时 | 必须 | 可选正计时/建议时间 | 否 | 否 |
| 刷新后恢复真实剩余时间 | 必须 | 可恢复进度 | 不适用 | 不适用 |
| 超时自动提交 | 必须 | 否 | 否 | 否 |
| Listening 开始前媒体预检 | 必须 | 应有 | 应有 | 片段按需 |
| Listening 单次连续播放 | 必须 | 否 | 否 | 否 |
| 音量 | 允许 | 允许 | 允许 | 允许 |
| 暂停 | 否 | 允许 | 允许 | 允许 |
| 拖动进度 | 否 | 允许 | 允许 | 允许片段 |
| 重听/循环 | 否 | 允许 | 允许 | 允许片段 |
| 倍速 | 否 | 可选 | 允许 | 可选 |
| 精听入口/听写/跟读 | 否 | 可跳转到独立模式 | 必须/按任务 | 否 |
| 原文/Transcript | 否 | 提交前默认否 | 允许 | 允许 |
| 正误/正确答案/分数/正确率 | 否 | 仅提交后切 Review | 训练规则决定 | 必须 |
| 解析/原文依据 | 否 | 仅提交后切 Review | 允许 | 必须 |
| 即时反馈 | 否 | 默认否，须显式选择 | 可按训练规则 | 不适用 |
| 错因笔记 | 否 | 提交后可用 | 允许 | 允许 |
| Reading 左文右题独立滚动 | 必须 | 必须 | 不适用 | 必须 |
| 文字高亮 | 可靠时允许 | 允许 | 允许 | 允许 |
| 屏幕笔记 | 可靠且有证据时允许 | 允许 | 允许 | 允许 |
| 地图自由缩放 | 否 | 可选 | 不适用 | 可选 |
| 地图答案热点/自动定位 | 否 | 否 | 不适用 | 有可靠坐标才允许 |
| 共享配对选项库 | 必须 | 必须 | 不适用 | 必须 |
| 右侧评分/已答统计栏 | 否 | 可低干扰显示已答 | 否 | 允许摘要 |
| “提交并判分”常驻按钮 | 否 | 可用但不遮挡题面 | 否 | 不适用 |
| 末 Part/Passage 结束科目 | 必须 | 可提交 | 不适用 | 不适用 |
| 返回练习列表主按钮 | 否 | 允许 | 允许 | 允许 |
| 退出确认 | 必须 | 未保存时需要 | 未保存时需要 | 否 |
| Reading Study / 翻译 / 查词 | 否 | 独立入口、不可干扰 | 否 | 可选辅助 |

## 必须由共享配置表达的能力

共享配置至少暴露：

```text
mode
canFlagQuestions
canPauseAudio
canSeekAudio
canReplayAudio
canChangePlaybackRate
canShowTranscript
canShowAnalysis
canShowCorrectness
canUseQuestionNotes
canUseMapZoom
canUseReadingStudy
canSubmitForScoring
showAnsweredSummary
showPersistentSubmit
requiresAudioPreflight
usesServerDeadline
confirmExit
```

`reviewMode` 由一次有效提交或已授权历史记录进入；不能由 URL 参数直接伪造。`simulationMode` 由服务端签发的模考 session 上下文进入；不能由普通练习页面自行切换。

## 页面共用边界

可以共用：题库数据、题型渲染器、原题结构、题号导航、阅读双栏、答案序列化和基础保存外壳。

必须隔离：

- Simulation 的倒计时、Listening 单次播放门禁和退出/结束流程；
- Intensive Listening 的 seek/replay/rate/segment 控制；
- Review 的答案、评分、解析和原文依据；
- Practice 的重做、常规提交和可选训练入口。

任何新增功能先在此矩阵登记，再进入共享 capability 配置和测试。未登记功能默认在 Simulation 禁止。
