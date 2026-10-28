# 语法候选题 v0.2 第十八轮独立核验（Codex）

审核日期：2026-10-28，Asia/Shanghai。**结论：通过本轮轻量核验，以剑桥题为准；AD1 关闭。新增 0 阻断、0 应修、0 建议；机经新确认问题 0 项。**

通过的是第十八轮说明文字修订及其无功能变化的验证。整体题库仍沿用[第十七轮“有条件通过”](GRAMMAR_ITEM_CANDIDATES_V0_2_ROUND17_CODEX_REVIEW.md)的人工验收边界；没有把 27,824 道剑桥自动题重新逐题审定，也没有给出上线许可。既有待决定事项见第 6 节。

## 1. 范围与 Git 事实

- 工作树：`/Users/zhouxin/.codex/worktrees/grammar-item-candidates/studytracker`；分支 `codex/grammar-item-candidates`。
- 开工 HEAD `f7e072b36f6f7845604de7aa558b28214c26120b`，工作树干净。按用户指令 fetch 后 ff-only 到 `8c49cf978bc3a17810554e487416a08e8123ebe5`；没有普通 merge、rebase、改写历史或合并 main。
- 被审范围 `f7e072b..8c49cf9` 恰为 7 文件，92 行增加、12 行删除：templates.py、reporting.py、两份报告，以及 FIXES / CODEX_HANDOFF / WORKLOG 三份文档。
- 阅读解析、static、raw、修订表、测试、api、app.py、models.py、miniprogram、.github/workflows 均无变化。
- 本审核只新增本报告、更新两份交接文件。生成与渲染在仓库外完整快照运行，未覆盖任何被审核文件。
- 另一树 `/Users/zhouxin/Desktop/studytracker` 仍是 main@6ded77d24586327ad94e151e172ae4811b4a2eed，behind 87；7 个既有 modified、22 个 untracked 入口未动。仅借用其中的 venv 执行 Ruff。

## 2. 用户六项清单逐项结果

| 项目 | 结果 | 独立证据与实际命令 |
|---|---|---|
| 1 改动范围 | 通过 | `git diff --stat f7e072b..8c49cf9` 与 `git diff --name-only f7e072b..8c49cf9`；7 文件精确匹配白名单。AST 比较：templates 仅 prepositional_target 的 docstring 不同；reporting 仅一个字符串常量不同，其他 AST 完全相同。 |
| 2 AD1 | 关闭 | 独立阅读 templates.py:691、reporting.py:285、FIXES.md:1033 / 1089；三处文字均明确“送复核”不等于“类别错误”，详见第 3 节。 |
| 3 双生成与对照 | 通过 | 完整 8c49 快照中用 G 连续两次 `scripts/generate_grammar_candidates.py --seed 20261018`。50,241 候选逐字段及字节均等于 29701e7 的本机生成结果；两次 4 交付文件相同。JSONL/XLSX 与提交一致，两报告仅 Python 版本差。报告新旧只改 counting_notes[11]，详见第 4 节。 |
| 4 测试 / Ruff / 图谱 | 通过 | G 四模块 155 通过；全新仅安装 Flask 及其依赖的环境按 ci.yml 全部 13 模块运行 223 项＝222 通过＋1 按设计跳过；额外 Node 检查成功。两 Python 文件 Ruff check / format --check 通过；G 渲染图谱后与提交逐字节一致。精确命令见第 5 节。 |
| 5 可选模拟导入 | 本轮未重跑 | 阅读解析、词汇表、模型、导入代码均未变；本轮明确为可选，按轻量范围省略。第十七轮已实测 236 updated / 81 skipped / 0 failed；这是历史证据，不冒充本轮实测，也不外推为现生产库结果。 |
| 6 待用户决定事项 | 主要五类准确，补明既有范围 | FIXES 第十八轮列出 10⁹、盲审、T1 答案规则、非并列 T2 多目标和上线。第 3 项不是所有教学口径的穷尽表，应连同此前披露的 T6 单位、介词化分词及连字符动词理解；本报告第 6 节明确列出。这些是既有遗留，不另计新问题。 |

## 3. AD1 与问题分级

**AD1 已关闭。** 新说明保留通用复核规则，同时承认命中里有复合连词、介词结构和可按非限定从句分析的结构。`prepositional_target` 是解析信号，不能直接决定语法类别或宣布原标注错误。项目暂按传统教学口径区分限定从句与短语 / 非谓语，并将边界问题留给教师判断，这与本项目候选题的用途一致。

FIXES 第十七轮对 `after listening to and observing Alex` 补充“也有非限定从句的分析，只送复核，不判定类别错误”，合理地限定了前面的“介词＋动名词”表述；它并未撤销复核或改变题目。`by the time` / `in case` 等复合连词的合法性也不再被一概否定。

剑桥本轮新增：**阻断 0、应修 0、建议 0**。本次没有新增代码、数据或措辞缺陷。下面的旧事项不因 AD1 关闭而关闭：非并列 T2 多目标、教学口径、机器 auto 与人工验收的区别。它们已在第十七轮报告中披露，不重复立项。

### 机经（暂缓）

本轮新确认 0 项。规则和题池完全未变，既有机经暂缓事项继续保留；没有把“未重新抽查”解释为旧问题消失。

## 4. 可复现结果、环境与 SHA-256

本机证据目录 O：`/Users/zhouxin/.codex/audits/grammar-v02-round18-20261028`，仅本机可见，含完整 8c49 快照、两次产物、verify.py、生成/测试日志与比较结果。旧基线为第十七轮审计目录中的完整 29701e7 快照及当时生成的全量候选池；本轮重新以 Git blob 核对了该快照的 **2,862 个文件**，仅两份带本机 Python 版本的生成报告按环境差异单独比较。没有依赖 Claude 的候选计数或仅凭聊天记忆认定相同。

两次均在 Mac **27.0.1 arm64**，Python **3.13.3**、spaCy **3.8.16**、en_core_web_trf **3.8.0**、torch **2.14.1 CPU**、openpyxl **3.1.5**，seed **20261018**。本轮复用同模型、同语料的解析缓存，重新运行整个出题/抽样/报告流程两次；没有声称重新解析全库。Ruff **0.15.21**。

| 文件 | 第一次 SHA-256 | 第二次 SHA-256 |
|---|---|---|
| `review_batch_v0_2.jsonl` | `782ecd3c5b34ed8ebb38e7288ce6994722ad9aa4b866fe34c39eb8c10bf604e4` | `782ecd3c5b34ed8ebb38e7288ce6994722ad9aa4b866fe34c39eb8c10bf604e4` |
| `review_batch_v0_2.xlsx` | `3a36f72b67d8516e9fe54eb43285ff68c99e4e4177982338537248eb8672e05d` | `3a36f72b67d8516e9fe54eb43285ff68c99e4e4177982338537248eb8672e05d` |
| `generation_report_v0_2.json` | `4c88bd021bfd041e18e6611a7677f89a6ceefa345a3603fc3139683e93381ebc` | `4c88bd021bfd041e18e6611a7677f89a6ceefa345a3603fc3139683e93381ebc` |
| `generation_report_v0_2.md` | `3eeb87bdfe544db4e6610fab64910e0dfc63996b6e13f9163832aae5efe017c6` | `3eeb87bdfe544db4e6610fab64910e0dfc63996b6e13f9163832aae5efe017c6` |

提交版 SHA-256 全部与用户给出的值一致：

| 文件 | 提交版 SHA-256 |
|---|---|
| `review_batch_v0_2.jsonl` | `782ecd3c5b34ed8ebb38e7288ce6994722ad9aa4b866fe34c39eb8c10bf604e4` |
| `review_batch_v0_2.xlsx` | `3a36f72b67d8516e9fe54eb43285ff68c99e4e4177982338537248eb8672e05d` |
| `generation_report_v0_2.json` | `ed9185402c422edd419704ad60ba699c51830be67123954b2e343d064d1419d5` |
| `generation_report_v0_2.md` | `ff8266ac18812bdd38ad16975a6218ae5a9cbe349ef3a402eb285e3f5701a7c2` |

比较口径分开核对：

- **本机第一次 vs 第二次**：四文件逐字节一致；全量候选也逐字节一致。
- **本机第十八轮 vs 提交版第十八轮**：JSONL/XLSX 逐字节一致；两份报告各只有 Python 版本一行 `3.11.15 → 3.13.3` 的差异，JSON 唯一路径为 `/environment/python`。
- **提交版第十八轮 vs 提交版 29701e7**：两份报告各只变计数说明一行，JSON 唯一路径为 `/counting_notes/11`。本机第十八轮 vs 本机第十七轮也各只有该行变化。
- **全量候选池**：50,241 题，题号、题干、答案、选项、干扰项、status、reasons、evidence 等所有字段 0 处变化；JSONL SHA-256 为 `6424292c8b5c5f3e8aabf4ff5d28199bd97a31ec5b48ee1b3862200e36d9832a`，两次及旧基线相同。
- auto 仍 **40,298**，其中剑桥 **27,824**；T1–T6 分别 **5821 / 4678 / 11401 / 395 / 5364 / 12639**。回归 13×6、7 项整句过滤及其他报告字段全部不变。
- 题目内容没有变化，因此按用户要求**不做新一轮 120 道随机抽查**。本轮没有用测试通过替代新的题目人工验收。

## 5. 实际命令与测试结果

以下变量仅是命令说明，不替换 HOME / CODEX_HOME 等系统变量：

```bash
R=/Users/zhouxin/.codex/worktrees/grammar-item-candidates/studytracker
O=/Users/zhouxin/.codex/audits/grammar-v02-round18-20261028
G="$R/.venv-grammar-tools/bin/python"
P=/Users/zhouxin/Desktop/studytracker/.venv/bin/python
F="$O/flask-only/bin/python"

# 在任务树执行，工作树干净后按指定提交快进
git status --short --branch
git log -5 --oneline
git fetch origin claude/word-memorization-system-eval-55v2y5
git merge --ff-only 8c49cf978bc3a17810554e487416a08e8123ebe5
git diff --stat f7e072b..8c49cf9
git diff --name-only f7e072b..8c49cf9
git diff f7e072b..8c49cf9 -- scripts/grammar_items/templates.py scripts/grammar_items/reporting.py

# git archive 完整快照解包到 O/source，复制匹配缓存；该目录内顺序执行两次
"$G" scripts/generate_grammar_candidates.py --seed 20261018
"$G" scripts/generate_grammar_candidates.py --seed 20261018
# 每次保存四文件和完整候选池；本机辅助脚本为 O/generate.py

# 以下专项、Ruff 和 CI 轻量测试均以 R 为 cwd
"$G" -m unittest tests.test_grammar_item_candidates tests.test_reading_jijing_text_fixes tests.test_reading_study_glossary tests.test_grammar_graph_draft -v
"$P" -m ruff check --config 'extend-exclude=[]' scripts/grammar_items/templates.py scripts/grammar_items/reporting.py
"$P" -m ruff format --check --config 'extend-exclude=[]' scripts/grammar_items/templates.py scripts/grammar_items/reporting.py
"$G" -m venv "$O/flask-only"
"$F" -m pip install --cert /etc/ssl/cert.pem Flask
"$F" -m pip list
"$F" -m unittest \
  tests.test_miniprogram_guest_access tests.test_miniprogram_dictation_grouping \
  tests.test_inventory_toefl_materials tests.test_organize_toefl_materials \
  tests.test_extract_toefl_answer_keys tests.test_map_toefl_answers_to_practice_docs \
  tests.test_import_toefl_official_reading tests.test_reading_vocab_grading \
  tests.test_stats_utils tests.test_grammar_graph_draft tests.test_grammar_item_candidates \
  tests.test_reading_jijing_text_fixes tests.test_reading_study_glossary -v
/Users/zhouxin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node tests/test_dictation_spell_queue.js

# 在 O/source 运行，不覆盖被审核图谱文件
"$G" scripts/render_grammar_graph_review.py
# 辅助 verify.py 做 AST、Git blob、全池字段、SHA、报告单行和图谱字节比较
"$G" "$O/verify.py"
```

结果：专项 **155 通过**；Flask-only **223 运行、222 通过、1 跳过**。唯一跳过项 `test_xlsx_blindness_dropdowns_and_byte_reproducibility`，原因 `openpyxl is optional in CI`；该测试已在 G 环境的 155 项中通过。Flask 环境仅有 Flask 3.1.3、其依赖与 pip，无 openpyxl/spaCy/SQLAlchemy 等项目依赖。Node exit 0，Ruff check / format 均 exit 0（2 文件格式不需变动），图谱重渲染逐字节一致。

辅助核验脚本调试时修正了 Git 非 ASCII 路径转义、对 XLSX 误作 UTF-8 差分、候选字段嵌套层级三处探针错误；只改了仓库外脚本，最终完整 verify.py 成功。它们不是被审代码/测试失败，也没有跳过相关比较。无新增业务测试，本轮没有可要求在旧代码上失败的新行为断言。

## 6. 上线前仍需用户决定

FIXES 第十八轮的五类主要事项准确。第 3 项标题仅写 T1，不穷尽此前报告保留的教学口径；下面明确其延伸范围，属于**既有遗留的归并**，不重复算新问题。

| 事项 | 需要明确的决定与当前边界 |
|---|---|
| 恢复 A-03 的 10⁹ | 授权修改 `static/reading_tests/ielts11_test1_reading.json` 及 `data/reading_study/ielts11_test1_p1.json` 的 sentence / structure / 难点等对应内容。正文优先 `10⁹`，说明补“10 的 9 次方，即十亿”；仅在显示不稳定时用 `10^9`。按第十七轮 §8 同步引用、重解析、生成、导入与客户端显示验证，并防止今后 raw 重建回流 109。在决定前维持该句 needs_review。 |
| 教师盲审范围与验收方式 | 明确是否只优先剑桥、审哪一批/哪些题型、自动题与待复核题怎样分开验收、接受标准及签收人。固定题号/版本；不能把 auto_pass 当成老师已审。 |
| 答案单位及教学分类口径 | T1 系表判分中心、小品词、被动分词，连同既有**连字符动词**、T6 的完整单位口径一起决定；另明确 according to、given＋名词短语、Seeing that 等在 T3/T6 的分类。AD1 只是说明现有传统口径及复核边界，未替用户解决这些争议。若暂不改内容，应明确保留复核、人工确认或排除范围。 |
| 非并列 T2 多目标 | 第十七轮点名 `ielts15_test3_p3 G-02 / gi_v02_18543efdcecd` 等，选择题干定位、接受多个有效答案或统一送复核。当前不能作为只有一个机器标准答案的题直接判错学生；第十二轮并列题干修复不覆盖此类。 |
| 发布范围及上线授权 | 明确先发布哪些经老师确认的剑桥题、needs_review 是否继续隔离、已披露技术边界是否接受，然后另行授权与当前 main 整合、验证、部署及导入。基于旧 main 的 236/81/0 不能当作当前生产库必然变更数。机经继续按用户决定暂缓。 |

`ambiguous()` 子串查重、插入语隔开的并列目标、W5、V4/V5 等已披露保守规则边界没有被本轮修复。它们不必都在说明文字核验中重新立项，但发布范围和教师验收应明确如何处理；本轮也未判断生产当前状态。

## 7. CI、交接与限制

- 被审 **8c49cf9** 的[精确提交 CI 40625571558](https://github.com/KB77GG/studytracker/actions/runs/40625571558)已读取：整体 success；**test 成功**，223 项运行/1 跳过、Node 成功；**lint advisory 失败**，112 条诊断与第十七轮末次提交逐条相同，format 步骤因上一步失败跳过。这不影响本轮两个改动 Python 文件本机 Ruff 双检查通过。
- 本审核正文及两份交接待普通 commit/push 到 `codex/grammar-item-candidates`，不带 skip-ci；推送后会核对该提交自己的 CI，并补记。最终提交与最终 CI 在补记/最终回复报告，不以被审提交 CI 代替。
- 强制检查均完成，无无法执行项。可选 SQLite 导入未重跑；不重复 120 题抽查；使用匹配解析缓存。以上均符合本轮轻量要求，不把上轮结果冒充本轮新测。
- O 中脚本/完整产物仅本机可见；正式审核报告及交接在获授权的任务分支提交推送后可跨电脑获取。没有改被审代码/数据、推 main、开 PR、后端部署、生产服务器/数据库操作、小程序上传/提审/发布或调用大模型 API。
- 下一位先读本报告的关闭范围与第 6 节，按用户决定安排教师验收及后续内容修改；“AD1 关闭”不自动扩大写入/发布授权。
