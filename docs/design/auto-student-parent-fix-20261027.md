# 自动学生/家长账号创建：验证与发布记录

## 范围与版本

- 用户于2026-10-27明确授权“没问题就部署吧”。此前仅本机修复，现授权提交、推送与后端部署；禁止真实账号回归及身份改绑的边界保持。
- 实施树：`/Users/zhouxin/.codex/worktrees/auto-student-parent-fix/studytracker`。原detached基线 `65f1859683c94ef41c938319515702e12709e96c`；本轮开工4 modified（app/CI/两交接）+1 untracked测试，均为本任务前轮内容。
- 已在 `codex/auto-student-parent-fix` 提交三个代码文件，并rebase到最新主线 `676569c6935962ee463fb467be703eb962c9fd43`，业务提交 **`2d0dbdb6cce48a98095e0fce8d75edff2420850b`**。独立复审三文件SHA与rebase前完全一致。
- 运行代码只改 `app.py`：补 `ParentStudentLink` 导入；两个User、首次flush、StudentProfile/ParentStudentLink写入与commit共用原try/rollback。保留姓名去空白、用户名/密码规则、权限、四字段成功响应及原错误码；不改models/schema、依赖文件、登录函数或历史身份。
- 新增 `tests/test_auto_student_accounts.py`；`.github/workflows/ci.yml` 新增独立 `account-provisioning` job。既有advisory Ruff设置与部署链路保留。

## 回归证据

[原CI40172013242](https://github.com/KB77GG/studytracker/actions/runs/40172013242) 的test成功、advisory lint失败，原日志含 `app.py:2703:12 F821 ParentStudentLink`。修复前真实app+内存SQLite复现NameError，首次flush的真实IntegrityError亦逃过原异常处理。这不证明生产曾实际失败。

新增13项回归覆盖：完整两账号/Profile/家长Link、空姓名、双方用户名占用及停用账号、重复提交、同名独立档案不合并、首次flush/Profile/Link的SQLite trigger失败、commit失败、完整回滚和原session重试、权限拒绝、旧新学生/家长网页登录、错密码和停用拒绝、模拟微信既有绑定登录、家长children读取。快照比较所有持久化身份/关联列。

测试加载完整应用，初始化前注入专用Config，不加载 `.env`；只连接 `sqlite:///:memory:`，上传目录为临时目录。禁止DNS/socket并断言无调用，工作树无app.db。微信仅替换provider返回值，不调用真实授权服务。

前轮项目venv和全新轻依赖venv各13 tests OK；两次独立审阅均无阻断并复测13项。全新环境只安装Flask、Flask-Login、Flask-SQLAlchemy、PyJWT、pypinyin、requests、certifi、websocket-client、openpyxl及其传递依赖，无Whisper/Kokoro等重模型。

本轮移到最新主线后的精确验证（以下均在实施树执行）：

```bash
TZ=UTC PYTHONDONTWRITEBYTECODE=1 /private/tmp/studytracker-account-ci-0howkl4a/venv/bin/python -m unittest tests.test_auto_student_accounts tests.test_miniprogram_guest_access tests.test_miniprogram_dictation_grouping tests.test_inventory_toefl_materials tests.test_organize_toefl_materials tests.test_extract_toefl_answer_keys tests.test_map_toefl_answers_to_practice_docs tests.test_import_toefl_official_reading tests.test_reading_vocab_grading tests.test_stats_utils -q
# 81 tests OK（13专项+原CI68）；SQLAlchemy/UTC既有弃用提示，不是失败。
node tests/test_dictation_spell_queue.js
# exit 0
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -m ruff check --no-cache --select F821 app.py
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -m ruff check --no-cache tests/test_auto_student_accounts.py
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -m ruff format --no-cache --check tests/test_auto_student_accounts.py
git diff --check
# 均通过；未清理无关Ruff告警。
```

临时venv路径不属于CI前提，GitHub job自行安装九轻依赖。`app.py`/新增测试亦通过 `ast.parse(..., feature_version=(3,10))`，这只是生产版本语法兼容验证，不冒充生产全流程实测。Ruby标准库 `YAML.load_file` 解析CI并验证UTC/命令/非advisory job通过。

| 文件 | SHA-256 |
| --- | --- |
| app.py | `5e6ee2b69cd2311d0339f0d0d9e76584507b9a78318b1ac5e36ee54abec2b45a` |
| tests/test_auto_student_accounts.py | `bf6d6e18fa92d04f495fba151b969f8dc13ed47f5272d32eebdaea1dac6e4962` |
| .github/workflows/ci.yml | `91086f9acbc8b8751bed7a90ce48e276231f1f56df64e4ae63d7c6bf9f4d912d` |

## 生产检查与发布

发布前只读SSH确认生产 `/root/apps/studytracker` 为 `80f215b5b94a90e592c4669c2bee41f7c55eb562`、tracked clean，服务active/running、NRestarts0、自2026-10-26 21:15:23 CST启动，5002 `/login` HTTP200。

SQLite使用 `file:/root/apps/studytracker/app.db?mode=ro` 和 `PRAGMA query_only=ON`，仅 `PRAGMA table_info` 核对 `user`、`student_profile`、`parent_student_link`；所需列均存在，包括primary_parent_id、guardian_view_token、关联is_active及时间戳。未读身份记录，未写SQL或迁移。

发布使用既有GitHub Actions→`sudo /usr/local/sbin/deploy-studytracker`：fetch/reset至main，安装原requirements，运行7个已有迁移脚本、同步entrance静态文件、重启服务。本修复无新增迁移或身份数据处理，未改此脚本。

业务提交已先推任务分支，分支CI成功后非强制推进main，以下运行均对应完整SHA `2d0dbdb6cce48a98095e0fce8d75edff2420850b`：

- [任务分支CI40503784820](https://github.com/KB77GG/studytracker/actions/runs/40503784820)：success；account-provisioning与test成功。
- [主线CI40504015846](https://github.com/KB77GG/studytracker/actions/runs/40504015846)：success；account-provisioning与test成功。
- [部署40504015784](https://github.com/KB77GG/studytracker/actions/runs/40504015784)：success；Node拼写门禁及SSH部署步骤成功。
- 两次CI的advisory Ruff仍有仓库存量告警；任务分支日志112条，不含F821或新增测试文件告警。本任务没有清理无关告警。

部署后生产HEAD即业务提交，tracked clean，以上三文件SHA逐字匹配。服务自 **2026-10-27 20:29:04 CST** active/running，NRestarts0；配置仍 `127.0.0.1:5002 / workers=1 / gthread / threads=6`。本机回环及公网 `/login` HTTP200；匿名家长children接口401；自动创建接口GET405（不发送创建POST）。部署后warning及以上journal行数0。

精确线上只读验收命令：

```bash
ssh root@47.110.45.193 'cd /root/apps/studytracker && git rev-parse HEAD && git status --short --untracked-files=no && sha256sum app.py tests/test_auto_student_accounts.py .github/workflows/ci.yml && systemctl show studytracker.service -p ActiveState -p SubState -p NRestarts -p ExecMainStartTimestamp -p ExecStart && curl -s -o /dev/null -w "local_login_http=%{http_code}\n" http://127.0.0.1:5002/login && curl -s -o /dev/null -w "anonymous_parent_http=%{http_code}\n" http://127.0.0.1:5002/api/miniprogram/parent/children && curl -s -o /dev/null -w "auto_student_get_http=%{http_code}\n" http://127.0.0.1:5002/api/users/auto-student'
ssh root@47.110.45.193 'cd /root/apps/studytracker && grep -E "^(bind|workers|worker_class|threads)[[:space:]]*=" gunicorn.conf.py && journalctl -u studytracker.service --since "2026-10-27 20:29:04" -p warning --no-pager -o cat | wc -l'
curl -L --max-time 20 --cacert /Users/zhouxin/Desktop/studytracker/.venv/lib/python3.13/site-packages/certifi/cacert.pem -sS -o /dev/null -w 'public_login_http=%{http_code}\n' https://studytracker.xin/login
```

未创建真实账号或回填/修改身份记录，未新增schema迁移；已有部署脚本仍会运行原七个迁移步骤和应用启动检查，不能将本次发布表述为没有运行任何迁移代码。未做真实微信登录或生产账号创建端到端验证；静态源码/哈希与隔离回归、只读线上健康核验的边界明确区分。

## 隔离树与交接

- 旧桌面资料树 `/Users/zhouxin/Desktop/studytracker` 本轮不改业务文件；原 `main@6ded77d2`、7 modified/22 untracked入口保留。原路径用途清单留在其已有CODEX_HANDOFF，本轮发布状态只需滚动其两份交接。
- 固定小程序树 `/Users/zhouxin/Desktop/studytracker-release` 未触碰，无小程序上传/提审/发布需求。
- rebase前五目标文件及完整diff保存于 `/private/tmp/studytracker-auto-accounts-deploy-20261027/`；两份旧本机交接另保存在Git stash（说明含 `auto-student-parent-fix handoff before rebase 20261027`），只是历史备份，勿对新文档整体apply。规范新交接从最新主线文档增量更新，不覆盖并行网页练习发布记录。临时备份非跨电脑交付。
- 业务已commit/push/deploy。本报告与实施树CODEX_HANDOFF/WORKLOG作为随后独立 `[skip ci]` 文档提交同步main与任务分支，避免再触发部署；最终文档HEAD以 `git log -1` 为准。文档提交后实施树无未提交业务源码；旧桌面资料树仍有原7/22脏状态，其本轮交接镜像仅本机。

## 保留边界

未创建真实账号、未核实历史生产失败、未做真实微信授权或多进程并发压力测试；未运行全量ML套件。普通学生档案和姓名验证入口不等同于自动账号接口。StudentProfile.full_name不唯一、家长按姓名查询的既有同名歧义保留，未自动合并/改绑。并发用户名抢占由唯一约束拒绝并回滚，可能返回既有db_error 500，顺序查重仍400。

回退应只revert本次业务提交并走正常部署，不恢复数据库或改历史身份；这会重新暴露原自动创建缺陷，尚未执行回退。生产验证采用源码/哈希/服务/匿名只读页面与schema，不用真实账号写入证明功能。

本次发布完成，无本任务待发布代码或阻塞项；下一步正常观察使用。若后续处理同名身份映射或凭据策略，需另立任务并明确授权，不在本修复中迁移身份。
