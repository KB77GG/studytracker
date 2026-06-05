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
BRANCH="main"
WATCH_ACTIONS="${SKIP_GITHUB_ACTIONS_WATCH:-0}"

echo "🚀 开始部署..."
CURRENT_BRANCH="$(git branch --show-current)"
if [ "$CURRENT_BRANCH" != "$BRANCH" ]; then
    echo "❌ 当前分支是 $CURRENT_BRANCH，请先切换到 $BRANCH 再部署"
    exit 1
fi

# 2. 本地 Git 提交
echo "📦 正在提交本地代码..."
git add .
if git diff --cached --quiet; then
    echo "ℹ️  没有新的改动需要提交，跳过 commit"
else
    git commit -m "$COMMIT_MSG"
fi
HEAD_SHA="$(git rev-parse HEAD)"
git push origin "$BRANCH"

if [ $? -ne 0 ]; then
    echo "❌ 本地推送失败，请检查 Git 状态"
    exit 1
fi

# 3. 可选上传 TOEFL 听力音频（uploads/ 是 gitignored，必须 scp 单独上传）
#    只在需要同步本地音频时启用：UPLOAD_TOEFL_AUDIO=1 ./deploy.sh "..."
if [ "${UPLOAD_TOEFL_AUDIO:-0}" = "1" ] && ls uploads/entrance/audio/toefl_tiered_*.mp3 >/dev/null 2>&1; then
    echo "🎧 上传 TOEFL 分档卷听力音频..."
    ssh root@$SERVER_IP "mkdir -p $REMOTE_DIR/uploads/entrance/audio"
    scp uploads/entrance/audio/toefl_tiered_*.mp3 root@$SERVER_IP:$REMOTE_DIR/uploads/entrance/audio/
    if [ $? -ne 0 ]; then
        echo "❌ 音频上传失败"
        exit 1
    fi
elif [ "${UPLOAD_TOEFL_AUDIO:-0}" = "1" ]; then
    echo "⚠️  本地没有 toefl_tiered_*.mp3，跳过音频上传"
else
    echo "⏭️  未设置 UPLOAD_TOEFL_AUDIO=1，跳过音频上传"
fi

# 4. 等待 GitHub Actions 完成服务器部署
echo "☁️  代码已推送到 $BRANCH，服务器部署交给 GitHub Actions"
if [ "$WATCH_ACTIONS" = "1" ]; then
    echo "⏭️  已设置 SKIP_GITHUB_ACTIONS_WATCH=1，不等待 Actions 结果"
    exit 0
fi

if ! command -v gh >/dev/null 2>&1; then
    echo "⚠️  未安装 GitHub CLI，无法等待 Actions 结果。请到 GitHub 查看 Deploy to Alibaba Cloud。"
    exit 0
fi

echo "⏳ 等待 GitHub Actions 部署开始..."
RUN_ID=""
for _ in {1..30}; do
    RUN_ID="$(gh run list \
        --branch "$BRANCH" \
        --commit "$HEAD_SHA" \
        --workflow "Deploy to Alibaba Cloud" \
        --limit 1 \
        --json databaseId \
        --jq '.[0].databaseId // empty' 2>/dev/null)"
    if [ -n "$RUN_ID" ]; then
        break
    fi
    sleep 2
done

if [ -z "$RUN_ID" ]; then
    echo "⚠️  暂未找到对应的 GitHub Actions run，请稍后在 GitHub 查看。"
    exit 0
fi

echo "📡 正在等待 GitHub Actions run $RUN_ID ..."
gh run watch "$RUN_ID" --exit-status
if [ $? -eq 0 ]; then
    echo "✅ GitHub Actions 部署成功！"
else
    echo "❌ GitHub Actions 部署失败，请查看 run $RUN_ID 日志"
    exit 1
fi
