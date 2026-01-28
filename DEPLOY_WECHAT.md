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

课堂反馈订阅消息需要配置环境变量：
```
WECHAT_FEEDBACK_TEMPLATE_ID=你的反馈模板ID
```

### 步骤 6：重启服务
```bash
systemctl restart studytracker
```

## 2. 小程序端开发

1. 打开 **微信开发者工具**。
2. 选择 **导入项目**。
3. 目录选择：`/Users/zhouxin/Desktop/studytracker/miniprogram`。
4. AppID 使用：`wx43ac836a9f623a0d`。
5. 确保在详情设置中勾选 **"不校验合法域名..."**（开发阶段）。

课堂反馈订阅模板 ID 需要同步到小程序端：
`miniprogram/pages/parent/profile/index.js` 的 `FEEDBACK_TEMPLATE_ID`。

现在您应该可以预览小程序，并尝试点击"微信一键登录"了！
