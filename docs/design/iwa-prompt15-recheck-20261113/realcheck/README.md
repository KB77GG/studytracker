# `.15` realcheck 核图记录修复复验

源码：`/private/tmp/studytracker-iwa-prompt15-recheck-20261113`，分支 `codex/iwa-prompt15-recheck-20261113`，HEAD `8884e9d904a66afea9124339cbbb07f9b36d38fe`（业务 `0701bcf5`），基线 `652450ca`。开始与结束均clean，未改产品、运行配置、服务、账本或历史报告。

结论：**本专项原 2 个 P2、1 个 P3 均关闭；没有发现本次修复引入的相邻路径问题。** 原探针不改预期原样重跑 **15/15**，新增相邻检查 **17/17**。就本专项而言不再阻止升级；实际升级仍需主审合并网页、迁移、其他复核结论，不代表真实识图准确性已验证。

## 原问题逐项关闭

| 原问题 | 修复位置与行为 | 复验 |
|---|---|---|
| P2 JSONL内嵌核对绕过图片/字段校验 | `realcheck.py:203` 拒绝输入中的 `image_check` 和 `image_frozen`；`apply_image_descriptions:394` 在 require-checked 下也拒绝无题图样本；`run:468` 在构造客户端/Recorder前再次核对字段、题图SHA、读数SHA | 三个原反例均exit2，0 fake文字请求，不再有TA；含只有`status=confirmed`和无图+require-checked场景 |
| P2 确认后改读数仍当已核对 | `imagecheck.py:171` 保存最终原串UTF-8 SHA；`check_problem:59`比对正文；`verify:64`连同图片检查；`prompts.visual_available:355`在提示门槛再校验 | 原40→90反例请求前拒绝，0调用；缺hash同样拒绝；原始读数及改正后文本各自保持 |
| P3 核对人/时间不同被当模型输入不同 | `realcheck_compare.py:58`只记录实际是否为有效确认；核对人/时间及原始模型读数不再进入该部分指纹 | 原相同messages、不同by/at对照被允许；最终读数改变和确认/未确认区别仍改变指纹 |

未改原探针以适配新行为；旧报告与旧代码树保留。`evidence.json`可与上一轮10/15逐项比较。

## 相邻路径（17/17）

- 未改读数：`edited=false`，hash等于实际原串UTF-8 SHA，原raw对象不变。
- 改正后：hash对应最终文本，原模型读数仍保留在审计字段。
- 核对文件正常载入后，再改内存中的读数或磁盘题图：`realcheck.run`在任何调用前拒绝。
- 两篇计划中第二篇记录无效：整次run在第一篇发请求前拒绝，0调用。
- 缺reading hash、存储正文变化：提示层也不再把读数视为可用。
- 相同读数不同审计元数据指纹相同；真实输入变化仍区分。
- 显式要求已核对但样本没有题图：拒绝。

## 精确命令

```bash
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -B \
  /Users/zhouxin/Desktop/studytracker/docs/design/iwa-prompt15-review-20261113/realcheck/probe.py \
  --source /private/tmp/studytracker-iwa-prompt15-recheck-20261113 \
  --out /Users/zhouxin/Desktop/studytracker/docs/design/iwa-prompt15-recheck-20261113/realcheck/evidence.json

/Users/zhouxin/Desktop/studytracker/.venv/bin/python -B \
  /Users/zhouxin/Desktop/studytracker/docs/design/iwa-prompt15-recheck-20261113/realcheck/adjacent_probe.py \
  --source /private/tmp/studytracker-iwa-prompt15-recheck-20261113 \
  --out /Users/zhouxin/Desktop/studytracker/docs/design/iwa-prompt15-recheck-20261113/realcheck/adjacent-evidence.json
```

均exit0。新增脚本Ruff/Black通过。`source-state.json`记录产品文件和旧探针SHA、HEAD及clean状态。

## 范围与限制

全部使用临时目录、合成文本/图片和FakeClient，socket连接禁止；0真实请求，未读取Key、私有学生原稿或运行库。未测真实图片准确性、付费模型或生产。批量对照仍没有核图阶段，所以Task1只出语言评价，是作者明确保留的限制；官方手工分阶段命令走已核对文件。

核对哈希用于检测确认后正文漂移，不是证明核对人判断正确的认证。继续遵守“看错则对照原图改正、重新确认后再评；看不清或拿不准不确认”。旧批次不自动重开。

报告及探针仅本机新增，未commit/push/deploy；规范交接由主审统一更新，本子任务未改两份交接。
