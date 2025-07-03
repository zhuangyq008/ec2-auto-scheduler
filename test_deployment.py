#!/usr/bin/env python3
"""
EC2调度器部署测试脚本
验证部署是否成功并测试基本功能
"""

import boto3
import json
import time
import argparse
from botocore.exceptions import ClientError

def test_lambda_function(function_name):
    """测试Lambda函数"""
    print(f"🧪 测试Lambda函数: {function_name}")
    
    lambda_client = boto3.client('lambda')
    
    try:
        # 调用Lambda函数
        response = lambda_client.invoke(
            FunctionName=function_name,
            Payload=json.dumps({})
        )
        
        # 读取响应
        payload = json.loads(response['Payload'].read())
        
        if response['StatusCode'] == 200:
            print("✅ Lambda函数调用成功")
            
            # 解析响应体
            if 'body' in payload:
                body = json.loads(payload['body'])
                print(f"📊 执行结果: {body.get('status', 'unknown')}")
                
                if 'actions' in body:
                    for action in body['actions']:
                        print(f"   - 操作: {action['action']}")
                        print(f"   - 成功: {len(action['success'])} 个实例")
                        print(f"   - 失败: {len(action['failed'])} 个实例")
            
            return True
        else:
            print(f"❌ Lambda函数调用失败: {payload}")
            return False
            
    except ClientError as e:
        print(f"❌ Lambda函数调用异常: {e}")
        return False

def test_dynamodb_config(table_name):
    """测试DynamoDB配置表"""
    print(f"🗄️  测试DynamoDB表: {table_name}")
    
    dynamodb = boto3.resource('dynamodb')
    
    try:
        table = dynamodb.Table(table_name)
        
        # 检查表状态
        table.load()
        print(f"✅ 表状态: {table.table_status}")
        
        # 扫描配置
        response = table.scan()
        configs = response['Items']
        
        print(f"📋 找到 {len(configs)} 个配置:")
        for config in configs:
            print(f"   - {config['config_id']}: {config.get('description', 'N/A')}")
            print(f"     标签: {config['tag_key']}={config['tag_value']}")
            print(f"     时间: {config['start_time']}-{config['stop_time']} ({config['timezone']})")
            print(f"     状态: {'启用' if config['enabled'] else '禁用'}")
        
        return True
        
    except ClientError as e:
        print(f"❌ DynamoDB表访问失败: {e}")
        return False

def test_iam_permissions(function_name):
    """测试IAM权限"""
    print("🔐 测试IAM权限...")
    
    lambda_client = boto3.client('lambda')
    
    try:
        # 获取函数配置
        response = lambda_client.get_function(FunctionName=function_name)
        role_arn = response['Configuration']['Role']
        
        print(f"📋 Lambda角色: {role_arn}")
        
        # 测试EC2权限
        ec2_client = boto3.client('ec2')
        try:
            ec2_client.describe_instances(MaxResults=5)
            print("✅ EC2权限正常")
        except ClientError:
            print("❌ EC2权限不足")
            return False
        
        return True
        
    except ClientError as e:
        print(f"❌ 权限检查失败: {e}")
        return False

def test_cloudwatch_logs(function_name):
    """测试CloudWatch日志"""
    print("📊 测试CloudWatch日志...")
    
    logs_client = boto3.client('logs')
    log_group_name = f"/aws/lambda/{function_name}"
    
    try:
        # 检查日志组
        response = logs_client.describe_log_groups(
            logGroupNamePrefix=log_group_name
        )
        
        if response['logGroups']:
            print("✅ CloudWatch日志组存在")
            
            # 获取最近的日志流
            streams_response = logs_client.describe_log_streams(
                logGroupName=log_group_name,
                orderBy='LastEventTime',
                descending=True,
                limit=1
            )
            
            if streams_response['logStreams']:
                stream_name = streams_response['logStreams'][0]['logStreamName']
                print(f"📝 最新日志流: {stream_name}")
                
                # 获取最近的日志事件
                events_response = logs_client.get_log_events(
                    logGroupName=log_group_name,
                    logStreamName=stream_name,
                    limit=5
                )
                
                if events_response['events']:
                    print("📋 最近的日志事件:")
                    for event in events_response['events'][-3:]:  # 显示最后3条
                        timestamp = time.strftime('%Y-%m-%d %H:%M:%S', 
                                                time.localtime(event['timestamp']/1000))
                        print(f"   [{timestamp}] {event['message'].strip()}")
            
            return True
        else:
            print("❌ CloudWatch日志组不存在")
            return False
            
    except ClientError as e:
        print(f"❌ CloudWatch日志检查失败: {e}")
        return False

def get_stack_outputs(stack_name):
    """获取CloudFormation堆栈输出"""
    cloudformation = boto3.client('cloudformation')
    
    try:
        response = cloudformation.describe_stacks(StackName=stack_name)
        stack = response['Stacks'][0]
        
        outputs = {}
        for output in stack.get('Outputs', []):
            outputs[output['OutputKey']] = output['OutputValue']
        
        return outputs
        
    except ClientError as e:
        print(f"❌ 获取堆栈输出失败: {e}")
        return {}

def main():
    parser = argparse.ArgumentParser(description='EC2调度器部署测试')
    parser.add_argument('--stack-name', default='ec2-scheduler-dev', 
                       help='CloudFormation堆栈名称')
    parser.add_argument('--function-name', help='Lambda函数名称')
    parser.add_argument('--table-name', help='DynamoDB表名称')
    
    args = parser.parse_args()
    
    print("🚀 开始测试EC2调度器部署...")
    print(f"📋 堆栈名称: {args.stack_name}")
    
    # 获取堆栈输出
    outputs = get_stack_outputs(args.stack_name)
    
    function_name = args.function_name or outputs.get('LambdaFunctionName')
    table_name = args.table_name or outputs.get('ConfigTableName')
    
    if not function_name:
        print("❌ 未找到Lambda函数名称")
        return False
    
    if not table_name:
        print("❌ 未找到DynamoDB表名称")
        return False
    
    print(f"🔧 Lambda函数: {function_name}")
    print(f"🗄️  DynamoDB表: {table_name}")
    print("-" * 50)
    
    # 执行测试
    tests = [
        ("DynamoDB配置表", lambda: test_dynamodb_config(table_name)),
        ("IAM权限", lambda: test_iam_permissions(function_name)),
        ("Lambda函数", lambda: test_lambda_function(function_name)),
        ("CloudWatch日志", lambda: test_cloudwatch_logs(function_name)),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n🧪 测试: {test_name}")
        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name} 测试通过")
            else:
                print(f"❌ {test_name} 测试失败")
        except Exception as e:
            print(f"❌ {test_name} 测试异常: {e}")
    
    print("\n" + "=" * 50)
    print(f"📊 测试结果: {passed}/{total} 通过")
    
    if passed == total:
        print("🎉 所有测试通过！部署成功！")
        print("\n📋 后续步骤:")
        print("1. 根据需要修改DynamoDB中的配置")
        print("2. 创建带有正确标签的EC2实例进行测试")
        print("3. 监控CloudWatch日志确认调度器正常工作")
        return True
    else:
        print("⚠️  部分测试失败，请检查配置")
        return False

if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)
