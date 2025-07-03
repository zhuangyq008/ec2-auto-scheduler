#!/bin/bash

# EC2调度器GitHub同步脚本
set -e

echo "🔄 开始同步EC2调度器到GitHub..."

# 检查是否有未提交的更改
if [[ -n $(git status --porcelain) ]]; then
    echo "📝 发现未提交的更改，正在添加..."
    git add .
    
    # 获取提交消息
    if [ -n "$1" ]; then
        COMMIT_MSG="$1"
    else
        echo "请输入提交消息："
        read COMMIT_MSG
        if [ -z "$COMMIT_MSG" ]; then
            COMMIT_MSG="Update EC2 scheduler - $(date '+%Y-%m-%d %H:%M:%S')"
        fi
    fi
    
    echo "💾 提交更改: $COMMIT_MSG"
    git commit -m "$COMMIT_MSG"
else
    echo "✅ 工作目录干净，无需提交"
fi

# 推送到GitHub
echo "🚀 推送到GitHub..."
git push origin main

echo "✅ 同步完成！"
echo "🔗 仓库地址: https://github.com/zhuangyq008/ec2-auto-scheduler"
echo ""
echo "📋 使用方法:"
echo "   ./sync_to_github.sh                    # 交互式提交"
echo "   ./sync_to_github.sh \"提交消息\"         # 直接指定提交消息"
