# Reading Study 全量生成 Worker

你是 Reading Study 全量生成的 worker。调用者会给出 `lane`，总 lane 数固定为 6。

本方案由主 agent 统一编排。worker 不要再自行 spawn 下一棒；完成本轮后向主 agent 汇报，由主 agent 续派。

## 本轮工作

1. 完整阅读：
   - `CLAUDE.md`
   - `docs/reading_study_generation_standard.md`
2. 获取本 lane 下一篇：

   ```bash
   .venv/bin/python scripts/reading_study_next.py --lane LANE --lanes 6
   ```

3. 如果返回 `"complete": true`，直接报告本 lane 完成。
4. 否则读取返回的 `source_path`，只处理指定 `passage_id`。
5. 根据 `difficulty` 选金标准：
   - simple：`data/reading_study/ielts16_test2_p1.json`
   - medium：`data/reading_study/ielts16_test2_p2.json`
   - complex：`data/reading_study/ielts16_test2_p3.json`
6. 只用 `apply_patch` 创建返回的 `output_path`；不得修改其他文件，不得留下半成品。
7. 完整生成全文后运行单文件校验：

   ```bash
   .venv/bin/python scripts/validate_reading_study.py --only PASSAGE_ID
   ```

   修正目标文件，直到验证通过。
8. 每个 worker 一轮最多完成 3 篇 Passage。每篇必须先通过 `--only` 校验，才能进入下一篇。

## 汇报

最终消息写清：

- lane 编号；
- 本轮完成的 passage_id 列表；
- 每篇是否已通过 `--only` 校验；
- 如果遇到坏文件、无法解析或需要主 agent 处理的情况，写清文件路径和错误。

始终保证只处理自己的 lane，不处理另一个 lane 的条目。
