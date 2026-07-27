# TOEFL 题库质量审计

## 技术摘要

- 当前扫描 47 套卷、143 个科目、2863 个题目对象。
- 47 套处于发布状态，其中 32 套仍标记为不完整（68.1%）。
- 严格门禁下可直接发布的科目为 0/143（0.0%）。未通过来源审阅的科目不会被视为可发布。
- 发现 critical 226、high 386、medium 23、low 0 项。

## v2 staging 重建状态（与旧发布库隔离）

- rescue 分支已整合 2026-01-21 A/B/C、2026-01-27 A/B、2026-01-28 A/B 七套，
  共 840 个原子题。
- 七套 v2 的 schema、引用、来源 SHA-256、自动题私有答案覆盖和公开答案泄漏检查全部通过。
- 对原来的 18 个 source blocker 完成渲染页复核后，11 题由现有证据恢复；当前合计 7 题，
  逐套为 4 / 1 / 1 / 0 / 1 / 0 / 0。没有用推测内容填补。
- 严格发布门禁下七套均为 blocked：1 月 21 日 A/B/C 与 1 月 27 日 B 仍有来源缺口；
  七套四科人工来源审阅均未 approved。1 月 27 日 A、1 月 28 日 A/B 已达到
  0 source-blocked / `publish_status=ready`，但仍不是可发布套卷。
- v2 staging 已接入按 `TOEFL_MOCK_FLOW_SPEC.md` 驱动的预览系统，但本报告不把“可预览”视作
  “已上线”。现有旧发布 JSON 与本次 staging 数据保持隔离。

### 本轮来源证据清理

| 套卷 | 已恢复 | 依据 | 仍 blocked |
|---|---|---|---|
| 2026-01-21_B | Reading M2 Q13；Listening M1 Q1/Q7、M2 Q1 | 渲染题卷页 + 答案 PDF | Reading M2 Q12（题卷缺页） |
| 2026-01-21_C | Listening M2 Q1/Q5 | 渲染题卷页 + 答案 PDF | Reading M1 Q24（答案 PDF 与可见选项含义冲突） |
| 2026-01-27_A | Listening M1 Q1/Q2、M2 Q1 | 渲染题卷页 + 答案 PDF | 无 |
| 2026-01-28_A | Reading M2 Q6；Listening M1 Q24 | 题卷 + 完整源文本；题卷 + 听力原文 | 无 |

2026-01-28_A 两处冲突没有沿用错误答案 PDF：Reading M2 Q6 的 `elab____` 由完整来源句
`elaborate cathedral architecture` 确认为 `orate`；Listening M1 Q24 由听力原文明确要求
素材必须原创或注明来源，确认为 A。证据路径与 SHA-256 均写入私有 `answer_key.json`。

仍未恢复的另外五题为 2026-01-21_A Listening M1 Q15/Q18/Q21、M2 Q9，以及
2026-01-27_B Listening M1 Q25；当前题卷只有相邻题或音频引导页，缺少实际题面和四个选项。

## 最高风险发现

| 检查项 | 数量 | 发布风险 |
|---|---:|---|
| 已发布但题卷不完整 | 32 | 学生会直接遇到缺题或缺科目 |
| 四选项结构不完整 | 50 | 题干与选项无法可靠作答或判分 |
| 自动题缺少可靠答案 | 99 | 成绩分母与错题报告不可信 |
| 听力模块复用同一整段音频 | 13 | Module 2 会从错误位置播放 |

## 主要问题分布

| 问题代码 | 数量 |
|---|---:|
| `grading_not_ready` | 144 |
| `source_profile_missing` | 139 |
| `order_answer_not_buildable` | 128 |
| `answer_missing` | 99 |
| `mc_option_count_invalid` | 50 |
| `published_exam_incomplete` | 32 |
| `question_order_noncontiguous` | 23 |
| `module_audio_reused` | 13 |
| `subject_review_pending` | 4 |
| `source_question_coverage_missing` | 3 |

## 套卷级发布状态

| 套卷 | 当前发布 | 内容状态 | 严格门禁 | Critical | High | Medium |
|---|---|---|---|---:|---:|---:|
| 2026-01-21_A | 是 | complete | blocked | 10 | 4 | 1 |
| 2026-01-21_B | 是 | complete | blocked | 6 | 4 | 1 |
| 2026-01-21_C | 是 | partial | blocked | 7 | 4 | 1 |
| 2026-01-27_A | 是 | partial | blocked | 8 | 4 | 1 |
| 2026-01-27_B | 是 | complete | blocked | 10 | 4 | 1 |
| 2026-01-28_A | 是 | partial | blocked | 10 | 4 | 1 |
| 2026-01-28_B | 是 | partial | blocked | 6 | 4 | 1 |
| 2026-02-01_A | 是 | complete | blocked | 9 | 4 | 1 |
| 2026-02-01_B | 是 | complete | blocked | 8 | 4 | 1 |
| 2026-02-01_C | 是 | partial | blocked | 8 | 4 | 0 |
| 2026-02-02 | 是 | complete | blocked | 8 | 4 | 1 |
| 2026-02-04_S1 | 是 | partial | blocked | 3 | 2 | 0 |
| 2026-02-08 | 是 | complete | blocked | 4 | 4 | 1 |
| 2026-02-10 | 是 | partial | blocked | 7 | 4 | 1 |
| 2026-02-23 | 是 | partial | blocked | 1 | 3 | 0 |
| 2026-02-25 | 是 | partial | blocked | 3 | 6 | 0 |
| 2026-02-28 | 是 | partial | blocked | 5 | 4 | 1 |
| 2026-03-02_A | 是 | partial | blocked | 5 | 2 | 0 |
| 2026-03-02_B | 是 | partial | blocked | 6 | 2 | 0 |
| 2026-03-04 | 是 | partial | blocked | 3 | 2 | 0 |
| 2026-03-06 | 是 | partial | blocked | 7 | 4 | 0 |
| 2026-03-08 | 是 | partial | blocked | 3 | 4 | 0 |
| 2026-03-08_OFFLINE | 是 | complete | blocked | 5 | 36 | 0 |
| 2026-03-10 | 是 | partial | blocked | 2 | 3 | 0 |
| 2026-03-11 | 是 | partial | blocked | 2 | 2 | 0 |
| 2026-03-14 | 是 | complete | blocked | 10 | 4 | 1 |
| 2026-03-14_OFFLINE_CN | 是 | partial | blocked | 1 | 2 | 0 |
| 2026-03-15 | 是 | partial | blocked | 6 | 4 | 0 |
| 2026-03-16 | 是 | partial | blocked | 2 | 2 | 0 |
| 2026-03-17 | 是 | complete | blocked | 4 | 6 | 1 |
| 2026-03-18 | 是 | partial | blocked | 3 | 4 | 0 |
| 2026-03-20 | 是 | complete | blocked | 6 | 6 | 1 |
| 2026-03-21_OFFLINE_CN | 是 | partial | blocked | 4 | 19 | 0 |
| 2026-03-23_S1 | 是 | complete | blocked | 5 | 6 | 1 |
| 2026-03-25 | 是 | complete | blocked | 3 | 4 | 0 |
| 2026-03-27 | 是 | complete | blocked | 3 | 6 | 1 |
| 2026-03-29_OFFLINE_CN | 是 | partial | blocked | 3 | 45 | 1 |
| 2026-03-30 | 是 | partial | blocked | 1 | 2 | 0 |
| 2026-04-01 | 是 | complete | blocked | 2 | 4 | 1 |
| 2026-04-05_S2 | 是 | partial | blocked | 5 | 76 | 1 |
| 2026-04-06 | 是 | partial | blocked | 3 | 3 | 0 |
| 2026-04-08 | 是 | partial | blocked | 7 | 4 | 1 |
| 2026-04-11_OFFLINE_CN | 是 | partial | blocked | 1 | 11 | 0 |
| 2026-04-13_S1 | 是 | partial | blocked | 5 | 4 | 1 |
| 2026-04-15_S1 | 是 | partial | blocked | 4 | 5 | 0 |
| ets-og-chapter-6 | 是 | - | blocked | 1 | 24 | 0 |
| ets-practice-1 | 是 | - | blocked | 1 | 23 | 0 |

## 第一套：2026-01-21_A

该套已建立页级来源结构档案，但四科仍处于人工审阅前状态。以下数量是导入后的题目覆盖，不代表内容语义已经核准。

| 科目 | 题目对象 | 计分项 | 门禁状态 | Critical | High | Medium |
|---|---:|---:|---|---:|---:|---:|
| reading | 22 | 49 | blocked | 1 | 1 | 0 |
| listening | 41 | 41 | blocked | 2 | 1 | 1 |
| writing | 12 | 12 | blocked | 7 | 1 | 0 |
| speaking | 11 | 11 | blocked | 0 | 1 | 0 |

## 门禁方法

- 题目 ID、Module 和题号范围必须唯一且可解析。
- 选择题必须恰好四个非空选项，答案必须属于可见选项。
- 填空答案数量必须与题号范围一致；组句答案必须可由展示词块构造。
- 听力与口语题必须解析到实际存在的静态音频；不同听力 Module 不得共用同一整段音频。
- 每套上线前必须建立带 SHA-256 的来源档案，并由人工将对应科目标记为 `approved`。

## 限制与下一步

- 本报告验证结构、覆盖率、来源哈希和媒体绑定，不自动判断题干与选项的语义匹配。
- 第一套需逐题对照原始 PDF，并对听力进行时间轴/题组抽验后才可批准。
- 任何无法从来源确定的内容保持 `review_required`，不得由模型猜测补全。
