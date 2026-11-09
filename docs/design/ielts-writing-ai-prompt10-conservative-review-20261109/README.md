# `.10` 删除识别重写复验：旧场景通过，保守处理仍有漏洞

源 HEAD `60f17341a14750668a467e802691ec94c418e9c7`，业务 `25188533`，基线 `d783134e`。提示词仍 `iwa-2026-11-08.10`。本轮仅离线复核，不改产品、配置或旧探针；没有读取Key、私有思考或学生资料，没有真实模型、生产或数据库操作。

**上一轮三类问题的全部原反例已关闭。** 七个旧探针原样满分，13个新旧模块对照的当前结果也全部正确，包括173词删后148词的提醒。396 Python、8 Node及lint通过，测试数量变化与移除继承导致的重复执行相符。

新检查遵循作者提出的保守契约：复杂或不支持的表达，**正确数字或明确无法确定都可通过**，没有强求自然语言全覆盖。然而当前仍会在以下六类情况下给错误数字或漏掉本应保留的核对提醒。它们属于动作/目标/引用处理约束的漏洞，不建议继续逐个追加词表。

## P2-1：并列或选择的宾语被截掉，剩余半句被当成已完整解析

`tools/ielts_writing_ai/deletion.py:52–54、192–205`。

- `Delete the final paragraph and the first paragraph.` 应删末段23词及首段18词，172→131，或保守给无法确定；当前只删末段，报149。
- `Delete the introduction and conclusion.` 只算首段，完全不提醒。
- `Delete the final paragraph or the first paragraph.` 未决定删哪一段，却确定报149。

根因：在`and/or`处先截断宾语，后面的目标没有经过清单检查，也没有使整条建议变成不确定。不是白名单缺词，而是未消费的内容被静默丢弃。重复动词 `Delete A and delete B` 的正对照正常；中文`删去最后一段和第一段`返回不确定也被本探针接受。

## P2-2：共享否定丢失，短属性否定又误伤删除动作

`deletion.py:63–65、175–189`。

- `Do not delete the introduction or remove the conclusion.` 两个动作都被否定，当前却把第二个当肯定，报剩149。中文`不要删除首段或删去结尾段`同样。
- `This paragraph is not needed so delete the conclusion.` 明确要求删结尾；当前任意两词窗口将`not needed so`当成删除否定，漏提醒。

重复否定、`but`后肯定、上轮完整句点拆分及较长属性否定的正对照均通过。修复不能仅继续扩大否定词列表；无法确定协调范围时应保守处理整条建议。

## P2-3：超过300字符的完整引用失去遮蔽

`deletion.py:42–44、165–172`。

成对引号里的371字符英文建议以`delete the conclusion because ...`开头，外面明确写`Ignore the advice "…" and keep the conclusion.`。当前引用正则只接受1–300字符，整段引用未被遮蔽，里面的删除命令被当成本次实际操作，追加149词提醒。

直双引号、直单引号、中文双引号及提升重点路径均复现；短引文和正常撇号正对照通过。该建议在评价规范化时没有被截断。长度上限可以限制采纳，但不能让超限引用内部文字重新成为动作；至少整条转成不确定，不得报数字。

## P2-4：局部删词明确指定的句子位置仍被问题引文覆盖

`deletion.py:388–405`，直接原因`:397–398`。

段落限定已修好，但局部删词的sentence分支直接用问题引文定位，未使用first/last/第N句限定。

- `删去最后一段；删去第一句中的“Country A”两个词。` 第一句没有这些词，目标无效；当前仍绑定末句、报149。
- 改成`第三句`，原文第三句确实有另一处Country A，应172−23−2=147，或不确定；当前仍报149。
- 首段加一个clearly后共173词，应删后148或不确定；当前算150，**字数不足提醒消失**。
- 问题引文指向第三句，但建议明确指最后一句时，同样被覆盖。

中英和完整normalize→copy路径均验证；不要求第三句一定能算，明确不确定也算通过。`this sentence`指代和同位置重叠正对照正常。

## P2-5：删除数量被当成位置

`deletion.py:263–287、361–364`。

`Delete two paragraphs.` / `Delete 2 paragraphs.` 没有指定哪两段，却被当成“第二段”，报136。`删去两段` / `删去三个段落`被当没有位置，回退到问题引文的末段，报149。

词元都在清单里，不等于其组合有唯一含义。数量和序号必须区分；无法确定具体多个目标时不给数字。

## P2-6：被清单接受但无法解析的显式序号仍回退

`deletion.py:69–74、244–258、361–364`。

词元`第二十`、`第二十一`会被接受，但`_number`无法转换；`None`再次表示“没有指定位置”，随后回退末段149。原文只有5段，正确应不确定；提升重点没有问题引文时则直接忽略、不提醒。`第十九段`正对照已正确给不确定。

不要求扩充所有中文数词。重点是显式序号无法解析后，必须保留“解析失败”，不能降为“未提供目标”。

## 建议：试用版先停止扩自由文本解析

最小方案是**暂时取消从自然语言建议推算精确剩余词数**：保留原文字数，统一使用条件提示“若采纳删减建议，请核对修改后字数”，不要断言某句要求删除。实际修改稿存在时，再对修改后的正文计数。

如果要保留精确数字，只支持整条建议完整匹配的少量固定句式：单个、肯定、单数的整段/整句删除，位置和引文都唯一；任何未消费文字、并列、选择、条件、未知数量、未完整遮蔽的引用都不报数。**不能先截掉不认识的后半句，再声称已完整匹配。**

以后采用结构化target可减少文本解析歧义，但结构正确和引文真实不等于删除合理，也不证明target与建议语义一致；还会增加当前模型输出格式负担。本轮不建议因此扩大提示词/模型范围，也未实施任何替代方案。

## 实测与边界

| 检查 | 主审独立复跑 |
| --- | --- |
| 原删除/schema/metrics | 189/189、175/175、120/120 |
| 上上轮intent/target | 178/178、112/112 |
| 上轮intent/target | 217/217、128/128 |
| 原baseline_compare | 当前13场景全部符合预期 |
| 新action_probe | 30场景211/242，13失败、17正对照通过，P2-1/2/3 |
| 新location_probe | 26场景173/186，13失败、13正对照通过，P2-4/5/6 |
| 完整套件 | 396 Python（21.113s、wrapper21.33s）+8 Node通过 |
| 代码检查 | Ruff、Black（53文件）、JS语法、diff通过；两个新探针lint通过 |

新探针总计44条失败断言属于上述六类问题，不是44个缺陷。所有输入/原稿和评分不变；探针允许不确定，未把保守提醒当错误。完整套件采用fake模型、临时数据库、剔除外部IWA环境并禁止非回环连接，首次沙箱回环权限失败经允许重跑，外部测试数据目录未被写入。

78个tracked工具文件前后SHA一致：`d7fceb25aaad413622cfc3b2880198ce12f4d9d4efb6acb1ff6617691ff3fbf7`。没有重跑所有43个历史探针、全部locale、Python3.10或浏览器流程；这里验证结果数据和复制文本，不声称真实模型格式或判断改善。

## 复现命令

仓库根目录执行，按实际环境调整PY/REPO；新两个探针当前预期exit1，允许的保守行为已写入断言，不应翻转断言掩盖问题。

```bash
PY=/Users/zhouxin/Desktop/studytracker/.venv/bin/python
REPO=/private/tmp/studytracker-iwa-prompt10-review-20261108
FIRST=docs/design/ielts-writing-ai-prompt10-review-20261108
SECOND=docs/design/ielts-writing-ai-prompt10-recheck-20261108
THIRD=docs/design/ielts-writing-ai-prompt10-finalcheck-20261108
NEW=docs/design/ielts-writing-ai-prompt10-conservative-review-20261109
$PY -B "$FIRST/deletion_probe.py" --repo "$REPO" --output /tmp/iwa10c-old-deletion.json
$PY -B "$FIRST/schema_probe.py" --repo "$REPO" --output /tmp/iwa10c-old-schema.json
$PY -B "$FIRST/metrics_probe.py" --repo "$REPO" --output /tmp/iwa10c-old-metrics.json
$PY -B "$SECOND/intent_probe.py" --repo "$REPO" --output /tmp/iwa10c-old-intent.json
$PY -B "$SECOND/target_probe.py" --repo "$REPO" --output /tmp/iwa10c-old-target.json
$PY -B "$THIRD/intent_probe.py" --repo "$REPO" --output /tmp/iwa10c-previous-intent.json
$PY -B "$THIRD/target_probe.py" --repo "$REPO" --output /tmp/iwa10c-previous-target.json
$PY -B "$THIRD/baseline_compare.py" --repo "$REPO" --output /tmp/iwa10c-previous-baseline.json
$PY -B "$NEW/action_probe.py" --repo "$REPO" --output /tmp/iwa10c-action.json
$PY -B "$NEW/location_probe.py" --repo "$REPO" --output /tmp/iwa10c-location.json
```

完整套件：桌面主树 `.venv/bin/python docs/design/iwa-prompt10-conservative-review-20261109/run_offline_tests.py`。runner/状态与首次沙箱失败日志只留本机；共享`offline-verification.json`、`offline-tests.log`保存命令和成功日志。共享日志仅去掉尾部空行，原始本机日志保留。

## 同步与下一步

审阅树 `/private/tmp/studytracker-iwa-prompt10-review-20261108`，本地 `codex/iwa-prompt10-review-20261108`。本报告、探针和两交接按既有授权仅提交推送`claude/ielts-writing-ai-trial`，最终文档HEAD见git log。主资料树 `/Users/zhouxin/Desktop/studytracker` main `6ded77d2` 原7 modified/23 untracked入口及其他任务资料保留。本轮没有合main、部署、生产访问/写库、小程序上传提审发布。

先决定采用统一条件提示，或把精确计数收缩到完整匹配的固定句式，再复验对应契约。`.10`仍没有新付费调用授权，未开账本、未改16000上限，不继承旧批次余次。老师材料仍待可靠原稿及第5份正确题目。
