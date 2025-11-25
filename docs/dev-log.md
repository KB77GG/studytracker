# 开发与部署日志（studytracker）

本文记录本轮开发与部署的关键变更、命令与排查过程，并按时间节点标注，便于复盘与接手。

## 开发变更（时间线）

### 📅 第一阶段：系统构建与核心功能（2025.10.10 - 2025.11.09）

#### 第 1 周：系统立项 & 功能规划（2025.10.10 - 10.14）
- **目标确立**：建立独立于排课系统的学习追踪平台，记录任务、用时、完成度与正确率。
- **功能确认**：
  - 用户权限（管理员 / 助教账号）。
  - 任务创建、编辑、删除；任务分类（基础 / 雅思 / 托福）。
  - 用时记录（开始 / 暂停 / 结束）；统计报告（按学生 / 按类别）；Excel 导出。

#### 第 2 周：数据库模型与基础结构（2025.10.15 - 10.18）
- **2025-10-15 ~ 10-17：模型设计与手动迁移**
  - 完成 `models.py`，新增 `Task` 模型关键字段：
    - 基础信息：`date`, `student_name`, `category`, `detail`, `status`, `note`, `created_by`
    - 计时字段：`planned_minutes`, `actual_seconds`, `started_at`, `ended_at`
    - 质量字段：`accuracy`（正确率）
  - 执行手动 SQL 迁移（SQLite）：
    ```sql
    ALTER TABLE task ADD COLUMN planned_minutes INTEGER DEFAULT 0;
    ALTER TABLE task ADD COLUMN actual_seconds INTEGER DEFAULT 0;
    ALTER TABLE task ADD COLUMN started_at DATETIME;
    ALTER TABLE task ADD COLUMN ended_at DATETIME;
    ALTER TABLE task ADD COLUMN accuracy FLOAT DEFAULT 0.0;
    ```

- **2025-10-18 14:00：前端改造（任务列表分组）**
  - `templates/tasks.html` 改为按学生折叠的分组列表（accordion），新增“完成率”列。
  - 筛选、计时、编辑、删除、状态切换等脚本适配分组结构；删除时自动清理分组空状态。
  - 新增页面：学生端 `student_today.html`、教师端 `teacher_plans.html`、家长报告 `parent_report.html`。

- **2025-10-18 16:00：数据模型重构**
  - `models.py` 新增：`StudentProfile`, `TeacherStudentLink`, `TaskCatalog`, `PlanTemplate`, `StudyPlan`, `PlanItem`, `PlanEvidence` 等。
  - 增加 `TimestampMixin`, `SoftDeleteMixin`。
  - `User` 扩展：email, display_name, 角色枚举。
  - **兼容性**：保留 `Task`, `StudySession` 旧模型用于兼容现有页面。

- **2025-10-18 18:00：后端路由与 API 扩展**
  - 新增教师工作台接口：计划创建、模板引用、待审核列表。
  - 新增学生端 API：计时开始/停止、提交、证据上传。
  - `config.py` 增加 `UPLOAD_FOLDER` 配置。

- **2025-10-18 20:00：迁移脚本**
  - 编写 `scripts/migrate_legacy.py`：从旧 `Task` 迁移到 `StudyPlan` 体系，幂等设计。

#### 第 3 周：后端路由与 API 开发（2025.10.19 - 10.22）
- **路由完善 (`app.py`)**：
  - 任务相关：`/tasks`, `/api/tasks/<id>/edit`, `/api/tasks/<id>/delete`
  - 计时系统：`/api/session/start`, `/api/session/stop/<session_id>`（支持多段计时）
  - 统计接口：`/report`, `/api/report/student/<name>`, `/api/export/report.xlsx`
- **2025-10-19：部署与网络配置**
  - Nginx 反代配置，域名解析 `studytracker.xin`。
  - 解决 SSH 连接超时问题（开放安全组 TCP 22）。

#### 第 4 周：前端页面深度开发（2025.10.23 - 10.30）
- **`tasks.html` 完整重构**：
  - 创建表单升级：下拉分类 optgroup、正确率、预计用时、备注栏。
  - 实时筛选（不刷新页面）：按学生/类别/状态过滤。
  - 计时器 UI：自动累计 `actual_seconds`，超时变色。
  - 交互优化：编辑对话框改为 Modal 弹窗。
- **2025-10-30 10:00：计时精度修复**
  - 前端在暂停/结束前先计算本地 `elapsed` 秒数传给后端，避免网络延迟误差。
  - 后端 `/api/session/stop` 接收可选 `seconds` 参数。
- **2025-10-30 11:00：PRG 模式修复**
  - 任务创建成功后改为 Redirect，防止刷新重复提交。
- **2025-10-30 11:30：PDF 导出**
  - 集成 WeasyPrint，实现 `/report/export/pdf`。

#### 第 5 周：统计与报告模块（2025.11.01 - 11.05）
- **可视化报表 (`report.html`)**：
  - 基于 Chart.js 实现：任务类别占比（饼图）、每日总用时（柱状图）、正确率趋势（折线图）。
- **Excel 导出**：
  - 生成包含学生列表、任务预计/实际用时、完成状态、正确率的详细报表。

#### 第 6 周：系统结构优化（2025.11.05 - 11.07）
- **视图优化**：支持按学生树状显示任务（结构清晰）。
- **视觉反馈**：自动高亮“超时任务”（实际用时 ≥ 计划用时 → 加粗红色）。

#### 第 7 周：部署策略确认（2025.11.08 - 11.09）
- **策略定型**：
  - 端口分离：不使用 5000 端口。
  - 架构确认：Nginx 反向代理 + Gunicorn + 独立域名。

---

### 📅 第二阶段：移动端扩展与架构升级（2025.11.16 - 至今）

- **2025-11-16 14:00：Dashboard 布局重构**
  - `templates/base.html` 改为侧边栏 + 顶部标题的工作台骨架。
  - `static/style.css` 补充侧栏、主面板、统计卡样式。

- **2025-11-16 15:30：任务页仪表盘化**
  - `tasks.html` 增加统计卡片（总任务、已完成、累计用时、平均正确率）。
  - `app.py` 增加 `top_students` 和 `recent_tasks` 数据汇总。

- **2025-11-20：Web 后台核心重构（Day 1）**
  - **环境搭建**：Flask + SQLAlchemy，设计 User/StudentProfile/StudyPlan 模型。
  - **功能实现**：用户认证（Flask-Login）、学生管理、学习计划创建。
  - **问题修复**：PDF 生成中文乱码，引入思源黑体并配置 ReportLab 字体路径。

- **2025-11-21：微信小程序核心开发（Day 2）**
  - **小程序初始化**：创建项目结构，设计登录/学生/家长页面。
  - **核心功能**：
    - 微信登录（`wx.login` + 后端 JWT 签发）。
    - 角色绑定（学生姓名匹配）。
    - 任务列表与详情页（下拉日期选择）。
    - 任务打卡（倒计时、照片上传、提交）。

- **2025-11-22：家长端与部署准备（Day 3）**
  - **家长端开发**：
    - `ParentStudentLink` 模型支持多学生绑定。
    - 家长首页：今日概览、最近动态。
  - **UI 优化**：登录页渐变背景、毛玻璃效果、自定义 TabBar 图标。
  - **部署自动化**：编写 `deploy.sh`，配置 Nginx/Gunicorn。

- **2025-11-23：关键 Bug 修复（Day 4）**
  - **解绑 401 错误**：修复 JWT payload 字段取值错误（`user_id` -> `sub`）。
  - **登录 500 错误**：解决用户名冲突问题（生成带随机后缀的唯一用户名）。
  - **绑定 500 错误（Schema 缺失）**：
    - 排查发现 `parent_student_link` 表缺失 `created_at/updated_at` 字段。
    - 创建 `debug/fix_db` 接口，使用静态默认值（'2000-01-01'）修复 SQLite 表结构。

- **2025-11-24：UI 升级与功能完善（Day 5）**
  - **登录流程优化**：未绑定用户强制引导角色选择，已绑定用户自动跳转。
  - **家长首页 UI 升级**：新增 7 日趋势柱状图（动态颜色）、学科分布进度条、时间轴样式动态列表。
  - **多学生支持**：家长首页新增“+”按钮，支持绑定多个孩子并切换。
  - **导航修复**：修复绑定页面无返回按钮问题（改用 `navigateTo`）。

- **2025-11-25：学生创建流程简化（Web 端）**
  - **需求变更**：学生仅需通过微信小程序绑定档案，无需 Web 账号。
  - **后端修改**：
    - `users_page` 新增 `create_student` 动作，仅创建 `StudentProfile`，不创建 `User`。
    - 移除 `auto_student`（一键生成账号）功能。
    - 新增 `delete_student` 软删除功能。
  - **前端修改**：
    - `templates/users.html` 重构，新增独立的“学生档案管理”区域。
    - 显示学生列表及微信绑定状态（已绑定微信/已绑定账号/未绑定）。
  - **部署**：更新代码并重启服务。

## 本地与服务器操作摘要（时间线）

- **2025-10-18 21:00** Git 初始化并推送到 GitHub。
- **2025-10-18 21:30** 服务器部署（Ubuntu 22.04）：
  - Clone 仓库，创建 venv，安装依赖。
  - 上传 `app.db`，运行迁移脚本。
  - 配置 Gunicorn (port 5002) 和 Systemd 服务。
- **2025-10-19 00:00** Nginx 配置：反代到 5002，域名 `studytracker.xin`。
- **2025-11-23 22:00** 数据库修复：执行 `curl .../debug/fix_db` 修复表结构。
- **2025-11-25 09:00** 部署更新：`./deploy.sh "简化学生创建流程"`。

## 域名与访问

- **域名**：`studytracker.xin` / `www.studytracker.xin`
- **IP**：47.110.45.193
- **备案状态**：DNS 解析正常，备案拦截中（需配置 hosts 或等待备案完成）。

## 备份建议

- **对象**：`app.db`、`uploads/`。
- **频率**：建议每日备份，保留 7-30 天。
