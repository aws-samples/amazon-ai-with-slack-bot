import json
import logging
import random
import string
import os
import boto3
import redis
from botocore.exceptions import ClientError
import settings

# Configs
WSS_SERVER = None
REDIS_ENDPOINT = "xxx.cache.amazonaws.com"
REGION = "ap-southeast-1"
WIN_SCORE = 100
LOSE_SCORE = -100

# DDB tables
connection_info_table = None
common_resources_table = None
player_info_table = None

# Redis
redis_client = None
LEADERBOARDS_SINGLE = "leaderboards_single"
LEADERBOARDS_MULTI= "leaderboards_multi"

# Logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Get dynamodb table
connection_info_table_name = os.environ['mainserver_tablename']
common_resources_table_name = os.environ['commonresource_tablename']
player_info_table_name = os.environ['palyerinfo_tablename']

def __init__():
    try:
        global WSS_SERVER
        apigatewayv2_client = boto3.client("apigatewayv2")
        apis = apigatewayv2_client.get_apis()["Items"]
        for api in apis:
            if api["Name"] == settings.PurgatoryMain_API_NAME:
                WSS_SERVER = "https://%s.execute-api.%s.amazonaws.com/%s" % (api["ApiId"], REGION, settings.STAGE)


        global connection_info_table
        global common_resources_table
        global player_info_table

        connection_info_table = boto3.resource('dynamodb').Table(connection_info_table_name)
        common_resources_table = boto3.resource('dynamodb').Table(common_resources_table_name)
        player_info_table = boto3.resource('dynamodb').Table(player_info_table_name)

        # Redis
        global redis_client
        pool = redis.ConnectionPool(host=REDIS_ENDPOINT, port=6379, db=0)
        redis_client = redis.Redis(connection_pool=pool)

        logger.info("Utils init successfully.")
    except Exception as err:
        logger.exception("Something went wrong when initializing utils: %s", err)

# -- Connection Related -- #
def isValidUserID(connection_id, user_id):
    item_response = connection_info_table.get_item(Key={'connection_id': connection_id})
    if 'Item' in item_response:
        return user_id == item_response['Item']['user_id']
    return False

def getUserIDFromConnID(connection_id):
    item_response = connection_info_table.get_item(Key={'connection_id': connection_id})
    if 'Item' in item_response:
        user_id = item_response['Item']['user_id']
    else:
        user_id = None
    return user_id

def getConnIDFromUserID(user_id):
    connection_ids = []
    scan_response = connection_info_table.scan(ProjectionExpression='connection_id')
    connection_ids = [item['connection_id'] for item in scan_response['Items']]
    for connection_id in connection_ids:
        if getUserIDFromConnID(connection_id) == user_id:
            return connection_id
    logger.error("Cannot get connection_id, user_id=%s" % (user_id))
    return -1

def getPeerPlayerIDFromRoom(user_id, room_name):
    item_response = common_resources_table.get_item(Key={'resource_name': room_name})
    players_in_room = item_response['Item']['players_in_room']
    for player_id in players_in_room:
        if player_id != user_id:
            return player_id

def handle_connect(connection_id, user_id):
    status_code = 200
    try:
        connection_info_table.put_item(
            Item={'connection_id': connection_id, 'user_id': user_id})
        logger.info(
            "Added connection. connection_id='%s', user_id='%s'.", connection_id, user_id)
    except ClientError:
        logger.exception(
            "Couldn't add connection. connection_id=%s, user_id=%s.", connection_id, user_id)
        status_code = 503
    return status_code

def handle_disconnect(connection_id, user_id):
    status_code = 200
    try:
        connection_info_table.delete_item(Key={'connection_id': connection_id})
        logger.info("Disconnected connection, clear connection data in DDB. connection_id='%s' user_id='%s'", connection_id, user_id)
    except ClientError:
        logger.exception("Couldn't disconnect connection. connection_id='%s'.", connection_id)
        status_code = 503
    return status_code

def server_response(connection_id, message):
    apig_management_client = boto3.client('apigatewaymanagementapi',endpoint_url=WSS_SERVER)
    send_response = apig_management_client.post_to_connection(Data=message, ConnectionId=connection_id)

# -- Room Related -- #

def getRoomNameFromUserId(user_id):
    player_room_key = "%s_in_room" % user_id
    item_response = common_resources_table.get_item(Key={'resource_name': player_room_key})
    if 'Item' in item_response:
        room_name = item_response['Item']['room_name']
    else:
        room_name = None
    return room_name


def handle_joinroom(connection_id, user_id):
    item_response = common_resources_table.get_item(Key={'resource_name': 'available_rooms'})
    room_name = ""
    peer_player_id = ""

    if 'Item' in item_response:
        room_names = item_response['Item']['room_names']
        if len(room_names) == 0:
            room_name = createRoom(user_id)
        else:
            room_name = room_names.pop()
            peer_player_id = joinOthersRoom(user_id, room_name)
            # The room is full and poped, update available_rooms
            common_resources_table.put_item(Item={'resource_name': 'available_rooms', 'room_names': room_names})
    else:
        room_name = createRoom(user_id)

    message = '{"action":"joinroom", "data":"%s"}' % room_name
    server_response(connection_id, message)
    if peer_player_id != "":
        message = '{"action":"peer_player_id", "data":"%s"}' % peer_player_id
        server_response(connection_id, message)

        peer_connection_id = getConnIDFromUserID(peer_player_id)
        message = '{"action":"peer_player_id", "data":"%s"}' % user_id
        server_response(peer_connection_id, message)

    return 200

def handle_exitroom(user_id, room_name):
    try:
        with common_resources_table.batch_writer() as batch:
            # Update available_rooms
            item_response = common_resources_table.get_item(Key={'resource_name': 'available_rooms'})
            room_names = item_response['Item']['room_names']

            # Update players_in_room
            item_response = common_resources_table.get_item(Key={'resource_name': room_name})
            players_in_room = item_response['Item']['players_in_room']
            players_in_room.remove(user_id)
            if len(players_in_room) == 0:
                # room is empty, delete room_name in available_rooms and room resource
                batch.delete_item(Key={"resource_name":room_name})
                room_names.remove(room_name)
                batch.put_item(Item={'resource_name': 'available_rooms', 'room_names': room_names})
            else:
                room_names.append(room_name)
                batch.put_item(Item={'resource_name': 'available_rooms', 'room_names': room_names})
                batch.put_item(Item={'resource_name': room_name, 'players_in_room': players_in_room})

            batch.delete_item(Key={"resource_name":"%s_in_room" % user_id})
            logger.info("User exited room. user_id=%s, room_name=%s." % (user_id, room_name))
            return 200
    except Exception as err:
        logger.exception("Something went wrong: %s", err)
        return 500

def handle_destroyroom(room_name):
    destroyroom(room_name)

def destroyroom(room_name):
    with common_resources_table.batch_writer() as batch:
        item_response = common_resources_table.get_item(Key={'resource_name': room_name})
        players_in_room = item_response['Item']['players_in_room']
        for user_id in players_in_room:
            batch.delete_item(Key={"resource_name":"%s_in_room" % user_id})
        batch.delete_item(Key={"resource_name":room_name})
        logger.info("Room destroyed. room_name=%s." % room_name)
        return 200

def handle_attack(user_id, peer_player_id, room_name):
    connection_id = getConnIDFromUserID(peer_player_id)
    message = '{"action":"attacked", "data":"FREEZE"}'
    server_response(connection_id, message)
    logger.info("[handle_attack] Player be attacked. attacker_id=%s, victim_id=%s, room_name=%s." % (user_id, peer_player_id, room_name))
    return 200

def handle_die(user_id, peer_player_id, room_name):
    in_battle_die = "%s_in_battle_die" % user_id
    redis_client.set(in_battle_die, 1)
    peer_connection_id = getConnIDFromUserID(peer_player_id)
    if redis_client.get("%s_in_battle_die" % peer_player_id) == None:
        peer_connection_id = getConnIDFromUserID(peer_player_id)
        message = '{"action":"player_died", "data":"%s"}' % user_id
        server_response(peer_connection_id, message)
        logger.info("[handle_die] Player died. died_user_id=%s, room_name=%s." % (user_id, room_name))
        return 200
    else:
        message = '{"action":"player_died", "data":"all"}'
        server_response(peer_connection_id, message)
        logger.info("[handle_die] Player all died, start battle settlement.")
        battle_settlement([user_id, peer_player_id], room_name)
        return 200

def handle_syncscore(user_id, peer_player_id, room_name, score):
    in_battle_score = "%s_in_battle_score" % user_id
    redis_client.set(in_battle_score, score)
    connection_id = getConnIDFromUserID(peer_player_id)
    message = '{"action":"player_syncscore", "data":%d}' % score
    server_response(connection_id, message)
    logger.info("[handle_syncscore]. user_id=%s, room_name=%s, current_score=%d." % (user_id, room_name, score))
    return 200

def createRoom(user_id):
    room_name = "%s_ROOM" % user_id

    # Init current which players in room
    players_in_room = [user_id]

    common_resources_table.put_item(Item={'resource_name': 'available_rooms', 'room_names': [room_name]})
    common_resources_table.put_item(Item={'resource_name': room_name, 'players_in_room': players_in_room})

    # Player's current room key
    player_room_key = "%s_in_room" % user_id
    common_resources_table.put_item(Item={'resource_name': player_room_key, 'room_name': room_name})
    logger.info("User created room. user_id=%s, room_name=%s." % (user_id, room_name))
    return room_name

def joinOthersRoom(user_id, room_name):
    item_response = common_resources_table.get_item(Key={'resource_name': room_name})
    players_in_room = item_response['Item']['players_in_room']
    peer_player_id = players_in_room[0]
    players_in_room.append(user_id)
    common_resources_table.put_item(Item={'resource_name': room_name, 'players_in_room': players_in_room})

    # Player's current room key
    player_room_key = "%s_in_room" % user_id
    common_resources_table.put_item(Item={'resource_name': player_room_key, 'room_name': room_name})
    logger.info("User joined other's room. user_id=%s, room_name=%s." % (user_id, room_name))

    return peer_player_id

def getUserInfo(user_id):
    item_response = player_info_table.get_item(Key={'user_id': user_id})
    if 'Item' not in item_response:
        return None
    else:
        return item_response['Item']

def handle_create_user(user_id):
    if user_id == "":
        res_msg =  "empty user_id"
        response = {'statusCode': 400, 'body': json.dumps({"msg": res_msg})}
        return response

    user_info = getUserInfo(user_id)
    if user_info != None:
        response = {'statusCode': 400, 'body': json.dumps({"msg": "Name Exists"})}
        return response

    user_info = {"user_id": user_id, "win": 0, "lose": 0, "highest_score": 0, "battle_score": 0}
    player_info_table.put_item(Item=user_info)
    redis_client.zadd(LEADERBOARDS_SINGLE, {user_id: 0})
    redis_client.zadd(LEADERBOARDS_MULTI, {user_id: 0})

    response = {'statusCode': 200, 'body': json.dumps({"msg": "Success"})}
    logger.info("Player '%s' create successfully." % user_id)
    return response

def handle_delete_user(user_id):
    if user_id == "":
        res_msg =  "empty user_id"
        response = {'statusCode': 400, 'body': json.dumps({"msg": res_msg})}
        return response

    user_info = getUserInfo(user_id)
    if user_info == None:
        response = {'statusCode': 400, 'body': json.dumps({"msg": "Name Not Exists"})}
        return response

    player_info_table.delete_item(Key={"user_id": user_id})

    redis_client.zrem(LEADERBOARDS_SINGLE, user_id)
    redis_client.zrem(LEADERBOARDS_MULTI, user_id)

    response = {'statusCode': 200, 'body': json.dumps({"msg": "Delete user Success"})}
    logger.info("Player '%s' delete successfully." % user_id)
    return response

def handle_set_score_single(user_id, score):
    if user_id == "" or score == "":
        res_msg =  "Invalid post data."
        response = {'statusCode': 400, 'body': json.dumps({"msg": res_msg})}
        return response

    user_info = getUserInfo(user_id)
    if user_info == None:
        response = {'statusCode': 400, 'body': json.dumps({"msg": "User not Exists"})}
        return response

    if user_info["highest_score"] < score:
        user_info["highest_score"] = score
        player_info_table.put_item(Item=user_info)
        res_msg = "highest_score updated to %d" % score
        response = {'statusCode': 200, 'body': json.dumps({"msg": res_msg})}
        logger.info(res_msg)
        update_leaderboards_single(user_id, score)
    else:
        res_msg = "highest_score remains %d" % user_info["highest_score"]
        response = {'statusCode': 200, 'body': json.dumps({"msg": res_msg})}
    return response

def handle_set_score_multi(user_id, is_win):
    print("handle_set_score_multi", user_id, is_win)
    response = {'statusCode': 200, 'body': json.dumps({"msg": "TEST"})}

def battle_settlement(battle_players, room_name):
    user_id_1 = battle_players[0]
    user_id_2 = battle_players[1]

    in_battle_score_1 = int(redis_client.get("%s_in_battle_score" % user_id_1))
    in_battle_score_2 = int(redis_client.get("%s_in_battle_score" % user_id_2))

    user_info_1 = getUserInfo(user_id_1)
    user_info_2 = getUserInfo(user_id_2)

    if user_info_1 == None or user_info_2 == None:
        logger.error("Got nonexists user_id=[%s, %s] when battle_settlement" % (user_id_1, user_id_2))
        return

    winner_id = None
    if in_battle_score_1 > in_battle_score_2:
        winner_id = user_id_1
    elif in_battle_score_1 < in_battle_score_2:
        winner_id = user_id_2

    message = '{"action":"battle_settlement", "data":"UNKNOW"}'
    for user_id in battle_players:
        user_info = getUserInfo(user_id)
        in_battle_score = int(redis_client.get("%s_in_battle_score" % user_id))
        connection_id = getConnIDFromUserID(user_id)
        if winner_id == None:
            message = '{"action":"battle_settlement", "data":"DRAW"}'
            user_info["battle_score"] += int(in_battle_score / 10)
            logger.info("Battle DRAW, user_id=%s, battle_score=%d" % (user_id, user_info["battle_score"]))
        elif user_id == winner_id:
            message = '{"action":"battle_settlement", "data":"WIN"}'
            user_info["win"] += 1
            user_info["battle_score"] += (WIN_SCORE + int(in_battle_score / 10))
            logger.info("Battle WIN, user_id=%s, battle_score=%d" % (user_id, user_info["battle_score"]))
        else:
            message = '{"action":"battle_settlement", "data":"LOSE"}'
            user_info["lose"] += 1
            user_info["battle_score"] += (LOSE_SCORE + int(in_battle_score / 10))
            logger.info("Battle LOSE, user_id=%s, battle_score=%d" % (user_id, user_info["battle_score"]))
        server_response(connection_id, message)
        update_leaderboards_multi(user_id, int(user_info["battle_score"]))
        player_info_table.put_item(Item=user_info)

    clear_battle_data(battle_players, room_name)

def clear_battle_data(battle_players, room_name):
    for user_id in battle_players:
        redis_client.delete("%s_in_battle_die" % user_id)
        redis_client.delete("%s_in_battle_score" % user_id)
    destroyroom(room_name)
    logger.info("All battle data cleared. room_name=%s, user_id=%s" % (room_name, battle_players))

def update_leaderboards_single(user_id, score):
    redis_client.zadd(LEADERBOARDS_SINGLE, {user_id: score})
    logger.info("leaderboards_single updated.")

def update_leaderboards_multi(user_id, score):
    redis_client.zadd(LEADERBOARDS_MULTI, {user_id: score})
    logger.info("leaderboards_multi updated.")

def handle_clear_all_data():
    all_ddb_tables = [connection_info_table_name, common_resources_table_name,player_info_table_name ]
    for ddb_table in all_ddb_tables:
        truncateDDBTable(ddb_table)
    redis_client.flushall()
    return {'statusCode': 200, 'body': json.dumps({"msg": "All data cleared."})}

def truncateDDBTable(tableName):
    dynamo = boto3.resource('dynamodb')
    table = dynamo.Table(tableName)
    tableKeyNames = [key.get("AttributeName") for key in table.key_schema]

    #Only retrieve the keys for each item in the table (minimize data transfer)
    projectionExpression = ", ".join('#' + key for key in tableKeyNames)
    expressionAttrNames = {'#'+key: key for key in tableKeyNames}
    counter = 0
    page = table.scan(ProjectionExpression=projectionExpression, ExpressionAttributeNames=expressionAttrNames)
    with table.batch_writer() as batch:
        while page["Count"] > 0:
            counter += page["Count"]
            # Delete items in batches
            for itemKeys in page["Items"]:
                batch.delete_item(Key=itemKeys)
            # Fetch the next page
            if 'LastEvaluatedKey' in page:
                page = table.scan(
                    ProjectionExpression=projectionExpression, ExpressionAttributeNames=expressionAttrNames,
                    ExclusiveStartKey=page['LastEvaluatedKey'])
            else:
                break
    logger.info(f"{tableName} deleted {counter}")

def handle_get_leaderboards_single(user_id):
    return get_leaderboards(user_id, True)

def handle_get_leaderboards_multi(user_id):
    return get_leaderboards(user_id, False)

def get_leaderboards(user_id, is_single):
    if is_single == True:
        leaderboards_key = LEADERBOARDS_SINGLE
        your_score_key = "highest_score"
    else:
        leaderboards_key = LEADERBOARDS_MULTI
        your_score_key = "battle_score"

    user_info = getUserInfo(user_id)
    if user_info == None:
        response = {'statusCode': 400, 'body': json.dumps({"msg": "User not Exists"})}
        return response

    top_users_raw = redis_client.zrevrangebyscore(name=leaderboards_key, max="+inf", min="-inf", withscores=True, start=0,num=9)
    top_users = []
    for user in top_users_raw:
        top_user = (user[0].decode("utf-8"), int(user[1]))
        top_users.append(top_user)
    your_rank = redis_client.zrevrank(leaderboards_key, user_id) + 1
    your_score = int(user_info[your_score_key])
    return {'statusCode': 200, 'body': json.dumps({"top_users": top_users, "your_rank": your_rank, "your_score": your_score})}


def battleMgrPrecheck(connection_id):
    user_id = getUserIDFromConnID(connection_id)
    if user_id == None:
        logger.error("[battleMgrPrecheck] Unknown user. connection_id='%s'", connection_id)
        return

    room_name = getRoomNameFromUserId(user_id)
    if room_name == None:
        logger.error("[battleMgrPrecheck] Unknown room_name. connection_id='%s', user_id='%s'", connection_id, user_id)
        return

    peer_player_id = getPeerPlayerIDFromRoom(user_id, room_name)
    if peer_player_id == None:
        logger.error("[battleMgrPrecheck] Unknown peer_player_id. connection_id='%s', user_id='%s'", connection_id, user_id)
        return

    return (user_id, room_name, peer_player_id)



