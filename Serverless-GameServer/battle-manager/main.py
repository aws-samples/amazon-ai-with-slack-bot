# Copyright Amazon.com, Inc. or its affiliates. All Rights Reserved.
# SPDX-License-Identifier: Apache-2.0

import json
import logging
import random
import string
import os
import sys
import boto3
from botocore.exceptions import ClientError
sys.path.append('/opt/python/libs')
import utils
utils.__init__()

logger = logging.getLogger()
logger.setLevel(logging.INFO)

def main_handler(event, context):
    try:
        # Validate request parameters
        route_key = event.get('requestContext', {}).get('routeKey')
        connection_id = event.get('requestContext', {}).get('connectionId')
        event_body = event.get('body')
        event_body = json.loads(event_body if event_body is not None else '{}')

        if route_key is None or connection_id is None:
            return {'statusCode': 400}

        # Default response
        response = {'statusCode': 200}

        if route_key == 'attack':
            if utils.battleMgrPrecheck(connection_id) == None:
                return {'statusCode': 400}
            user_id, room_name, peer_player_id = utils.battleMgrPrecheck(connection_id)
            response['statusCode'] = utils.handle_attack(user_id, peer_player_id, room_name)
            return response

        if route_key == 'die':
            if utils.battleMgrPrecheck(connection_id) == None:
                return {'statusCode': 400}
            user_id, room_name, peer_player_id = utils.battleMgrPrecheck(connection_id)
            response['statusCode'] = utils.handle_die(user_id, peer_player_id, room_name)
            return response

        if route_key == 'syncscore':
            if utils.battleMgrPrecheck(connection_id) == None:
                return {'statusCode': 400}
            if "score" not in event_body:
                return {'statusCode': 400}
            score = event_body["score"]
            user_id, room_name, peer_player_id = utils.battleMgrPrecheck(connection_id)
            response['statusCode'] = utils.handle_syncscore(user_id, peer_player_id, room_name, score)
            return response

    except Exception as err:
        logger.exception("Something went wrong: %s", err)
        return {'statusCode': 500}
