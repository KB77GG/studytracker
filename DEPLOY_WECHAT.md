# 微信小程序集成部署指南

## 1. 服务器端部署

### 步骤 1：提交代码到仓库
在本地（您的电脑）执行：
```bash
git add .
git commit -m "feat: add wechat mini program integration"
git push origin main
```

### 步骤 2：更新服务器代码
登录阿里云服务器，执行：
```bash
cd /root/apps/studytracker
git pull
```

### 步骤 3：安装新依赖
服务器上需要安装 `requests` 和 `pyjwt`：
```bash
# 确保在虚拟环境中或系统环境中安装（取决于您的运行方式）
pip3 install requests pyjwt
```

### 步骤 4：执行数据库迁移
在服务器上运行迁移脚本，为数据库添加新字段：
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

### 步骤 5：配置 AppSecret
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

### 步骤 6：重启服务
```bash
systemctl restart studytracker
```

## 2. 小程序自动上传

本仓库已接入微信官方 `miniprogram-ci`。它会把 `miniprogram/` 上传到微信公众平台，生成一个新的开发版本/体验版；提交审核和发布正式版仍需要在微信公众平台手动操作。

### 准备代码上传密钥

1. 使用小程序管理员账号登录 [微信公众平台](https://mp.weixin.qq.com)。
2. 进入 **开发管理 → 开发设置 → 小程序代码上传**。
3. 下载代码上传密钥。
4. 如果在本地或 GitHub Actions 上传，请在该页面配置对应 IP 白名单；如果上传机器 IP 不固定，需要按微信后台策略处理白名单限制。

不要把密钥文件提交到仓库。`.gitignore` 已忽略常见上传密钥文件名。

### 本地上传

推荐把密钥文件放在仓库外，或放在已忽略的本地路径，然后执行：

```bash
export WECHAT_MP_PRIVATE_KEY_PATH=/absolute/path/to/private.wx75cdd8fc1ca68c69.key
npm ci
npm run mp:upload -- --version 0.1.1 --desc "teacher homework edit controls"
```

也可以直接用环境变量传密钥内容：

```bash
export WECHAT_MP_PRIVATE_KEY="$(cat /absolute/path/to/private.key)"
npm run mp:upload -- --version 0.1.1 --desc "teacher homework edit controls"
```

现有 `./deploy.sh "提交备注"` 已集成小程序上传：当检测到 `WECHAT_MP_PRIVATE_KEY`、`WECHAT_MP_PRIVATE_KEY_BASE64` 或 `WECHAT_MP_PRIVATE_KEY_PATH` 时，会在服务器部署成功后自动上传小程序；未配置密钥时会跳过并提示。临时跳过可设置：

```bash
SKIP_MINIPROGRAM_UPLOAD=1 ./deploy.sh "只部署后端"
```

### GitHub Actions 自动上传

推送到 `main` 后，`.github/workflows/deploy.yml` 会先部署服务器，再尝试上传小程序。需要在 GitHub 仓库设置里配置以下 Secret：

- `WECHAT_MP_PRIVATE_KEY`：代码上传密钥内容；或
- `WECHAT_MP_PRIVATE_KEY_BASE64`：密钥文件内容的 base64 编码。

可选配置：

- `WECHAT_MP_APPID`：默认读取 `miniprogram/project.config.json`，当前为 `wx75cdd8fc1ca68c69`。
- Repository Variable `WECHAT_MP_ROBOT`：指定 CI 机器人编号，默认 `1`。

## 3. 小程序端开发

1. 打开 **微信开发者工具**。
2. 选择 **导入项目**。
3. 目录选择：`/Users/zhouxin/Desktop/studytracker/miniprogram`。
4. AppID 使用：`wx75cdd8fc1ca68c69`。
5. 确保在详情设置中勾选 **"不校验合法域名..."**（开发阶段）。

课堂反馈订阅模板 ID 需要同步到小程序端：
`miniprogram/pages/parent/profile/index.js` 的 `FEEDBACK_TEMPLATE_ID`。

现在您应该可以预览小程序，并尝试点击"微信一键登录"了！
