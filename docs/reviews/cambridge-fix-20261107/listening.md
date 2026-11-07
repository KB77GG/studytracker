# 剑桥听力窄范围修订与验证

实施树 `/private/tmp/studytracker-cambridge-fix-20261107`，分支 `codex/cambridge-explanations-fix-20261107`，基线 `40cd8225db1b0a5da188b1dd99d4521dc5853328`。开工clean；本子任务负责听力builder、听力manifest、18个听力静态JSON及定向测试。其他agent的阅读/显示/共享服务修改并行存在，不属于本报告独立完成范围。没有commit/push/deploy或生产数据库写入，主agent统一记录交接与发布状态。

## 修订范围

- 逐题重新写定 **26条解释**：此前确认的23条实错，另剑18T1 Q3/Q23/Q40三条不准确论证。文本均按题干与本卷原文解释目标空格，去掉串题、“原文无法确定”和错误的单复数词数规则。没有批量使用模型重写。
- 剑18T1 Q14/15现在覆盖时间可用性及奉献精神；Q29/30覆盖市场空缺及退货原因、双方认可；Q23覆盖Chantal评价与Hugo“才一年级”的回应。
- 剑18T1 Q33/34各保留自身单空题干。Q34仅保留`− this process had to be completed quickly to reduce ...`，麻醉的共享说明继续由collect呈现，避免实际表单重复两次。
- 剑4T3Q4的逆时间由225.25→99.76修为225.69→234.84；依据为原文及同源sidecar第26–28句，包含Thursday、September7及确认。
- 剑10T2Q1旧定位105.00→105.73对应开场而非姓氏，改为136.00→142.50，覆盖Hardie和H-A-R-D-I-E拼写。当前sidecar映射后的证据136.00→141.64，真实derive输出可用。

精确窄改：**18套、33题；analysis26、title2、start/end/answer_sentences各7**。完整差异清单见`listening-scope.json`。以基线逐题比较，去除这些允许字段后72套原/新数据完全相等：**所有answer/answers、id、number、options、group结构、共享collect、transcript、音频路径及生成时间均未改**，不会借此次修解析改变评分答案。

持久人工修订在 `data/cambridge_content_corrections/listening.json`，仅包含允许的展示/定位字段。builder在完整test组装后调用共享`apply_content_corrections(..., subject='listening')`，后续重建可保留修订。

## 原文定位证据

| 题目 | 修后原题坐标（秒） | 新lyc_index | 依据 |
|---|---|---|---|
| 剑18T1 Q14、15 | 167.90–201.58 | [14,18] | enough hours、dedication、full energy |
| 剑18T1 Q23 | 144.78–153.16 | [15,16] | harsh、only first years、lot to learn |
| 剑18T1 Q29、30 | 334.27–360.29 | [46,50] | gap in the market、returned、good to know |
| 剑4T3 Q4 | 225.69–234.84 | [26,28] | Thursday、seventh of September、that's right |
| 剑10T2 Q1 | 136.00–142.50 | [15,17] | Hardie、拼写请求、H-A-R-D-I-E |

新lyc_index按builder `location_span_from_content`现有的**1-based闭区间**约定写入；旧导入来源的索引习惯不统一，未全库改写。当前Web/模考证据实际按start/end映射，不读取lyc_index。每项`answer_sentences.start_time/end_time`与顶层秒数严格同步。

## 构建策略解耦与限制

`use_analyze_location`现在只影响时间来源，不再借此切换解析。未审源文本默认`ai_analyze`优先，缺失则回退`analyze`；人工manifest最后覆盖。删除无其他调用的四短语`is_usable_analysis`过滤器，避免把一个浅层词表误当语义验收。没有添加“读取已发布JSON做隐式回退”，保持构建确定性。

**本轮没有重建全部337条历史source-analysis选择。** 它们来自此前35套的定位回退策略；今后运行整套或全库builder时，新的解析来源策略可能改变未审核文本，必须审阅输出diff后再发布，不能把构建成功等同于新增内容验收。本次18个静态JSON是人工manifest窄补，不是整套重建。

剑18T1S1与剑19T2S2各一条旧frozen transcript逆序仍保留。当前sidecar有有效时间（I see为155.07–155.64；training为261.90–276.06），derive展示会使用sidecar。没有把当前侧时间直接写回旧原轨快照，避免破坏历史映射；原始数据本身仍是后续来源维护项。没有全量实听2880题，也没有主张所有解析已人工终审。

## 验证

cwd固定为本实施树，借用主资料树Python环境：

```bash
PYTHONDONTWRITEBYTECODE=1 /Users/zhouxin/Desktop/studytracker/.venv/bin/python -m unittest tests.test_cambridge_listening_corrections -v
/Users/zhouxin/Desktop/studytracker/.venv/bin/ruff check --target-version py310 scripts/build_listening_test_practice.py tests/test_cambridge_listening_corrections.py
/Users/zhouxin/Desktop/studytracker/.venv/bin/black --check tests/test_cambridge_listening_corrections.py
git diff --check
```

结果：**8/8通过**；Ruff按生产Python3.10目标通过；测试文件Black通过；diff通过。默认项目py313规则仍对原有`timezone.utc`报UP017（基线已有，保留生产3.10兼容，不改为3.11新增UTC别名）。测试覆盖：时间切换不改变解析、缺AI回退、完整builder末端人工补丁、五题C18原文证据链、C4逆时间修复、C10姓拼写定位、两单空题干、manifest幂等及禁评分字段。

实际`derive_listening_payload`使用仓库已提交sidecar，定向7个定位项全部有完整证据；没有mock映射函数、没有放宽覆盖率门禁。合成builder测试只写临时raw/report，无网络、无数据库。全库运行态及页面复核由展示agent/主agent另行记录。

先前一次测试因断言误写Thursday大写而失败，已核基线评分字段本就是小写`thursday`，只改测试断言后最终8/8通过，**未改答案字段**。

下一步：独立审阅人工文本并合并共享服务/显示链路验证，主agent按用户授权决定提交发布；本子任务自身未提交或部署。
