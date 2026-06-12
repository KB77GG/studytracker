# TOEFL 答案提取报告

- 生成时间：2026-06-11T22:19:30+08:00
- 扫描目录：`/Users/zhouxin/Desktop/新托福资料`
- 选中套题：3
- 筛选规则：日期倒序；必须有阅读、听力题面；拒绝路径中带“缺/仅/待补/后续/部分”的套题。

## 选中样本

| 套题 | 答案 PDF | 全部答案 | 选项答案 | 校验 |
|---|---|---:|---:|---|
| 2026-04-08 | `4.8新托福真题/4.8答案.pdf` | 97 | 67 | 通过 |
| 2026-04-01 | `4.1新托福真题/4.1答案.pdf` | 97 | 67 | 通过 |
| 2026-03-27 | `3.27新托福真题/3.27答案.pdf` | 97 | 67 | 通过 |

## 最近未选样本

| 套题 | 答案 PDF | 原因 |
|---|---|---|
| 2026-04-11 | `4.11-国内线下-后续还会补充/04.11_阅读+答案.pdf` | missing companion sections: listening；partial/incomplete marker present |
| 2026-04-06 | `4.6新托福真题/4.6答案.pdf` | missing companion sections: listening；partial/incomplete marker present |
| 2026-04-05 | `4.5新托福真题/4.5答案.pdf` | partial/incomplete marker present |
| 2026-03-30 | `3.30新托福真题/3.30答案.pdf` | partial/incomplete marker present |
| 2026-03-29 | `3.29-国内线下-后续还会补充/3.29 答案.pdf` | partial/incomplete marker present |
| 2026-03-20 | `3.20新托福真题/3.20答案.pdf` | 超过 latest 数量 |
| 2026-03-18 | `3.18新托福真题/3.18答案.pdf` | 超过 latest 数量 |
| 2026-03-17 | `3.17新托福真题/3.17答案.pdf` | 超过 latest 数量 |
| 2026-03-16 | `3.16托福真题/3.16答案.pdf` | 超过 latest 数量 |
| 2026-03-15 | `3.15新托福真题/3.15答案.pdf` | 超过 latest 数量 |
| 2026-03-14 | `3.14新托福真题/参考答案-2026新托福真题.pdf` | 超过 latest 数量 |
| 2026-03-11 | `3.11新托福真题/3.11答案.pdf` | 超过 latest 数量 |

## 回填约束

- 唯一键使用 `exam_key + section + block + source_question_no`。
- `block=extra` 的题号会从 1 重启，不能只用题号关联。
- `section_question_no` 是科目内累计编号，仅作为辅助定位。
- `choice_question_no` 是当前块内仅统计选择题的序号，不等于原题号。
- 业务库回填前必须提供 section/task 到目标 `section_id` 的显式映射。
