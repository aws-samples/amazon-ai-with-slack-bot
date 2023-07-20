import os
import boto3
import json
from urllib.parse import parse_qs

import sys
sys.path.append('/opt/python/libs')
import utils

SUPPORTTED_LANGUAGE = ['af', 'sq', 'am', 'ar', 'hy', 'auto', 'az', 'bn', 'bs', 'bg', 'fr-CA', 'ca', 'zh', 'zh-TW', 'hr',
                       'cs', 'da', 'fa-AF', 'nl', 'en', 'et', 'fi', 'fr', 'ka', 'de', 'el', 'gu', 'ht', 'ha', 'he',
                       'hi', 'hu', 'is', 'id', 'ga', 'it', 'ja', 'kn', 'kk', 'ko', 'lv', 'lt', 'mk', 'ms', 'ml', 'mt',
                       'mr', 'es-MX', 'mn', 'no', 'ps', 'fa', 'pl', 'pt-PT', 'pt', 'pa', 'ro', 'ru', 'sr', 'si', 'sk',
                       'sl', 'so', 'es', 'sw', 'sv', 'tl', 'ta', 'te', 'th', 'tr', 'uk', 'ur', 'uz', 'vi', 'cy']

SUPPORTTED_SD_MODEL = ["v1-5-pruned-emaonly.safetensors", "DreamShaper.safetensors"]

# Show usage of different cmd
def cmd_usage(cmd):
    if cmd == "Chat":
        return f"*J.A.R.V.I.S {cmd}*\n>*Usage*: /chat [None_Empty_Prompt]"
    elif cmd == "Translate":
        return f"*J.A.R.V.I.S {cmd}*\n>*Usage*: /translate {SUPPORTTED_LANGUAGE} [None_Empty_Prompt]"
    elif cmd == "Image":
        return f"*J.A.R.V.I.S {cmd}*\n>*Usage*: /image {SUPPORTTED_SD_MODEL} [None_Empty_Prompt]"
    elif cmd == "T2s":
        return f"*J.A.R.V.I.S {cmd}*\n>*Usage*: /t2s [None_Empty_Prompt]"
    else:
        return f"*J.A.R.V.I.S {cmd}* Empty Prompt"

def is_input_valid(cmd, parsed_params):
    if "text" not in parsed_params:
        return False
    if cmd == "Image":
        model = parsed_params["text"][0].split(" ")[0]
        if model not in SUPPORTTED_SD_MODEL or len(parsed_params["text"][0].split(" ")) == 1:
            return False
    if cmd == "Translate":
        target_language = parsed_params["text"][0].split(" ")[0]
        if target_language not in SUPPORTTED_LANGUAGE or len(parsed_params["text"][0].split(" ")) == 1:
            return False
    return True

# Just send message to SNS to trigger another lambda
# Different lambda function with different system environment variable of SNSTOPIC
def lambda_handler(event, context):

    # Log all events
    print(f"Archive Event: {event}")

    resource = event.get("resource")
    slack_body = event.get("body")
    headers = event.get("headers")

    # Verify request
    if not utils.verify_request(headers, slack_body):
        print("Unauthorized request.")
        return {
            'statusCode': 403,
            'body': "Unauthorized"
        }

    # Parse request body
    parsed_params = parse_qs(slack_body)


    # Get needed information from request body
    cmd = resource.split('/')[1].capitalize()
    if not is_input_valid(cmd, parsed_params):
        return {
            'statusCode': 200,
            'body': cmd_usage(cmd)
        }
    prompt = parsed_params["text"][0]
    response_url = parsed_params["response_url"][0]
    channel_id = parsed_params["channel_id"][0]

    print(f"Entry Log: cmd={cmd}, prompt={prompt}, channel_id={channel_id}")

    message = {
        "response_url": response_url,
        "channel_id": channel_id,
        "prompt": prompt
    }

    sns_client = boto3.client('sns')
    response = sns_client.publish (
        TargetArn = os.environ.get('SNSTOPIC'),
        Message = json.dumps({'default': json.dumps(message)}),
        MessageStructure = 'json'
    )

    return {
        'statusCode': 200,
        'body': f"*J.A.R.V.I.S {cmd}*\n>*Input*: {prompt}\nWorking on your case, please wait."
    }
