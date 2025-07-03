import json
import boto3
import os
import logging
from datetime import datetime, time
from typing import Dict, List, Optional, Tuple
import pytz
from botocore.exceptions import ClientError

# 配置日志
logger = logging.getLogger()
logger.setLevel(os.environ.get('LOG_LEVEL', 'INFO'))

# AWS客户端
ec2_client = boto3.client('ec2')
dynamodb = boto3.resource('dynamodb')
sns_client = boto3.client('sns')

# 环境变量
CONFIG_TABLE_NAME = os.environ['CONFIG_TABLE_NAME']
config_table = dynamodb.Table(CONFIG_TABLE_NAME)

class EC2Scheduler:
    def __init__(self):
        self.config = self._load_config()
    
    def _load_config(self) -> Dict:
        """从DynamoDB加载配置"""
        try:
            response = config_table.get_item(Key={'config_id': 'default'})
            if 'Item' not in response:
                logger.warning("未找到默认配置，使用内置默认值")
                return self._get_default_config()
            
            config = response['Item']
            logger.info(f"已加载配置: {json.dumps(config, default=str, ensure_ascii=False)}")
            return config
            
        except ClientError as e:
            logger.error(f"加载配置失败: {e}")
            return self._get_default_config()
    
    def _get_default_config(self) -> Dict:
        """获取默认配置"""
        return {
            'config_id': 'default',
            'tag_key': 'Env',
            'tag_value': 'Dev',
            'start_time': '09:00',
            'stop_time': '00:00',
            'timezone': 'Asia/Shanghai',
            'enabled': True,
            'dry_run': False,
            'exclude_instance_ids': [],
            'notification_topic': None
        }
    
    def _get_current_time_in_timezone(self) -> datetime:
        """获取指定时区的当前时间"""
        tz = pytz.timezone(self.config.get('timezone', 'Asia/Shanghai'))
        return datetime.now(tz)
    
    def _parse_time(self, time_str: str) -> time:
        """解析时间字符串"""
        hour, minute = map(int, time_str.split(':'))
        return time(hour, minute)
    
    def _should_start_instances(self, current_time: datetime) -> bool:
        """判断是否应该启动实例"""
        start_time = self._parse_time(self.config['start_time'])
        current_time_only = current_time.time()
        
        # 检查是否在启动时间的前后5分钟内
        start_datetime = datetime.combine(current_time.date(), start_time)
        start_datetime = start_datetime.replace(tzinfo=current_time.tzinfo)
        
        time_diff = abs((current_time - start_datetime).total_seconds())
        return time_diff <= 300  # 5分钟内
    
    def _should_stop_instances(self, current_time: datetime) -> bool:
        """判断是否应该停止实例"""
        stop_time = self._parse_time(self.config['stop_time'])
        current_time_only = current_time.time()
        
        # 处理跨天情况（如00:00）
        if stop_time.hour == 0 and stop_time.minute == 0:
            # 检查是否接近午夜
            midnight = time(0, 0)
            current_seconds = current_time_only.hour * 3600 + current_time_only.minute * 60
            midnight_seconds = 0
            
            # 在23:55-00:05之间认为是停止时间
            if current_seconds >= 23 * 3600 + 55 * 60 or current_seconds <= 5 * 60:
                return True
        else:
            # 正常时间检查
            stop_datetime = datetime.combine(current_time.date(), stop_time)
            stop_datetime = stop_datetime.replace(tzinfo=current_time.tzinfo)
            
            time_diff = abs((current_time - stop_datetime).total_seconds())
            return time_diff <= 300  # 5分钟内
        
        return False
    
    def _find_target_instances(self) -> List[Dict]:
        """查找目标EC2实例"""
        try:
            tag_key = self.config['tag_key']
            tag_value = self.config['tag_value']
            exclude_ids = self.config.get('exclude_instance_ids', [])
            
            response = ec2_client.describe_instances(
                Filters=[
                    {
                        'Name': f'tag:{tag_key}',
                        'Values': [tag_value]
                    },
                    {
                        'Name': 'instance-state-name',
                        'Values': ['running', 'stopped']
                    }
                ]
            )
            
            instances = []
            for reservation in response['Reservations']:
                for instance in reservation['Instances']:
                    if instance['InstanceId'] not in exclude_ids:
                        instances.append({
                            'InstanceId': instance['InstanceId'],
                            'State': instance['State']['Name'],
                            'InstanceType': instance['InstanceType'],
                            'Tags': instance.get('Tags', [])
                        })
            
            logger.info(f"找到 {len(instances)} 个匹配的实例")
            return instances
            
        except ClientError as e:
            logger.error(f"查找实例失败: {e}")
            return []
    
    def _start_instances(self, instance_ids: List[str]) -> Dict:
        """启动EC2实例"""
        if not instance_ids:
            return {'success': [], 'failed': []}
        
        if self.config.get('dry_run', False):
            logger.info(f"[DRY RUN] 将启动实例: {instance_ids}")
            return {'success': instance_ids, 'failed': []}
        
        try:
            response = ec2_client.start_instances(InstanceIds=instance_ids)
            success_ids = [inst['InstanceId'] for inst in response['StartingInstances']]
            logger.info(f"成功启动实例: {success_ids}")
            return {'success': success_ids, 'failed': []}
            
        except ClientError as e:
            logger.error(f"启动实例失败: {e}")
            return {'success': [], 'failed': instance_ids}
    
    def _stop_instances(self, instance_ids: List[str]) -> Dict:
        """停止EC2实例"""
        if not instance_ids:
            return {'success': [], 'failed': []}
        
        if self.config.get('dry_run', False):
            logger.info(f"[DRY RUN] 将停止实例: {instance_ids}")
            return {'success': instance_ids, 'failed': []}
        
        try:
            response = ec2_client.stop_instances(InstanceIds=instance_ids)
            success_ids = [inst['InstanceId'] for inst in response['StoppingInstances']]
            logger.info(f"成功停止实例: {success_ids}")
            return {'success': success_ids, 'failed': []}
            
        except ClientError as e:
            logger.error(f"停止实例失败: {e}")
            return {'success': [], 'failed': instance_ids}
    
    def _send_notification(self, message: str):
        """发送通知"""
        topic_arn = self.config.get('notification_topic')
        if not topic_arn:
            return
        
        try:
            sns_client.publish(
                TopicArn=topic_arn,
                Message=message,
                Subject='EC2调度器通知'
            )
            logger.info("通知已发送")
        except ClientError as e:
            logger.error(f"发送通知失败: {e}")
    
    def run(self) -> Dict:
        """执行调度逻辑"""
        if not self.config.get('enabled', True):
            logger.info("EC2调度器已禁用")
            return {'status': 'disabled', 'message': '调度器已禁用'}
        
        current_time = self._get_current_time_in_timezone()
        logger.info(f"当前时间: {current_time.strftime('%Y-%m-%d %H:%M:%S %Z')}")
        
        instances = self._find_target_instances()
        if not instances:
            logger.info("未找到匹配的实例")
            return {'status': 'no_instances', 'message': '未找到匹配的实例'}
        
        result = {
            'status': 'completed',
            'current_time': current_time.isoformat(),
            'total_instances': len(instances),
            'actions': []
        }
        
        # 判断应该执行的操作
        should_start = self._should_start_instances(current_time)
        should_stop = self._should_stop_instances(current_time)
        
        if should_start:
            # 启动已停止的实例
            stopped_instances = [inst['InstanceId'] for inst in instances if inst['State'] == 'stopped']
            if stopped_instances:
                start_result = self._start_instances(stopped_instances)
                result['actions'].append({
                    'action': 'start',
                    'success': start_result['success'],
                    'failed': start_result['failed']
                })
                
                if start_result['success']:
                    message = f"已启动 {len(start_result['success'])} 个实例: {start_result['success']}"
                    logger.info(message)
                    self._send_notification(message)
        
        elif should_stop:
            # 停止正在运行的实例
            running_instances = [inst['InstanceId'] for inst in instances if inst['State'] == 'running']
            if running_instances:
                stop_result = self._stop_instances(running_instances)
                result['actions'].append({
                    'action': 'stop',
                    'success': stop_result['success'],
                    'failed': stop_result['failed']
                })
                
                if stop_result['success']:
                    message = f"已停止 {len(stop_result['success'])} 个实例: {stop_result['success']}"
                    logger.info(message)
                    self._send_notification(message)
        
        else:
            logger.info("当前时间不在启动或停止时间窗口内")
            result['status'] = 'no_action'
            result['message'] = '当前时间不在启动或停止时间窗口内'
        
        return result

def lambda_handler(event, context):
    """Lambda入口函数"""
    logger.info(f"收到事件: {json.dumps(event, ensure_ascii=False)}")
    
    try:
        scheduler = EC2Scheduler()
        result = scheduler.run()
        
        logger.info(f"执行结果: {json.dumps(result, default=str, ensure_ascii=False)}")
        
        return {
            'statusCode': 200,
            'body': json.dumps(result, default=str, ensure_ascii=False)
        }
        
    except Exception as e:
        logger.error(f"执行失败: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({
                'status': 'error',
                'message': str(e)
            }, ensure_ascii=False)
        }
