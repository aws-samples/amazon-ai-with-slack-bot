#!/usr/bin/python3
import socket
import boto3
import requests
import random
import time
import json
import redis
from websocket import create_connection

ENV = "DEV"

if ENV == "PRODUCTION":
    MAIN_WSS_URL = "wss://xxx.execute-api.ap-southeast-1.amazonaws.com/production"
    PLAYERMGR_URL = "https://xxx.execute-api.ap-southeast-1.amazonaws.com/production"
    GM_URL = "https://xxx.execute-api.ap-southeast-1.amazonaws.com/production"
    PLAYER_INFO_TABLE = "player_info_production"
if ENV == "STAGING":
    MAIN_WSS_URL = "wss://xxx.execute-api.ap-southeast-1.amazonaws.com/staging"
    PLAYERMGR_URL = "https://xxx.execute-api.ap-southeast-1.amazonaws.com/staging"
    GM_URL = "https://xxx.execute-api.ap-southeast-1.amazonaws.com/staging"
    PLAYER_INFO_TABLE = "player_info_staging"
elif ENV == "DEV":
    MAIN_WSS_URL = "wss://xxx.execute-api.ap-southeast-1.amazonaws.com/dev"
    PLAYERMGR_URL = "https://xxx.execute-api.ap-southeast-1.amazonaws.com/dev"
    GM_URL = "https://xxx.execute-api.ap-southeast-1.amazonaws.com/dev"
    PLAYER_INFO_TABLE = "player_info_dev"

# PRODUCTION

REDIS_ENDPOINT = "xxx.cache.amazonaws.com"

USER_NUM = 100

def api_test():
    client = boto3.client("apigatewayv2")

    apis = client.get_apis()["Items"]
    for api in apis:
        print(api["Name"], api["ApiId"])

def delete_user(user_id):
    url = "%s/delete_user" % PLAYERMGR_URL
    res = requests.post(url, json={"user_id": user_id})
    print("Delete user %s: %s" % (user_id, res.json()['msg']))

def create_user(user_id):
    url = "%s/create_user" % PLAYERMGR_URL
    res = requests.post(url, json={"user_id": user_id})
    print("Create user %s: %s" % (user_id, res.json()['msg']))

def generate_users():
    for i in range(USER_NUM):
        create_user("Array_%d" %i )

def set_score_single(user_id, score):
    url = "%s/set_score_single" % PLAYERMGR_URL
    res = requests.post(url, json={"user_id": user_id, "score": score})
    print(res.json())

def generate_leaderboards_single():
    for i in range(USER_NUM):
        user_id = "Array_%d" % i
        score = random.randint(0, 5000)
        set_score_single(user_id, score)

def generate_leaderboards_multi():
    half = int(USER_NUM / 2)
    for i in range(half):
        user_id_1 = "Array_%d" % i
        user_id_2 = "Array_%d" % (i+half)
        simulate_battle(user_id_1, user_id_2)


def simulate_battle(user_id_1, user_id_2):
    ws1 = create_connection("%s?user_id=%s" % (MAIN_WSS_URL, user_id_1))
    ws2 = create_connection("%s?user_id=%s" % (MAIN_WSS_URL, user_id_2))

    ws1.send(json.dumps({"action":"joinroom"}))
    print("ws1 Received: '%s'" % ws1.recv())

    ws2.send(json.dumps({"action":"joinroom"}))
    print("ws2 Received: '%s'" % ws2.recv())
    print("ws2 Received: '%s'" % ws2.recv())
    print("ws1 Received: '%s'" % ws1.recv())

    ws1.send(json.dumps({"action":"syncscore", "score": random.randint(0, 2000)}))
    print("ws2 Received: '%s'" % ws2.recv())
    ws2.send(json.dumps({"action":"syncscore", "score": random.randint(0, 2000)}))
    print("ws1 Received: '%s'" % ws1.recv())

    ws1.send(json.dumps({"action":"die"}))
    print("ws2 Received: '%s'" % ws2.recv())
    ws2.send(json.dumps({"action":"die"}))
    print("ws1 Received: '%s'" % ws1.recv())
    print("ws1 Received: '%s'" % ws1.recv())
    print("ws2 Received: '%s'" % ws2.recv())
    ws1.close()
    ws2.close()

def get_leaderboards_single(user_id):
    url = "%s/get_leaderboards_single?user_id=%s" % (PLAYERMGR_URL, user_id)
    res = requests.get(url)
    print("Single Leaderboard")
    print(res.json())

def get_leaderboards_multi(user_id):
    url = "%s/get_leaderboards_multi?user_id=%s" % (PLAYERMGR_URL, user_id)
    res = requests.get(url)
    print("Multi Leaderboard")
    print(res.json())

def clear_all_data():
    url = "%s/clear_all_data" % GM_URL
    res = requests.post(url, json={"foo": "bar"})
    print(res.status_code)
    print(res.json())

def get_all_player_info():
    ddb_client = boto3.client("dynamodb")
    all_player_info = ddb_client.scan(TableName=PLAYER_INFO_TABLE)["Items"]
    for player_info in all_player_info:
        print("user_id=%s, highest_score=%s, battle_score=%s, win=%s, lose=%s" % (player_info["user_id"]['S'],
                                                                                  player_info["highest_score"]['N'],
                                                                                  player_info["battle_score"]['N'],
                                                                                  player_info["win"]['N'],
                                                                                  player_info["lose"]['N']))
    print("All %d users." % len(all_player_info))

def get_player_info(user_id):
    if "MacBook" in socket.gethostname():
        print("Cannot connect to redis locally.")
        return
    pool = redis.ConnectionPool(host=REDIS_ENDPOINT, port=6379, db=0)
    redis_client = redis.Redis(connection_pool=pool)

    if redis_client.zrevrank("leaderboards_single", user_id) != None:
        single_rank = redis_client.zrevrank("leaderboards_single", user_id) + 1
    else:
        single_rank = None

    if redis_client.zrevrank("leaderboards_multi", user_id) != None:
        multi_rank = redis_client.zrevrank("leaderboards_multi", user_id) + 1
    else:
        multi_rank = None

    ddb_client = boto3.client("dynamodb")
    player_info = ddb_client.get_item(TableName=PLAYER_INFO_TABLE,Key={'user_id': {'S': user_id}})["Item"]
    print("user_id=%s, highest_score=%s, battle_score=%s, win=%s, lose=%s, single_rank=%d, multi_rank=%d" % (
        player_info["user_id"]['S'],
        player_info["highest_score"]['N'],
        player_info["battle_score"]['N'],
        player_info["win"]['N'],
        player_info["lose"]['N'],
        single_rank,
        multi_rank)
    )

def unit_test():
    print("%s ENV testing." % ENV)
    user_name = "Taro"
    create_user(user_name)
    get_leaderboards_single(user_name)
    get_leaderboards_multi(user_name)
    delete_user("Taro")
    simulate_battle("Array_%d" % random.randint(0, 50), "Array_%d" % random.randint(50, 100))


def tmp_test():
    url = "%s/tmp_test" % GM_URL
    res = requests.post(url, json={"foo": "bar"})
    print(res.status_code)
    print(res.json())

#get_all_player_info()
#clear_all_data()
#generate_users()
#generate_leaderboards_single()
#generate_leaderboards_multi()

unit_test()
#tmp_test()
