#!/usr/bin/env python3
"""
EC2调度器配置管理工具
用于管理DynamoDB中的调度配置
"""

import boto3
import json
import argparse
import sys
from datetime import datetime
from botocore.exceptions import ClientError

class ConfigManager:
    def __init__(self, table_name):
        self.dynamodb = boto3.resource('dynamodb')
        self.table = self.dynamodb.Table(table_name)
        self.table_name = table_name
    
    def list_configs(self):
        """列出所有配置"""
        try:
            response = self.table.scan()
            configs = response['Items']
            
            if not configs:
                print("❌ 未找到任何配置")
                return
            
            print(f"📋 配置表: {self.table_name}")
            print(f"📊 共找到 {len(configs)} 个配置:\n")
            
            for config in configs:
                self._print_config(config)
                print("-" * 50)
                
        except ClientError as e:
            print(f"❌ 获取配置失败: {e}")
    
    def get_config(self, config_id):
        """获取指定配置"""
        try:
            response = self.table.get_item(Key={'config_id': config_id})
            if 'Item' not in response:
                print(f"❌ 未找到配置: {config_id}")
                return None
            
            config = response['Item']
            self._print_config(config)
            return config
            
        except ClientError as e:
            print(f"❌ 获取配置失败: {e}")
            return None
    
    def create_config(self, config_data):
        """创建新配置"""
        try:
            # 添加时间戳
            config_data['created_at'] = datetime.utcnow().isoformat() + 'Z'
            config_data['updated_at'] = datetime.utcnow().isoformat() + 'Z'
            
            self.table.put_item(Item=config_data)
            print(f"✅ 配置创建成功: {config_data['config_id']}")
            
        except ClientError as e:
            print(f"❌ 创建配置失败: {e}")
    
    def update_config(self, config_id, updates):
        """更新配置"""
        try:
            # 构建更新表达式
            update_expression = "SET "
            expression_values = {}
            
            for key, value in updates.items():
                update_expression += f"{key} = :{key}, "
                expression_values[f":{key}"] = value
            
            # 添加更新时间
            update_expression += "updated_at = :updated_at"
            expression_values[":updated_at"] = datetime.utcnow().isoformat() + 'Z'
            
            self.table.update_item(
                Key={'config_id': config_id},
                UpdateExpression=update_expression,
                ExpressionAttributeValues=expression_values
            )
            
            print(f"✅ 配置更新成功: {config_id}")
            
        except ClientError as e:
            print(f"❌ 更新配置失败: {e}")
    
    def delete_config(self, config_id):
        """删除配置"""
        try:
            self.table.delete_item(Key={'config_id': config_id})
            print(f"✅ 配置删除成功: {config_id}")
            
        except ClientError as e:
            print(f"❌ 删除配置失败: {e}")
    
    def _print_config(self, config):
        """打印配置信息"""
        print(f"🔧 配置ID: {config['config_id']}")
        print(f"📝 描述: {config.get('description', 'N/A')}")
        print(f"🏷️  标签: {config['tag_key']}={config['tag_value']}")
        print(f"⏰ 启动时间: {config['start_time']} ({config['timezone']})")
        print(f"⏹️  停止时间: {config['stop_time']} ({config['timezone']})")
        print(f"✅ 启用状态: {'是' if config['enabled'] else '否'}")
        print(f"🧪 测试模式: {'是' if config.get('dry_run', False) else '否'}")
        
        if config.get('exclude_instance_ids'):
            print(f"🚫 排除实例: {', '.join(config['exclude_instance_ids'])}")
        
        if config.get('notification_topic'):
            print(f"📧 通知主题: {config['notification_topic']}")
        
        print(f"📅 创建时间: {config.get('created_at', 'N/A')}")
        print(f"📅 更新时间: {config.get('updated_at', 'N/A')}")

def main():
    parser = argparse.ArgumentParser(description='EC2调度器配置管理工具')
    parser.add_argument('--table', required=True, help='DynamoDB表名')
    
    subparsers = parser.add_subparsers(dest='command', help='可用命令')
    
    # 列出配置
    subparsers.add_parser('list', help='列出所有配置')
    
    # 获取配置
    get_parser = subparsers.add_parser('get', help='获取指定配置')
    get_parser.add_argument('config_id', help='配置ID')
    
    # 创建配置
    create_parser = subparsers.add_parser('create', help='创建新配置')
    create_parser.add_argument('--config-id', required=True, help='配置ID')
    create_parser.add_argument('--tag-key', default='Env', help='EC2标签键')
    create_parser.add_argument('--tag-value', default='Dev', help='EC2标签值')
    create_parser.add_argument('--start-time', default='09:00', help='启动时间 (HH:MM)')
    create_parser.add_argument('--stop-time', default='00:00', help='停止时间 (HH:MM)')
    create_parser.add_argument('--timezone', default='Asia/Shanghai', help='时区')
    create_parser.add_argument('--enabled', action='store_true', default=True, help='启用调度')
    create_parser.add_argument('--dry-run', action='store_true', help='测试模式')
    create_parser.add_argument('--description', help='配置描述')
    create_parser.add_argument('--exclude-instances', nargs='*', help='排除的实例ID列表')
    create_parser.add_argument('--notification-topic', help='SNS通知主题ARN')
    
    # 更新配置
    update_parser = subparsers.add_parser('update', help='更新配置')
    update_parser.add_argument('config_id', help='配置ID')
    update_parser.add_argument('--tag-key', help='EC2标签键')
    update_parser.add_argument('--tag-value', help='EC2标签值')
    update_parser.add_argument('--start-time', help='启动时间 (HH:MM)')
    update_parser.add_argument('--stop-time', help='停止时间 (HH:MM)')
    update_parser.add_argument('--timezone', help='时区')
    update_parser.add_argument('--enabled', type=bool, help='启用调度')
    update_parser.add_argument('--dry-run', type=bool, help='测试模式')
    update_parser.add_argument('--description', help='配置描述')
    
    # 删除配置
    delete_parser = subparsers.add_parser('delete', help='删除配置')
    delete_parser.add_argument('config_id', help='配置ID')
    delete_parser.add_argument('--confirm', action='store_true', help='确认删除')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    manager = ConfigManager(args.table)
    
    if args.command == 'list':
        manager.list_configs()
        
    elif args.command == 'get':
        manager.get_config(args.config_id)
        
    elif args.command == 'create':
        config_data = {
            'config_id': args.config_id,
            'tag_key': args.tag_key,
            'tag_value': args.tag_value,
            'start_time': args.start_time,
            'stop_time': args.stop_time,
            'timezone': args.timezone,
            'enabled': args.enabled,
            'dry_run': args.dry_run,
            'exclude_instance_ids': args.exclude_instances or [],
            'description': args.description or f'配置 {args.config_id}'
        }
        
        if args.notification_topic:
            config_data['notification_topic'] = args.notification_topic
        
        manager.create_config(config_data)
        
    elif args.command == 'update':
        updates = {}
        
        if args.tag_key:
            updates['tag_key'] = args.tag_key
        if args.tag_value:
            updates['tag_value'] = args.tag_value
        if args.start_time:
            updates['start_time'] = args.start_time
        if args.stop_time:
            updates['stop_time'] = args.stop_time
        if args.timezone:
            updates['timezone'] = args.timezone
        if args.enabled is not None:
            updates['enabled'] = args.enabled
        if args.dry_run is not None:
            updates['dry_run'] = args.dry_run
        if args.description:
            updates['description'] = args.description
        
        if not updates:
            print("❌ 没有指定要更新的字段")
            return
        
        manager.update_config(args.config_id, updates)
        
    elif args.command == 'delete':
        if not args.confirm:
            print("❌ 请使用 --confirm 参数确认删除操作")
            return
        
        manager.delete_config(args.config_id)

if __name__ == '__main__':
    main()
