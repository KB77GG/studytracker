# 发布前听力题干独立审查

工作树 `/private/tmp/studytracker-cambridge-fix-20261107`；分支 `codex/cambridge-explanations-fix-20261107`；开工 HEAD `40cd8225db1b0a5da188b1dd99d4521dc5853328`。已重新读 AGENTS、CLAUDE、两交接并核 git。既有本轮解析修复全部保留。本审查不 commit/push/deploy，主 agent 负责集成和最终发布记录。

## 范围和方法

- 全量扫描剑桥4–21听力 72 套、288 个 Section、568 题组、2880 题：题号顺序、题干空格、collect/table 占位符、选项键与答案字母、原始 group/题目归属、说明中的题号范围、词数候选、地图/图表文件。
- 对照只读源 `/Users/zhouxin/Desktop/studytracker/data/idictation_xyy_listening/raw.json`。脚本保存原文件 SHA256。所有题目 number/options 与所属原始题目一致；初始 group 的 desc/collect/table/img_url/collect_option 与原始组一致。上游本身仍可能错，不能把“原样导入”当成内容正确。
- 手工复核高风险：全部7个重复同ID空格、全部4个数字空格、全部9条题号范围异常、全部6个词数候选、6组单空短题干重复；37组98题共享多空题干的空格数与题目数一致，按现有共享题干逻辑处理。实际全库渲染由独立展示 agent 的 `presentation-stems.*` 复核。
- 两题双空/词数矛盾引出原书核验：查看剑9原书扫描题页与答案页；剑6原题扫描和原书答案页文本；剑4原书答案页搜索索引。均区分原题印刷连接词、两空输入及单题分值。

## 新确认问题

### 1. 四道数字空格位置不被识别

剑18 Test3 Q1–4 原题 title 为 `【1】` 至 `【4】`；当前 `questionTemplate` 只识别空 `【 】`，因此保留旧数字方框并把输入控件追加到句尾，尤其 Q1 地址、Q4 会员类型的作答位置错误。collect 中对应的 `$68$` 至 `$71$` 本身正确。

已交展示 agent 处理通用空格识别及专项重编号；本 agent **没有**额外改这4条 title，以免通过改静态文本掩盖通用渲染根因。最终验证结果以其修复报告为准。

### 2. 七道单题双空处理失真，其中四道还有源评分表示错误

| 题目 | 原题结构 / 本库 ID | 旧显示与评分问题 |
| --- | --- | --- |
| 剑4 T1 Q11 | 两空，印有 and，ID21802 | 空 title 走 targetTemplate，第二个 `$21802$` 未成为可作答输入；答案仅正序组合，反序错误判0，原key明确两项必需、顺序不限。 |
| 剑6 T1 Q7 | from 两个时间 to，ID1578 | 第二空变为不可输入的 ghost blank；本库将两端时间拆为替代答案，任填一端得1，完整两端得0。 |
| 剑6 T1 Q19 | 两个星期，印有 and，ID1590 | 第二空变 ghost blank；本库允许仅一个星期得1，原题需要两个。 |
| 剑6 T1 Q32 | 两种材料，印有 and，ID1602 | 第二空变 ghost blank；本库将两种材料当替代答案，单填一种得1，完整两种得0。 |
| 剑6 T3 Q36 | 两空，印有 and，ID1672 | 单题 title 双空，split(limit=2) 截掉第二空及尾句；两词上限本身正确，预印 and 不是学生应写的第三词。 |
| 剑9 T1 Q33 | 两空，印有 or，ID1220 | 同上，尾句被截断；原key明确两项都要、顺序不限、共1分。 |
| 剑9 T2 Q12 | between 两天 and，ID1239 | 第二空变 ghost blank；原书p35确有两空，p154 key用斜线记两天，本库组合答案不能再被拆成全局替代项。 |

这里的七题应保留一个题号、一个逻辑答案和1分，同时提供两个真实输入。不能把第二空删除、复制第一空，或要求学生把预印连接词算进词数。两个输入由展示 agent 实现并通过复验；后续主 agent 明确授权本 agent 完成下述4题评分专用修复。没有修改历史数据或重评成绩。

原书依据：

- [剑6原题扫描](https://ieltsresources.org/Cambridges/Cambridge%206/Cambridge%206.pdf)：书页11、13、16、64的对应题目均印有同题号两空；该镜像末尾简编答案不作最终判分权威。[剑6原书全文文本](https://studylib.net/doc/27113174/ielts-6) 书页151及155，分别支持 Q7 两端时间、Q19 两天、Q32 两种材料和 Q36 两种材料。另[原书PDF索引](https://file.qyqeducation.com/%E5%89%91%E6%A1%A5%E9%9B%85%E6%80%9D%E7%9C%9F%E9%A2%98/%E5%89%91%E6%A1%A5%E9%9B%85%E6%80%9D%E7%9C%9F%E9%A2%986.pdf)结果一致；其直链当时连接失败，未声称已完整下载该镜像。
- [剑9原书扫描](https://hasanboy.uz/wp-content/uploads/2018/06/Cambridge-Practice-Tests-for-IELTS-9.pdf)：可视核书页15/152（T1 Q33）和35/154（T2 Q12）。下载缓存 `/private/tmp/cambridge9-source-20261107.pdf`；核验图片 `/private/tmp/cambridge9-{question15,question35,answer152,answer154}-20261107.png`。PDF与整页图仅本机缓存，不入仓库。
- [剑4原书答案页索引](https://file.qyqeducation.com/%E5%89%91%E6%A1%A5%E9%9B%85%E6%80%9D%E7%9C%9F%E9%A2%98/%E5%89%91%E6%A1%A5%E9%9B%85%E6%80%9D%E7%9C%9F%E9%A2%984.pdf)：书页152，Q11标明两项必需、顺序不限、共1分。这里依据可读原书答案索引，未称已可视核该镜像整页。

这些是原书内容的第三方镜像，并非 Cambridge 官方网站托管；不使用改成“三词上限/单空”的第三方练习站作为修复依据。

`listening-stems.json.baseline_grading_examples` 直接从固定生产 Git 对象取原评分函数和题库运行，保存可复现失败。例如：

- C6T1Q7：`10`→1、`4.30`→1、`10, 4.30`→0。
- C6T1Q19：`Monday`→1。
- C6T1Q32：`metal`→1、`metal and leather`→0。
- C4T1Q11：原key接受的反序组合→0。

C6T3Q36和C9T1Q33的现有组合 key 本身可以覆盖正确两项，但旧单输入模式让按原题只写两词的回答失败。因此“原始评分源错误”与“输入/序列化不支持双空”应分别描述，不能宣称七题的标准答案内容都错。

### 3. 九条题号范围说明误写成 and

| 套题 | 题组ID | 实际完整范围 |
| --- | --- | --- |
| 剑11 T2 | 209 / 217 | Q1–10 / Q31–40 |
| 剑12 T6 | 184 / 189 | Q1–10 / Q31–40 |
| 剑13 T2 | 156 / 162 | Q1–10 / Q31–40 |
| 剑16 T3 | 85 | Q31–40 |
| 剑17 T2 | 43 | Q8–10 |
| 剑18 T3 | 19 | Q5–10 |

这些组的 desc 将首尾两个题号用 and 相连；实际数据题目连续完整。应改为范围连字符，不能把正常两题多选组的 and 全局替换。剑11 T2 g209 另有 `Complete th notes` 拼写遗漏。主 agent 已实现受控 groups.desc 更正契约；本 agent 已把以上9组desc及 th→the 写入 listening.json 和对应静态JSON。最终重跑范围说明异常为0；JSON保留源旧desc与当前desc的9个差异。

### 4. 四条题干粘词已窄修

- 剑5 T3 Q13–15 共享三空题干：`thesame`→`the same`；原 collect 已是正确分词。
- 剑15 T4 Q8：`wasprovided`→`was provided`；原 collect 已是正确分词。

已修改 `data/cambridge_content_corrections/listening.json` 和两个对应静态JSON，只加4个 title 修订；Q13–15仍保持同一三空共享题干。新增 `test_source_form_words_are_not_joined_in_visible_titles`，听力更正测试9/9通过。事前已通知主 agent，未修改其 scope 审计脚本。旧实施统计18套33题因此扩为至少20套37题；最终总范围由主 agent 统一归并其他修复。

## 已排除的结构候选

- 没有缺号、重复题号、跨组未知占位符、漏占位符、选项键重复/空值、空选项内容、正确字母不在选项表、选择题无选项。
- 859条空 title 都有共享题干、collect/table或图像等上下文，不能直接算作空题。其中230条为合并多选，其余629条主要为表格/笔记/图示项。
- 100条多空 title 中，98条分成37个合法共享题干簇，簇内题数与空数相等；剩余2条就是上表的单题双空异常。另6组重复短题干对应不同上下文，不据此认定串题。
- 6个词数候选中4个是字母数字混合邮编，简单英文单词正则误报；其余2个为双空题的预印连接词问题，不应更改整组词数限制。
- 36条数字紧邻空格候选大多是题号或地址/费用/年份。四条 `【数字】` 单独列为实错；其余不能机械删除所有数字。
- 30张本地题图全部存在且可解码，地图/图表题组均有本地图文件；尺寸及对应test/section/group见JSON。这里只验证文件存在、可解码和源关联，没有逐张完成地图内容的视觉语义终审。

## 复现和验证

```sh
cd /private/tmp/studytracker-cambridge-fix-20261107
PYTHONDONTWRITEBYTECODE=1 /Users/zhouxin/Desktop/studytracker/.venv/bin/python docs/reviews/cambridge-release-20261107/listening-stems.py
PYTHONDONTWRITEBYTECODE=1 /Users/zhouxin/Desktop/studytracker/.venv/bin/python -m unittest tests.test_cambridge_listening_corrections -q
/Users/zhouxin/Desktop/studytracker/.venv/bin/ruff check --target-version py310 docs/reviews/cambridge-release-20261107/listening-stems.py tests/test_cambridge_listening_corrections.py
/Users/zhouxin/Desktop/studytracker/.venv/bin/black --check docs/reviews/cambridge-release-20261107/listening-stems.py
git diff --check
```

初轮以上命令通过；JSON记录扫描候选而非全为已确认错误。原评分失败样例从固定baseline加载，不会因本轮评分修复而丢失。后续修复交付与全库渲染结果见主报告/展示报告。

边界：全库结构扫描和风险候选人工复核不等于2880题逐题语义终审，也不是全部标准答案重新核对官方key。未检查真实学生历史作答或重算成绩；没有迁移/写入数据库、提交、推送或发布。规范两交接由主 agent 统一更新，以上数据更正和报告当前仅本机可见。

### 独立展示复验补记

在展示 agent 写入通用修复后，独立执行 `node --test tests/test_cambridge_stem_controls.js`：18/18通过。该组含全144套每个逻辑答案只出现一次、全部7道听力双空、完整尾句、数字方框与专项重编号、保存/回填/清空及只读门禁。此时评分源修复仍由主 agent 处理；这次通过仅确认显示与答案序列化，不能据此宣称旧评分语义已全部改正。

### 评分专用修复与最终内容补记

主 agent 后续授权本 agent 实现4题评分修复，和展示字段更正严格分开：

- 新增 `services/cambridge_answer_corrections.py` 和 `data/cambridge_content_corrections/listening_answers.json`。仅审定 C4T1Q11、C6T1Q7/19/32；manifest仅允许answer，helper从它派生answers数组。四题静态JSON同步二者，未扩大通用 normalize。明确各part变体与顺序见 `listening-answer-rules.json`。
- Q7两端时间按from/to固定顺序，保留10/10 am及4.30/4:30、可选pm的合理变体；两项之间to/and/空格均有完整组合。Q11/Q19/Q32接受正反组合和两词格式，缺少任一项均0分；Q19反序沿用原有接受范围。
- builder在显示更正之后另应用评分更正。`grade_listening_test_answers` 仅在deepcopy上应用，用于未来普通、模考与旧专项任务的新提交；不改原payload或持久快照。`review_snapshot` 仅在授权答后副本上应用当前正确key，原saved results和分数保持保存值。主agent已收到该接线变更。
- 新增 `tests.test_cambridge_answer_corrections` 7项：完整/缺项/反序/时间变体、真实旧key、重编号快照、section筛选、仅四题字段边界、构建持久化、review不重评以及非法manifest拒绝。
- 剑6T2Q40题干恢复完整电影名 The Lights of New York。原书p39、原扫描PDF索引35和本库transcript order25一致：[原题扫描](https://ieltsresources.org/Cambridges/Cambridge%206/Cambridge%206.pdf)。只改现有title字段；collect中的源OCR错字仍保留在冻结源，但新renderer优先完整正确title，页面不再显示该错字。没有扩展collect修订权限。

最终内容测试11项、评分专用7项、跨JS/Python真实序列化130场景(1个测试)合计19项通过；加既有听力/机经评分合计24项通过；review/delivery/mock review另45项通过。目标Ruff、增改专用module/tests/audit的black及diff检查通过。扩查builder与question_type_review的格式仍不合全文件formatter；同样检查生产baseline也失败，未为本轮扩大重排。独立逐字段比较生产baseline全144套5760题id/number/answer/answers/options/type，仅上述4题answer与answers改变，其余5756题完全一致。最终新增静态题干5条（4粘词+电影名）、题组desc9条、评分4题；之前已审定解析/定位更正保持。发布与远端验证仍由主agent完成，本agent未commit/push/deploy。
