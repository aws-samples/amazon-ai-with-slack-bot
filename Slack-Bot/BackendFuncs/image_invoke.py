import requests
import json
import boto3
from slack_sdk import WebClient
import uuid

import sys
sys.path.append('/opt/python/libs')
import utils

# Don't get this config from OS environment to avoid resync infra
SD_CONFIG = "SD-General"
Sagemaker_Endpoint = "SixInOne"
S3_InputBucket = "slack-bot-aigc-images"

# Get secret value from secretsmanager
def get_sd_config(config_name):
    ssm_client = boto3.client("ssm")
    config = json.loads(ssm_client.get_parameter(Name=config_name)["Parameter"]["Value"])
    return config

# Get image from Sagemaker
def get_ans(prompt, channel):

    # Save sagemaker async inference input to S3
    inference_id = str(uuid.uuid4())
    sagemaker_client = boto3.client("sagemaker-runtime")
    payload = get_sd_config(SD_CONFIG)
    model = prompt.split(" ")[0]
    prompt = ' '.join(prompt.split(" ")[1:])
    if utils.is_json(prompt):
        prompt = json.loads(prompt)
        for key in payload["txt2img_payload"]:
            if key in prompt:
                payload["txt2img_payload"][key] = prompt[key]
    else:
        payload["txt2img_payload"]["prompt"] = prompt
    payload["username"] = model # Create same username as the model(all-in-one-ai)

    s3_resource = boto3.resource("s3")
    s3_object = s3_resource.Object(S3_InputBucket, f"inputs/{inference_id}")
    s3_object.put(Body=bytes(json.dumps(payload).encode('UTF-8')))

    # Invoke Sagemaker Async Endpoint
    input_location = f"s3://{S3_InputBucket}/inputs/{inference_id}"
    response = sagemaker_client.invoke_endpoint_async(
        EndpointName=Sagemaker_Endpoint,
        ContentType='application/json',
        Accept="application/json;jpeg",
        InputLocation=input_location
    )
    output_location = response["OutputLocation"]
    object_key = "/".join(output_location.split("/")[3:])
    save_session(object_key, channel)
    return output_location

def save_session(object_key, channel):
    ddb_table = boto3.resource('dynamodb').Table("Slack-Bot-Image")
    ddb_table.put_item(Item={'object_key': object_key, 'channel': channel})

# Formatted message
def format_response(prompt, ans):
    msg = [
        {
            "type": "header",
            "text":
            {
                "type": "plain_text",
                "text": "J.A.R.V.I.S Image"
            }
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Input :*"
                }
            ]
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"{prompt}"
                }
            ]
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*J.A.R.V.I.S:*"
                }
            ]
        },
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"{ans}"
                }
            ]
        },
    ]
    return msg

def send_back_response(prompt, message, channel):
    slack_token = utils.get_secret_value('slack-bot-token')
    slack_client = WebClient(token=slack_token)
    response = format_response(prompt, message)
    slack_response = slack_client.chat_postMessage(
        text = "J.A.R.V.I.S",
        channel = channel,
        blocks = response
    )

def lambda_handler(event, context):

    for record in event["Records"]:
        msg = json.loads(record["Sns"]["Message"])
        prompt = msg["prompt"]
        channel = msg["channel_id"]

        try:
            ans = get_ans(prompt, channel)
            message = ans.replace("\n", " ")
            print(f"Conversation. You:{prompt}. J.A.R.V.I.S:{message}")
            send_back_response(prompt, message, channel)
            return {
                'statusCode': 200,
                'body': f"{message}"
            }
        except Exception as err:
            import traceback
            print(traceback.format_exc())
            message = "Something is wrong, assistant is being fixed."
            send_back_response(prompt, message, channel)
            return {
                    'statusCode': 200,
                    'body': message
            }
