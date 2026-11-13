# `.15` 第二次修复：realcheck 原探针与相邻回归

源码工作树 `/private/tmp/studytracker-iwa-prompt15-final-recheck-20261113`，分支 `codex/iwa-prompt15-final-recheck-20261113`，HEAD `e3901a0c4312f42c7a90996f47e18b4d96d4935d`，业务修复 `d92f0839`。先读该树 AGENTS/CLAUDE/两交接及 `iwa-prompt15-fix2-claude-20261113/README.md`，核对 Git；源码树本专项起止 clean。产品代码、旧探针和旧报告均未修改。

本专项 **15/15 + 17/17 均通过**，没有发现原核图记录绑定、JSONL入口或比较指纹的回归。全部临时合成文本和图片、FakeClient、阻断socket；0真实调用，没有读取私有配置、Key、官方/学生原稿、试用库或服务。

## 精确命令

cwd：`/Users/zhouxin/Desktop/studytracker`。

```bash
.venv/bin/python -B docs/design/iwa-prompt15-review-20261113/realcheck/probe.py \
  --source /private/tmp/studytracker-iwa-prompt15-final-recheck-20261113 \
  --out docs/design/iwa-prompt15-final-recheck-20261113/realcheck/evidence.json

.venv/bin/python -B docs/design/iwa-prompt15-recheck-20261113/realcheck/adjacent_probe.py \
  --source /private/tmp/studytracker-iwa-prompt15-final-recheck-20261113 \
  --out docs/design/iwa-prompt15-final-recheck-20261113/realcheck/adjacent-evidence.json
```

两条均exit0。原探针SHA、相关产品SHA及源码状态见 `source-state.json`。这两次运行没有改预期、没有使用用户真实数据。

- 原15项：合法确认保留原读数、绑定图片、确认后读数/图片变化在调用前拒绝、JSONL内嵌确认拒绝、无图不能绕过要求、审计元数据变化不影响同输入比较、已有核对文件不可覆盖。
- 相邻17项：确认hash对应最终UTF-8文本，载入后改正文/图片仍被run拒绝，第二样本无效时首样本也不先发请求，缺hash的提示门禁关闭，真实输入/核对状态变化仍改变比较指纹。

本专项不代替网页排队 P2 验收、真实官方样本回放或实际服务升级，后者由主审归并。未运行付费模型，不据此宣称读图或评分质量改善。

## 共享审核交付

父目录 `share-audit.json` 是两轮旧报告的逐文件SHA白名单：原20文件+22文件交付包，加续核4文件，共46个Markdown/JSON/Python文本。3份完整测试日志排除，ZIP和`.tmp`不在共享白名单。候选材料含数值、布尔、哈希、源码路径和合成用例，没有观察到学生身份/正文、完整模型回答/思考或真实密钥；JSON中的`response_text`只在SHA容器里出现，值为64字符哈希。检查没有为了比对而读取私有原件，因此不把模式扫描当作万能隐私证明。

核心探针有源码/输出路径参数；两份历史`run_offline_tests.py`在第11行固定Mac源码路径，只作为执行记录共享，异机应在本地副本调整路径。旧`web_gate_probe.py`保留首次复核行为，修后旧记录被拒绝时会读空值报错；最新网页验证应使用功能分支内`verify/web_gate_probe_adapted.py`，不能把冻结的历史探针直接用作当前验收。token迁移探针要求仓库能读取`cd82fc1b`历史；官方实样探针需Mac私有文件，报告只分享其聚合证据。

本子任务只写本目录四文件及父目录`share-audit.json`，未改规范交接或执行git add/commit/push。合并交接、实际同步和运行升级状态由主审记录；本专项产物完成时仍仅本机。
