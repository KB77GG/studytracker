# TOEFL 真题答案批量回填方案

## 执行命令

```bash
.venv/bin/python scripts/extract_toefl_answer_keys.py \
  --root "/Users/zhouxin/Desktop/新托福资料" \
  --latest 3 \
  --output-dir data/toefl_answer_keys/latest_complete \
  --strict
```

筛选规则：

- 只扫描文件名含“答案”或“参考答案”的 PDF。
- 按路径中的考试日期倒序。
- 至少存在阅读、听力题面或无科目标记的整卷 PDF。
- 路径或文件名出现“缺、仅、待补、后续、部分”即排除。
- 同一套题的相同 PDF 按 SHA-256 去重，优先使用目录层级最浅的副本。

## 输出格式

- `answer_keys.json`：完整提取记录、来源哈希、筛选审计和校验警告。
- `answer_keys.csv`：一行一个答案，包含填词和选择题。
- `choice_map.json`：按 `exam_key / section / block / source_question_no` 查询选项。
- `backfill_template.csv`：只含 A-D 选择题，目标 ID 字段留空，供审核后回填。
- `report.md`：选中样本、排除原因和题数校验结果。

稳定唯一键为：

```text
exam_key + section + block + source_question_no
```

例如：

```text
2026-04-08:listening:extra:q15
```

不能只使用题号。阅读和听力各自有主卷与“加试”，加试都会从 Q1 重新编号。

## 与现有题目数据对齐的风险

1. `entrance_test_question.sequence` 是 section 内局部序号。现有多个 section 都从 1 开始，不能直接对应 PDF 的科目总题号。
2. 现有分档诊断卷会混用不同日期。例如阅读可能来自 4.6，听力来自 2.23，因此不能把一个 `exam_key` 整体绑定到一张业务试卷。
3. 阅读题是节选、改编或重排后的子集。现有 4.8 阅读只有 3 题，原答案 PDF 的阅读选择题为主卷 Q21-Q35，不能按 `sequence=1..3` 直接回填。
4. 听力清单目前只使用主卷 Q1-Q8。已核验 4.8、4.1、3.27 的 24 个答案与 `data/toefl_listening_q1_8/manifest.json` 全部一致，但加试及 Q9-Q32 没有现成目标题。
5. 当前 `app.db` 中分档 TOEFL 卷只有阅读和写作 section；监听迁移脚本存在，但数据库快照中未见对应 listening section。回填前必须确认目标环境是否已执行迁移。
6. 仅凭答案序列不能可靠匹配改编阅读题，因为 A-D 重复度高。阅读应使用题干指纹、选项文本或人工映射，不应使用答案值反推题号。
7. PDF 选项字母必须保持原始顺序。若导入题目时重排过选项，即使题干匹配，原字母也可能失效。
8. `4.6` 听力缺 Q1，`4.5` 听力题面缺 Q4-Q6，`4.11` 目录标记后续补充；这些套题不应自动回填。

推荐回填门槛：

- `target_question_id` 明确且唯一。
- `match_method` 为 `exact_source_id`、`stem_fingerprint` 或人工确认。
- 目标题的四个选项顺序与来源一致。
- `match_status` 从 `unmatched` 改为 `reviewed` 后才允许更新数据库。
