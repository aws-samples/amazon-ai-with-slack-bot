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

        if path == "/clear_all_data":
            response = utils.handle_clear_all_data()
            return response

        if path == "/tmp_test":
            return {'statusCode': 200, 'body': json.dumps({"msg": "test finished"})}

        return response
    except Exception as err:
        logger.exception("Something went wrong: %s", err)
        return {'statusCode': 500}
