# EC2 自动调度器

基于AWS Lambda和SAM的EC2实例自动启停调度器，支持ARM64架构和Python 3.12运行时。

## 功能特性

- 🕘 **定时调度**: 根据配置的时间自动启动和停止EC2实例
- 🏷️ **标签过滤**: 基于EC2标签筛选需要管理的实例
- 🌏 **时区支持**: 支持多时区，默认北京时间
- ⚙️ **灵活配置**: 所有配置存储在DynamoDB中，支持动态修改
- 🧪 **测试模式**: 支持dry-run模式，不实际执行操作
- 📧 **通知功能**: 可选的SNS通知支持
- 🔒 **安全设计**: 最小权限原则，支持实例排除列表
- 📊 **日志监控**: 详细的CloudWatch日志记录

## 架构设计

```
EventBridge (定时触发)
    ↓
Lambda函数 (ARM64, Python3.12)
    ↓
DynamoDB (配置存储) + EC2 API (实例管理)
    ↓
CloudWatch Logs (日志) + SNS (可选通知)
```

## 可配置项

所有配置存储在DynamoDB表中，支持以下配置项：

### 核心配置
- `tag_key`: EC2标签键 (默认: "Env")
- `tag_value`: EC2标签值 (默认: "Dev")
- `start_time`: 启动时间 (默认: "09:00")
- `stop_time`: 停止时间 (默认: "00:00")
- `timezone`: 时区 (默认: "Asia/Shanghai")
- `enabled`: 是否启用 (默认: true)
- `dry_run`: 测试模式 (默认: false)

### 高级配置
- `exclude_instance_ids`: 排除的实例ID列表
- `notification_topic`: SNS主题ARN
- `description`: 配置描述

## 快速开始

### 1. 部署应用

```bash
# 克隆或创建项目目录
cd ec2-scheduler

# 部署到开发环境
./deploy.sh dev

# 或部署到生产环境
./deploy.sh prod
```

### 2. 查看配置

```bash
# 获取表名
TABLE_NAME=$(aws cloudformation describe-stacks \
    --stack-name ec2-scheduler-dev \
    --query 'Stacks[0].Outputs[?OutputKey==`ConfigTableName`].OutputValue' \
    --output text)

# 查看所有配置
python3 manage_config.py --table $TABLE_NAME list
```

### 3. 修改配置

```bash
# 更新默认配置
python3 manage_config.py --table $TABLE_NAME update default \
    --tag-key "Environment" \
    --tag-value "Development" \
    --start-time "08:30" \
    --stop-time "18:00"

# 创建新配置
python3 manage_config.py --table $TABLE_NAME create \
    --config-id "production" \
    --tag-key "Env" \
    --tag-value "Prod" \
    --start-time "07:00" \
    --stop-time "23:00" \
    --description "生产环境配置"
```

### 4. 测试运行

```bash
# 获取Lambda函数名
FUNCTION_NAME=$(aws cloudformation describe-stacks \
    --stack-name ec2-scheduler-dev \
    --query 'Stacks[0].Outputs[?OutputKey==`LambdaFunctionName`].OutputValue' \
    --output text)

# 手动触发测试
aws lambda invoke \
    --function-name $FUNCTION_NAME \
    --payload '{}' \
    response.json

# 查看结果
cat response.json | jq .

# 查看日志
aws logs tail /aws/lambda/$FUNCTION_NAME --follow
```

## 配置管理

### 使用配置管理工具

```bash
# 列出所有配置
python3 manage_config.py --table <TABLE_NAME> list

# 获取特定配置
python3 manage_config.py --table <TABLE_NAME> get default

# 创建新配置
python3 manage_config.py --table <TABLE_NAME> create \
    --config-id "my-config" \
    --tag-key "Project" \
    --tag-value "MyProject" \
    --start-time "09:00" \
    --stop-time "18:00" \
    --description "我的项目配置"

# 更新配置
python3 manage_config.py --table <TABLE_NAME> update default \
    --enabled true \
    --dry-run false

# 删除配置
python3 manage_config.py --table <TABLE_NAME> delete my-config --confirm
```

### 直接使用AWS CLI

```bash
# 查看配置
aws dynamodb get-item \
    --table-name <TABLE_NAME> \
    --key '{"config_id": {"S": "default"}}'

# 更新配置
aws dynamodb update-item \
    --table-name <TABLE_NAME> \
    --key '{"config_id": {"S": "default"}}' \
    --update-expression "SET enabled = :enabled" \
    --expression-attribute-values '{":enabled": {"BOOL": true}}'
```

## 时间配置说明

### 时间格式
- 使用24小时制，格式为 "HH:MM"
- 例如: "09:00", "18:30", "00:00"

### 跨天处理
- 停止时间 "00:00" 表示午夜（第二天的00:00）
- 系统会自动处理跨天的时间计算

### 时区支持
- 默认使用 "Asia/Shanghai" (北京时间)
- 支持所有pytz时区，如 "UTC", "US/Eastern" 等

### 触发窗口
- 系统每10分钟检查一次
- 在目标时间前后5分钟内会触发操作
- 例如：启动时间09:00，在08:55-09:05之间会执行启动操作

## 监控和日志

### CloudWatch日志
```bash
# 实时查看日志
aws logs tail /aws/lambda/<FUNCTION_NAME> --follow

# 查看特定时间段的日志
aws logs filter-log-events \
    --log-group-name /aws/lambda/<FUNCTION_NAME> \
    --start-time 1640995200000 \
    --end-time 1641081600000
```

### CloudWatch指标
Lambda函数会自动生成以下指标：
- 调用次数
- 错误次数
- 执行时间
- 内存使用量

### SNS通知（可选）
```bash
# 创建SNS主题
aws sns create-topic --name ec2-scheduler-notifications

# 订阅邮件通知
aws sns subscribe \
    --topic-arn arn:aws:sns:us-east-1:123456789012:ec2-scheduler-notifications \
    --protocol email \
    --notification-endpoint your-email@example.com

# 在配置中设置通知主题
python3 manage_config.py --table <TABLE_NAME> update default \
    --notification-topic arn:aws:sns:us-east-1:123456789012:ec2-scheduler-notifications
```

## 安全最佳实践

### IAM权限
Lambda函数使用最小权限原则，只能：
- 查看和操作EC2实例
- 读写配置DynamoDB表
- 写入CloudWatch日志
- 发送SNS通知（如果配置）

### 实例保护
- 使用 `exclude_instance_ids` 排除关键实例
- 只操作带有特定标签的实例
- 支持dry-run模式进行测试

### 配置安全
- 配置存储在DynamoDB中，支持加密
- 支持多环境部署（dev/staging/prod）
- 配置变更有时间戳记录

## 故障排除

### 常见问题

1. **实例没有被启动/停止**
   - 检查实例是否有正确的标签
   - 确认当前时间是否在触发窗口内
   - 查看Lambda日志确认执行情况

2. **权限错误**
   - 确认Lambda角色有足够的EC2权限
   - 检查实例是否在同一个AWS账户中

3. **时区问题**
   - 确认配置的时区是否正确
   - 检查服务器时间和目标时区的时差

4. **配置不生效**
   - 确认配置的 `enabled` 字段为 `true`
   - 检查是否在 `dry_run` 模式

### 调试命令

```bash
# 检查Lambda函数状态
aws lambda get-function --function-name <FUNCTION_NAME>

# 查看最近的执行日志
aws logs describe-log-streams \
    --log-group-name /aws/lambda/<FUNCTION_NAME> \
    --order-by LastEventTime \
    --descending \
    --max-items 1

# 手动触发并查看结果
aws lambda invoke \
    --function-name <FUNCTION_NAME> \
    --payload '{}' \
    --log-type Tail \
    response.json

# 查看DynamoDB表内容
aws dynamodb scan --table-name <TABLE_NAME>
```

## 成本优化

### ARM64架构优势
- 相比x86_64节省约20%的计算成本
- 更好的性能功耗比

### 按需计费
- Lambda按实际执行时间计费
- DynamoDB按需计费模式
- 无固定成本，只在使用时付费

### 资源优化
- 内存设置为256MB，适合大多数场景
- 超时时间5分钟，足够处理大量实例
- 每10分钟检查一次，平衡及时性和成本

## 扩展功能

### 添加更多触发条件
可以修改代码支持：
- 基于CPU使用率的智能调度
- 工作日/周末不同的调度策略
- 节假日特殊处理

### 集成其他服务
- 与AWS Systems Manager集成
- 支持RDS实例调度
- 集成Slack/Teams通知

### 多区域支持
- 支持跨区域实例管理
- 区域级别的配置管理

## 许可证

MIT License

## 贡献

欢迎提交Issue和Pull Request来改进这个项目。

## 支持

如有问题，请：
1. 查看CloudWatch日志
2. 检查配置是否正确
3. 参考故障排除部分
4. 提交Issue描述问题
