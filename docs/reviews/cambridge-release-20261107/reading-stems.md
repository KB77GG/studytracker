# 剑桥阅读题干补查（2026-11-07）

工作树：`/private/tmp/studytracker-cambridge-fix-20261107`；分支 `codex/cambridge-explanations-fix-20261107`；审计生产基线 `40cd8225db1b0a5da188b1dd99d4521dc5853328`。本文及配套脚本是本机审计证据，发布状态由主任务的 `docs/CODEX_HANDOFF.md` 记录。本子任务未 commit、push 或 deploy。

## 范围与方法

遍历剑 4–21 的 72 套、216 篇、613 题组、2880 题。对照本机 `data/idictation_reading/raw.json` 中的原始题组、`collect`、表格、题号及 `sub_essay_code`，检查题号完整性、题目 ID 唯一性、占位符归属、本地题图、标题匹配段号及词数限制候选。原始文件 SHA256 是 `0487d669ad899761572d5361cf8dd992cd69d05d8763c5474db55e61a1f28b13`。

该范围覆盖结构及源字段比较，不代表 2880 题全部完成人工语义终审。实际 DOM/输入控件交互及听力检查由并行任务独立复核。

复现命令（默认不改题库）：

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/zhouxin/Desktop/studytracker/.venv/bin/python docs/reviews/cambridge-release-20261107/reading-stems.py --raw /Users/zhouxin/Desktop/studytracker/data/idictation_reading/raw.json
```

## 已确认并修复：标题匹配丢失目标段号

35 组、200 题的原始题目具有明确的 `sub_essay_code`，但构建器没有保留它，发布题干为空。旧前端靠题目顺序推算段号，没有跳过例题；对另一些指令措辞则没有生成题干。按源段码核对，200 题中 42 题显示错误段号、40 题为空，118 题恰好显示正确。

例如剑 10 T1 Q19–21 应为 G/H/I，旧页面显示 F/G/H；剑 5 T3 Q14–17 应为 B/D/E/F；剑 7 T2 Q27–30 应为 B/C/E/F。剑 6 T3 使用 Key Point 命名，现标题同时给出 `Paragraph B (Key Point Two)` 等对应关系。

修复保留原始显式段码，在构建器和校正清单中形成明确题干；已发布和旧专项快照通过同一清单修复。前端不再按索引猜段号。200 题的答案、选项、ID、题号及评分配置均未改动。独立测试的 `HEADING_TARGETS` 列出了全部 35 组源段码，而不是直接以清单内容作为预期。

## 已确认：一题两个物理空

以下五题的原始题面重复同一题 ID，以 `and` 连接两个空。旧页面只给第一个空提供输入控件，第二个空显示不可填写下划线；直接填写原纸面每空答案会和单题合并答案存储不一致。

| 试卷 | 题号 | 既有单题合并答案 |
| --- | --- | --- |
| 剑 4 T1 | 21 | bowhead and humpback |
| 剑 7 T2 | 26 | farmers and consumers |
| 剑 9 T3 | 33 | Jupiter and Saturn |
| 剑 9 T3 | 35 | sensors and circuits |
| 剑 10 T2 | 23 | books and activities |

已移交展示任务实现双输入与原有答案串的往返转换，仍为一题一分，不修改答案或答卷结构。发布前需以该任务的全库实际渲染报告确认完成状态。

## 已修复：六组说明及四张正文图

六组原始说明文字有明确笔误：

- 剑 14 T2 P3 Q38–40：`Reading Passage 1` 应为 3。
- 剑 9 T4 P1 Q1–6：`Reading Passage 2` 应为 1。
- 剑 12 T5 P1 Q1–5、剑 13 T2 P1 Q10–13：`Reading Passage 3` 应为 1。
- 剑 5 T3 P3 Q27–31：`Reading Passage 1` 应为 3。
- 剑 10 T3 P1 Q1–4：`paragraphs S -E` 应为 B–E；罗马数字范围 `i-v ii` 应为 i–viii（现有选项 I–VIII，例题段 A 不在 Q1–4 中）。

原文内的四张图也被构建器遗漏，已下载并逐张目视核查：剑 4 T1 P3 的 Fig.1（圆内运动线）和 Fig.2（圆/方词义调查表），剑 7 T4 P3 的 Table 1（噪声与校对错误数），剑 10 T3 P3 的太平洋地图。前两篇正文明确引用相应图表，因此不是仅凭字段非空推断缺图。

六组 `desc` 已经窄修。四图以原始字节写入本地静态目录，SHA256、来源 URL、位置记录在 `reading-stems-context.json`；不依赖第三方图床运行。构建器保留 `paragraph_img`，清单为旧快照补入 `content.images`，模板按原有零起点段索引插入图片，导语不占用段索引。四图均在训练和模拟模式下验证出现一次、位置正确。

复现恢复操作（仅这六组说明及四图；图片本地已存在时不下载）：

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/zhouxin/Desktop/studytracker/.venv/bin/python docs/reviews/cambridge-release-20261107/reading-stems-context.py --raw /Users/zhouxin/Desktop/studytracker/data/idictation_reading/raw.json
```

## 未发现及候选排除

- 72 套均为连续 1–40 题，无缺题或同套重复 ID；所有结构占位符都归属于当前题组且每题可定位；既有题组图的本地文件均存在。
- 题组可见字段相对原始转换仅有上述六处已审核的 `desc` 修正，无未审核差异。
- 38 组阅读多选题主问句都有显示来源：37 组在 `group.title`，剑 21 T2 在 `collect_option.title`，该字段由选项区显示。不能因各子题 `title` 为空就判定漏题干。
- 自动词数扫描五个候选中，两项为“一个词及/或一个数字”的正常答案（`4 sides`、`10 times`）；其余三项是上表的双空问题。未据此改动原始词数限制。
- 另记录 85 篇副标题、23 篇词汇注释、19 篇主图及一篇 Key Point 小标题没有完整传到当前正文显示。这是原文上下文完整性待处理项，不自动计作 128 道错误题，也未声称它们都影响答案。

## 验证

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/zhouxin/Desktop/studytracker/.venv/bin/python -m unittest tests.test_cambridge_reading_stems tests.test_cambridge_reading_corrections -v
node --test tests/test_cambridge_reading_introduction.js tests/test_cambridge_reading_figures.js
node docs/reviews/cambridge-release-20261107/reading-stems-render.js
/Users/zhouxin/Desktop/studytracker/.venv/bin/ruff check scripts/build_reading_test_practice.py tests/test_cambridge_reading_stems.py docs/reviews/cambridge-release-20261107/reading-stems.py --target-version py310
PYTHONDONTWRITEBYTECODE=1 /Users/zhouxin/Desktop/studytracker/.venv/bin/python docs/reviews/cambridge-fix-20261107/reading_verify.py --raw /Users/zhouxin/Desktop/studytracker/data/idictation_reading/raw.json --output docs/reviews/cambridge-release-20261107/reading-rebuild.json
```

当前结果：16 个 Python 测试通过；4 个 Node 测试通过；Ruff 通过。额外以实际生产基线模板函数及基线题库执行 200 个标题题，确认旧版 42 错段、40 空题干、118 正确；新版模板执行 200/200 与源段码一致（`reading-stems-render.json`）。全部 72 套从 raw 内存重建后校正内容一致，2880 题的评分及未审核字段与基线一致，A–Z 原文完全保留（`reading-rebuild.json`）。

本轮阅读累计涉及 39 个静态试卷 JSON、205 个不同题目（新增 200 个标题，其中一题与先前解析校正重叠）、六组说明、五篇导语及三篇原文的四张图片。最终跨科范围校验与双空交互结果由主任务统一维护。
