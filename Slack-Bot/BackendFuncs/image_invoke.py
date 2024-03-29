import requests
import json
import boto3
from slack_sdk import WebClient

import sys
sys.path.append('/opt/python/libs')
import utils

Sagemaker_Endpoint = utils.get_secret_value('sd-endpoint')

Default_Payload = {
    "stable_diffusion_model": "v1-5-pruned-emaonly.safetensors",
    "sagemaker_endpoint": Sagemaker_Endpoint,
    "task_type": "txt2img",
    "prompt": "a cute panda",
    "denoising_strength": 0.75,
    "embeddings": [],
    "lora_model": [],
    "hypernetwork_model": [],
    "controlnet_model": [],
    "denoising_strength": 0.75,
    "styles": [""],
    "seed": -1,
    "subseed": -1,
    "subseed_strength": 0,
    "seed_resize_from_h": -1,
    "seed_resize_from_w": -1,
    "batch_size": 1,
    "n_iter": 1,
    "steps": 50,
    "cfg_scale": 7,
    "width": 512,
    "height": 512,
    "restore_faces": "true",
    "tiling": "false",
    "negative_prompt": "",
    "override_settings": {},
    "script_args": [],
    "sampler_index": "Euler",
    "script_name": "",
    "enable_hr": "false",
    "firstphase_width": 0,
    "firstphase_height": 0,
    "hr_scale": 2,
    "hr_upscaler": "string",
    "hr_second_pass_steps": 0,
    "hr_resize_x": 0,
    "hr_resize_y": 0,
}

# Get image from Sagemaker
def get_ans(prompt, channel):

    api-key = utils.get_secret_value('sd-api-key')
    headers = {
        'x-api-key': api-key,
        'Content-Type': 'application/json',
        'Accept': 'application/json',
    }

    payload = Default_Payload
    model = prompt.split(" ")[0]
    prompt = ' '.join(prompt.split(" ")[1:])
    if utils.is_json(prompt):
        prompt = json.loads(prompt)
        for key in payload:
            if key in prompt:
                payload[key] = prompt[key]
    else:
        payload["prompt"] = prompt
    payload["stable_diffusion_model"] = model

    invoke_url = utils.get_secret_value('sd-invoke-url')
    response = requests.post(invoke_url, headers=headers, json=payload)
    return response['output_path']

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
            print(f"Input:{prompt}. Endpoint:{Sagemaker_Endpoint} J.A.R.V.I.S:{message}")
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
