# 写作试用 .9 复验：旧数字丢失已关闭，发现先截短再核实的新回归

源码 `80b5dcf6185299a11b1d4a37bfac11f697e5f890`（业务 `b8a7c1ee`），基线 `478461a828575f21fb22798e8bce7260f5fce07b`，提示词仍 `iwa-2026-11-06.9`。本轮仅离线复核，没有改业务、私有配置或调用真实模型。

## 结论

原P2已修复：原始真实输出、展开评语、关键数字调序和四候选情况下，75/80均完整保留，复制一致。30项上限和显式遗漏提示属于已约定的新行为，旧“最多4个”的断言应更新，不能据其失败认定旧缺陷未修。

但新增 **1项P2：完整引文核实退化成只核实前300字符**。建议恢复“先核实完整引用，再处理显示长度”的顺序后复验；目前不建议启动 `.9` 真实批次。本轮没有新的付费授权。

## P2：先截短再核实，使含编造结尾的引用被采用

位置：`tools/ielts_writing_ai/review.py:253–259`。

```python
figure = figure.strip()[:300]
...
if essay_lib.contains_quote(essay, figure):
    kept.append(figure)
```

使用已有合成Task 1作文中的一段真实文字作为前300字符，后接原文不存在的编造结尾，放入该矛盾的唯一 `figures` 条目。整段引用实际不在原文中；新版先丢弃第300字符以后的内容，再核实真实前缀，结果仍采用该矛盾并在复制文本中显示“对照”。基线先核实完整条目，正确丢弃。

影响是**校验未覆盖模型提供的完整引用**，不是编造结尾原样显示：它被截掉，剩余前缀被当作已核实证据。它还会虚增遗漏数：30个真实条目加一条这种无效长引用，本应没有遗漏，却提示遗漏1个；31个真实条目加它，本应遗漏1个，却提示2个。评分项不因这一列表操作直接改变；不能将本例说成分数错误。该路径处理的是模型可自由返回的引用列表，提示词要求短引用不能代替服务端验证。

最小修复：保留完整去空白原串，用它核实原文；通过后才生成显示用短串。保留本轮去重、顺序、最多30项和遗漏提示。不要删去长度反例、改为只校验前缀，或为某个样本加入特例。正反控制包括真实长引用、带编造结尾的长引用、短编造引用及旧版对照。

## 其他检查与边界

- Mac Python3.13.3：371项Python通过（21.202秒，wrapper21.48秒），8项Node通过；ruff、black（51文件）、JS语法和diff检查通过。
- JSON/结构探针82/82、统计探针100/100通过；坏JSON仍拒绝，格式诊断不参与出分，旧输出回放的计数和用量口径不变。
- 证据探针：按新保留契约更新后的原144项全部通过；新增61项中54项通过，7项失败均来自上述同一核实顺序回归，总198/205，exit1。真实长引用仍接受、短伪造引用拒绝、基线拒绝同一伪造长引用均已对照。
- 原评审文件未改；新证据探针只将旧显示约定换为完整去重保留，并保留原缺陷的正向断言，另加新长度顺序反例。
- 页面检查8场景107/107通过，使用真实归一化/接口复制文本、实际 `iwa.js` 的渲染函数和最小DOM替身，验证证据展示、遗漏提示、文本转义及模拟剪贴板内容；不是完整浏览器/布局/真机验收。具体结果见探针JSON。
- 提示词未变，未验证 `.9` 的真实首轮JSON率、短文可用率或评分准确度。未重跑全部locale、Python3.10、31个历史探针或完整浏览器；没有读取Key、私有思考正文、老师原稿或学生资料。
- 完整JSON示例、priorities复用反馈等上一轮建议未实施，不作为本轮新增阻断。

## 复现与交付

本轮便携探针及精确命令、输出见同目录的 `evidence_keepall_probe.py/json`、`ui_evidence_probe.*`、`offline-verification.json`。证据探针使用正确行为断言，新回归仍存在时退出1；JSON和统计复跑的是上一轮共享脚本，输出另存本轮目录。

在仓库根目录复跑（输出到新文件，不覆盖历史报告）：

```bash
python docs/design/ielts-writing-ai-prompt9-recheck-20261107/evidence_keepall_probe.py --repo . --output /tmp/iwa9-keepall.json
python docs/design/ielts-writing-ai-prompt9-recheck-20261107/ui_evidence_probe.py --repo . --output /tmp/iwa9-ui.json
python docs/design/ielts-writing-ai-prompt9-review-20261107/json_shape_probe.py --repo . --output /tmp/iwa9-json.json
python docs/design/ielts-writing-ai-prompt9-review-20261107/metrics_probe.py --repo . --output /tmp/iwa9-metrics.json
```

完整测试本机入口：主树 `.venv/bin/python docs/design/iwa-prompt9-recheck-20261107/run_offline_tests.py`，使用模型替身、临时数据库、屏蔽外部IWA配置并仅允许回环网络；测试设定的外部数据目录未写入。报告日志保留，末尾空行可能为Git格式检查去除，测试内容不改。

审阅树 `/private/tmp/studytracker-iwa-realcheck-review-20261103`，功能分支 `claude/ielts-writing-ai-trial`，从干净478461a8经HTTPS fetch+ff-only到80b5dcf6。主资料树 `/Users/zhouxin/Desktop/studytracker` 仍main6ded77d2，原7 modified/23 untracked入口保留。本机运行器与过程文件在 `docs/design/iwa-prompt9-recheck-20261107/`；共享报告与两份规范交接按既有授权仅推功能分支，最终报告HEAD见git log。未改业务、合并main、部署或操作生产数据库/外部服务/小程序上传提审发布。上一批9/14账本已结束，未用5次不能续用，本轮0次真实请求。
