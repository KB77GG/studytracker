# 教师词汇复习周清单与布置任务提醒

本地实现记录：2026-11-17。工作树 `/private/tmp/studytracker-vocabulary-error-pilot-20261117`，分支 `codex/vocabulary-error-pilot-20261117`，本轮基线 `f414a126`。本部分未 commit、push、部署或操作生产；未触碰固定小程序 release 工作树。核心模型、规则、学生流程由同工作树的其他 agent 同时修改，根交接文档由主 agent 统一更新。

## 行为

- 后台 `/teacher/vocabulary-review` 提供周清单。按北京时间周一至周日筛选，按词义汇总涉及学生与能力。分开显示「连续失败暂停」「过载且逾期转低频」「重新进入必做」「材料待核对」事件；单列当前状态与暂停截止日期，避免把历史事件误当当前状态。
- `tasks.html` 选择学生后显示其过载或暂停待讲解提示，并提供该学生周清单链接；建议减少本次新词量。仅作提醒，不阻塞原任务提交。
- 默认开关关闭时，不渲染导航、提醒元素或请求脚本；直接请求报告返回未启用且不查询新规则表。没有新增 DDL、自动启用、参数编辑或消息推送。
- 网页会话和小程序 Bearer API 都校验 staff 角色与学生范围：教师只看主教师/TeacherStudentLink 授权学生；管理员、助教沿用既有共享管理权限。学生、家长、课程规划员、访客、停用账号不可查看。按名字查询若重名一律拒绝，不根据当前权限猜测学生。
- 周清单最多显示 200 个授权档案、5000 条事件，并显示截断提示；可从任务提醒按档案 ID 查询单个学生。所有读取均只读，不在查看时自动结束暂停、转低频或写事件。暂停到期显示「暂停期已到，可复测」，实际状态流转仍由学生复测路径负责。

## 接口与文件

只读 GET 路由：

- `/api/teacher/vocabulary-review/weekly` 与 `/assignment-load`（网页会话）
- `/api/miniprogram/teacher/vocabulary-review/weekly` 与 `/assignment-load`（Bearer）
- weekly 可传 `week=YYYY-MM-DD`、`profile_id`；assignment-load 可传 `profile_id` 或精确 `student_name`。

新增 `services/vocabulary_error_reporting.py`、`api/vocabulary_error_reports.py`、`templates/vocabulary_error_report.html`、`static/css/vocabulary_error_report.css`、`static/js/vocabulary_assignment_load.js`。最小接入改动位于 `api/__init__.py`（仅蓝图导入/注册）、`templates/base.html`、`templates/tasks.html`。

合成数据测试位于 `tests/test_vocabulary_error_reports.py`、`tests/test_vocabulary_assignment_load.js`。没有学生作答正文、令牌、身份资料被写入本报告。

## 验证

以下命令均在上述工作树执行：

```sh
/Users/zhouxin/Desktop/studytracker/.venv/bin/python -m unittest discover -s tests -p test_vocabulary_error_reports.py -v
/private/tmp/studytracker-stage2-py310/bin/python -m unittest discover -s tests -p test_vocabulary_error_reports.py -v
node --test tests/test_vocabulary_assignment_load.js
/Users/zhouxin/Desktop/studytracker/.venv/bin/ruff check services/vocabulary_error_reporting.py api/vocabulary_error_reports.py tests/test_vocabulary_error_reports.py
/Users/zhouxin/Desktop/studytracker/.venv/bin/black --check services/vocabulary_error_reporting.py api/vocabulary_error_reports.py tests/test_vocabulary_error_reports.py
node --check static/js/vocabulary_assignment_load.js
git diff --check
```

结果：Python 3.13 与 3.10 各 18/18 通过；Node 6/6 通过；ruff、black、JS 语法、diff 空白检查通过。

独立复查追加两项先失败后通过的回归：没有错词 queue 的抽查材料异常也按词义进入周清单，且校验 checkpoint 所属学生，防止交叉引用泄露；暂停天数文案跟随配置。材料异常不统一声称转低频：错误队列显示低频状态，抽查显示「抽查未完成，材料待核对」。

覆盖授权范围、跨老师拒绝、非 staff 拒绝、重名拒绝、软删除/停用/非学生档案拒绝、事件与队列所属学生不一致时拒绝、北京时间周界、多个状态按词义汇总、HTML 转义、OFF 零 SQL（删除事件表仍可正常返回关闭状态）、实际 25 条到期能力产生 20 条安排/5 条超载、只读 SELECT 验证、异步学生切换竞态、网络失败与开关关闭清空提示。

尚未做真实浏览器人工视觉验收、生产回读或正式全套回归（由主 agent 整合执行）。教师网页随后端上线即可使用；小程序 Bearer API 已备好，但本轮未新增小程序教师入口，也未上传/提审/发布小程序。
