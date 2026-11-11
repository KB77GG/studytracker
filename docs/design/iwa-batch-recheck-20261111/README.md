# realcheck-batch 第二轮离线复核（2026-11-11 至 12）

**结论：原预算、识图和失败停机问题已关闭，但还不能启动付费批次。** 新的反例不再突破总请求上限；它们会造成重复运行、不同输入的无效对照，以及盲评计数失真。所有反例使用合成资料和假模型，主审已独立复跑。产品未修改，真实请求为 0，未读实际 Key 或试用配置。

## 基线与范围

- 业务：`50d557fdc08a38670d2f3bd8be30692cd86bd65b`；连同说明的被测 HEAD：`d84c412a8513a049d4b3dfc6e6f29a170f741236`。
- 审阅树：`/private/tmp/studytracker-iwa-holdout-review-20261111`，分支 `codex/iwa-holdout-review-20261111`，从已发布 `7b222c8c` 干净快进。89 个工具文件组合 SHA256 `dff5eaaf190f17b3576d458b3e0e05967151ad48ca52e8faf53a9e595fbbd656`，与被测提交一致。后续审阅提交只新增本目录和更新两交接。
- 主资料树：`/Users/zhouxin/Desktop/studytracker`，main `6ded77d2`、behind113，已有 7 modified / 23 untracked 顶层入口保留；本轮只增审阅材料和交接，不切主分支或合并业务。
- 本轮检查新执行器及其承诺。没有重跑所有历史探针、多 locale、Python 3.10 或浏览器全流程；不以演示分数判断真实模型质量。

## 已通过的原修复

作者的 `verify/batch_probe.py` 5/5、`verify/metrics_blind_probe_fixed.py` 6/6 在 Mac 主审复跑通过：

- 每次请求前加锁预留、fsync；被杀而结果不明的请求仍计费额。正常双批次互斥；中断 5 次后同上限拒绝、无新增请求，探针明确加额度后账本与传输计数一致。
- 先识图，每张一次，失败也冻结；任一图失败时文字请求为 0，续跑不重新识图。成功时两个模型沿用同一识图结果。
- 评价失败过半以非零退出，不写完成标记；已取消的 bash 中文编码问题不再适用。
- AI 与评委在同一出分集合上对比，双模型另有共同集合；计划排序端点缺分不偷换中间档。
- 账本含历史失败/结果未知尝试，费用未知部分不冒充完整；分数白名单导出；盲评的原证据缺口已补齐；`0.5` 等不再截成整数。

## 剩余问题

### P2-1：父进程退出，仍运行的子进程没有持有批次锁

`batch.py:377–380` 的锁由父进程持有，`:288` 启动 realcheck 未传递锁描述符。dev/Flash 已完成、dev/Pro 第一次请求等待中，仅杀批次父进程后，realcheck 仍活着，第二批次却能取得锁并启动第二个 dev/Pro。

独立探针：正常 56 次替身请求变成 **70 次**，dev/Pro 从 14 变成 28，两子进程重叠并写相同输出路径。账本同样为 70，**仍小于 112 上限**。这是重复消耗与结果写入竞争，不是上轮的超预算漏洞。

建议：让执行中的子进程持续持有同一批次锁，或者统一生命周期直到子进程确实结束。验收要杀父进程，确认子进程活着期间第二批次被拒，不能只测父子都正常存活或只杀子进程。

证据：[runner_parent_lock_probe.json](runner_parent_lock_probe.json)、[专项说明](runner_review.md)。

### P2-2：续跑前不核对数据，改过作文后仍花请求或沿用旧报告

`batch.py:341` 记录代码/模型/价格，未记录样本、参考资料或图片的指纹；`:244` 只按 `.done` 跳过。已完成 Flash、Pro 中断后，给同 ID 原稿加一句再续跑，会先发 **2 次 Pro 请求**，到最后比较才 exit6 拒绝。若两边都已完成，改稿后续跑直接 exit0，仍使用旧报告。

建议：第一次运行先固化每组输入清单（含题干、作文、参考评分/批注、图片内容哈希及冻结识图结果），每次续跑在任何请求或跳过完成项之前核对；不同数据用新输出目录。只在最后 compare 校验消息指纹太晚。

证据：[source_probe.json](source_probe.json) 的两个 `*_resume_refuses_changed_source*` 断言；[专项说明](source_review.md)。

### P2-3：盲评缺整行或整侧时，仍被标为完整

`blindtally.py:64–104` 只检查表中现存行，没有预期行清单。空文件、整个乙侧被删，都会返回 `complete=true`；把必须填数字的“其他漏报”改成“参考”也绕过检查。不是空白格处理没修好，而是缺失的格子根本没被检查。

建议：生成盲评表时保存样本/侧别/行 ID/行类型清单，计数前核对完整性；只有生成时指定的参考行才允许不计数。空文件、少行、重复行、缺侧以及漏报数字行改成“参考”均应不完整。

### P2-4：同一条改列建议，在盲评里计了两次

`realcheck_compare.py:210,234` 同一 improvement 同时进入 optional 与 reclassified，`:720,731` 都作为待判行输出。合成正反对照两模型各只有一条相同错误建议，A 经程序改列、B 直接给出可选优化；每个出现位置判②后，统计 **A=2，B=1**。

建议：一条来源反馈只有一个待判 ID，将改列状态和支撑引文合并到那一行，或作为不计数的参考。不能因显示路径不同而给某个模型重复计错。

证据：[metrics_independent.json](metrics_independent.json) 的 `findings`；[专项说明](metrics_review.md)。15 个已有正确契约均通过，但不表示这两项新反例已经修复。

### P2-5：已填盲评会被正常续跑覆盖，旧计数却继续显示完整

`batch.py:337` 即使两边 `.done` 都存在也重写对照；`realcheck_compare.py:836,838` 重新写入空盲评表。合成测试先生成表、填判断与备注并完成 tally，再沿同一 seed 执行 `Batch.run_group`：模型调用为 0，但判断和备注全部丢失；旧 `blind_tally.json` 仍为 `complete=true`，新表重算则为 false。

建议：已完成对照及人工填写的文件默认不可覆盖；确需重新生成时另存版本，并使 tally 明确绑定原表/映射的指纹，变更后失效。不能只判断“续跑没有增加请求”就认为断点续跑正确。

证据：[metrics_resume.json](metrics_resume.json)、[可复现探针](metrics_resume.py)。

## 非阻断的单独限制

单独运行 realcheck 时，不可读题图第一次保留诊断文字，冻结失败后重用却清空该字段。实际模型消息一致，但 compare 把元数据差异判为输入不同。新 batch 会在题图失败时先停，因此不影响其成功路径；记为 P3，建议统一失败识图元数据。来源探针 34/37 中的另一个失败即此项，不要与上述两条续跑断言混为三项批次阻断。

## 验证与复现

在主资料树用 `.venv/bin/python` 运行。完整命令在各专项文件与脚本顶部；所有新探针只操作自己创建的临时目录/进程，不访问真实服务。

```sh
.venv/bin/python docs/design/iwa-batch-recheck-20261111/run_offline_tests.py
.venv/bin/python -B docs/design/iwa-batch-recheck-20261111/runner_parent_lock_probe.py --repo /private/tmp/studytracker-iwa-holdout-review-20261111 --out docs/design/iwa-batch-recheck-20261111/runner_parent_lock_probe.json
.venv/bin/python -B docs/design/iwa-batch-recheck-20261111/source_probe.py --repo /private/tmp/studytracker-iwa-holdout-review-20261111 --output docs/design/iwa-batch-recheck-20261111/source_probe.json
.venv/bin/python -B docs/design/iwa-batch-recheck-20261111/metrics_independent.py --repo /private/tmp/studytracker-iwa-holdout-review-20261111 --out docs/design/iwa-batch-recheck-20261111/metrics_independent.json
```

- **435 Python + 8 Node** 通过；测试运行约 25 秒，临时数据哨兵未写。套件允许回环假 HTTP，禁止外网；探针禁止网络。日志及命令见 `offline-tests.json/log`。
- 独立树 `ruff check tools/ielts_writing_ai`、`black --check tools/ielts_writing_ai`（63 文件）、`node --check tools/ielts_writing_ai/static/iwa.js`、`git diff --check` 通过。
- 作者探针 5/5、6/6；独立指标 15 个正例通过，反例另列；来源 34/37（两条 P2 续跑断言、一条 P3）；父进程探针 exit0 表示证据采集完成，不能当作产品合格。

## 正常附件彩排

11 月 12 日在 Mac 用原本机附件跑通 main、vision 及两阶段正常续跑，13/13 验证通过。第一阶段 92 次文字替身，第二阶段 8 次文字 + 2 次识图替身，13 个运行目录 / 6 个对照组；两次续跑新增请求均为 0。全程 fake、无 Key，网络审计钩子拒绝所有连接。Python 日志能严格按 UTF-8 读取。

私有输出：`/Users/zhouxin/iwa-compare-dry-20261111-batch-recheck/`。命令：

```sh
.venv/bin/python tmp/iwa-batch-recheck-20261111/dry_run.py --repo /private/tmp/studytracker-iwa-holdout-review-20261111
```

本机包装器在 ignored `tmp/`，实际样本及输出不进 Git；仅 [dryrun_metadata.json](dryrun_metadata.json) 导出计数/布尔值。此前彩排目录未覆盖，源材料未修改。正常彩排没有填盲评，P2-5 另用合成表核实。

`dryrun_metadata.json` 的 code_sha256 是产品自带的 Python 源码指纹；`source_state.json` 的 SHA 是全部 89 个跟踪工具文件（含前端/测试/文档）的组合，两种定义不同，不能直接比较。

## 执行与共享状态

本目录只共享数字、合成探针和测试日志；作文原文、题图、模型演示输出、盲评正文和映射继续放仓库外，不提交。两份规范交接同步更新；审阅材料按已有授权仅同步 `claude/ielts-writing-ai-trial`。专项报告中的“仅本机”指子审写入时的状态；根报告统一发布时一并同步。最终提交/推送确认见主回复和本机交接确认条。

本轮不改产品修复，不读 Key，不发送真实请求，不合 main、不部署、不访问生产或数据库，小程序未上传/提审/发布。先修上述执行与测量边界再复验，通过后才确认真实新批次：第一阶段无官方 184 / 有官方 224，第二阶段 16 文字 + 2 识图。当前官方组仍为空模板，旧 B 已并入学生组，不另跑。
