import os
import boto3
import botocore
import botocore.session
from aws_secretsmanager_caching import SecretCache, SecretCacheConfig
import json
import time
import hmac
import hashlib

# Get secret value from secretsmanager
def get_secret_value(secret_id):
    client = botocore.session.get_session().create_client('secretsmanager')
    cache_config = SecretCacheConfig()
    cache = SecretCache( config = cache_config, client = client)
    return cache.get_secret_string(secret_id)

# Verify request from slack
def verify_request(headers, body):
    signing_secret = os.environ["SIGNING_SECRET"]

    if "X-Slack-Request-Timestamp" not in headers or "X-Slack-Signature" not in headers:
        return False

    timestamp = headers["X-Slack-Request-Timestamp"]
    slack_signature = headers["X-Slack-Signature"]
    if abs(time.time() - int(timestamp)) > 60 * 5:
        return False
    sig_basestring = "v0:" + timestamp + ":" + body
    my_signature = 'v0=' + hmac.new(signing_secret.encode(), sig_basestring.encode(), hashlib.sha256).hexdigest()
    if my_signature == slack_signature:
        return True
    return False

def is_json(input_string):
    try:
        json.loads(input_string)
    except ValueError as e:
        return False
    return True

