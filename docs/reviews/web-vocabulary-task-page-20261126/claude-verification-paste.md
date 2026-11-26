# 给 Claude 的完整验证补充（2026-11-26）

> 历史验收记录：以下正文是用户已认可的上一轮验证，保留其当时状态；后续补测、分支提交/推送和 CI 以 [branch-review.md](branch-review.md) 为准。

结论先更正：实现完成，已有自动化与部分浏览器验收；**不能宣称计划 A01–A14 已全部验收通过**。原生缩放、真实输入法/长按、真实微信设备等仍待补。以下来自本机实际日志与测试代码复核，不是云端 CI 结果。

实现位置 `/private/tmp/studytracker-web-vocabulary-20261126`，分支 `codex/web-vocabulary-task-page-20261126`，HEAD/开发基线 `f81a5e4a4d81282eb67b994a4cfcc5574fb78747`；工作内容尚未提交。30 个产品/配置/测试文件与验收 manifest 的 SHA-256 全部一致。本轮只复核和补文档，没有重跑或更改产品。

## 命令与结果

| 验证 | 结果 | 本机日志 |
|---|---|---|
| Python 3.13 unittest | 226/226，29.723s | `validation/full-py313.log` |
| Python 3.10 unittest，使用下述兼容入口 | 226/226，32.947s | `validation/full-py310.log` |
| 日期门禁 pytest | 两版本各20/20，0.49s/0.39s | `validation/date-py313.log`、`date-py310.log` |
| Node | 58/58，其中新页面31项 | `validation/full-node.log` |

226 项拆分：新增 67；计划 §8.2 原主回归 107；扩展回归 52。原小程序相关模块仍全部通过：`test_vocabulary_group_learning_api` 10 项、`test_miniprogram_grading` 6 项；还覆盖原分组学习31、自主复习37、复习门禁5、账号13、日期展示5，以及错误复习24、数字学习11、数字复习9、对抗回归8。

实际可复现命令（Bash/Zsh；现在使用绝对解释器路径，验收时的临时 `.venv` 链接已清理）：

```bash
cd /private/tmp/studytracker-web-vocabulary-20261126
vocab_test_modules=(
  tests.test_task_plan_item_sync
  tests.test_vocabulary_task_submission
  tests.test_practice_student_identity
  tests.test_practice_vocabulary_tasks
  tests.test_practice_vocabulary_web
  tests.test_practice_vocabulary_routes
  tests.test_practice_vocabulary_task_list
  tests.test_practice_vocabulary_adversarial
  tests.test_vocabulary_group_learning
  tests.test_vocabulary_group_learning_api
  tests.test_vocabulary_autonomous_review
  tests.test_vocabulary_flow_backlog_gate
  tests.test_auto_student_accounts
  tests.test_miniprogram_grading
  tests.test_task_date_gate
  tests.test_task_date_gate_display_contract
  tests.test_vocabulary_error_review_integration
  tests.test_vocabulary_numeric_learning
  tests.test_vocabulary_numeric_review
  tests.test_vocabulary_stage2_adversarial
)
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -m unittest "${vocab_test_modules[@]}" -q
/private/tmp/studytracker-web-vocab-py310/bin/python \
  docs/reviews/web-vocabulary-task-page-20261126/run_compat_tests.py "${vocab_test_modules[@]}"
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -m pytest tests/test_task_date_gate.py -q
/private/tmp/studytracker-web-vocab-py310/bin/python -m pytest tests/test_task_date_gate.py -q
node --test tests/test_practice_vocabulary_core.js tests/test_practice_task_lists.js \
  tests/test_practice_shell.js tests/test_vocabulary_feedback.js
git diff --check
```

**Python 3.10 限定必须保留**：原有 `test_miniprogram_grading` 导入了3.11才提供的 `datetime.UTC`。兼容入口只给测试进程添加 `datetime.UTC = datetime.timezone.utc`，再加载原测试；不能说原命令在3.10不作处理就全通过。10个改动涉及的产品 Python 文件另做原生3.10编译通过，没有加此别名。首次依赖缺失失败已补装重跑，不隐藏这些前置失败。

`test_task_date_gate.py` 使用 pytest 函数，unittest 只导入、不收集其用例；上面的独立 pytest 命令实际执行了20项。另有新增 Python Ruff、两模板 Jinja 解析、7个JS语法与 diff 检查通过记录。

## 你指出的实现点

1. **答前/再测不泄题**：`test_practice_vocabulary_web.py::test_retry_and_error_snapshot_do_not_reveal_answers`、`test_practice_vocabulary_routes.py::test_stale_question_error_snapshot_and_retry_never_leak_answer`、`test_practice_vocabulary_adversarial.py::test_active_retry_and_nested_conflict_payloads_hide_current_and_future_answers` 通过。作答阶段 familiarity 仅保留 word_id/viewed；当前未作答题及再测题清除已答内容；嵌套冲突响应也清洗。已答反馈和明确的订正题可展示已公开答案，这是批准的订正行为。
2. **听音选义无选项时补齐**：`test_meaning_options_match_actual_miniprogram_algorithm`、`test_fallback_built_before_familiarity_is_hidden` 通过。服务端先补选项，再去掉熟悉材料；测试调用实际小程序JS比较稳定排序，前端提交选项 label。
3. **换学生拒绝旧页面**：`test_actual_name_switch_rejects_old_page_before_task_lookup` 实际修改姓名会话后，以旧页面标识请求，返回409 `identity_changed`，未创建学习流；`test_security_headers_types_size_origin_and_identity_drift` 覆盖CSRF、同源、身份头。不是仅伪造一个错误字符串的测试。
4. **列表显示进行中**：`test_practice_vocabulary_task_list.py::test_active_flow_is_displayed_without_writing_task_status` 通过；已有active flow显示“进行中”，Task.status仍pending，不为显示而写任务。
5. **订正恢复不跳过**：`test_comprehensive_pending_correction_survives_sync_and_is_bounded` 通过：错答→重新POST sync仍有correction_required和已公开正确答案，之后验证两次上限。**这是接口恢复测试；之前浏览器虽走了订正，未专门记录“停在订正态按F5”的实测，不能扩写成已有该证据。**

以上路径均相对仓库 `tests/`，完整逐项 `ok` 可在 `full-py310.log` 查到。

## A01–A14 逐项结论

“已有”仅指下列证据，不代表右栏待办已经完成。

| 编号 | 已有验证 | 待补或证据边界 |
|---|---|---|
| A01 | 助教/老师分组、URL、词书与范围标题；浏览器页头与合成词书相符 | boot元数据book_id/范围未单独加断言；生产入口未验 |
| A02 | 原四类payload在最终代码中开关off/on逐字段相等；旧听写排除；web_practice_required(v2)不强制跳网页 | 未保存并逐字段对比f81a5e4原代码的历史payload快照 |
| A03 | 未开始/进行中/已完成状态、同题续学、完成后GET只读；浏览器刷新回原题 | 订正态浏览器F5专项待补，见上条5 |
| A04 | 未来、当日、次日03:00边界、完成只读，日期pytest20项；未来页浏览器提示 | 生产时区/真实任务未验证 |
| A05 | 归属、同名、课堂/教师、账号优先、会话令牌、CSRF/Origin、实际姓名切换拒绝 | 生产身份数据与两个真实浏览器学生登录切换未验 |
| A06 | 四目标及数字/同义词、六mode、缺材料、响应清洗；六mode浏览器操作/展示 | 真实题库材料和音质未验 |
| A07 | 对/错/忘了、再测不改首答、订正上限；综合任务错答→订正→结果实走 | 订正态F5专项待补 |
| A08 | Node模拟IME、compositionend同轮Enter、repeat、先松开Enter、在途提交；真实双SQLite连接同attempt只一记录；浏览器普通Enter/数字键 | **真实键盘长按、系统中文输入法候选确认未实测** |
| A09 | 音频URL/答前隐藏/跨题音频隔离测试；浏览器503失败→重播成功 | **5秒慢加载、8秒超时未单独实测；没有假Audio覆盖Player超时的单测** |
| A10 | 同attempt幂等、持久化与恢复逻辑；浏览器保存失败重试、服务端已写后返回503再重试 | **503模拟响应失败，不是真离线或网络层丢弃响应；真离线/丢响应后刷新待补** |
| A11 | 独立网页cookie与小程序Bearer客户端交替、旧位置拒绝；首答分数不变 | **真实微信真机/开发者工具切换未验** |
| A12 | 提前结算拒绝、数据库失败回滚、重复结算只读；浏览器结算503→重试成功 | 生产故障不做写入演练 |
| A13 | 网页结算后Task/PlanItem/家长API一致；5/6=83.3%，首次65秒不被重放900秒覆盖 | 老师/家长真实界面未登录核验 |
| A14 | 1440×900、1280×800、1024×768、390×844；主操作可见；Tab焦点、帮助Esc；1152×720与960×600空间代理 | **原生125%/150%缩放未验；代理视口不能替代缩放；未遍历所有状态/控件或多浏览器** |

浏览器全部使用合成学生、内存库和本地合成音；没有真实学生数据或生产操作。核心流程已实走，不等于上述缺口已验收。

## 截图和文件可见性

本机报告目录 `docs/reviews/web-vocabulary-task-page-20261126/` 下已有：

- `screenshots/familiarity-1440.jpg`
- `screenshots/familiarity-1280.jpg`
- `screenshots/familiarity-1024.jpg`
- `screenshots/correction-1440.jpg`
- `screenshots/result-final-1440.jpg`
- `screenshots/effective-125-percent.jpg`、`effective-150-percent.jpg` **只代表可用空间代理，不是原生缩放截图**。

这些文件及代码仍仅在Mac本机；本段正文可以复制给云端，但本机路径本身不会让云端获得文件。未commit/push、远端CI未运行、未部署，main未动。本轮收到的是补贴验证要求，未把“需要授权推分支”的第三方建议视为已获得推送授权。
