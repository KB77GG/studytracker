# Flash / Pro 执行包离线复核（2026-11-11）

**结论：常规彩排通过，付费执行条件未通过。真实模型请求 0 次。** 本轮按“先离线复核和彩排，确认无问题再跑真实调用”执行；未修改产品、提示词或执行脚本来掩盖失败。以下是程序复现，不是新一批模型质量报告。

## 基线与本机材料

- 审阅树：`/private/tmp/studytracker-iwa-holdout-review-20261111`，分支 `codex/iwa-holdout-review-20261111`，被审源码 **76ab483fe0c944c1c7c0164cdf53d2bca9f1bbd7**；本报告提交后 HEAD 会变化，工具源码未改。
- 主资料树：`/Users/zhouxin/Desktop/studytracker`，main **6ded77d2**，原 7 modified / 23 untracked 顶层入口保留。本轮没有从该脏工作树 pull、切分支或发布。其他旧 IWA 树 47ccd240 / 817c4c4b 保持不动。
- 用户 ZIP SHA256：`e5c7c9f08cc0f76f347a6c7dfae2eb88eda26e6311b919cfcefca7d55fe301db`。已校验 CRC、路径、无链接、六个 JSONL 的约定 SHA；解压 **9 个文件**到仓库外 `/Users/zhouxin/iwa-calibration/`，目录私有权限、文件0600，没有覆盖不同内容。
- 实际加载23篇有正文材料（学生1、双评委Task2四篇、Task1两篇、排序10、低分合成6）；70条批注引文通过现有定位校验，两张图存在。只有quote/note，没有逐条“双评委共同指出”的来源标签，不能把全部清单当作两位评委一致结论。未取得机构原始PDF，不能据此确认提取准确。
- 官方模板5篇正文为空、加载会拒绝；没有生成 `official.jsonl`。本次附件没有官方PDF；此前下载的网上出版物未作整篇逐字复制。本轮不把官方组占位文本当作真实答卷。
- 演示原始输出、作文、评语、日志及盲评映射仅在 `/Users/zhouxin/iwa-compare-dry-20261111-review/`；本目录只有数字、校验状态、合成探针与审阅说明。未读取真实Key或配置，未发送学生/机构内容到模型。

## 需要先修复的事项

| 优先级 | 复现结果 | 必须达到的行为 |
|---|---|---|
| P1 | 请求只在内存/最终报告中记账；5次模拟请求后中断，重启按0计，总数189/184；两个实例同时进入，总数212/184 | HTTP前持久预留并fsync、全批次互斥、恢复核对源码/输入/条件；未知结果的预留也占用额度 |
| P1（第二阶段） | 两张图重复轮次识图，实际4次识图+4次文字，虽未超Flash总额10却超识图子额2 | 单独锁定文字/识图额度，每图仅识别一次并冻结成功或失败状态 |
| P2 | 首轮图不可用、次轮成功，Flash与Pro的同篇输入不同，4次评价后才拒绝对照 | 在两个文字模型运行前冻结同一份图信息；不可用则停止或两边一致处理 |
| P2 | 每组全部评价校验失败仍exit0，十个模型/组步骤全跑、全写.done | 按计划样本分母检查最终失败率；超过一半按说明停机 |
| P2 | 原生Mac bash3.2输出非法UTF-8、阶段/退出码丢失 | 裸变量统一加花括号；正常与异常路径均严格解码验证 |
| P2 | 盲评表遗漏矛盾另一引文、需人工确认、段号、立场/备注、改列支撑与计数更正 | 匿名表完整呈现判断依据和程序限定语 |
| P2 | 评委差距算全部样本，AI差距仅算出分样本，最小例子可反转结论 | 同时给全体/同集合参照；用于比较的差距使用同一组行，失败率单列 |
| P2 | 最高/最低标称档失败时偷换端点，甚至仅一档出分也给跨度0 | 原计划端点缺失时null；幸存档跨度如保留则另命名并标明实际档位 |
| P2 | 当前4次/0.04元+已归档20次/0.20元，摘要仍只报4次/0.04元 | 质量只看最终采用运行；调用和费用计全部尝试，包括未完成历史 |

此外：漏报计数把 `0.5` 截成0、`1–2`截成1，应整格验证非负整数；“纯数字”导出整份复制teacher对象，合成附加文字能进入JSON，应白名单取分数字段。本次附件teacher键均为分数字段，**没有观察到本批真实泄露**。

详细行号、反例与修复边界见 [runner_review.md](runner_review.md)、[metrics_blind_review.md](metrics_blind_review.md)、[source_review.md](source_review.md)。不建议继续扩张反馈关键词规则；先修请求记账和对照测量本身。

## 已通过的检查

- 产品 **415 Python / 8 Node** 通过。第一次沙箱禁止回环服务产生22个错误；同一隔离runner经批准复跑通过，415项耗时21.503秒（外层21.68秒）。fake/临时SQLite，禁止非回环连接，外部哨兵数据目录未写。没有重跑多locale或Python3.10。
- Ruff、Black（60文件）、JS语法、bash语法、`git diff --check`通过。语法通过并不排除Mac运行时编码问题。
- 原百分点探针 **33/33**：0差、精确小数差两个旧P2已关闭。请求条件与标记隔离探针14/14：high/32000/300、严格JSON、零传输重试正确；老师分数、评语、批注不进入实际模型消息。
- 实际附件配合fake完整彩排：第一阶段10个模型/组运行共92次替身调用；第二阶段2个运行8次文字+2次识图替身；共12个run、6组compare。全部exit0、所有评价ready；正常完成后重跑两阶段均跳过，不增加替身调用。官方组跳过。全部输出在私有目录；四次主脚本日志都复现UTF-8损坏。
- **这些结果不能当评分准确率。** fake只验证程序通路；合成边界探针exit0表示完成复现，不是缺陷验收通过。

## 精确复验命令

从主资料树运行（不读真实配置、不联网）：

```sh
.venv/bin/python docs/design/iwa-holdout-execution-review-20261111/run_offline_tests.py
.venv/bin/python -B docs/design/iwa-holdout-execution-review-20261111/runner_probe.py --repo /private/tmp/studytracker-iwa-holdout-review-20261111 --out /tmp/iwa-runner-probe.json
.venv/bin/python -B docs/design/iwa-holdout-execution-review-20261111/runner_realcheck_probe.py --repo /private/tmp/studytracker-iwa-holdout-review-20261111 --out /tmp/iwa-cli-probe.json
.venv/bin/python -B docs/design/iwa-holdout-execution-review-20261111/metrics_blind_probe.py --repo /private/tmp/studytracker-iwa-holdout-review-20261111 --out /tmp/iwa-metrics-probe.json
.venv/bin/python -B docs/design/iwa-holdout-execution-review-20261111/source_probe.py --repo /private/tmp/studytracker-iwa-holdout-review-20261111 --out /tmp/iwa-source-probe.json
```

产品检查在独立树运行：

```sh
/Users/zhouxin/Desktop/studytracker/.venv/bin/ruff check tools/ielts_writing_ai docs/design/ielts-writing-ai-model-comparison-plan-20261110/*.py
/Users/zhouxin/Desktop/studytracker/.venv/bin/black --check tools/ielts_writing_ai docs/design/ielts-writing-ai-model-comparison-plan-20261110/*.py
node --check tools/ielts_writing_ai/static/iwa.js
/bin/bash -n docs/design/ielts-writing-ai-model-comparison-plan-20261110/run_comparison.sh
git diff --check
```

本机彩排包装器 `.tmp/iwa-holdout-review-20261111/dry_run.py` 清除外部IWA/代理、设置不存在配置/fake、禁止所有socket连接，使用 `/bin/bash` 和实际私有附件。它拒绝覆盖已有输出，所以不应原样重复建立同名目录。包装器/解压器和私有结果不提交；报告数字见 `dry-run.json`、数据结构校验见 `data-audit.json`。

## 下一步及授权状态

先按上述反例修复执行与指标，再复核；不自动提高额度或降格验收。原说明第0节要求付费前另行确认具体上限，目前没有对此新上限的直接确认，本轮未建付费账本。

官方组仍空时第一阶段计划上限184，若有效加入官方组为224；第二阶段16文字+2识图另计。待程序安全条件通过后再请用户确认实际范围。旧单篇B不另行执行，以免和本次学生组重复。成本8–15元是估算，不是脚本实施的金额硬限。

本轮仅将脱敏审阅文档/数字/合成探针及两交接同步功能分支；没有合并main、部署、生产数据库操作、小程序发布、模型调用或真实配置更改。
