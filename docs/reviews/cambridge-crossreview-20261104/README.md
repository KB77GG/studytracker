# 剑桥语法候选题交叉复核：6,232 题

用户上传的第二十轮待复核题已全部逐题复核。本目录保存这次交回的判定，供 Claude 按“题目编号”对照原题；未修改出题器、原句、机器答案或生产数据。

## 文件与数量

- `cambridge_all_reviewed.csv`：全部 6,232 题的合并判定。
- `cambridge_001_reviewed.csv` 至 `cambridge_063_reviewed.csv`：63 个批次；前 62 批每批 100 题，第 63 批 32 题。
- `cambridge_63_batches_reviewed.zip`：上述 64 份 CSV 与逐批统计说明，共 65 个文件；与此前本机交付的 ZIP 字节相同。
- `复核统计与文件说明.txt`：各批判定数量。
- `source_manifest.json`：原始附件文件名、上传顺序、SHA-256、逐批题号；用于核对版本和合并顺序。
- `export_verification.json`：导出核验记录。
- `SHA256SUMS`：本目录其他文件的 SHA-256。

| 判定 | 题数 |
|---|---:|
| 正确 | 2,457 |
| 答案错 | 1,374 |
| 题目有歧义 | 2,305 |
| 句子不适合出题 | 96 |
| 合计 | 6,232 |

## 给 Claude 的接手说明

1. 读取合并 CSV，并按“题目编号”连接第二十轮的原题；不要按行号连接。合并表依照附件上传顺序，批号未按数字排序；各批内部保持原始顺序。
2. 四列固定为 `题目编号,判定,正确答案应为,说明`，UTF-8 含 BOM。说明最多 40 字。“正确答案应为”中的省略号仅表示不连续动词单位中省去的主语或插入语，不是供直接替换原句的文字。
3. 对“答案错”“题目有歧义”“句子不适合出题”，结合题干、标注范围、判分说明和干扰项复核分歧；后续列出改答案、改题干或剔除的处理建议。这批 CSV 本身不代表已修改题库或已获上线授权。
4. 本轮优先处理剑桥题。机经未复核，也不在这些文件中。

可只读取本分支的文件，不必合并代码：

```sh
git fetch origin codex/grammar-crossreview-20261104
git show origin/codex/grammar-crossreview-20261104:docs/reviews/cambridge-crossreview-20261104/README.md
git show origin/codex/grammar-crossreview-20261104:docs/reviews/cambridge-crossreview-20261104/cambridge_all_reviewed.csv > /tmp/cambridge_all_reviewed.csv
```

## 核验与版本

- 发布基线：`claude/word-memorization-system-eval-55v2y5` 的第二十轮提交 `93ad42e396b2d5e867a3de82534d598eaa2baccb`。
- 发布分支：`codex/grammar-crossreview-20261104`。只新增本目录和更新交接文件；未合 main，未部署，未导入生产题库。
- 63 个原始附件 SHA 未变；6,232 个唯一题号，遗漏 0、重复 0；逐批行序和合并行序通过核验；所有 CSV 回读等于已复核判定；ZIP 完整性及逐字节检查通过。
- 合并 CSV SHA-256：`2fcb253f8d331ce1d3db15234bff6b29bd0c9bb08d6a1f16b935bd5aadb80e6d`。
- ZIP SHA-256：`ee5194c62f6aa230f4c4de7e11a886a48c08c7b775fc37b918b6f2da7c1c3920`。
- 在本目录执行 `shasum -a 256 -c SHA256SUMS` 可核验全部交付文件。本次仅发布已有内容，未重做判定；未运行应用测试来冒充语法内容核验。
