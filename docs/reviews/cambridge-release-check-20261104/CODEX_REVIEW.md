# 剑桥首批上线题：593 道独立验收结果

复核日期：2026-11-04。题目版本：`f74238fecdcd30d297c065f81766d4e63a3039f8`。复核方：Codex。

**593 道逐题复核完毕：正确 585 / 答案错 1 / 题目有歧义 5 / 句子不适合出题 2。**

按尚待用户确认的“每类问题题不超过 2 道”标准，主句谓语不达标；其余五类达到本次样本门槛。达到样本门槛不等于已授权上线，也不表示已发现的问题题可以原样保留。本次只提交复核结果，未改题目、判分规则或首批 8,048 道题号清单。

## 交付与读取

- [合并结果](release_check_all_reviewed.csv)：593 行，固定四列 `题目编号,判定,正确答案应为,说明`。
- `release_check_001_reviewed.csv` 至 `release_check_006_reviewed.csv`：与六份输入逐批、逐行对应；第六批 93 行，前五批各 100 行。
- [完整性核验](review_verification.json)：输入 SHA-256、分题型及分批计数、输出 SHA-256。
- [结果校验和](REVIEW_SHA256SUMS)：只覆盖本轮七份结果 CSV，未覆盖或替换原输入文件的 `SHA256SUMS`。

CSV 为 UTF-8 BOM、LF 换行。合并顺序为批次 001 至 006，每批保持输入顺序；不是重新按题号排序。说明均不超过 40 字。六个文件与题型不是一一对应：004 后 7 行属于完整主语，005 后 7 行属于动词身份。

给 Claude 的读取方式：

```bash
git fetch origin codex/grammar-release-check-20261104
git show origin/codex/grammar-release-check-20261104:docs/reviews/cambridge-release-check-20261104/CODEX_REVIEW.md
git show origin/codex/grammar-release-check-20261104:docs/reviews/cambridge-release-check-20261104/release_check_all_reviewed.csv > /tmp/release_check_all_reviewed.csv
```

不必合并本分支即可读取结果。请按题目编号连接原题；先核对下面八道，再决定修题、换题与验收口径。

## 分题型统计

| 题型 | 复核数 | 正确 | 答案错 | 有歧义 | 不适合 | 问题合计 | 按建议门槛 |
|---|---:|---:|---:|---:|---:|---:|---|
| 主句谓语 | 100 | 96 | 1 | 2 | 1 | 4 | 不达标 |
| 从句边界 | 100 | 98 | 0 | 2 | 0 | 2 | 达到样本门槛 |
| 从句类型 | 100 | 100 | 0 | 0 | 0 | 0 | 达到样本门槛 |
| 状语关系 | 93 | 93 | 0 | 0 | 0 | 0 | 全量 93 道未发现问题 |
| 完整主语 | 100 | 100 | 0 | 0 | 0 | 0 | 达到样本门槛 |
| 动词身份 | 100 | 98 | 0 | 1 | 1 | 2 | 达到样本门槛 |
| 合计 | 593 | 585 | 1 | 5 | 2 | 8 | 主句谓语需先处理 |

样本内正确比例为 585/593，约 98.65%。五类各抽 100 道，状语关系检查了首批全部 93 道；这不是对其余 7,455 道逐题作出的结论，不能把样本比例当作全量正确率保证。“干净句子”是程序筛选条件，不能替代人工确认。

原说明把“不超过 2 道”与“≤2%”并列，二者在 93 道时不同：2/93 约为 2.15%。本次该类为 0，不影响结果；正式采用验收标准时应明确按数量还是比例。这一标准仍待用户确认，本次没有代为批准。

## 八道需要处理的题

行号均指 CSV 的数据行，不含表头；文本文件行号需再加 1。

| 批次:数据行 | 题目编号 | 位置 | 判定 | 复核结论 |
|---|---|---|---|---|
| 001:25 | `gi_v02_03c41810c4d1` | ielts13_test3_p3 C-04 | 句子不适合出题 | `well- argued` 内有多余空格；局部谓语答案可以成立，但原句尚有排印问题。 |
| 001:46 | `gi_v02_38f3f11016c8` | ielts17_test1_p3 D-05 | 题目有歧义 | `There was to be a new order ...` 中 `was to be` 表预定安排，现仅高亮并以 `was` 判分；需先明确准情态结构按限定动词还是实义谓语中心判分。 |
| 001:65 | `gi_v02_99c7151620e7` | ielts20_test4_p1 D-13 | 题目有歧义 | `The two were married in 1924.` 通常可读为结婚事件，`were married` 为谓语；也可作婚姻状态的系表分析。只接受 `were` 会排斥合理的被动读法。 |
| 001:97 | `gi_v02_371cc2983c00` | ielts9_test4_p1 B-02 | 答案错 | `she then had to take work as a teacher`，答案只标 `had`、判分词也是 `had`。`had to` 表必须，实义谓语核心为 `take`；应标 `had to take`。 |
| 002:6 | `gi_v02_58e9dce8fe5d` | ielts11_test1_p3 A-02 | 题目有歧义 | `They believe that ... , and at present ...` 的后半分句可独立陈述，也可与前半共同成为 believe 的内容。仅接受前半名词性从句的范围不唯一。 |
| 002:66 | `gi_v02_16c4ed2d59fc` | ielts20_test2_p2 D-28 | 题目有歧义 | `Other research shows that ... , and again this is linked ...` 亦有并列内容是否共同受 shows 支配的范围歧义。 |
| 005:97 | `gi_v02_664eb480e7cf` | ielts11_test1_p1 A-02 | 句子不适合出题 | `Applying the most conservative estimates ... , the human population will increase ...` 的 Applying 的执行者是估算者，并非主句主语 human population。非谓语选项本身正确，但按通常的分词逻辑主语规则，原句不适合作无说明的语法范例。 |
| 006:78 | `gi_v02_b12fd3d9c310` | ielts6_test4_p2 C-05 | 题目有歧义 | `including a National Literacy Crusade` 中 including 通常列为介词；当前仅有主句谓语、从句谓语、非谓语三个选项，未覆盖这一词性分析。 |

### 判定依据与处理建议

1. **T1 的语义核心与有限动词不是同一问题。** 用户说明明确要求判分词是主句谓语核心。`have to + 动词` 的实义动作在后一个动词；British Council 的讲解也把 `may have to live` 中的 live 认作 main verb，而把 have to 视为 semi-modal。本题应以 take 为核心，并展示完整 `had to take`。参见 [British Council：Modal verbs](https://learnenglish.britishcouncil.org/free-resources/grammar/english-grammar-reference/modal-verbs)、[Cambridge：have to](https://dictionary.cambridge.org/us/dictionary/english/have-to)。
2. **准情态与系表/被动的边界不强行判错。** `was to be` 的安排义见 [Cambridge：Be to](https://dictionary.cambridge.org/grammar/british-grammar/future-other-expressions-to-talk-about-the-future)。`were married` 的两种读法会影响判分核心；因此二者记“有歧义”，建议暂换题或先明确可接受答案范围。未改写原句。
3. **并列 that 内容的范围应避免单一隐藏分析。** 两道 T2 均可有宽、窄两种句法分组；省略第二个 that 并不能单独证明后句已退出宾语内容。建议换成范围明确的句子，或设计题干锚定及多答案机制。CSV 依要求不为“有歧义”填一个假定唯一答案。
4. **原句适用性与局部答案分开。** Applying 的非谓语身份无误，但分词行为者与主句主语不一致；依据 [Purdue OWL：Dangling Modifiers](https://owl.purdue.edu/owl/general_writing/mechanics/dangling_modifiers_and_how_to_correct_them.html) 的常规教学规则，建议首批语法题暂不用这句。此结论针对无补充说明的语法教学用途，不是在评价原阅读文章的整体质量。
5. **including 的介词化用法应明确口径。** [Cambridge](https://dictionary.cambridge.org/us/dictionary/english/including) 与 [Oxford Learner’s Dictionaries](https://www.oxfordlearnersdictionaries.com/definition/english/including) 均收作介词。上一批待复核交叉复核也对 `gi_v02_6682d85fab3d` 使用相同的“选项未覆盖介词”口径。建议换目标或增加选项/说明，暂不按“非谓语必然正确”放行。

同一句其他题不连坐：ielts6_test4_p2 C-05 的 T1（`established`）和 T5（`the government of Nicaragua`）仍正确；ielts9_test4_p1 B-02 的 because 原因关系题也正确。只有原句排印或逻辑主语问题才涉及句子本身。

T6 按本次题干判断高亮动词所属的有限谓语或非谓语身份，不把 T1 的“实义核心判分”要求移植过去。例如 006:21 的 `had`（had to meet）属从句有限谓语部分、006:62 的 `has`（has to act）属主句有限谓语部分，现有分类答案成立；这不等于建议把这些单词当作 T1 的实义判分核心。

## 复核方法与完整性验证

- 按六份原文件顺序逐题读取题干、原句/高亮、机器答案、判分词、干扰项；分类选项按原文件核验。人工逐题作语法判断，没有用自动通过状态替代判断，也没有调用大模型 API 批量评分。
- 重点区分从句与非谓语、并列层级、同类从句多解、谓语核心及完整主语。疑义项目再次检查；`were married` 最终按两种读法记“有歧义”，未把有争议分析算作确定的答案错误。
- 原六份输入文件 SHA-256 未变。593 个题号唯一，全部属于 8,048 道首批清单；六个逐批结果与合并 CSV 的 ID、顺序及四列内容一致；无缺项、重复项、越界判定或超长说明。
- CSV 由 Artifact Tool 写入静态值并回读核验，再导出；用独立 CSV 解析核对保存后的文件。交付未加入题干、原句或额外评分列。
- 未重新生成题库、修改选题脚本、更新阅读解析、导入数据库或开发练习功能。本次验收不能替代这些任务的功能测试。

本机审核证据目录：`/Users/zhouxin/.codex/audits/grammar-release-check-20261104/`。实际使用的主要命令：

```bash
git fetch origin claude/word-memorization-system-eval-55v2y5
git worktree add -b codex/grammar-release-check-20261104 /Users/zhouxin/.codex/worktrees/grammar-release-check-20261104/studytracker f74238fecdcd30d297c065f81766d4e63a3039f8
# 在本机审核证据目录中运行；read_rows.py 分批展示所有 593 行。
/Users/zhouxin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node export_reviews.mjs
/Users/zhouxin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 verify_reviews.py
# 在结果目录中：
shasum -a 256 -c REVIEW_SHA256SUMS
# 在审核工作树中：
git diff --check
```

`verify_reviews.py` 实测 593/593，计数见上表；可跨电脑复查的输入/输出 SHA 和计数保存在 `review_verification.json`。源材料自身的 `SHA256SUMS` 同样保留。

## 后续

先由 Claude 核对八道分歧，按题型处理问题后再确定首批题目和验收标准。主句谓语的问题涉及规则口径，建议查同类后重新抽验；其余类别也应处理已点名题。发现并处理这些题之前，不把整批 8,048 道表述为“人工验收通过”。本轮不执行上线。

## 发布确认

结果已在独立分支 `codex/grammar-release-check-20261104` 发布，结果提交为 `6fe2de80b92101605164be9ba5199aa4b389be6c`。重新 fetch 后，12 个交付文件的 Git blob 与字节内容全部相同，完整 tree 一致。随后只补记本段与两份交接，CSV 内容保持不变。

[该结果提交的 CI](https://github.com/KB77GG/studytracker/actions/runs/41852821745) 已完成：test 通过（Python 轻量测试与 Node 拼写队列均成功）；lint 的 Ruff check 未通过，format 步骤跳过，工作流将其设为 advisory，因此整体 CI 为 success。本次只新增审核文件，没有修改 Python 代码，也未清理代码规范检查问题。CI 仅检查仓库测试，语法结论来自上述逐题复核。

本轮未推 main、未部署、未开 PR、未导入生产数据库，小程序未上传或发布。最终分支提交以 Git HEAD 为准。
