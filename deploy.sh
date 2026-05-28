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
if git diff --cached --quiet; then
    echo "ℹ️  没有新的改动需要提交，跳过 commit"
else
    git commit -m "$COMMIT_MSG"
fi
git push origin main

if [ $? -ne 0 ]; then
    echo "❌ 本地推送失败，请检查 Git 状态"
    exit 1
fi

# 3. 上传 TOEFL 听力音频（uploads/ 是 gitignored，必须 scp 单独上传）
#    幂等：scp 会直接覆盖，文件存在但变化时也会更新。
if ls uploads/entrance/audio/toefl_tiered_*.mp3 >/dev/null 2>&1; then
    echo "🎧 上传 TOEFL 分档卷听力音频..."
    ssh root@$SERVER_IP "mkdir -p $REMOTE_DIR/uploads/entrance/audio"
    scp uploads/entrance/audio/toefl_tiered_*.mp3 root@$SERVER_IP:$REMOTE_DIR/uploads/entrance/audio/
    if [ $? -ne 0 ]; then
        echo "❌ 音频上传失败"
        exit 1
    fi
else
    echo "⚠️  本地没有 toefl_tiered_*.mp3，跳过音频上传"
fi

# 4. 服务器远程更新
echo "☁️  正在连接服务器更新代码..."
ssh root@$SERVER_IP "apt-get update && apt-get install -y python3-pip python3-cffi python3-brotli libpango-1.0-0 libpangoft2-1.0-0 fonts-noto-cjk && cd $REMOTE_DIR && git pull && .venv/bin/pip install -r requirements.txt && .venv/bin/python3 create_plan_table.py && .venv/bin/python3 create_speaking_tables.py && .venv/bin/python3 add_feedback_column.py && .venv/bin/python3 add_explanation_column.py && .venv/bin/python3 add_dictation_book_id.py && .venv/bin/python3 add_dictation_range_columns.py && .venv/bin/python3 add_dictation_mode_column.py && .venv/bin/python3 add_student_answer_uncertain_column.py && .venv/bin/python3 add_word_mastery_table.py && .venv/bin/python3 add_student_saved_word_table.py && .venv/bin/python3 add_word_enrichment_columns.py && .venv/bin/python3 add_word_translation_cache.py && .venv/bin/python3 scripts/migrate_planitem_resource.py && .venv/bin/python3 create_mock_exam_tables.py && .venv/bin/python3 scripts/add_listening_to_toefl_tiered.py && systemctl restart studytracker"

if [ $? -eq 0 ]; then
    echo "✅ 部署成功！"
else
    echo "❌ 服务器更新失败"
    exit 1
fi
