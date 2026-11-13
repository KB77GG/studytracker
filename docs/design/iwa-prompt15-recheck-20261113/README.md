# `.15` 修复复验：4项关闭，旧记录排队后仍可补确认（余1P2）

## 本轮续核：远端无新修复，P2再次复现

收到用户转贴的 Claude 总结后重新核对：`git fetch origin claude/ielts-writing-ai-trial` 成功，`git rev-parse origin/claude/ielts-writing-ai-trial` 仍为 `8884e9d904a66afea9124339cbbb07f9b36d38fe`。贴文对应已经复验的 `0701bcf5 / 8884e9d9`，不是剩余排队场景的后续修复；两轮作者交接的事实已在本机规范交接中归并，无需重复覆盖。

原 `mixed_queue_probe.py` 未改预期再次运行，仍 **15/20、exit1**，confirm/skip 在重新排队后均错误返回202；新评价为 `.15`、原精修/改写仍 `.14` 且结果不变。独立只读审查也确认页面与原子写库都仅判断任意queued，作者测试只覆盖直接确认旧完成记录。本轮没有重跑上一轮492Python+8Node及其他已通过探针，也没有重新读取官方私有实样或认证真实服务健康。

新证据与精确命令见 [followup/README.md](followup/README.md)。保留 `.14` / vision none 的既有运行设置，未升级、未读改真实配置/数据库、未重启、0付费调用；旧账本保持closed。仍需 Claude 提供针对排队场景的新修复，通过后才升级本机试用。此续核及两交接仅本机，未commit/push/deploy；先前22文件ZIP未重新打包，不包含本次续核。

## 结论

固定复核 `8884e9d904a66afea9124339cbbb07f9b36d38fe`（业务 `0701bcf5`）。原5项问题中，读数指纹、JSONL入口校验、对照元数据、畸形请求4项关闭。旧完成记录的直接confirm/skip现已拒绝，但**正常点击重新生成、任务排队时仍会重新开放核对入口**，导致同一记录的新读数与旧精修/改写混用。因此该旧结果P2尚未完全关闭，暂不切换本机试用服务。

没有新增真实调用；未改变代码、配置、数据库、试用服务或生产。当前试用仍沿用上一轮`.14`/vision none状态，本轮未重新认证其在线健康。用户“读错先改正、确认后继续”的偏好保留；关闭的账本不重开，新批次范围/上限未在本轮授权。

## 唯一尚未关闭项

位置：`tools/ielts_writing_ai/web.py:427`、`storage.py:357–367`。页面判断和写库都只要求“存在任意 queued 生成”，这不是“首次生成前等待核对”。

真实调用路径的离线复现（合成数据/假模型，无直接DB修改）：

1. 用`.14`创建三个结果均完成的带图记录，再由新代码打开。
2. 此时旧记录标签正确，confirm/skip均409。
3. 另一个普通提交占住默认的两个后台worker。在旧记录点击“重新生成评价”，新attempt进入queued。
4. 旧记录变成`awaiting_check=true`、`unchecked_legacy=false`。改正读数140→160并confirm，或者skip，都返回202。
5. 新评价按`.15`生成，原`.14`精修/改写的ID与完整结果没变，但整份记录已失去“未经核对的旧结果”提示。

新探针 `web/mixed_queue_probe.py` **15/20、exit1**，5个失败都属于这一P2；主审已用原旧探针和作者适配探针分别seed，均复现。不是篡改数据库制造状态，也不是只有单worker才发生；仅用公共API与实际双worker调度。

建议沿用作者已选产品规则：旧记录始终不可补确认，需重新提交。用首次流程的持久状态或全部生成历史判断，并在原子写库处使用同样条件。不要只把“有queued”改成“当前三个都queued”而忽略历史attempt；重新生成不应改变旧记录身份。新提交首次等待、skip、重启和正常再生成须继续通过。

范围限制：未证明分数一定改变，只证明新读数与两份旧输出错配。没有发现额外请求越限；当前本机原空作文库的存量状态本轮未读取，不能声称真实学生已受影响。

## 验证结果

| 检查 | 结果 |
| --- | --- |
| 完整套件（外部故意设`IWA_VISION_PROVIDER=none`） | **492 Python + 8 Node通过**，原CLI环境隔离问题关闭 |
| 原realcheck反例，预期未改 | **15/15**（原10/15） |
| 新realcheck相邻检查 | **17/17**：载入后改图/文本、第二样本坏记录均首调用前拒绝；同审计异元数据可比、真输入改变仍区分 |
| 作者网页适配探针 | **45/45**，只改旧完成记录的正确409预期，原38项未削弱 |
| 新网页排队探针 | **15/20**，5失败同一个剩余P2 |
| Mac官方实样确认探针 | **70/70**，34抄题/194自写正确 |
| 原段落探针 / 独立token迁移 | **70/70、22/22**，原9段和既有结果保持 |
| 识图/预算探针 | **139/139**，0网络尝试 |
| 升级流程静态核查 | **9/9**，未实际升级/读真实配置 |
| 静态检查 | 产品Ruff、Black69文件、JS；新报告Python脚本Ruff/Black通过 |

全套在本机Python3.13.3运行，先因沙箱禁回环端口出现24错误，获准在沙箱外同脚本复跑后492通过。包装器清继承IWA/代理、使用临时目录、禁止非回环连接，保留none覆盖验证新增CLI测试隔离；临时数据哨兵未写。未重跑三locale、Python3.10、全部历史probe或真实浏览器，不把作者浏览器结论当作本机重新验收。

命令：

```bash
.venv/bin/python -B docs/design/iwa-prompt15-recheck-20261113/run_offline_tests.py
```

剩余P2的可移植命令（将两个源码路径换为当地对应checkout）：

```bash
python -B web/mixed_queue_probe.py \
  --repo /path/to/8884e9d9 \
  --old-repo /path/to/cd82fc1b \
  --seed-probe /path/to/8884e9d9/docs/design/ielts-writing-ai-model-comparison-plan-20261110/verify/web_gate_probe_adapted.py \
  --out mixed-queue-evidence.json
```

修后期望20/20；其他已通过检查须保持。精确Mac命令、逐项证据、行号和限制见[网页复验](web/README.md)、[realcheck复验](realcheck/README.md)、[抄题/静态升级](copy/README.md)。

## 工作树、交接与后续

- 主资料树`/Users/zhouxin/Desktop/studytracker`仍main@`6ded77d24586327ad94e151e172ae4811b4a2eed`，原7modified/23untracked顶层入口保留。本轮仅新增本报告目录、私有交付zip及两规范交接。
- 新源码树`/private/tmp/studytracker-iwa-prompt15-recheck-20261113`、分支`codex/iwa-prompt15-recheck-20261113`、8884e9d9，前后clean，95工具文件SHA不变；旧652450ca审阅树和cd82fc1b运行树不修改。
- 已读取并合并Claude两轮单独交接文件的当前事实；教师82页完整包仍只在本机且老师未填写。没有把学生正文/完整评价放进此报告或Git。
- 本轮报告/两交接**尚未commit/push，仅本机可见**；远端仍作者8884e9d9。没有main合并、生产后端/前端/数据库部署或小程序上传/提审/发布。
- 待仅剩的旧记录身份门禁修复并复验后，再停旧实例、检查无活跃任务、一致性备份SQLite及私有配置、切换运行源码。此次没有备份/改库或切换动作，也没有新付费请求。
