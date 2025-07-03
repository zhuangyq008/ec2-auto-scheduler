import json
import boto3
import logging
from botocore.exceptions import ClientError
import urllib3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource('dynamodb')

def send_response(event, context, response_status, response_data=None, physical_resource_id=None):
    """发送CloudFormation自定义资源响应"""
    if response_data is None:
        response_data = {}
    
    response_url = event['ResponseURL']
    
    response_body = {
        'Status': response_status,
        'Reason': f'See CloudWatch Log Stream: {context.log_stream_name}',
        'PhysicalResourceId': physical_resource_id or context.log_stream_name,
        'StackId': event['StackId'],
        'RequestId': event['RequestId'],
        'LogicalResourceId': event['LogicalResourceId'],
        'Data': response_data
    }
    
    json_response_body = json.dumps(response_body)
    
    headers = {
        'content-type': '',
        'content-length': str(len(json_response_body))
    }
    
    try:
        http = urllib3.PoolManager()
        response = http.request('PUT', response_url, body=json_response_body, headers=headers)
        logger.info(f"CloudFormation响应状态: {response.status}")
    except Exception as e:
        logger.error(f"发送CloudFormation响应失败: {e}")

def create_default_config(table_name):
    """创建默认配置"""
    table = dynamodb.Table(table_name)
    
    default_config = {
        'config_id': 'default',
        'tag_key': 'Env',
        'tag_value': 'Dev',
        'start_time': '09:00',
        'stop_time': '00:00',
        'timezone': 'Asia/Shanghai',
        'enabled': True,
        'dry_run': False,
        'exclude_instance_ids': [],
        'notification_topic': None,
        'description': '默认EC2调度配置',
        'created_at': '2024-01-01T00:00:00Z',
        'updated_at': '2024-01-01T00:00:00Z'
    }
    
    try:
        # 检查配置是否已存在
        response = table.get_item(Key={'config_id': 'default'})
        if 'Item' in response:
            logger.info("默认配置已存在，跳过创建")
            return True
        
        # 创建默认配置
        table.put_item(Item=default_config)
        logger.info("默认配置创建成功")
        
        # 创建示例配置
        example_config = {
            'config_id': 'example',
            'tag_key': 'Environment',
            'tag_value': 'Development',
            'start_time': '08:30',
            'stop_time': '18:00',
            'timezone': 'Asia/Shanghai',
            'enabled': False,
            'dry_run': True,
            'exclude_instance_ids': ['i-1234567890abcdef0'],
            'notification_topic': 'arn:aws:sns:us-east-1:123456789012:ec2-notifications',
            'description': '示例配置 - 工作时间启停',
            'created_at': '2024-01-01T00:00:00Z',
            'updated_at': '2024-01-01T00:00:00Z'
        }
        
        table.put_item(Item=example_config)
        logger.info("示例配置创建成功")
        
        return True
        
    except ClientError as e:
        logger.error(f"创建配置失败: {e}")
        return False

def lambda_handler(event, context):
    """Lambda入口函数"""
    logger.info(f"收到事件: {json.dumps(event)}")
    
    try:
        request_type = event['RequestType']
        table_name = event['ResourceProperties']['TableName']
        
        if request_type == 'Create':
            logger.info("创建资源")
            success = create_default_config(table_name)
            if success:
                send_response(event, context, 'SUCCESS', {'Message': '配置初始化成功'})
            else:
                send_response(event, context, 'FAILED', {'Message': '配置初始化失败'})
                
        elif request_type == 'Update':
            logger.info("更新资源")
            # 对于更新，我们不做任何操作，避免覆盖用户配置
            send_response(event, context, 'SUCCESS', {'Message': '配置更新跳过'})
            
        elif request_type == 'Delete':
            logger.info("删除资源")
            # 对于删除，我们不删除配置，让用户手动决定
            send_response(event, context, 'SUCCESS', {'Message': '配置保留'})
            
    except Exception as e:
        logger.error(f"处理失败: {str(e)}", exc_info=True)
        send_response(event, context, 'FAILED', {'Message': str(e)})
    
    return {'statusCode': 200}
