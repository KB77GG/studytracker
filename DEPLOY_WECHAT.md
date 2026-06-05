# 微信小程序集成部署指南

## 1. 服务器端部署

### 推荐流程：本地推送，GitHub Actions 部署服务器

在本地执行：

```bash
./deploy.sh "本次提交说明"
```

`deploy.sh` 只负责提交和推送代码，然后等待 GitHub Actions 的 `Deploy to Alibaba Cloud` 工作流完成。服务器端的拉代码、安装依赖、迁移和重启由 GitHub Actions 通过 `/usr/local/sbin/deploy-studytracker` 执行，避免本地脚本和 Actions 同时 SSH 到服务器造成 `git pull` 冲突。

如需只推送、不等待 Actions：

```bash
SKIP_GITHUB_ACTIONS_WATCH=1 ./deploy.sh "本次提交说明"
```

如需同步本地 gitignored 的 TOEFL 分档卷音频：

```bash
UPLOAD_TOEFL_AUDIO=1 ./deploy.sh "同步 TOEFL 音频"
```

### 手动服务器维护

一般不需要手动登录服务器部署。确实需要排查时，服务器项目目录是：

```bash
cd /root/apps/studytracker
```

### 服务器依赖
服务器上需要安装 `requests` 和 `pyjwt`：
```bash
# 确保在虚拟环境中或系统环境中安装（取决于您的运行方式）
pip3 install requests pyjwt
```

### 数据库迁移
GitHub Actions 部署脚本会执行当前项目需要的迁移脚本。历史上手动执行过：
```bash
python3 migrate_wechat.py
```

如需启用课堂反馈功能，请创建反馈表：
```bash
python3 create_class_feedback_table.py
```

如果已经创建过表，需要补充图片字段：
```bash
python3 add_class_feedback_image.py
```

### 配置 AppSecret
打开 `api/wechat.py`，找到 `WECHAT_APP_SECRET`，填入您的小程序 AppSecret。
或者，您可以在 `config.py` 中添加 `WECHAT_APP_SECRET = '您的密钥'`。

订阅消息模板需要配置环境变量：
```
WECHAT_TASK_TEMPLATE_ID=学生作业提醒模板ID
WECHAT_COURSE_TEMPLATE_ID=课程提醒模板ID
WECHAT_FEEDBACK_TEMPLATE_ID=你的反馈模板ID
```

排课系统对接需要配置环境变量：
```
SCHEDULER_BASE_URL=http://127.0.0.1:5000
SCHEDULER_PUSH_TOKEN=与 training_scheduler /home/admin/training_scheduler/.env 中 PUSH_TOKEN 相同
```

当前线上 `studytracker.service` 已在 systemd unit 中配置上述 `SCHEDULER_*` 变量。`studytracker` 只调用 `training_scheduler` 的接口，不占用 5000 端口，也不负责启动、停止或清理 `training_scheduler` 的 gunicorn 进程；`training_scheduler` 的生命周期由它自己的 `gunicorn.service` 管理。

### 手动重启服务
```bash
systemctl restart studytracker
```

## 2. 小程序端开发

1. 打开 **微信开发者工具**。
2. 选择 **导入项目**。
3. 目录选择：`/Users/zhouxin/Desktop/studytracker/miniprogram`。
4. AppID 使用：`wx75cdd8fc1ca68c69`。
5. 确保在详情设置中勾选 **"不校验合法域名..."**（开发阶段）。

小程序代码上传仍然手动在微信开发者工具完成；当前仓库不配置自动上传到微信公众平台。

课堂反馈订阅模板 ID 需要同步到小程序端：
`miniprogram/pages/parent/profile/index.js` 的 `FEEDBACK_TEMPLATE_ID`。

现在您应该可以预览小程序，并尝试点击"微信一键登录"了！
