# 剑桥首批上线题：验收抽查（593 道）

- 首批上线题：8,048 道，清单在 `data/grammar_items/release_v0_2_cambridge_ids.csv`，统计在 `data/grammar_items/release_v0_2_cambridge.md`。
- 抽查题：本目录 `release_check_001.csv` 至 `release_check_006.csv`，共 593 道：
  - 主句谓语、从句边界、从句类型、完整主语、动词身份各 100 道；
  - 状语关系 93 道（全部）。
- 复核说明和输出格式见 `docs/GRAMMAR_RELEASE_CHECK_PROMPT.md`。结果请按“题目编号,判定,正确答案应为,说明”交回本目录（例如 `release_check_all_reviewed.csv`）。
- 由 `scripts/select_grammar_release.py`（种子 20261104）从第二十轮题库生成，可复现。`SHA256SUMS` 是本目录 CSV 的校验和。
