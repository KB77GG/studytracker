# GitHub Actions 自动部署配置指南

本项目已自带 GitHub Actions 工作流（`.github/workflows/deploy.yml`），用于在推送到 `main` 分支后自动通过 SSH 部署到阿里云服务器。按照以下步骤准备仓库机密即可完成「代码一推，自动上线」。

## 先决条件
- 服务器上已部署本项目代码，并位于 `/root/apps/studytracker`（如有不同，请修改工作流里的路径）。
- 服务器已经可以通过 SSH 登录，且对应的私钥可用。
- 服务器上已准备好虚拟环境 `.venv/`，包含 `requirements.txt` 所需依赖；工作流会在部署时再次安装依赖以确保最新。

## 配置仓库 Secrets
1. 打开 GitHub 仓库页面，点击顶部 **Settings**。
2. 在左侧选择 **Secrets and variables** -> **Actions**。
3. 点击 **New repository secret** 依次添加以下三个机密（名称需完全一致）：
   - `SERVER_IP`：`47.110.45.193`（服务器公网 IP）。
   - `SERVER_USER`：`root`（或用于 SSH 登录的用户名）。
   - `SSH_PRIVATE_KEY`：用于登录服务器的私钥全文，需包含 `-----BEGIN OPENSSH PRIVATE KEY-----` 与 `-----END OPENSSH PRIVATE KEY-----`。可在本地终端运行 `cat ~/.ssh/id_rsa` 获取。

## 工作流执行内容概览
当向 `main` 分支推送代码时，`deploy.yml` 会：
1. Checkout 仓库代码。
2. 使用 `appleboy/ssh-action` 通过上方机密连接服务器。
3. 在 `/root/apps/studytracker` 目录下拉取最新 `main` 分支代码。
4. 通过 `.venv/bin/pip install -r requirements.txt` 更新依赖。
5. 运行数据库迁移脚本：`create_plan_table.py`、`add_feedback_column.py`、`add_explanation_column.py`、`add_dictation_book_id.py`。
6. 调用 `systemctl restart studytracker` 重启服务。

如需调整部署逻辑或新增脚本，可直接编辑 `.github/workflows/deploy.yml`，并根据需要在服务器端更新路径或服务名。

## 验证部署
- 完成 Secrets 配置后，推送到 `main`（或通过 GitHub 手动重新运行最新部署工作流）即会触发自动上线。
- 可在 GitHub 仓库的 **Actions** 标签页查看工作流运行日志，确认步骤是否执行成功。
