# `.10` 条件字数提醒复核通过；思考输出上限提高到32000

2026-11-09。审阅源 `e5ae8308e96aabca609a601eabaf5ce25592ec14`，删除提醒业务 `23a8b031`；本轮按用户“调高”新增预算改动 `ab984f68`。提示词仍 `iwa-2026-11-08.10`。没有真实模型调用、私有配置读取或生产操作。

## 复核结论

新的约定可以通过本轮离线复核：程序不再识别删除对象、不推算删后字数，只在提到删除且字数接近下限时附条件提示，列出原文字数和下限。原建议保留；否定或引用中的删除内容得到条件提示，是已经接受的取舍。

独立 `reminder_probe.py` 经主审复跑 **341/341**，没有确认的缺陷：

- 21种建议分别通过评分项和提升重点两条路径：普通中英删除、and/or并列、共享否定、长引用、明确句子局部词语、删除数量、无法解析的序号等；上轮六类误算都不再出现。
- 示例句 `can cut traffic`、`dropped sharply`、`can remove barriers`，以及改写、精简、压缩建议不误触本轮对照。
- Task 2论证问题和可选优化也能附提示；条件中的Task1原文172/下限150、Task2原文97/下限250准确。
- 5组段落长度控制确认仅在既定门槛下附提示；等于门槛时也提醒，是可接受的保守边界。
- 原稿/输入/分数不变，原建议完整保留，结果与复制一致；旧的 `analyse` / `_deletion_target` 已移除。

**结论范围**：不声称覆盖所有中英文表达。这里保证的是程序追加的文字不推算剩余词数，模型原建议自身若虚报数字，仍须按其他规则或人工核查。也不声称条件提示证明实际存在删除意图。

## 调高的范围

- `config.py` 的Settings默认和环境加载缺省值均从16000改为 **32000**；README和`.env.example`同步，业务提交 `ab984f68`。
- 该预算是思考与正式回答的总输出上限，high/max共用；不切换思考档位，默认仍off。下一批原计划仍是high；非思考评价4500、精修、改写、300秒网络超时都未调整。
- 2026-11-07 weak曾耗尽16000且无正文，提高到32000是给正文留余量的尝试，不证明已经解决截断或评分问题。
- 已核对[官方Chat Completions文档](https://api-docs.deepseek.com/api/create-chat-completion/)：32000在max_tokens允许范围内；[思考模式文档](https://api-docs.deepseek.com/guides/thinking_mode/)区分thinking开关和reasoning_effort。
- **显式配置仍优先**：没有读取或更改任何私有`.env`。若现有环境写死16000，它仍覆盖默认。未来获授权验证应显式设置 `IWA_EVALUATE_THINKING_MAX_TOKENS=32000`，以check和实际请求报告为准。本轮没有打开新付费账本。
- 真实HTTP客户端在本地替身服务器发送32000的正文已核对，realcheck记录/报告预算也是32000；自定义预算覆盖、off和精修/改写隔离仍通过。历史16000截断样本保持原样。

## 验证

| 项目 | 结果 |
| --- | --- |
| 完整Python套件 | 383通过，21.232秒（runner21.52秒） |
| Node草稿测试 | 8通过 |
| 新条件提示探针 | 341/341 |
| `.10`结构探针（未改） | 175/175 |
| 指标探针新契约副本 | 120/120 |
| Ruff / Black / JS语法 / diff | 通过，Black53文件 |

指标探针原件未修改。新副本仅将两条寻找旧提示的断言改为条件文案，观察字段也改为原文字数/下限/新提示次数，其余118条原检查保留。首次副本把顶部汇总也算入逐条提示，119/120；修正探针定位后120/120，并没有改变产品来迎合测试。新副本不要求恢复已经取消的精确数字。

完整套件使用fake模型和临时目录，剔除外部IWA环境，审计钩子阻止非回环连接。首次沙箱限制本机端口，获准用同一隔离runner重跑通过，外部测试数据目录未写。运行时macOS/Python3.13.3；没有重跑全部历史探针、三locale、Python3.10或浏览器全流程。

## 复现

```sh
PY=/Users/zhouxin/Desktop/studytracker/.venv/bin/python
REPO=/private/tmp/studytracker-iwa-prompt10-review-20261108
D=docs/design/ielts-writing-ai-prompt10-reminder-review-20261109
$PY -B "$D/reminder_probe.py" --repo "$REPO" --output /tmp/iwa-reminder.json
$PY -B "$D/metrics_reminder_probe.py" --repo "$REPO" --output /tmp/iwa-reminder-metrics.json
$PY -B docs/design/ielts-writing-ai-prompt10-review-20261108/schema_probe.py --repo "$REPO" --output /tmp/iwa-reminder-schema.json
```

完整隔离命令在主资料树：`.venv/bin/python docs/design/iwa-prompt10-reminder-review-20261109/run_offline_tests.py`。本机runner/源状态/初次沙箱日志未提交；成功日志和验证JSON在本共享目录。测试时的e5ae8308加4文件改动与已提交ab984f68逐文件哈希一致。

## 交接和发布状态

工作树 `/private/tmp/studytracker-iwa-prompt10-review-20261108`，本地分支 `codex/iwa-prompt10-review-20261108`。开工clean d5dfbfc8经HTTPS fetch/ff-only至e5ae8308。本轮业务4文件及本目录8文件、两交接按已有约定同步功能分支 `claude/ielts-writing-ai-trial`，最终文档HEAD见git log。

主资料树 `/Users/zhouxin/Desktop/studytracker` 仍main `6ded77d2`，原7 modified/23 untracked入口保留，只增加本轮资料及两交接记录。main未合并/推送，未部署、未访问生产或生产DB，小程序未上传/提审/发布。

下一步可进入`.10`真实验证的授权环节，建议新账本7篇合成作文、只评价、deepseek-flash/high/32000、最多14次，300秒超时；这是待授权方案，本轮“调高”只执行了配置与离线验证，没有据此调用模型。老师素材仍待可靠原稿和第5份正确题目。
