import json
import boto3

main_server_table = boto3.resource('dynamodb').Table('main_server')
common_resources_table = boto3.resource('dynamodb').Table('common_resources')

# 通过 connection_id 获取 user_id
def getUserIDFromConnID(connection_id):
    item_response = main_server_table.get_item(Key={'connection_id': connection_id})
    if 'Item' in item_response:
        user_id = item_response['Item']['user_id']
    else:
        user_id = None
    return user_id

# 通过 user_id 获取 connection_id
# 这里做了遍历，生产环境中应该使用索引
def getConnIDFromUserID(user_id):
    connection_ids = []
    scan_response = main_server_table.scan(ProjectionExpression='connection_id')
    connection_ids = [item['connection_id'] for item in scan_response['Items']]
    for connection_id in connection_ids:
        if getUserIDFromConnID(connection_id) == user_id:
            return connection_id
    print(f"Cannot get connection_id, user_id={user_id}")
    return -1

# 通过 APIGatewayManagementAPI 发送消息给客户端
# WSS_SERVER 为 API Gateway 的域名
def server_response(connection_id, message):
    apig_management_client = boto3.client('apigatewaymanagementapi',endpoint_url="https://4deycosvil.execute-api.us-east-1.amazonaws.com/dev")
    send_response = apig_management_client.post_to_connection(Data=message, ConnectionId=connection_id)

# 创建新房间
def createRoom(user_id):
    room_name = "%s_ROOM" % user_id

    # 初始化房间信息
    players_in_room = [user_id]

    # 记录当前可加入的房间以及房间内的玩家
    common_resources_table.put_item(Item={'resource_name': 'available_rooms', 'room_names': [room_name]})
    common_resources_table.put_item(Item={'resource_name': room_name, 'players_in_room': players_in_room})

    # 添加一个索引，记录玩家所在的房间
    player_room_key = "%s_in_room" % user_id
    common_resources_table.put_item(Item={'resource_name': player_room_key, 'room_name': room_name})
    print("User created room. user_id=%s, room_name=%s." % (user_id, room_name))
    return room_name

# 加入其他玩家的房间
def joinOthersRoom(user_id, room_name):
    # 更新房间信息
    item_response = common_resources_table.get_item(Key={'resource_name': room_name})
    players_in_room = item_response['Item']['players_in_room']
    peer_player_id = players_in_room[0]
    players_in_room.append(user_id)
    common_resources_table.put_item(Item={'resource_name': room_name, 'players_in_room': players_in_room})

    # 添加一个索引，记录玩家所在的房间
    player_room_key = "%s_in_room" % user_id
    common_resources_table.put_item(Item={'resource_name': player_room_key, 'room_name': room_name})
    print("User joined other's room. user_id=%s, room_name=%s." % (user_id, room_name))
    return peer_player_id

def main_handler(event, context):
    try:
        # Validate request parameters
        route_key = event.get('requestContext', {}).get('routeKey')
        connection_id = event.get('requestContext', {}).get('connectionId')
        event_body = event.get('body')
        event_body = json.loads(event_body if event_body is not None else '{}')

        if route_key is None or connection_id is None:
            return {'statusCode': 400}

        if route_key == 'joinroom':
            user_id = getUserIDFromConnID(connection_id)
            # 当有新玩家加入时，先检查是否有空余房间，如果有则加入，如果没有则创建新房间
            item_response = common_resources_table.get_item(Key={'resource_name': 'available_rooms'})
            room_name = "" # 房间名
            peer_player_id = "" # 对手的玩家ID

            if 'Item' in item_response:
                room_names = item_response['Item']['room_names']
                # 如果没有空余房间，则创建新房间
                if len(room_names) == 0:
                    room_name = createRoom(user_id)
                else:
                    room_name = room_names.pop()
                    peer_player_id = joinOthersRoom(user_id, room_name)
                    # 匹配完成，更新可用房间列表
                    common_resources_table.put_item(Item={'resource_name': 'available_rooms', 'room_names': room_names})
            # 如果没有空余房间，则创建新房间
            else:
                room_name = createRoom(user_id)

            # 加入房间后，返回 json 数据给客户端处理
            message = '{"action":"joinroom", "data":"%s"}' % room_name
            server_response(connection_id, message)
            # 如果匹配完成，则 peer_player_id 不为空，需要通知双方对手
            if peer_player_id != "":
                message = '{"action":"peer_player_id", "data":"%s"}' % peer_player_id
                server_response(connection_id, message)

                peer_connection_id = getConnIDFromUserID(peer_player_id)
                message = '{"action":"peer_player_id", "data":"%s"}' % user_id
                server_response(peer_connection_id, message)

            return {'statusCode': 200}

        if route_key == 'exitroom':
            print('test exitroom')
            return {'statusCode': 200}

        if route_key == 'destroyroom':
            print('test destroyroom')
            return {'statusCode': 200}

    except Exception as err:
        print(err)
        return {'statusCode': 500}
