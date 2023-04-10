import json
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

from slack_sdk.errors import SlackApiError
import sys
sys.path.append('/opt/python/libs')
import utils

# Get answer from chatGPT
def get_ans(prompt):
    return "DEV"

# Formatted message
def format_response(prompt, ans):
    msg = [
        {
            "type": "header",
            "text":
            {
                "type": "plain_text",
                "text": "J.A.R.V.I.S Template"
            }
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*You:*"
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
            ans = get_ans(prompt)
            message = ans.replace("\n", " ")
            print(f"Conversation. You:{prompt}. J.A.R.V.I.S:{message}")
            send_back_response(prompt, message, channel)
            return {
                'statusCode': 200,
                'body': f"{message}"
            }
        except Exception as err:
            print(f"Something went wrong: {err}")
            if "That model is currently overloaded with other requests" in str(err):
                message = "That model is currently overloaded with other requests."
                send_back_response(prompt, message, channel)
                return {
                    'statusCode': 200,
                    'body': message
                }
            else:
                message = "Something is wrong, assistant is being fixed."
                send_back_response(prompt, message, channel)
                return {
                    'statusCode': 200,
                    'body': message
                }
