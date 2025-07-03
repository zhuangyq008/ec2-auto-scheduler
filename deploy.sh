#!/bin/bash

# EC2调度器部署脚本
set -e

echo "🚀 开始部署EC2调度器..."

# 检查必要工具
command -v sam >/dev/null 2>&1 || { echo "❌ 请先安装AWS SAM CLI"; exit 1; }
command -v aws >/dev/null 2>&1 || { echo "❌ 请先安装AWS CLI"; exit 1; }

# 检查AWS凭证
aws sts get-caller-identity >/dev/null 2>&1 || { echo "❌ 请先配置AWS凭证"; exit 1; }

# 设置环境变量
ENVIRONMENT=${1:-dev}
STACK_NAME="ec2-scheduler-${ENVIRONMENT}"

echo "📋 部署环境: ${ENVIRONMENT}"
echo "📋 Stack名称: ${STACK_NAME}"

# 构建应用
echo "🔨 构建SAM应用..."
sam build

# 部署应用
echo "🚀 部署到AWS..."
sam deploy \
    --stack-name "${STACK_NAME}" \
    --parameter-overrides Environment="${ENVIRONMENT}" \
    --capabilities CAPABILITY_IAM \
    --resolve-s3 \
    --no-confirm-changeset

# 获取输出
echo "📊 获取部署信息..."
CONFIG_TABLE=$(aws cloudformation describe-stacks \
    --stack-name "${STACK_NAME}" \
    --query 'Stacks[0].Outputs[?OutputKey==`ConfigTableName`].OutputValue' \
    --output text)

LAMBDA_FUNCTION=$(aws cloudformation describe-stacks \
    --stack-name "${STACK_NAME}" \
    --query 'Stacks[0].Outputs[?OutputKey==`LambdaFunctionName`].OutputValue' \
    --output text)

echo "✅ 部署完成！"
echo ""
echo "📋 部署信息:"
echo "   - 配置表: ${CONFIG_TABLE}"
echo "   - Lambda函数: ${LAMBDA_FUNCTION}"
echo ""
echo "🔧 后续步骤:"
echo "   1. 查看配置: aws dynamodb scan --table-name ${CONFIG_TABLE}"
echo "   2. 测试函数: aws lambda invoke --function-name ${LAMBDA_FUNCTION} --payload '{}' response.json"
echo "   3. 查看日志: aws logs tail /aws/lambda/${LAMBDA_FUNCTION} --follow"
echo ""
echo "📖 配置说明:"
echo "   - 默认标签: Env=Dev"
echo "   - 启动时间: 09:00 (北京时间)"
echo "   - 停止时间: 00:00 (北京时间)"
echo "   - 检查间隔: 10分钟"
echo ""
echo "⚠️  注意: 请根据需要修改DynamoDB中的配置！"
