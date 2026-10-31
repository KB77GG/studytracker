# 任务安排试用版：发布前验证记录

记录日期：2026-10-31（Asia/Shanghai）。本记录覆盖本地候选和合成环境验证，**不代表已提交、已推送或已部署**。用户解锁电脑后，Chrome 合成环境的词汇安排主要流程已完成。

## 候选与范围

- 实施树：`/Users/zhouxin/.codex/worktrees/task-planner-beta/studytracker`。
- 分支：`codex/task-planner-beta`；记录时 HEAD：`ee94abb30d56b3c9623c519f75c1ffa9679c65b5`。业务改动仍为该基线上的未提交改动。
- 开工时实施树干净；当前已修改 `.github/workflows/ci.yml`、`api/__init__.py`、`services/task_deletion.py`、`templates/base.html`、`templates/tasks.html` 和两份规范交接文件。新增 planner 模型、服务、资源适配器、蓝图、CLI、timer/service、网页模板/JS/CSS、三份测试及本版说明。完整文件状态以同树 `git status --short --branch` 为准。
- 旧资料树 `/Users/zhouxin/Desktop/studytracker` 的原有改动保留；本轮候选不从该树发布。固定小程序发布树未修改，本版没有小程序上传、提审或发布动作。
- 本版是人工选定具体内容、保存草稿、确认安排后按日期自动布置；学生自动开关默认关闭。支持题型专项、阅读整篇、词汇指定范围、精听。长期教材顺序规则和自动选择下一段内容不在本版范围内。

以下命令均在实施树执行。Python 使用现有虚拟环境 `/Users/zhouxin/Desktop/studytracker/.venv/bin/python`。前三项测试结果由主 agent 执行并提供；整理本记录时未重复运行这些测试。

## 自动化验证

### 任务安排专项：46 tests OK，5.152 秒

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/zhouxin/Desktop/studytracker/.venv/bin/python -m unittest tests.test_task_planner tests.test_task_planner_resources -v
```

测试使用轻量 Flask、合成账号/学生、临时 SQLite 与合成资源，不导入真实应用入口或连接真实生产库。覆盖：

- staff 权限、未登录拒绝、CSRF 与 JSON 写请求要求，同名学生禁止猜测归属。
- 草稿不生成正式 Task/PlanItem，确认与学生启用相互独立，修改后撤销确认，版本冲突和取消。
- 前置任务同学生及日期约束，有效提交与退回/部分通过的区别，词汇结算同时匹配学生和任务。
- 北京时间 03:05 至 09:00 前执行窗口，仅当日且已启用的安排自动执行，不补发过期或提前发布未来日期。
- 内容校验与冻结 hash、资源下线/变更、四类资源创建、已有任务与待发布安排冲突、整篇与题型专项交叉重复。
- 失败事务回滚及重试、并发发布幂等、无重复 Task/PlanItem；已取消正式任务保留原安排发布历史且不重发，取消的前置任务不放行。
- HTTP 请求被测试替身阻止，合成发布不会调用真实微信或其他外部消息。

### 浏览器脚本行为：最终 17 tests passed

```sh
node --test tests/test_task_planner_client.js
```

主 agent 已同步日志中文化修订并执行，最终17/17通过，JS语法检查通过；不替代真实浏览器交互验收。

### 既有相关模块回归：71 tests OK，6.557 秒

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/zhouxin/Desktop/studytracker/.venv/bin/python -m unittest \
  tests.test_auto_student_accounts \
  tests.test_task_assignment_deduplication \
  tests.test_task_assignment_history \
  tests.test_task_assignment_routes \
  tests.test_task_date_gate \
  tests.test_task_timer_date_gate \
  tests.test_task_date_gate_display_contract -v
```

此结果覆盖既有账号、任务布置、重复检查、历史与日期门禁的相关回归；没有运行全仓 ML 或语音模型套件。

### 目标静态检查：通过

独立复核执行了以下精确命令，Ruff 返回 `All checks passed!`，diff 检查 exit 0 且无输出：

```sh
/Users/zhouxin/Desktop/studytracker/.venv/bin/ruff check \
  models_task_planner.py \
  services/task_planner.py \
  services/task_planner_resources.py \
  api/task_planner.py \
  scripts/run_task_planner.py \
  tests/test_task_planner.py \
  tests/test_task_planner_resources.py \
  api/__init__.py \
  services/task_deletion.py
git diff --check
```

五个新增运行文件的 Python 3.10 语法解析通过：

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/zhouxin/Desktop/studytracker/.venv/bin/python - <<'PY'
import ast
from pathlib import Path
paths = ['models_task_planner.py', 'services/task_planner.py', 'services/task_planner_resources.py', 'api/task_planner.py', 'scripts/run_task_planner.py']
for name in paths:
    ast.parse(Path(name).read_text(encoding='utf-8'), filename=name, feature_version=(3, 10))
print('Python 3.10 grammar: 5 runtime files passed')
PY
```

这验证语法兼容性，不等同于在生产 Python 3.10 下完成全部运行时测试。

### CLI 导入边界：通过

独立复核仅导入脚本定义，没有执行 `main()`、初始化数据库或运行调度：

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/zhouxin/Desktop/studytracker/.venv/bin/python - <<'PY'
import runpy
import sys
runpy.run_path('scripts/run_task_planner.py', run_name='planner_import_audit')
blocked = sorted(name for name in sys.modules if name == 'app' or name.split('.')[0] in {'torch', 'whisper', 'kokoro', 'transformers', 'spacy', 'tts'})
notifications = sorted(name for name in sys.modules if any(word in name.lower() for word in ('wechat', 'wecom', 'notification')))
print({'heavy_or_app_modules': blocked, 'message_modules': notifications})
PY
```

实际输出：`{'heavy_or_app_modules': [], 'message_modules': []}`。静态审阅创建链路也未发现外部消息调用或任务插入通知 hook。

## 浏览器验收与局限

本地合成页面在 Chrome 中已完成：选择合成学生与词书第 1–3 词 → 保存草稿 → 接受确认对话框并确认安排 → 当日“立即布置”。页面显示“已布置 1”和成功消息；查看操作日志包含 `save_draft`、`confirm`、`publish`。学生筛选及该学生的自动启用开关操作也成功。以上均为合成账号、词书与任务，不涉及真实学生。

首轮验证曾因电脑锁屏停在确认对话框。用户随后解锁，主 agent 已继续完成上述流程；锁屏不再是该 Chrome 流程的待办或阻断。浏览器交互证据只覆盖上述已观察步骤，不扩展为所有任务类型和所有浏览器完整通过。

Chrome 390×844 窄屏截图检查通过：`scrollWidth = 375 <= innerWidth = 390`，未发现横向溢出；检查后已重置 viewport。截图 `/private/tmp/task-planner-beta-preview.jpg` 含合成信息，仅保留本机，不作为线上验收截图。

应用内浏览器（IAB）的点击/输入异常记录为本次工具限制，不阻断已完成的 Chrome 验收；不记录为产品故障，也不声称 IAB 全流程通过。其他资源类型的完整浏览器交互、微信 WebView 和真机仍无本轮完整通过证据。

## 独立只读审阅

审阅对象：新增模型、核心服务、API、资源适配器、API 初始化、旧任务取消服务、CLI 与 systemd timer/service。未发现需要新增阻断上线的代码问题。

已核对：北京时间当日和执行窗口、学生启用与有效确认、执行时复核确认人权限、同名学生和前置归属、资源冻结内容复核、SQLite 写事务与失败回滚、原任务幂等返回、取消正式任务留存记录且不会重发、新增三表为增量创建、调度无需加载应用或重模型、无微信发送链路。

保留一个操作边界：同日已有未发布、锁定或删除的 StudyPlan 会使创建回滚并标为执行失败，需要人工处理该日期已有计划；不会覆盖原计划。阅读/精听沿用既有正式任务资源机制，发布前核验资源内容，不宣称发布后所有外部资产永久不可变化。

## 发布状态与下一步

- 本记录产生时尚未 commit/push/deploy；部署待定。已获上线授权不等于实际部署成功。
- 自动化和浏览器操作均使用合成数据，没有向真实学生创建测试任务，没有代答或修改真实成绩，没有微信消息。
- 本轮验证未安装或启动生产 timer，没有生产 schema 写入。生产既有服务状态不能作为本功能已上线的证据。
- 最终17项客户端测试已通过，生产一致性备份已完成：`/root/backups/studytracker/task-planner-20261031-122157/app.db`，quick_check=ok、发布前planner表0。下一步提交/推送、部署并验证新增表/鉴权/服务配置/timer。生产学生开关保持默认关闭，交由助教明确选题、确认并启用；合成环境已测试开关不表示任何真实学生已启用。
- 部署后的 commit、push、CI、生产 HEAD、服务与 timer 状态应另行补充，不能改写为本发布前记录已经验证。

本文件先暂存在 `/private/tmp/task-planner-validation.md`，仅本机可见。主 agent 负责通过已授权方式复制到实施树并同步更新 `docs/CODEX_HANDOFF.md` 和 `docs/WORKLOG.md`；此子 agent 未直接修改工作树或执行提交/部署。
