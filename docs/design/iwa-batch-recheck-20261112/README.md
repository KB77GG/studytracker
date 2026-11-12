# 批次与盲评第三轮离线复核（2026-11-12）

**结论：上轮 5 个 P2 和 1 个 P3 的复现场景全部关闭；执行器复验通过。还剩 1 个盲评完整性 P2，建议补齐后再做正式模型对照。** 没有发现预算或正常续跑回归。本轮产品未改、真实请求为 0。

## 被测基线

- 业务 `45072df927f4c5836e79cc420deb3ecc8371d6f7`，连同说明的 HEAD `f5c3f51d603e69fe2600953f17720e33be5273e6`。
- 独立树 `/private/tmp/studytracker-iwa-holdout-review-20261111`，分支 `codex/iwa-holdout-review-20261111`，从 clean `76276d91` 快进。90 个跟踪工具文件的组合 SHA256：`308f020cca0038f79d709f6c0d14cb78564cb67dd8b947bfaf56d37aa7a585cb`，与提交相同。审阅报告提交不改变这些工具文件。
- 主资料树 `/Users/zhouxin/Desktop/studytracker` 保持 main `6ded77d2`、behind113，既有 7 modified / 23 untracked 顶层入口保留；只新增本目录与两交接。旧两棵IWA审阅树未操作。

## 上轮修复已确认

| 原问题 | 本轮独立结果 |
|---|---|
| 父进程被杀，子进程继续工作却无锁 | 子进程仍持锁，第二批 exit2、0 新请求；成功后原 cap112 续跑，沿用结果补 `.done`，整批仍56次、Pro14次。失败子进程exit4不被沿用，已用预算保留。 |
| 改稿后续跑才发现输入不同 | 题目、作文、参考分/批注、图片字节等改变，在请求前exit2、账本不变；冻结图结果和done指纹也核对。可选官方组首次追加可单独运行，之后同样固定。 |
| 盲评缺行仍完整 | 空表、缺侧、缺行、重复/未知行、待判项改“参考”均拒绝。 |
| 改列建议重复计错 | 同一条只显示一次，保留说明和支撑；两边各一个错误统计1比1。 |
| 续跑覆盖人工盲评 | 真实组续跑保留表、映射、判断备注和计数字节；直接compare写已有盲评目录也拒绝。改表或映射后旧计数正确显示过期。 |
| 失败识图诊断重用不一致 | 冻结失败保留诊断，模型输入和导出输入一致，单独对照通过。 |

作者适配的原场景没有削弱：来源探针 AST 只有三处内部 helper 调用更新，37 个预期保持；指标/续跑探针调整行编号列、行清单和新构造参数，原用例保留。不能把内部接口变更造成的旧脚本报错当成产品回归。

## 剩余 P2：盲评表没有绑定原始映射和不可编辑列

位置：`realcheck_compare.py:842` 的行清单仅记录 `id/sample/side/kind`；`blindtally.py:90,99,104` 按编号匹配，用传入映射决定模型，用表里可改的标签决定漏报类别。计数时才保存当前两文件的哈希，能识别**计数后改文件**，却不能判断第一次计数时两文件是否配套。

### 反例一：拿错合法映射，模型结论反转

1. 同一个合成比较，用 seed0 和 seed1 分别正常生成盲评，两个 key 的行编号和类型相同、甲乙映射相反。
2. 填好 seed0 的表，其中 A 一条②、B 没有。正确计数是 **A=1，B=0**。
3. 误用 seed1 的 key 后，仍 `complete=true`，计数变成 **A=0，B=1**。
4. 再计数会给错配的两文件重新存哈希，因此 `current=true`，汇总也显示完整且当前。

这需要混用了两份独立生成的文件；**正常固定 seed、未混文件的批次续跑已通过**。这是避免误配导致静默误判的需求，不是防范有意篡改全部本地文件。

### 反例二：漏报行改成另一合法标签，计数悄悄换类

④行本来填2，将其标签改成同样合法的“其他漏报”后，原类2变0、另一类0变2，仍完整。未知标签会被拒绝，但两个合法标签互换未被发现。

### 建议的限定修复

- 生成时为表与对应 key 绑定同一比较/模板标识，并核验不可编辑列的指纹；只有判断、备注两列可自由填写。
- 每个 count 行在清单里保存确定的类别，不能由用户表里的标签重新推断。
- 不需要改提示词、模型调用、评分阈值或批处理架构。保留目前有效的续跑、不覆盖和过期检测。

证据：[metrics_consistency.json](metrics_consistency.json)；[脚本](metrics_consistency.py)；[专项说明](metrics_review.md)。脚本保留14个正对照，新增3条正确期望断言；本版本为14/17、exit1，三个失败对应上述一个P2，修复后应原样17/17。

## 验证结果与命令

- 主机 Python3.13.3：**445 Python + 8 Node**，约30秒，临时数据哨兵未写；套件只允许回环假HTTP，禁止外网。`offline-tests.json/log`记录命令。
- 作者 batch 探针5/5，新真实进程测试1/1；独立生命周期20/20；原父进程探针也验证锁未释放、第二批被拒。28仅是该旧探针停在开发组后的次数，不是整批次数；完整续跑56另测。
- 来源37/37（原预期）+30/30（新增边界）；指标适配18/18；填表续跑字节检查通过；盲评一致性14个正对照通过，上述3个拒绝断言失败。
- 独立树 Ruff、Black64工具文件、JS语法、diff检查通过。没有重复所有历史探针、多locale、Python3.10或真实浏览器检查；不据此宣称真实模型判断准确。

主资料树运行：

```sh
.venv/bin/python docs/design/iwa-batch-recheck-20261112/run_offline_tests.py
.venv/bin/python -B docs/design/iwa-batch-recheck-20261112/runner_lifecycle_probe.py --repo /private/tmp/studytracker-iwa-holdout-review-20261111 --out docs/design/iwa-batch-recheck-20261112/runner_lifecycle_probe.json
.venv/bin/python -B docs/design/iwa-batch-recheck-20261112/source_manifest_probe.py --repo /private/tmp/studytracker-iwa-holdout-review-20261111 --output docs/design/iwa-batch-recheck-20261112/source_manifest.json
.venv/bin/python -B docs/design/iwa-batch-recheck-20261112/metrics_consistency.py --repo /private/tmp/studytracker-iwa-holdout-review-20261111 --out docs/design/iwa-batch-recheck-20261112/metrics_consistency.json
```

适配探针的完整命令见各专项报告，脚本位于仓库 `docs/design/ielts-writing-ai-model-comparison-plan-20261110/verify/`。主审已复跑新生命周期、来源、指标一致性和三个适配探针。

## 实际附件的正常彩排

原附件六JSONL与两题图全程只读；`official.jsonl`仍缺失，官方组跳过。新私有目录 `/Users/zhouxin/iwa-compare-dry-20261112-review/`，原始结果不提交。

```sh
.venv/bin/python tmp/iwa-batch-recheck-20261112/dry_run.py --repo /private/tmp/studytracker-iwa-holdout-review-20261111
```

主审已获准执行：main92文字替身、vision8文字+2识图替身，13运行/6比较，两阶段续跑均0新增，13/13检查通过。全部fake、未配置Key、子进程网络阻断、清外部IWA与代理、明确不存在.env。`dryrun_metadata.json`仅含数字/布尔值。其Python源码指纹与`source_state.json`全部工具文件组合指纹定义不同。专项说明中的“包装器未执行”是子审写报告时的状态，本节更新为主审执行结果。

## 交付与后续

仅新增本目录的脱敏证据及更新 `docs/CODEX_HANDOFF.md`、`docs/WORKLOG.md`，按已有授权同步功能分支；最终提交和push确认见git与本机确认条。专项报告里的“仅本机”是各子审交付时的状态，统一随根报告发布。私人作文、题图、原始演示/盲评/映射和ignored包装器不提交。

真实调用0，未读实际Key，不改产品或生产配置，未合main、部署、写生产数据库或上传/提审/发布小程序。执行器已通过本轮范围，但正式盲评结论仍应先补唯一绑定缺口。复验后再确认付费上限：第一阶段无官方184/有官方224，第二阶段16文字+2识图；没有自动挪用旧授权，旧B不另跑。
