import json
import boto3

# 通过boto3.resource('dynamodb')获取DynamoDB的资源
# player_info 为表名对应于 template.yaml 中的 Resources -> PlayerInfoTable -> Properties -> TableName
player_info_table = boto3.resource('dynamodb').Table("player_info")

# 设置返回的headers以支持CORS
headers = {
    'Access-Control-Allow-Origin': '*',
    'Access-Control-Allow-Methods': 'POST,OPTIONS',
    'Access-Control-Allow-Headers':'Content-Type,Access-Control-Allow-Origin,Access-Control-Allow-Methods,Access-Control-Allow-Headers',
}

# 判断user_id是否存在
def getUserInfo(user_id):
    response = player_info_table.get_item(Key={"user_id": user_id})
    if "Item" in response:
        return response["Item"]
    else:
        return None

def main_handler(event, context):
    try:
        print(event) # 通过打印event，可以在CloudWatch Log看到event的结构
        path = event.get('path') # 获取path
        method = event.get('httpMethod') # 获取method
        event_body = event.get('body') # 获取body
        event_body = json.loads(event_body if event_body is not None else '{}') # 将body转换为dict
        # 如果path为/create_user，对应于 template.yaml 中的 /create_user 路径
        if path == "/create_user":
            if method == "POST":
                if "user_id" in event_body and event_body["user_id"] != "":
                    if getUserInfo(event_body["user_id"]) == None:
                        player_info_table.put_item(Item={"user_id": event_body["user_id"]})
                        return { 'statusCode': 200, 'headers': headers, 'body': json.dumps({"msg": "create user success"}), }
                    else:
                        return { 'statusCode': 400, 'headers': headers, 'body': json.dumps({"msg": "user_id exists"}), }
                else:
                    return { 'statusCode': 400, 'headers': headers, 'body': json.dumps({"msg": "empty user_id"}), }
            elif method == "OPTIONS":
                return { 'statusCode': 200, 'headers': headers, 'body': json.dumps({"msg": "options success"}), }
        elif path == "/delete_user":
            if method == "POST":
                if "user_id" in event_body and event_body["user_id"] != "":
                    if getUserInfo(event_body["user_id"]) != None:
                        player_info_table.delete_item(Key={"user_id": event_body["user_id"]})
                        return { 'statusCode': 200, 'headers': headers, 'body': json.dumps({"msg": "delete user success"}), }
                    else:
                        return { 'statusCode': 400, 'headers': headers, 'body': json.dumps({"msg": "user_id not exists"}), }
                else:
                    return { 'statusCode': 400, 'headers': headers, 'body': json.dumps({"msg": "empty user_id"}), }
            elif method == "OPTIONS":
                return { 'statusCode': 200, 'headers': headers, 'body': json.dumps({"msg": "options success"}), }
    except Exception as err:
        print(err)
        return { 'statusCode': 500, 'headers': headers, 'body': json.dumps({"msg": str(err)}) }
