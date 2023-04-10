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

        # Handle on connect
        if route_key == '$connect':
            # Create a random user_id for anonymous
            tmp_guest_user_id = ''.join(random.choices(string.ascii_uppercase+string.digits, k=12))
            user_id = event.get('queryStringParameters', {'user_id': tmp_guest_user_id}).get('user_id')
            response['statusCode'] = utils.handle_connect(connection_id, user_id)
            return response

        # Handle on disconnect
        elif route_key == '$disconnect':
            user_id = utils.getUserIDFromConnID(connection_id)
            if user_id == None:
                response['statusCode'] = 404
                logger.info("Unknown user disconnect. connection_id='%s'", connection_id)
                return response
            else:
                response['statusCode'] = utils.handle_disconnect(connection_id, user_id)
                return response
        elif route_key == 'test':
            logger.info("Test route11")
            return response
        else:
            msg = "routeKey '%s' not registered" % event_body["action"]
            logger.info(msg)
            response['statusCode'] = 404
            response['body'] = msg
            return response

    except Exception as err:
        logger.exception("Something went wrong: %s", err)
        return {'statusCode': 500}
