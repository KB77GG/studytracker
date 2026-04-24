#!/bin/bash

# 1. 提示用户输入提交信息
if [ -z "$1" ]; then
    echo "请提供提交备注 (Commit message)"
    echo "用法: ./deploy.sh \"你的提交备注\""
    exit 1
fi

COMMIT_MSG="$1"
SERVER_IP="47.110.45.193"
REMOTE_DIR="/root/apps/studytracker"

echo "🚀 开始部署..."

# 2. 本地 Git 提交
echo "📦 正在提交本地代码..."
git add .
git commit -m "$COMMIT_MSG"
git push origin main

if [ $? -ne 0 ]; then
    echo "❌ 本地提交失败，请检查 Git 状态"
    exit 1
fi

# 3. 服务器远程更新
echo "☁️  正在连接服务器更新代码..."
ssh root@$SERVER_IP "apt-get update && apt-get install -y python3-pip python3-cffi python3-brotli libpango-1.0-0 libpangoft2-1.0-0 fonts-noto-cjk && cd $REMOTE_DIR && git pull && .venv/bin/pip install -r requirements.txt && .venv/bin/python3 create_plan_table.py && .venv/bin/python3 create_speaking_tables.py && .venv/bin/python3 add_feedback_column.py && .venv/bin/python3 add_explanation_column.py && .venv/bin/python3 add_dictation_book_id.py && .venv/bin/python3 add_dictation_range_columns.py && .venv/bin/python3 add_dictation_mode_column.py && .venv/bin/python3 add_student_answer_uncertain_column.py && systemctl restart studytracker"

if [ $? -eq 0 ]; then
    echo "✅ 部署成功！"
else
    echo "❌ 服务器更新失败"
    exit 1
fi
