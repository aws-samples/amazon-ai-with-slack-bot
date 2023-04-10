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
        path = event.get('path')
        res_msg = "Path '%s' not registered." % path
        response = {'statusCode': 404, 'body': json.dumps({"msg": res_msg})}

        event_body = event.get('body')
        event_body = json.loads(event_body if event_body is not None else '{}')

        if path == "/create_user":
            user_id = event_body["user_id"]
            response = utils.handle_create_user(user_id)
            return response
        elif path == "/delete_user":
            user_id = event_body["user_id"]
            response = utils.handle_delete_user(user_id)
            return response
        elif path == "/set_score_single":
            user_id = event_body["user_id"]
            score = event_body["score"]
            response = utils.handle_set_score_single(user_id, score)
            return response
        elif path == "/get_leaderboards_single":
            queryString = event.get('queryStringParameters')
            if "user_id" in queryString:
                response = utils.handle_get_leaderboards_single(queryString["user_id"])
                return response
            else:
                return {'statusCode': 400, 'body': json.dumps({"msg": "Invalid user_id"})}
        elif path == "/get_leaderboards_multi":
            queryString = event.get('queryStringParameters')
            if "user_id" in queryString:
                response = utils.handle_get_leaderboards_multi(queryString["user_id"])
                return response
            else:
                return {'statusCode': 400, 'body': json.dumps({"msg": "Invalid user_id"})}

        return response
    except Exception as err:
        logger.exception("Something went wrong: %s", err)
        return {'statusCode': 500}
