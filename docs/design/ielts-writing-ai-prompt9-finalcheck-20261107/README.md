# 写作试用 .9 最终离线复验通过

源码 `f919067850cbe5fc7ebcaa4fdc2bf10633faeef7`，业务修复 `600938c3`，基线 `073963588cbfce286fb01798dd7feba869070ef8`，提示词仍 `iwa-2026-11-06.9`。

本轮限定复验通过：关键证据被截掉的问题，以及先截短再核实完整引文的回归，都已关闭。没有发现本次改动范围内的遗留阻断。本轮未修改业务、默认档位或私有配置，未调用真实模型。

## 验证结果

| 检查 | 本机结果 |
|---|---:|
| 完整Python套件 | 373/373（21.419秒） |
| Node草稿测试 | 8/8 |
| 独立数字/引用/兼容证据探针 | 205/205 |
| 页面与复制DOM探针 | 107/107，8场景 |
| JSON结构/严格解析探针 | 82/82 |
| realcheck统计/结果接入探针 | 100/100 |
| Ruff、Black（51文件）、JS语法、diff检查 | 通过 |

上述探针均使用此前已提交的脚本，**没有为了本次通过而改断言**。输出写入新目录，历史报告不动。JSON探针有意传入坏类型时的TypeError/AttributeError日志属于预期拒绝，退出0，不是未捕获异常。

## 修复确认

- `_evidence_figures`使用完整去空白原串生成去重key，完整核实成功后才加入已核实列表并截至300字符显示。
- 真实355字符引用照常接受；真实300字符前缀加编造结尾被拒；唯一对照无效时，矛盾条目不采用，复制无对照。
- 30个真实数字加伪造长引用，遗漏数为0；31个加伪造长引用，遗漏数为1。无效引用不再计入遗漏数。
- 全部保留、模型顺序、去重、30项上限、显式遗漏提示，以及原始/展开comment的75/80关键证据均保持。
- 评分项、argument引用和claim的相关路径已只读核对，都是完整核实后再显示截短，没有发现相同的顺序问题。
- 页面/复制验证实际后端归一化与复制路径，以及实际 `iwa.js` 函数体；DOM和剪贴板是测试替身，**不等于真实浏览器/CSS布局/系统剪贴板验收**。

## 复跑命令

在仓库根目录运行，使用已安装试用依赖的Python，输出写到新文件：

```bash
python docs/design/ielts-writing-ai-prompt9-recheck-20261107/evidence_keepall_probe.py --repo . --output /tmp/iwa9-final-evidence.json
python docs/design/ielts-writing-ai-prompt9-recheck-20261107/ui_evidence_probe.py --repo . --output /tmp/iwa9-final-ui.json
python docs/design/ielts-writing-ai-prompt9-review-20261107/json_shape_probe.py --repo . --output /tmp/iwa9-final-json.json
python docs/design/ielts-writing-ai-prompt9-review-20261107/metrics_probe.py --repo . --output /tmp/iwa9-final-metrics.json
```

均应退出0。精确命令和结果见 `offline-verification.json`；额外只读审查见 `reviewer_notes.json`。

本机完整测试入口：主资料树 `.venv/bin/python docs/design/iwa-prompt9-finalcheck-20261107/run_offline_tests.py`。fake模型、临时SQLite、剔除外部IWA配置、仅回环网络；故意设置的外部数据目录没有被写入。使用Python3.13.3；未重跑全部locale、Python3.10或所有33个历史探针，没有真实浏览器全流程。

## 下一步及限制

本次结论是**程序修复通过**。完整引文能在原文找到，不等于批评成立；本轮没有 `.9` 真实JSON率、误批/漏报率或评分准确度的新结论。此前提出的完整合法JSON示例、priorities从已采用反馈选择等建议未在本次实施，不作为此修复的阻断。

可进入下一批真实验证的授权阶段，建议条件明确为：当前 `.9`、deepseek-flash、high、7篇内置合成作文、只做evaluate、新账本、总计最多14次实际HTTP、每次最多16000输出token；不含精修、改写、识图、其他模型/档位或老师素材。重点看首轮JSON率、短文最终可用性和Task1反馈。**本离线报告不代表已获授权或已运行**；真实运行状态以独立批次账本与最新交接为准。旧 `.8` 的9/14已结束，未用5次不续用。

审阅树 `/private/tmp/studytracker-iwa-realcheck-review-20261103`，功能分支 `claude/ielts-writing-ai-trial`，从干净07396358经HTTPS fetch+ff-only到f9190678。主资料树 `/Users/zhouxin/Desktop/studytracker` 仍main6ded77d2，原7 modified/23 untracked入口保留。本机运行器/过程文件在 `docs/design/iwa-prompt9-finalcheck-20261107/`；共享报告与两份规范交接按既有授权只推功能分支，最终文档HEAD见git log。未改业务、合并main、部署或操作生产数据库/外部服务/小程序发布；没有读取Key、私有思考正文或老师材料。
