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

        if route_key == 'joinroom':
            user_id = utils.getUserIDFromConnID(connection_id)
            if user_id == None:
                response['statusCode'] = 403
                logger.info("Unknown user joinroom. connection_id='%s'", connection_id)
            else:
                response['statusCode'] = utils.handle_joinroom(connection_id, user_id)
            return response

        if route_key == 'exitroom':
            user_id = utils.getUserIDFromConnID(connection_id)
            room_name = utils.getRoomNameFromUserId(user_id)
            if user_id == None:
                response['statusCode'] = 403
                logger.info("Unknown user exitroom. connection_id='%s'", connection_id)
            elif room_name == None:
                response['statusCode'] = 403
                logger.info("Unknown room_name to exitroom. connection_id='%s', user_id='%s'", connection_id, user_id)
            else:
                response['statusCode'] = utils.handle_exitroom(user_id, room_name)
            return response

        if route_key == 'destroyroom':
            user_id = utils.getUserIDFromConnID(connection_id)
            room_name = utils.getRoomNameFromUserId(user_id)
            if user_id == None:
                response['statusCode'] = 403
                logger.info("Unknown user exitroom. connection_id='%s'", connection_id)
            elif room_name == None:
                response['statusCode'] = 403
                logger.info("Unknown room_name to exitroom. connection_id='%s', user_id='%s'", connection_id, user_id)
            else:
                response['statusCode'] = utils.handle_destroyroom(room_name)
            return response

    except Exception as err:
        logger.exception("Something went wrong: %s", err)
        return {'statusCode': 500}
