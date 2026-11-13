# `.13` 离线复核：段落与识图默认路径通过，抄题处理暂不通过

复核 `ac95392d` / `fdf4704ee3ec1aa80aad5e5e9d59f04a6edbc380`，基线 `9c60a347`。**2 个 P2 均涉及抄题处理，另有 1 个非法识图配置的 P3。未调用真实模型。** 不把 `.13` 切到现有试用服务，不改本机 `.env`，也不启动尚未授权的 Task 1 批次。

## 已确认通过

- 460 项 Python、8 项 Node 在本机 Python 3.13.3 下通过；Ruff、Black（66 文件）、JS 语法、`git diff --check` 通过。首次沙箱因禁止本机回环服务产生 24 个错误；同一离线 runner 获准在沙箱外运行后全通过。runner 移除外部 IWA/代理变量、使用临时 fake 配置并禁止非回环网络，外部数据目录哨兵未被写入。没有再跑多 locale、Python 3.10 或全部历史探针。
- **段落修复**：本轮之前的两次真实回答离线回放，P1–P9 全部保留，分数仍为 5.5/5.0。各次条目 `returned=kept=15`，不再有段落超限。20 段、重复段、错误段号定位及问题/优化条数上限通过；复制文本及真实 JS 渲染函数的 DOM 替身检查保留全部9段，旧结果缺少新字段仍可显示。不是完整浏览器端到端复测。
- **识图默认路径**：DeepSeek Flash、thinking disabled、2000 token、180 秒及覆盖值3000/240正确传入请求；评价仍 Pro/high/32000/420，精修改写仍 Flash。八类失败每种仅一次尝试，失败记账且同账本重跑0新增。模拟在 urllib opener 层拦截，未连接真实模型；作者本地HTTP桩测试也随全套通过。与 [DeepSeek 官方识图格式](https://api-docs.deepseek.com/guides/vision/) 一致，真实图表读数准确性尚未验证。
- **已有样本兼容**：7 篇开发样本及本机5份JSONL中的23篇材料，新旧实际评价 messages 逐项完全相同，均未触发抄题；5个文件SHA未变。版本不同仍不能绕过比较工具的版本保护；这是输入未变的事实，不是重新证明模型质量。

## P2-1：相似句被当成整句抄题，排除了新增观点

位置：`essay.py:210–235`、`prompts.py:412–425`、`review.py:399–412`。

检测只看词序相似度，却把整个句子的内容和语言全部排除。以下探针全部为自写合成内容：

- 题目只说明图表展示某地通勤方式比例，并没有给出升降趋势。
- 学生自写概述句借用了这些名词，同时明确说汽车比例上升。程序仍把包含新趋势的整句14词判抄题；换成相反的下降也命中。
- 一篇原本 **152 词** 的完整 Task1，经此处理传给模型的有效词数变成 **138**；结果加低于150词的警告，`copied_note` 明令不给这句话内容及语言记分。
- Task2 在题干观点中加否定表达反对立场，也会整句排除。

这是已复现的请求/提示错误；没有用真实调用去声称它一定导致多少分变化。不能把它当作无害的“文字相似提示”。`copy_probe.py` 的17/17表示这些行为可复现，**不表示产品通过验收**。

## P2-2：原本要修的官方样卷仍漏掉16词抄题

旧批次原稿、题目、原始回答未改。用户转录与已确认的官方批注表明，开头两段是抄题，按同一空白分词法为 **34词**；原文228词，排除后 **194词**。

新规则实际只认出两句共 **18词**，向模型发送 **210词**。漏掉的中间句16词，正则分为17 token，匹配14个（82.35%），低于85%阈值。两次回放均如此。公开证据只记录词数、比例、哈希，不提交作文/引文。

因此“容许本篇拼写差异、已识别3句”的合成测试不能替代这篇实际输入验证。降低阈值会扩大 P2-1 的误判，不能只为这篇调到82%。这是另一个方向的真实缺口，不是新增需求。

## P3：非法识图超时未在配置阶段拒绝

`config.py:303` 接受 `IWA_VISION_TIMEOUT=inf`，`validate()` 通过，底层 socket 超时转换抛出未捕获 `OverflowError`，realcheck 中止；`0` 实际回退文字默认120秒但摘要仍显示0，`-1/nan` 被归为 `invalid_response`。

默认180与合法覆盖240均正常。**未观察真实超额或实际网络错误**；是非法配置的本地模拟边界。建议加载时校验有限且大于0，并在发请求/预留预算前拒绝，不必重写已通过的默认识图请求逻辑。

## 给 Claude 的建议

1. 保留已通过的全部段落与 DeepSeek 识图适配。
2. **相似比对仅作待确认线索，不据此整句扣字数或禁止计分。** 已确认的抄题用明确原文区间/来源标注表示；用户原稿保持只读，展示原始词数和有确认依据的排除词数。自写的新观点、趋势、否定或数据不能因共用题干名词被整句排除。官方要求不认可抄题，不等于认可任何相似度阈值。[官方样卷与考官评语](https://ielts.org/cdn/Sample-tests/ielts-academic-writing-sample-tasks-2023.pdf)
3. 把本报告的两个方向都做成回归：152→138不应发生；已确认的34词不能只标18。避免继续补关键词或只调整阈值。
4. 合法识图请求路径无需再改；补有限正超时校验即可。复核关闭后再更新本机服务、配置识图，然后单独授权一张题图验证。旧Task2批次已结束，不续用余额；本轮没有16文字+4识图的新授权。

## 可复现命令与证据

以下均从 `/Users/zhouxin/Desktop/studytracker` 执行，不调用付费模型：

```bash
.venv/bin/python -B docs/design/iwa-prompt13-review-20261113/run_offline_tests.py
.venv/bin/python -B docs/design/iwa-prompt13-review-20261113/copy_probe.py \
  --source /private/tmp/studytracker-iwa-prompt13-review-20261113 \
  --out docs/design/iwa-prompt13-review-20261113/copy-evidence.json
.venv/bin/python -B docs/design/iwa-prompt13-review-20261113/vision_probe.py \
  --source /private/tmp/studytracker-iwa-prompt13-review-20261113 \
  --out docs/design/iwa-prompt13-review-20261113/vision-evidence.json
.venv/bin/python -B docs/design/iwa-prompt13-review-20261113/paragraph_probe.py \
  --repo /private/tmp/studytracker-iwa-prompt13-review-20261113 \
  --private-run /Users/zhouxin/iwa-compare-official-lowband-20261113/official-t2/run_data.json \
  --samples-dir /Users/zhouxin/iwa-calibration \
  --output docs/design/iwa-prompt13-review-20261113/paragraph_probe.json
```

- `copy-evidence.json`：17/17复现，1个P2；全部合成材料。
- `vision-evidence.json`：24/24检查，默认路径通过，另列非法配置P3。
- `paragraph_probe.json`：58/60；失败的两项恰为两次实样的18/210与34/194不符，exit1应保留。其余段落、UI/copy、计数、兼容、30篇消息比对均通过。两个agent探针均由主审独立复跑。
- `offline-tests.json/log`：460 + 8通过；只有 fake/本地回环服务，不读真实Key。

## 工作树与当前运行状态

- 新复核树 `/private/tmp/studytracker-iwa-prompt13-review-20261113`，分支 `codex/iwa-prompt13-review-20261113`，从 `origin/claude/ielts-writing-ai-trial@fdf4704e` 新建。只加脱敏复核与交接，不改产品。
- **原运行树保持** `/private/tmp/studytracker-iwa-holdout-review-20261111`、`codex/iwa-holdout-review-20261111@9c60a347`，不快进、不重启；产品仍`.12`。沙箱外状态核对 PID68530、5055 health ok。沙箱内曾因进程身份不可读误报PID不可信，不能据此认定服务停止。
- 实际私有配置仍评价Pro/high/32000/420、精修改写Flash，vision none；未改Key、账号或额度。**代码支持识图，不等于本机已配置/实测识图。**
- 主树 `/Users/zhouxin/Desktop/studytracker` 仍main6ded77d2、原7modified/23untracked入口保留；本轮只新增本复核目录和更新两交接。
- 按已有同步约定只把脱敏报告和两交接提交推功能分支，最终提交号以Git/主树同步确认条为准；完整原稿、回答、思考、Key/配置仍仅本机。无main合并、生产访问/数据库写入、部署、小程序上传/提审/发布。
