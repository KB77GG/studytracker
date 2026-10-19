# 语法候选题 v0.2 — Codex 独立审核记录

审核日期：2026-10-18 至 2026-10-19（Mac，Asia/Shanghai）。审核方：Codex；本轮未参与 Claude 的 v0.2 实现或自查，没有调用大模型 API，也没有委派审核。

## 结论：不通过

**1 项阻断、4 项应修、4 项建议。** 主要阻断是 B3“完整动词单位”仍被原标注范围截断，已确认至少 9 道自动通过的 T6 题漏掉助动词、否定词、不定式 to 或小品词。测试和跨机器复现通过，不能据此认定题目质量通过。

另有抽样中的 OCR 坏句、新标注的从句边界与同位语范围问题，以及 B4 报告缺项。新增标注的两处教学解释、单引号识别和存量 Ruff 问题列为建议。已披露的 51 句保守过滤、G-08 误伤、跨从句引语不配对不重复计作新发现。

30 题抽样：29 题答案与目标范围正确，1 题“句子不适合出题”。这只是小样本结果，不能替代老师的 360 题审核，也不代表全池错误率。建议先处理阻断和应修项，再重新生成并复核；本轮没有修复任何被审核文件。

## 审核对象、边界与现场

- 审核范围：`e970dd6..e8019c2`；实现提交 `c3c1eef`、`67fb9cf`，文档提交 `e8019c2`。先执行用户指定的 fetch 和 fast-forward，确认 HEAD 为 **`e8019c2ddcb23fa9e585d48bd824f31b0cd3e1b9`**。
- 执行工作树：`/Users/zhouxin/.codex/worktrees/grammar-item-candidates/studytracker`，分支 `codex/grammar-item-candidates`。审核开始、生成结束时工作树均干净；随后只写本记录、`docs/CODEX_HANDOFF.md`、`docs/WORKLOG.md`。
- 原项目 `/Users/zhouxin/Desktop/studytracker` 仍为 `main@6ded77d24586327ad94e151e172ae4811b4a2eed`，7 modified / 22 untracked 入口保留，没有在那里切分支、合并或改文件。
- 先读目录链 AGENTS、CLAUDE、交接最新节、WORKLOG 顶部，再读两版计划、自查与拆句记录；以实际 Git、原始 JSON、独立运行结果为依据。
- 临时审核目录：`/tmp/studytracker-grammar-v02-codex-audit.R7RDty`，下文简称 `$AUDIT`；Mac 的 `/tmp` 解析为 `/private/tmp`。临时脚本、日志、SQLite、解析缓存和图片只在本机，不是交付源码。
- 为同时满足“从零生成”和“不得修改被审核文件”，将 **e8019c2 的原样代码与输入**用 `git archive` 导出到 `$AUDIT/source` 后运行，没有改生成器。首次不存在 `parse_cache_v0_2.jsonl`，第二次使用第一次的缓存。导出副本产生文件，原工作树四份交付保持原字节。
- 没有访问生产服务器/生产数据库，没有 main push、部署、PR、小程序上传/提审/发布；只在临时 SQLite 中执行模拟导入。

## 15 项检查结果

| # | 检查与实际结果 | 命令/证据 |
|---:|---|---|
| 1 | 范围通过：69 files，6816 insertions / 4131 deletions；25 个阅读标注文件、21 个机经 static 文件、修订表、出题器/构建脚本/测试、CI 一行、交付和文档。未发现范围外业务改动。 | `git diff --stat e970dd6..e8019c2`；逐类审查 diff |
| 2 | 保护范围通过：raw、官方剑雅 static、api、models.py、app.py、miniprogram 全部无差异。 | 下节 protected diff，输出空 |
| 3 | 33 条逐条通过：根据前后文判断开/闭引号与叙述归属，详见修订表；29 处句界空格及 4 处授权修订，没有其他文本替换。 | `$AUDIT/audit_data.py` + 独立人工阅读 |
| 4 | `--check` 输出 **0 fix(es) not yet applied**，exit 0；21 个 static 文件仅 28 处段落 text 行变化，其他字段完全相同。 | 修订脚本；逐文件 `git diff --unified=0` |
| 5 | 全部 **171 篇**机经用真实构建函数在内存重建，段落对象（含原始文字）与 static 完全一致；未下载图片。 | `audit_data.py` 调 `build_tests(raw, 'jijing')`，仅将 `localize_image` 替成返回空串的函数 |
| 6 | 28→59，新增 31；ID 后缀、连续 sentence_index、paragraph_label 均正确；其余 **997** 个句子对象除 index 数字外字节相同。validator **317 valid / 0 errors**。完整段落字面拼接有基线空白差异，不能声称全段逐字相等，详见下文。 | 原 JSON 对象字节比较；validator；paragraph-diffs.json |
| 7 | 临时库先导入基线：created=317；再导入当前：**updated=25 / skipped=292 / failed=0 / created=0 / ignored=0**。 | `import_check.py`，明确 sqlite 临时 URI，并断言 engine.url |
| 8 | 59 句全部逐句阅读 translation、structure、difficult_points、expressions；翻译未发现实质错译，表达合适，无过时“缺空格所以合并”说明。发现 F3/F4、建议 S2/S3；逐句覆盖见表。 | 直接读 59 条标注及其前后句；非仅复核拆句说明 |
| 9 | B1 两个匹配正则、缩写排除正则和切片范围逐字对照一致；B2 三模板条件和降级一致；B3 有阻断 F1；B4 有应修 F5。高亮连续合并逻辑正确。 | checks.py、templates.py、review_batch.py、reporting.py 的 diff 与全量池探针 |
| 10 | 引号补回有价值，当前语料未发现越界补词；377 次范围变化均在许可边界内，其中 376 次仅补标点，1 次补回原标注中的 ` theories'`，语义正确。单引号分类器存在合成反例，见 S1；建议保留有界修复思路并增强识别。 | 包装 `close_quotes` 记录全部调用，不改模块文件；`verify_final.py` |
| 11 | 指定三套 **57 passed**；Flask-only CI 列表 **125 ran / 124 passed / 1 skipped**，Node exit 0。Ruff **未全通过**：构建脚本存量 UP017 两处、format 一处；其余 8 个改动 Python 文件通过。 | 完整命令见下节；S4 区分基线 |
| 12 | Mac 从零全量生成成功；JSONL/XLSX 与提交版逐字节相同，两份报告仅 Python 版本行不同；第二次四文件与第一次均逐字节一致。 | 四文件双 SHA-256 见后文 |
| 13 | v0.2 B5 的四行要求、v0.1 第 11 节全部九例符合预期；拆句 G-04、G-04b 分别核对。 | 报告 regression_cases 与全量池；结果表见后文 |
| 14 | 种子 **20261019**；每表 5 道 auto_pass，共 30，结果 29 正确 / 1 不适合；另抽 15 道 possible_relative_adverb：4 确定定语、1 两可、10 状语。 | `samples.py`；明细及方法见后文 |
| 15 | 7 sheets，六题型各 60 数据行（含表头 max_row=61）；360 行逐格与 JSONL teacher_row 核对一致；无池状态泄露；H2:H61 四项下拉；冻结 D2。七表均渲染查看。显示层正确，输入动词单位仍可能不全（F1）。 | openpyxl 只读检查；artifact-tool 只读导入/渲染，未回写 xlsx |

### 第 6 项的字面拼接限定

28 个原单元应用修订后，每一组新句用单空格拼回都 **逐字等于该修复后原单元**。25 个改动文件中，完整段落拼接与 static 的逐字比较仍有 7 处差异，均为基线已存在的换行/重复空白；统一空白后完全相同：

`reading_jijing_46_test_84_p1` B、D；`reading_jijing_53_test_83_p2` A；`reading_jijing_78_test_102_p2` E；`reading_jijing_88_test_98_p3` B、E、F。

其中只有第一处 B 是本次 28 个修订段落之一，例如 static 保留 `yet\nMasterCard`，句子拼接是 `yet MasterCard`。validator 的通过不代表字面相同。本轮未改这些空白，也没有用标准化结果冒充严格比较通过。此为验收文字与基线的既有差异，不是新增回归。

## 实际运行命令与审核方法

以下命令工作目录均为执行工作树，临时输出统一写入 `$AUDIT`。环境变量名称未覆盖 HOME/CODEX_HOME 等系统变量。

```sh
git fetch origin claude/word-memorization-system-eval-55v2y5
git merge --ff-only origin/claude/word-memorization-system-eval-55v2y5
git rev-parse HEAD
git status --short --branch
git log -5 --oneline
git diff --stat e970dd6..e8019c2
git diff e970dd6..e8019c2 -- data/idictation_reading_jijing/raw.json static/reading_tests/ api/ models.py app.py miniprogram/

AUDIT=/tmp/studytracker-grammar-v02-codex-audit.R7RDty
.venv-grammar-tools/bin/python scripts/reading_jijing_text_fixes.py --check
.venv-grammar-tools/bin/python scripts/validate_reading_study.py
.venv-grammar-tools/bin/python -m unittest tests.test_grammar_item_candidates tests.test_reading_jijing_text_fixes tests.test_grammar_graph_draft -v
.venv-grammar-tools/bin/python "$AUDIT/audit_data.py"
git archive e970dd6 data/reading_study 'static/reading_tests/*.json' 'static/reading_jijing/*.json' | tar -x -C "$AUDIT/baseline"
/Users/zhouxin/Desktop/studytracker/.venv/bin/python "$AUDIT/import_check.py"

.venv-grammar-tools/bin/python -m venv "$AUDIT/flask-only"
"$AUDIT/flask-only/bin/python" -m pip install --cert /etc/ssl/cert.pem Flask==3.1.3
"$AUDIT/flask-only/bin/python" -m unittest tests.test_miniprogram_guest_access tests.test_miniprogram_dictation_grouping tests.test_inventory_toefl_materials tests.test_organize_toefl_materials tests.test_extract_toefl_answer_keys tests.test_map_toefl_answers_to_practice_docs tests.test_import_toefl_official_reading tests.test_reading_vocab_grading tests.test_stats_utils tests.test_grammar_graph_draft tests.test_grammar_item_candidates tests.test_reading_jijing_text_fixes -v
/Users/zhouxin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node tests/test_dictation_spell_queue.js

/Users/zhouxin/Desktop/studytracker/.venv/bin/python -m ruff check --config 'extend-exclude=[]' scripts/build_reading_test_practice.py scripts/generate_grammar_candidates.py scripts/grammar_items/checks.py scripts/grammar_items/reporting.py scripts/grammar_items/review_batch.py scripts/grammar_items/templates.py scripts/reading_jijing_text_fixes.py tests/test_grammar_item_candidates.py tests/test_reading_jijing_text_fixes.py
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -m ruff format --check --config 'extend-exclude=[]' scripts/build_reading_test_practice.py scripts/generate_grammar_candidates.py scripts/grammar_items/checks.py scripts/grammar_items/reporting.py scripts/grammar_items/review_batch.py scripts/grammar_items/templates.py scripts/reading_jijing_text_fixes.py tests/test_grammar_item_candidates.py tests/test_reading_jijing_text_fixes.py
git show e970dd6:scripts/build_reading_test_practice.py > "$AUDIT/baseline-builder.py"
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -m ruff check --config pyproject.toml --config 'extend-exclude=[]' "$AUDIT/baseline-builder.py"
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -m ruff format --check --config pyproject.toml --config 'extend-exclude=[]' "$AUDIT/baseline-builder.py"

git archive e8019c2 scripts/grammar_items scripts/generate_grammar_candidates.py api/__init__.py api/reading_study_glossary.py data/reading_study data/grammar_graph | tar -x -C "$AUDIT/source"
PYTHONDONTWRITEBYTECODE=1 .venv-grammar-tools/bin/python "$AUDIT/source/scripts/generate_grammar_candidates.py" --seed 20261018
# 保存第一次四份文件至 $AUDIT/first-files 后，再执行同一生成命令
PYTHONDONTWRITEBYTECODE=1 .venv-grammar-tools/bin/python "$AUDIT/source/scripts/generate_grammar_candidates.py" --seed 20261018
.venv-grammar-tools/bin/python "$AUDIT/samples.py"
.venv-grammar-tools/bin/python "$AUDIT/probe_rules.py"
.venv-grammar-tools/bin/python "$AUDIT/verify_final.py"
/Users/zhouxin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node "$AUDIT/render.mjs"
```

Flask-only 环境除 pip 自带组件外仅安装 Flask 及其传递依赖，缺 openpyxl 的写表测试按设计 skip；不是 spaCy 环境中的假“轻量”测试。测试列表从 CI 文件提取并核对。Ruff 显式清空 extend-exclude，避免 scripts 被配置忽略后产生假通过。

自写审核脚本的核心不变量：用 `JSONDecoder.raw_decode` 取得每个原始句子对象的原字节，只替换 `sentence_index` 后的数字再比较；不采用 JSON 重序列化掩盖格式差异。static 恢复新旧段落 text 后，其他 JSON 对象必须完全相同；额外核对 diff 的每个增删行均为 text 行。导入脚本不 import app.py，明确使用 `make_app(database_uri='sqlite:////tmp/.../audit-import.sqlite')` 并核验 engine.url，只创建临时库内 ReadingPassageAnalysis 表。

探针初版有两处审核脚本自身的假设错误（ParseCache 环境字典须仅包含其四个键；teacher_row 返回 dict 而非 list），修正临时探针后完整重跑通过；没有改被审核代码以获得通过。

## 问题清单

### F1 — 阻断：B3 完整动词单位仍被原标注边界截断

- 位置：`scripts/grammar_items/templates.py:114`（verb_unit 的 start/end 过滤）、`:553`（T6 传入原 span）；同一函数也用于 `:293` 的 T1 干扰项。
- 问题：aux/auxpass/neg/prt 子节点在原标注范围外时被静默丢弃。B3 定义并没有这个截断条件；即使只漏否定词，题目仍可 `auto_pass`。
- 复现：从缓存按句子 SHA-1 取 tokens，对每道 T6 的 parser.head_token 找出上述四类直接子节点，检查其字符范围是否包含在 target.parts。共 38 道出现差异（12 auto_pass / 26 needs_review）。不能把 38 都算作语法错误：人工排除了 `sailed by noting` 中 by 被误作 prt、`want it to using` 中 to 被误挂给 using 两例；`-were` 一例另含原文排印问题。以下 **9 道 auto_pass** 均明确缺失：

| 题目编号 | passage_id / 句 ID | 现目标 | 漏掉的单位成分 |
|---|---|---|---|
| gi_v02_88bfd8b15d26 | ielts11_test1_p3 B-06 | reduce | could；应为 `【could】, argues Angel, 【reduce】` |
| gi_v02_14238a86fcf3 | ielts15_test2_p3 F-04 | cross out | to |
| gi_v02_69129d9bf252 | ielts18_test4_p3 H-04 | are | not（插入语之后） |
| gi_v02_8aa480f73c33 | ielts7_test3_p2 B-04 | take | did（倒装） |
| gi_v02_7ff82ab4b444 | ielts9_test2_p2 B-02 | can put | down；`put it all down to` |
| gi_v02_f38641df8872 | ielts9_test3_p2 A-03 | close | to |
| gi_v02_21d87055c7e2 | reading_jijing_44_test_29_p1 E-04 | handle | do not；`They do not, however, handle ...` |
| gi_v02_50d6455ed0ff | reading_jijing_44_test_29_p1 G-01 | have | do；`Cockroaches do, however, have ...` |
| gi_v02_7836de3dae6a | reading_jijing_50_test_30_p1 E-04 | are | not；`are certainly not simple` |

- 建议改法：按中心动词的完整依存单位构造 T6/T1 干扰项，超出原 span 或解析有疑义时明确降级，不得静默截断后通过。保留不连续 parts；对插入语、倒装、否定、小品词补回归测试。T1 原答案在计划中要求不变，应把该兼容要求与 T6 新单位逻辑分开处理，不能粗暴改共用函数导致未经评估的答案变化。

### F2 — 应修：自动通过抽样仍含 OCR 断词句

- 位置：`reading_jijing_85_test_12_p3` C-05；`data/reading_study/reading_jijing_85_test_12_p3.json:550`；题 `gi_v02_c03ab3d84792`，主句谓语数据行 14 / Excel 行 15。
- 问题：原句 `The researchers had calcu lated that ...`；机器显示 `【had】 calcu 【lated】`，单词 calculated 被拆坏，不适合作为正常点选题。该源句问题在基线已存在，非此次 28 单元修订引入，但它实际进入了 v0.2 自动通过池和交付表。
- 复现：按种子 20261019 抽样，或直接查 JSONL 题目编号；原 difficult_points 已承认多余空格。
- 建议改法：另行批准原文修复或制定可泛化的 OCR/文本质量复核规则，再重生成；不得仅按此 ID 加黑名单，也不应只把高亮扩大到包含乱码便当作解决。本轮没有越权修原文。

### F3 — 应修：新标注的 when 从句漏掉直接引语宾语

- 位置：`data/reading_study/reading_jijing_16_test_97_p2.json:41`，F-36c。
- 问题：contrast_clause 只到 `when I could have said to the clients`，没有包括冒号后的 `'Why don't I give that to you in 48 hours?'`；后者正是 said 的引语内容，应包含在该从句的完整范围中。
- 复现：T2 `gi_v02_5292f996cd08` 已因 boundary_mismatch 转复核；T3 `gi_v02_fb72620dba8d` 仍自动通过，目标使用截短范围。直接对照 structure 和该句的句法即可确认，不依赖模型判断。
- 建议改法：将 contrast_clause 延伸到完整引语末尾，direct_speech 仍作其内层成分；再验证 T2/T3/T4。when 的对比含义、翻译和 could have said 解释本身合理。

### F4 — 应修：同位语范围包含了未连接的限定谓语

- 位置：`data/reading_study/reading_jijing_71_test_1_p2.json:210`，E-01。
- 问题：把 `'Lo Scopone Scientifico', translates as 'Scientific Scopone'` 整体标为 apposition。片名是 title 的同位语，但后面的限定谓语 translates 不会因原文漏 which 就成为名词性同位语。difficult_points 已说明缺 which，structure 却仍给出完整正常成分标签，二者不一致。
- 复现：直接查看该 structure[3] 与 difficult_points[0]；无需更改或猜补原文。
- 建议改法：同位语仅覆盖片名，余下异常结构如实单独标明；依据项目约定标记残缺或转人工审核。不得在 sentence 中偷偷添加 which。该句翻译按 intended meaning 可接受。

### F5 — 应修：B4 统计报告不完整

- 位置：`scripts/grammar_items/reporting.py:130` relative_adverb_stats、`:143` resplit_stats；两份 generation_report_v0_2。
- 问题：possible_relative_adverb 只有 items_by_template、distinct_targets，**没有逐句列表**；resplit 只有当前总数 12688 和新 ID，**没有修复前 12657**。B4 明确要求这两项。
- 复现：读取报告这两个键，或直接阅读上述函数的 return。两份报告均缺，不是 Markdown 排版遗漏。
- 建议改法：输出按 passage_id/sentence_id/目标边界去重的命中列表（可附题号），并明确 before/after/added 统计，测试报告字段；不要硬编码只有本轮有效的句子黑名单。

### S1 — 建议：保留有界补引号，但完善撇号识别

- 位置：`scripts/grammar_items/templates.py:59` single_quote_role、`:70` balance_single_quotes。
- 复现：`single_quote_role("students' books", 8)` 返回 close；年代缩写 `'80s` 的开头被视为 open。对原标注完整的 `"'The students' books'"`，输入去掉两端引号的 span，close_quotes 返回 `"'The students' books"`，只补左侧，右侧仍漏。
- 评价：这是函数级可复现边界问题，本次全语料跟踪未确认它产生了新的错误题，故列建议而非已发生的应修题。377 次实际范围变化均未越出传入边界；唯一补回文字的是 `ielts14_test3_p1` 的 `known as 'implicit theories'`，补回的 `theories'` 确属原标注和短语。
- 建议改法：区分所有格/省略撇号与引语定界符，增加复数所有格、名字所有格、年代缩写和嵌套引语的测试；继续禁止跨 raw span 为了凑配对而延长答案。可保留现有修复意图，不能把“在原范围内”当成所有引号都已正确的证明。

### S2 — 建议：When it comes to 的教学角色需更精确

- 位置：`reading_jijing_18_test_53_p2` E-01c，structure 的 time_clause。
- 问题：此处固定搭配表示“说到/涉及考试”，语义是论题范围；直接以“时间”关系教学不够准确，与自身 difficult_points/translation 的说明不一致。不同教学体系对这类固定 when 结构的形式分类可能不同，不把它断言为整句标注错误。
- 复现：读本句；当前因跨句引号而整句 rejected/unbalanced_quotes_or_brackets，没有泄入 T4 时间自动题。
- 建议改法：教师统一此类固定搭配的标签和关系题准入，保留现有正确释义；避免以后引号处理改变后直接成为时间题。

### S3 — 建议：couldn't 的解释区分假设可行性与推测

- 位置：`data/reading_study/reading_jijing_73_test_5_p1.json:27`，H-01b 的 difficult_points。
- 问题：`You couldn't do this in New York ...` 在这里强调假设在纽约做这种建筑冷却方案不可行，现解释笼统称“推测”。翻译“没法这样做”和“不指过去”合理，不能据此把本句判为翻译错误。
- 建议改法：解释成“假设在纽约就无法做到，could 表示假设条件下的能力/可行性”，与对已发生事实作否定推测区分；保留引语和 Pearce said 在同一句。

### S4 — 建议：明确存量 Ruff 未通过

- 位置：`scripts/build_reading_test_practice.py:279`、`:335` 的 timezone.utc（UP017），以及该文件 format --check。
- 复现：上述目标文件 Ruff 命令均 exit 1；另外 8 个改动 Python 文件无告警。e970dd6 导出的构建脚本同样有两处 UP017 和格式问题（另外还报原有 import 排序）。
- 建议改法：后续授权维护时清理；当前审核不修。它不是 v0.2 新增业务缺陷，但 Claude“目标文件 Ruff 通过”的概括不足以覆盖用户要求的全部改动 Python 文件。

## 33 条修订逐条核对

以下是读取完整原句与前后引述上下文后的判断，不用双引号奇偶数代替语义判断。G-08 的问号与 Pepperberg asked 属于同一句；I-03b 的引语与 he says 同样保留。

| # | passage_id / 原句 ID | find → replace | 独立判断 |
|---:|---|---|---|
| 1 | reading_jijing_10_test_78_p3 E-04 | `hese."Manufa` → `hese. "Manufa` | 开引号属于下一句，空格放其前；通过 |
| 2 | reading_jijing_10_test_78_p3 P-01 | `ects."The po` → `ects. "The po` | 开引号属于下一句，空格放其前；通过 |
| 3 | reading_jijing_14_test_23_p1 G-02 | `ates.'The ro` → `ates. 'The ro` | 开引号属于下一句，空格放其前；通过 |
| 4 | reading_jijing_14_test_23_p3 H-01 | `usie.'Whilst` → `usie. 'Whilst` | 开引号属于下一句，空格放其前；通过 |
| 5 | reading_jijing_16_test_97_p2 B-09 | `trol."Being ` → `trol." Being ` | 闭引号属于前文，空格放其后；通过 |
| 6 | reading_jijing_16_test_97_p2 F-36 | `appen.I've p` → `appen. I've p` | 两个独立句界之间补空格；通过 |
| 7 | reading_jijing_18_test_53_p2 E-01 | `ools.'Unique` → `ools. 'Unique` | 开引号属于下一句，空格放其前；通过 |
| 8 | reading_jijing_18_test_53_p2 E-01 | `said.'When i` → `said. 'When i` | 开引号属于下一句，空格放其前；通过 |
| 9 | reading_jijing_23_test_46_p1 B-04 | `that.'Some s` → `that.' Some s` | 闭引号属于前文，空格放其后；通过 |
| 10 | reading_jijing_24_test_56_p1 D-01 | `reas.'Dogs a` → `reas. 'Dogs a` | 开引号属于下一句，空格放其前；通过 |
| 11 | reading_jijing_38_test_22_p1 E-03 | `orse.'Intere` → `orse.' Intere` | 闭引号属于前文，空格放其后；通过 |
| 12 | reading_jijing_44_test_29_p1 H-03 | `lear).Gregor` → `lear). Gregor` | 两个独立句界之间补空格；通过 |
| 13 | reading_jijing_46_test_84_p1 B-09 | ` Asia.Thaila` → ` Asia. Thaila` | 两个独立句界之间补空格；通过 |
| 14 | reading_jijing_53_test_83_p2 B-03 | `port."I'm 47` → `port. "I'm 47` | 开引号属于下一句，空格放其前；通过 |
| 15 | reading_jijing_56_test_64_p2 G-03 | ` case.The cu` → ` case. The cu` | 两个独立句界之间补空格；通过 |
| 16 | reading_jijing_56_test_64_p2 G-03 | `that t his may` → `that this may` | 授权修正 t his → this；通过 |
| 17 | reading_jijing_65_test_69_p1 I-03 | `role.'All mu` → `role. 'All mu` | 开引号属于下一句，空格放其前；通过 |
| 18 | reading_jijing_71_test_1_p2 E-01 | `yer'.'Scopon` → `yer'. 'Scopon` | 闭引号属于前文，空格放其后；通过 |
| 19 | reading_jijing_71_test_1_p2 E-01 | `Scientifico',translates` → `Scientifico', translates` | 授权补结束引号后逗号与 translates 间空格；通过 |
| 20 | reading_jijing_71_test_1_p3 A-01 | `meteorologist,.Alfred` → `meteorologist, Alfred` | 授权修正 meteorologist,.Alfred → meteorologist, Alfred；通过 |
| 21 | reading_jijing_73_test_5_p1 H-01 | `ight.'You co` → `ight. 'You co` | 开引号属于下一句，空格放其前；通过 |
| 22 | reading_jijing_76_test_43_p2 E-04 | `iques.Morris` → `iques. Morris` | 两个独立句界之间补空格；通过 |
| 23 | reading_jijing_78_test_102_p2 G-01 | `poons.Today'` → `poons. Today'` | 两个独立句界之间补空格；通过 |
| 24 | reading_jijing_78_test_102_p3 E-03 | `them."When w` → `them. "When w` | 开引号属于下一句，空格放其前；通过 |
| 25 | reading_jijing_82_test_4_p1 F-04 | `ubber.Ford's` → `ubber. Ford's` | 两个独立句界之间补空格；通过 |
| 26 | reading_jijing_83_test_95_p1 G-08 | `rent?"Pepper` → `rent?" Pepper` | 闭引号属于前文，空格放其后；问句+引述语仍为一句；通过 |
| 27 | reading_jijing_85_test_12_p1 C-05 | `says."It off` → `says. "It off` | 开引号属于下一句，空格放其前；通过 |
| 28 | reading_jijing_85_test_12_p1 C-05 | `n it."Peter ` → `n it." Peter ` | 闭引号属于前文，空格放其后；通过 |
| 29 | reading_jijing_85_test_12_p1 C-05 | `as that,"he says` → `as that," he says` | 授权补引语后的 he says 前空格；通过 |
| 30 | reading_jijing_88_test_98_p2 D-02 | `don't.The bi` → `don't. The bi` | 两个独立句界之间补空格；通过 |
| 31 | reading_jijing_88_test_98_p2 G-04 | `sion."For in` → `sion." For in` | 闭引号属于前文，空格放其后；通过 |
| 32 | reading_jijing_88_test_98_p3 D-10 | `cards.That's` → `cards. That's` | 两个独立句界之间补空格；通过 |
| 33 | reading_jijing_91_test_49_p1 F-07 | `fuel."After ` → `fuel." After ` | 闭引号属于前文，空格放其后；通过 |

## 59 句新标注逐句审核覆盖

每行列出的所有 ID 均分别阅读了四项字段及拆分边界。“未发现问题”仅表示本次人工审核未发现实质问题，不等于自动标注质量保证。两项应修涉及 2 句，两项语义精度建议涉及另外 2 句，其余 55 句未发现实质问题；所有 59 句 translation/expressions 未发现须更正项。

拆分判断：26 个需要拆句的原单元按完整句界拆，A-01、G-08 仅修文字。直接引语后的 he says / he said / Pearce said / Pepperberg asked 与引语保持一起，做法合理。F-36 的长引语拆为五个句子，其中引号跨句，符合“不改原文”的前提；不应为了让每个独立句引号成对而补造字符。不存在把单独的 he says 当一条新句的情况。

| passage_id | 本次逐句审核的 ID | 四项字段与拆句结论 |
|---|---|---|
| reading_jijing_10_test_78_p3 | E-04, E-04b | 各句翻译、成分/role、难点、表达及拆句均未发现实质问题 |
| reading_jijing_10_test_78_p3 | P-01, P-01b | 各句翻译、成分/role、难点、表达及拆句均未发现实质问题 |
| reading_jijing_14_test_23_p1 | G-02, G-02b | 各句翻译、成分/role、难点、表达及拆句均未发现实质问题 |
| reading_jijing_14_test_23_p3 | H-01, H-01b | 各句翻译、成分/role、难点、表达及拆句均未发现实质问题 |
| reading_jijing_16_test_97_p2 | B-09, B-09b | 各句翻译、成分/role、难点、表达及拆句均未发现实质问题 |
| reading_jijing_16_test_97_p2 | F-36, F-36b, F-36c, F-36d, F-36e | F-36c 从句边界需修（F3）；其余四句未发现问题，长引语跨句已如实说明 |
| reading_jijing_18_test_53_p2 | E-01, E-01b, E-01c | E-01c 的固定搭配关系标签建议教师复核（S2）；另外两句未发现问题 |
| reading_jijing_23_test_46_p1 | B-04, B-04b | 各句翻译、成分/role、难点、表达及拆句均未发现实质问题 |
| reading_jijing_24_test_56_p1 | D-01, D-01b | 各句翻译、成分/role、难点、表达及拆句均未发现实质问题 |
| reading_jijing_38_test_22_p1 | E-03, E-03b | 各句翻译、成分/role、难点、表达及拆句均未发现实质问题 |
| reading_jijing_44_test_29_p1 | H-03, H-03b | 各句翻译、成分/role、难点、表达及拆句均未发现实质问题 |
| reading_jijing_46_test_84_p1 | B-09, B-09b | 各句翻译、成分/role、难点、表达及拆句均未发现实质问题 |
| reading_jijing_53_test_83_p2 | B-03, B-03b | 各句翻译、成分/role、难点、表达及拆句均未发现实质问题 |
| reading_jijing_56_test_64_p2 | G-03, G-03b | 各句翻译、成分/role、难点、表达及拆句均未发现实质问题 |
| reading_jijing_65_test_69_p1 | I-03, I-03b | 两句均未发现问题；引语与 he says 保持一起 |
| reading_jijing_71_test_1_p2 | E-01, E-01b | E-01 的 apposition 范围需修（F4）；E-01b 未发现问题 |
| reading_jijing_71_test_1_p3 | A-01 | 只修 meteorologist, Alfred；未发现问题 |
| reading_jijing_73_test_5_p1 | H-01, H-01b | H-01b 的情态含义解释可更精确（S3）；H-01 未发现问题 |
| reading_jijing_76_test_43_p2 | E-04, E-04b | 各句翻译、成分/role、难点、表达及拆句均未发现实质问题 |
| reading_jijing_78_test_102_p2 | G-01, G-01b | 各句翻译、成分/role、难点、表达及拆句均未发现实质问题 |
| reading_jijing_78_test_102_p3 | E-03, E-03b | 各句翻译、成分/role、难点、表达及拆句均未发现实质问题 |
| reading_jijing_82_test_4_p1 | F-04, F-04b | 各句翻译、成分/role、难点、表达及拆句均未发现实质问题 |
| reading_jijing_83_test_95_p1 | G-08 | 补空格后问句与 Pepperberg asked 保持一句正确；已知 multi_sentence_unit 误伤 |
| reading_jijing_85_test_12_p1 | C-05, C-05b, C-05c | 各句翻译、成分/role、难点、表达及拆句均未发现实质问题 |
| reading_jijing_88_test_98_p2 | D-02, D-02b | 各句翻译、成分/role、难点、表达及拆句均未发现实质问题 |
| reading_jijing_88_test_98_p2 | G-04, G-04b | 各句翻译、成分/role、难点、表达及拆句均未发现实质问题 |
| reading_jijing_88_test_98_p3 | D-10, D-10b | 各句翻译、成分/role、难点、表达及拆句均未发现实质问题 |
| reading_jijing_91_test_49_p1 | F-07, F-07b | 各句翻译、成分/role、难点、表达及拆句均未发现实质问题 |

## 抽样方法与 30 题明细

读取提交版 `review_batch_v0_2.jsonl`，保持文件内顺序；建 `random.Random(20261019)`，按代码 TEMPLATES 的固定顺序，依次从各模板 50 道 pool_status=auto_pass 中 `sample(pool, 5)`。未按难易或先前审核结果挑选。下表“数据行”即 review_row；Excel 实际行 = 数据行 + 1（第 1 行是表头）。

种子与 Claude 的 777 不同，但随机抽样仍偶然重叠 2 题（gi_v02_6af6ac639a3c、gi_v02_1a5108714938）。没有为获得零重叠而擅自改种子或重新抽样；两题也独立重判。因此 30 道均为本次审核，其中 28 道未出现在 Claude 的 30 题清单。

| # | 题目编号 | 工作表 | 数据行 / Excel 行 | 判定及核对要点 |
|---:|---|---|---|---|
| 1 | gi_v02_c4d79d40f062 | 主句谓语 | 42 / 43 | 正确；release |
| 2 | gi_v02_875f1982868a | 主句谓语 | 23 / 24 | 正确；want |
| 3 | gi_v02_0a616e4e0b8c | 主句谓语 | 56 / 57 | 正确；was carried out |
| 4 | gi_v02_0862c2167da3 | 主句谓语 | 8 / 9 | 正确；was |
| 5 | gi_v02_c03ab3d84792 | 主句谓语 | 14 / 15 | 句子不适合出题；calcu lated 断词，F2 |
| 6 | gi_v02_760fb5484b40 | 从句边界 | 41 / 42 | 正确；which distinguishes … 完整 |
| 7 | gi_v02_6af6ac639a3c | 从句边界 | 45 / 46 | 正确；that is successfully corrected |
| 8 | gi_v02_4276c99e4eca | 从句边界 | 25 / 26 | 正确；While … England |
| 9 | gi_v02_da2b02a8d022 | 从句边界 | 24 / 25 | 正确；Manton uncovered |
| 10 | gi_v02_d80049255b08 | 从句边界 | 56 / 57 | 正确；they’ve developed |
| 11 | gi_v02_11e4b1465666 | 从句类型 | 2 / 3 | 正确；Whereas … 状语从句 |
| 12 | gi_v02_8ac2f7a4a6e7 | 从句类型 | 28 / 29 | 正确；buried for safekeeping 非谓语 |
| 13 | gi_v02_13a520e26200 | 从句类型 | 11 / 12 | 正确；that … could be kept … 名词性从句 |
| 14 | gi_v02_162149514805 | 从句类型 | 1 / 2 | 正确；If … development 状语从句 |
| 15 | gi_v02_9e5d77c8ddd1 | 从句类型 | 55 / 56 | 正确；they look a little bit like cherries 并列分句 |
| 16 | gi_v02_47fd858c1be0 | 状语关系 | 42 / 43 | 正确；until … development，时间 |
| 17 | gi_v02_1a5108714938 | 状语关系 | 21 / 22 | 正确；If … continued，条件 |
| 18 | gi_v02_a842071cfde4 | 状语关系 | 35 / 36 | 正确；so that …，目的 |
| 19 | gi_v02_41c6de54d739 | 状语关系 | 49 / 50 | 正确；after … vanished，时间 |
| 20 | gi_v02_aaff48fdaf69 | 状语关系 | 19 / 20 | 正确；until she moved …，时间 |
| 21 | gi_v02_574bc7bfa27c | 完整主语 | 46 / 47 | 正确；The thinking in each chapter |
| 22 | gi_v02_30d370f90ebe | 完整主语 | 26 / 27 | 正确；Stores |
| 23 | gi_v02_08bfdb2e97f4 | 完整主语 | 6 / 7 | 正确；The incorrect answers |
| 24 | gi_v02_b8d0763b151a | 完整主语 | 8 / 9 | 正确；it |
| 25 | gi_v02_e51a0f714ece | 完整主语 | 33 / 34 | 正确；These ideas |
| 26 | gi_v02_4f1d8041517d | 动词身份 | 52 / 53 | 正确；have drawn，主句谓语 |
| 27 | gi_v02_4cfd0e856351 | 动词身份 | 21 / 22 | 正确；revealed，主句谓语 |
| 28 | gi_v02_94a3674baa88 | 动词身份 | 19 / 20 | 正确；was，主句谓语 |
| 29 | gi_v02_911117cef560 | 动词身份 | 36 / 37 | 正确；reproduce，主句谓语 |
| 30 | gi_v02_5dfbdcdd3a64 | 动词身份 | 7 / 8 | 正确；【are】 decidedly 【influenced】，从句谓语 |

其中第 16 题源句另有 `At other limes` 排印瑕疵，但目标 until 的边界和“时间”答案明确；第 19 题原句表达不够自然，同样未改变目标 after 的关系判断。这些不是把整句语言质量逐项认证为完美的结论。

## possible_relative_adverb 的 15 题独立抽查

全量 49,654 候选中取 reasons 含 possible_relative_adverb 的 **228 道题**，按 item_id 排序，用独立的 `random.Random(20261019).sample(pool, 15)` 抽样。抽样单位是题目，不是去重后的目标；此次恰好为 15 个不同来源目标。全部为 needs_review。109 个去重目标，T2=87、T3=109、T4=32，与报告一致。

| # | 题目编号 | passage_id / 句 ID | 人工判断与依据 |
|---:|---|---|---|
| 1 | gi_v02_978b04977909 | ielts9_test1_p1 I-03 | 状语；when 表示 Empress 决定种植的时间，不修饰 France |
| 2 | gi_v02_508cfa56eabd | ielts8_test4_p2 J-02 | 定语；when 补充 late 1960s 的时间内容 |
| 3 | gi_v02_c6f1e2319329 | reading_jijing_88_test_98_p3 C-01 | 状语；makes sense when … 的条件/时间 |
| 4 | gi_v02_1f41dc73d4f3 | ielts6_test2_p2 K-37 | 状语；get help when you need it |
| 5 | gi_v02_3c70bc3761ed | ielts18_test3_p2 B-03 | 状语；发动机回火时导致断臂 |
| 6 | gi_v02_7be3533cea95 | ielts15_test4_p2 H-01 | 状语；Spain 征服时已有这种语言 |
| 7 | gi_v02_8b229a84a21f | reading_jijing_44_test_29_p3 A-02 | 定语；when 补充 Second World War |
| 8 | gi_v02_48578aaf7d01 | ielts11_test2_p3 H-01 | 状语；看到静止物时处理运动信息 |
| 9 | gi_v02_44a78fb23d4e | reading_jijing_53_test_83_p3 A-02 | 状语；燃料配额耗尽时的情况，不修饰 lamp |
| 10 | gi_v02_c1f39530c292 | ielts10_test3_p1 A-01 | 定语；when 解释 beginning of time 所指时期 |
| 11 | gi_v02_04d87142654c | ielts20_test2_p2 F-39 | 状语；本应专注时占据心神 |
| 12 | gi_v02_5ed90cb62276 | reading_jijing_40_test_75_p1 C-01 | 两可；Later in his life, when he was in his forties 可作时间补充，也可整体作时间状语，不硬判 |
| 13 | gi_v02_250fba7ae9d9 | reading_jijing_83_test_95_p1 A-02 | 定语；At a time when … 明确修饰 time |
| 14 | gi_v02_0087e03e6b6b | reading_jijing_84_test_73_p2 D-24 | 状语；离校时放弃运动 |
| 15 | gi_v02_8bdfc44fa6c0 | ielts19_test2_p2 E-01 | 状语；运动员承受压力时的体验 |

确定定语 **4/15（26.7%）**，加上两可最多 5/15；其余 10/15 为状语。这里只是样本描述，不作全库精确率结论。这条保守规则确实能拦截部分定语误标，代价是很多正常状语转人工；符合计划的风险提示用途，不能将“命中”解释为“已经确认标错”。

## 全部回归例句

| 计划 / 例句 | 实际结果 |
|---|---|
| v0.1 ielts7_test3_p1 K-03 | 整句 rejected：too_short + unbalanced_quotes_or_brackets |
| v0.1 ielts8_test4_p1 C-04 | 无 he felt 目标；T1/T5/T6(a) 因 no_main_verb_tag 无题；T3 to introduce… 与 T6 to introduce 非谓语均 auto_pass |
| v0.1 reading_jijing_76_test_43_p2 H-02 | T5 needs_review/subject_mismatch；T1 had/lost/out、T6 had lost out 自动通过 |
| v0.1 reading_jijing_73_test_5_p2 F-05 | 整句 rejected：tagged_fragment + unknown_span |
| v0.1 reading_jijing_56_test_64_p2 C-01 | 整句 rejected：clause_attached_to_conjunction |
| v0.1 ielts13_test2_p2 C-04 | 整句 rejected：clause_attached_to_conjunction（计划指定保守拒绝） |
| v0.1 reading_jijing_91_test_49_p3 D-02 | T1 occurred，attended / representing 干扰项，auto_pass |
| v0.1 ielts11_test3_p2 A-04 | T2 that apply, in varying degrees and combinations, to all migrations，auto_pass |
| v0.1 ielts15_test2_p3 D-05 | T2 完整 that … low-status individuals 名词性从句，auto_pass |
| v0.2 ielts4_test2_p2 G-31 | when 目标 T2/T3/T4 全 needs_review/possible_relative_adverb；T6 不在 B2 范围，仍 auto_pass 符合计划 |
| v0.2 ielts6_test3_p1 C-06 | born 目标为 was born，单一连续 parts，T6 auto_pass；T1 中两个 was 导致歧义复核不违反 B5 |
| v0.2 reading_jijing_88_test_98_p2 G-04、G-04b | 已拆两句，前句引号 loss aversion 完整；后句独立，原文拼回一致；全库 glued_sentence_boundary=0 |
| v0.2 B5 最后一行 | 上述全部 v0.1 例保持要求，含 C-04 / H-02 完整动词单位 |

整句独立统计：tagged_fragment=36、clause_attached_to_conjunction=2、glued_sentence_boundary=0、multi_sentence_unit=51。回归句 ID 仅在报告常量中用于展示，没有用于生成黑名单。

## 生成环境与双次 SHA-256

本机 macOS / Darwin arm64，Python **3.13.3**；spaCy **3.8.16**、en_core_web_trf **3.8.0**、torch **2.14.1**（CPU）、openpyxl **3.1.5**、Flask **3.1.3**。使用现有独立 `.venv-grammar-tools`，没有向线上依赖环境安装分析模型。全量 317 篇、12688 句、49654 题，六模板计数与提交版全部一致。

| 文件 | 第一次 SHA-256（冷缓存） | 第二次 SHA-256（热缓存） |
|---|---|---|
| generation_report_v0_2.json | `78740410e0d7371f106f0ff1992e2e591600e0e02a6cc7040c62f14edee018d6` | `78740410e0d7371f106f0ff1992e2e591600e0e02a6cc7040c62f14edee018d6` |
| generation_report_v0_2.md | `2bfc357074cb7da24c9b1327c7cd05cb332bca9795e2ad6d903459b07c445dfd` | `2bfc357074cb7da24c9b1327c7cd05cb332bca9795e2ad6d903459b07c445dfd` |
| review_batch_v0_2.jsonl | `804b16b48af2a9682a9e5878c2a56e3dde3517538c690432bfc242574ae3bc47` | `804b16b48af2a9682a9e5878c2a56e3dde3517538c690432bfc242574ae3bc47` |
| review_batch_v0_2.xlsx | `16bf96c0bad50e9764e79f2b5d2987e0c10c2f6c4241510d13f2dd896b7e8234` | `16bf96c0bad50e9764e79f2b5d2987e0c10c2f6c4241510d13f2dd896b7e8234` |

提交版 JSONL/XLSX 哈希与上表相同。报告比较按字节进行，且分别断言：`committed.replace(b'3.11.15', b'3.13.3') == generated`，diff 各只有一个 Python 行：JSON 第 16 行、Markdown 第 36 行；未忽略其他字段。提交版报告哈希：

- generation_report_v0_2.json：`e5bdb081a59ea78f17d762e7ff225f29c32a0493f688dfb44711c3eac738f62b`。
- generation_report_v0_2.md：`0d4ef2f34cb0810bfde216a871f34d8b24e172c9fe315a1222a9e001952995a2`。

## 已披露遗留项的评估

- **51 句 multi_sentence_unit**：代码严格实现计划正则；G-08 的问句加引述语本来是一句，过滤属于已知误伤。当前只是损失候选召回，不是错误题自动通过。本轮不算新缺陷，也未重拆其他句子。
- **12 处跨范围的引语**：不能为了引号成对把不属于从句的文字纳入目标；保留语法范围的原则合理。老师仍可能认为显示不够清楚，后续可改展示上下文或提示，但不能扩大答案冒充修正。
- **同方实现和自查**：本轮已增加独立检查。生成文件一致证明复现性，不证明 Claude 或 spaCy 的语法判断正确；F1/F2/F3 是两者都可能漏过的具体例证。

## 与用户要求不一致之处及发布状态

1. 未把第 6 项的“完整段落逐字一致”报告为通过：7 处基线空白差异已如实列明；28 组新句对修复后的原单元精确相同。没有通过修改额外句子来消除差异。
2. 第 11 项 Ruff 没有全部通过，原因见 S4；不是工具无法运行。
3. 不同随机种子仍出现两题偶然重叠；保留指定种子与原样抽样，未人为换题。
4. 第 12 项在 e8019c2 的原样临时导出副本生成，以满足只读边界；环境、输入、源码与正式 worktree 一致，四份原交付未被覆盖。这不是更换算法或模型。
5. 所有要求的检查均已实际执行；没有用自查结论代替本次运行，没有因失败自行修代码。

本轮仅三份审核/交接 Markdown 将提交并推送 `codex/grammar-item-candidates`；提交信息不带 `[skip ci]`。GitHub CI 结果在推送后补记。审核用临时文件与环境仍仅本机可见，未部署，未操作生产。

## GitHub CI

待本审核记录首次提交推送后记录实际运行链接、提交 SHA、test/lint 结果；不以本地测试冒充 GitHub CI。
