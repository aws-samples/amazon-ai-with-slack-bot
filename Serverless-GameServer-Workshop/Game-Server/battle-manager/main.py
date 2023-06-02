import json
import boto3

main_server_table = boto3.resource('dynamodb').Table('main_server')
common_resources_table = boto3.resource('dynamodb').Table('common_resources')

# 通过 user_id 获取 connection_id
# 这里做了遍历，生产环境中应该使用索引
def getConnIDFromUserID(user_id):
    connection_ids = []
    scan_response = main_server_table.scan(ProjectionExpression='connection_id')
    connection_ids = [item['connection_id'] for item in scan_response['Items']]
    for connection_id in connection_ids:
        if getUserIDFromConnID(connection_id) == user_id:
            return connection_id
    print("Cannot get connection_id, user_id=%s" % (user_id))
    return -1

def server_response(connection_id, message):
    apig_management_client = boto3.client('apigatewaymanagementapi',endpoint_url="https://aabbcc.execute-api.us-east-1.amazonaws.com/dev")
    send_response = apig_management_client.post_to_connection(Data=message, ConnectionId=connection_id)

# 通过 connection_id 获取 user_id
def getUserIDFromConnID(connection_id):
    item_response = main_server_table.get_item(Key={'connection_id': connection_id})
    if 'Item' in item_response:
        user_id = item_response['Item']['user_id']
    else:
        user_id = None
    return user_id

# 通过 user_id 获取 room_name
def getRoomNameFromUserId(user_id):
    player_room_key = "%s_in_room" % user_id
    item_response = common_resources_table.get_item(Key={'resource_name': player_room_key})
    if 'Item' in item_response:
        room_name = item_response['Item']['room_name']
    else:
        room_name = None
    return room_name

# 通过 user_id, room_name 获取对手的 user_id
def getPeerPlayerIDFromRoom(user_id, room_name):
    item_response = common_resources_table.get_item(Key={'resource_name': room_name})
    players_in_room = item_response['Item']['players_in_room']
    for player_id in players_in_room:
        if player_id != user_id:
            return player_id

# 获取对局信息
def battleMgrPrecheck(connection_id):
    user_id = getUserIDFromConnID(connection_id)
    room_name = getRoomNameFromUserId(user_id)
    peer_player_id = getPeerPlayerIDFromRoom(user_id, room_name)
    return (user_id, room_name, peer_player_id)

# 对局结算
def battle_settlement(battle_players, room_name):
    user_id_1 = battle_players[0]
    user_id_2 = battle_players[1]

    in_battle_score_1 = int(common_resources_table.get_item(Key={'resource_name': "%s_in_battle_score" % user_id_1})['Item']['score'])
    in_battle_score_2 = int(common_resources_table.get_item(Key={'resource_name': "%s_in_battle_score" % user_id_2})['Item']['score'])

    winner_id = None
    if in_battle_score_1 > in_battle_score_2:
        winner_id = user_id_1
    elif in_battle_score_1 < in_battle_score_2:
        winner_id = user_id_2

    message = '{"action":"battle_settlement", "data":"UNKNOW"}'
    for user_id in battle_players:
        in_battle_score = int(common_resources_table.get_item(Key={'resource_name': "%s_in_battle_score" % user_id})['Item']['score'])
        connection_id = getConnIDFromUserID(user_id)
        if winner_id == None:
            message = '{"action":"battle_settlement", "data":"DRAW"}'
            print("Battle DRAW, user_id=%s, score=%d" % (user_id, in_battle_score))
        elif user_id == winner_id:
            message = '{"action":"battle_settlement", "data":"WIN"}'
            print("Battle WIN, user_id=%s, score=%d" % (user_id, in_battle_score))
        else:
            message = '{"action":"battle_settlement", "data":"LOSE"}'
            print("Battle LOSE, user_id=%s, score=%d" % (user_id, in_battle_score))
        server_response(connection_id, message)

    clear_battle_data(battle_players, room_name)

# 清除对局数据
def clear_battle_data(battle_players, room_name):
    for user_id in battle_players:
        common_resources_table.delete_item(Key={'resource_name': "%s_in_battle_score" % user_id})
        common_resources_table.delete_item(Key={'resource_name': "%s_in_battle_die" % user_id})

    with common_resources_table.batch_writer() as batch:
        item_response = common_resources_table.get_item(Key={'resource_name': room_name})
        players_in_room = item_response['Item']['players_in_room']
        for user_id in players_in_room:
            batch.delete_item(Key={"resource_name":"%s_in_room" % user_id})
        batch.delete_item(Key={"resource_name":room_name})
    print("All battle data cleared. room_name=%s, user_id=%s" % (room_name, battle_players))

def main_handler(event, context):
    try:
        # Validate request parameters
        route_key = event.get('requestContext', {}).get('routeKey')
        connection_id = event.get('requestContext', {}).get('connectionId')
        event_body = event.get('body')
        event_body = json.loads(event_body if event_body is not None else '{}')

        if route_key is None or connection_id is None:
            return {'statusCode': 400}

        if route_key == 'attack':
            # 根据 connection_id 获取 对局信息
            user_id, room_name, peer_player_id = battleMgrPrecheck(connection_id)
            # 获取对手的 connection_id
            connection_id = getConnIDFromUserID(peer_player_id)
            # 向对手发送攻击消息
            message = '{"action":"attacked", "data":"FREEZE"}'
            server_response(connection_id, message)
            print("[handle_attack] Player be attacked. attacker_id=%s, victim_id=%s, room_name=%s." % (user_id, peer_player_id, room_name))
            return {'statusCode': 200}

        if route_key == 'die':
            user_id, room_name, peer_player_id = battleMgrPrecheck(connection_id)
            in_battle_die = "%s_in_battle_die" % user_id
            common_resources_table.put_item(Item={'resource_name': in_battle_die, 'die': 1})
            peer_connection_id = getConnIDFromUserID(peer_player_id)
            item_response = common_resources_table.get_item(Key={'resource_name': "%s_in_battle_die" % peer_player_id})
            if 'Item' not in item_response:
                peer_connection_id = getConnIDFromUserID(peer_player_id)
                message = '{"action":"player_died", "data":"%s"}' % user_id
                server_response(peer_connection_id, message)
                print("[handle_die] Player died. died_user_id=%s, room_name=%s." % (user_id, room_name))
                return {'statusCode': 200}
            else:
                message = '{"action":"player_died", "data":"all"}'
                server_response(peer_connection_id, message)
                print("[handle_die] Player all died, start battle settlement.")
                battle_settlement([user_id, peer_player_id], room_name)
                return {'statusCode': 200}

        if route_key == 'syncscore':
            score = event_body["score"]
            user_id, room_name, peer_player_id = battleMgrPrecheck(connection_id)
            in_battle_score = "%s_in_battle_score" % user_id
            common_resources_table.put_item(Item={'resource_name': in_battle_score, 'score': score})
            peer_connection_id = getConnIDFromUserID(peer_player_id)
            message = '{"action":"player_syncscore", "data":%d}' % score
            server_response(peer_connection_id, message)
            print("[handle_syncscore]. user_id=%s, room_name=%s, current_score=%d." % (user_id, room_name, score))
            return {'statusCode': 200}

    except Exception as err:
        print(err)
        return {'statusCode': 500}
