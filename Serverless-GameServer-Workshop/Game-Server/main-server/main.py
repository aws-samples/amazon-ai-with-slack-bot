import json
import random
import string
import boto3

# main_server 为表名对应于 template.yaml 中的 Resources -> MainServerTable -> Properties -> TableName
main_server_table = boto3.resource('dynamodb').Table("main_server")

def main_handler(event, context):
    try:
        #print(event) # 通过打印event，可以在CloudWatch Log看到event的结构
        # 获取routeKey
        route_key = event.get('requestContext', {}).get('routeKey')

        # 获取connectionId，针对每个 WebSocket 连接，API Gateway 会分配一个 connectionId
        connection_id = event.get('requestContext', {}).get('connectionId')
        event_body = event.get('body')
        event_body = json.loads(event_body if event_body is not None else '{}')

        if route_key is None or connection_id is None:
            return {'statusCode': 400, 'body': 'routeKey or connectionId is None'}

        # Handle on connect
        if route_key == '$connect':
            # 如果连接时没有 user_id 参数，则生成一个随机的guest user id
            tmp_guest_user_id = ''.join(random.choices(string.ascii_uppercase+string.digits, k=12))
            user_id = event.get('queryStringParameters', {'user_id': tmp_guest_user_id}).get('user_id')
            main_server_table.put_item(Item={'user_id': user_id, 'connection_id': connection_id})
            print(f"connect user_id: {user_id}, connection_id: {connection_id}") # 打印user_id 和 connection_id，可以在CloudWatch Log看到user_id
            return {'statusCode': 200}

        # Handle on disconnect
        elif route_key == '$disconnect':
            main_server_table.delete_item(Key={'connection_id': connection_id})
            print(f"disconnect connection_id: {connection_id}") # 打印 connection_id，可以在CloudWatch Log看到 connection_id
            return {'statusCode': 200}
        else:
            print("routeKey '%s' not registered" % event_body["action"])
            return {'statusCode': 400}

    except Exception as err:
        print(err)
        return {'statusCode': 500}
