import json
import boto3
from slack_sdk import WebClient

import sys
sys.path.append('/opt/python/libs')
import utils

def format_response(prompt, ans):
    parsed_msg = prompt.split(" ")
    target_language = parsed_msg[0]
    source = ' '.join(parsed_msg[1:])
    msg = [
        {
            "type": "header",
            "text":
            {
                "type": "plain_text",
                "text": "Translate Result"
            }
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Source:*\n{source}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Result:*\n{ans}"
                },
            ]
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*target_language:*\n{target_language}"
                }
            ]
        }
    ]
    return msg

# Get translate result
def get_ans(prompt):
    parsed_msg = prompt.split(" ")
    target_language = parsed_msg[0]
    source = ' '.join(parsed_msg[1:])
    translate = boto3.client("translate")
    source_language = "auto"
    response = translate.translate_text(Text=source, SourceLanguageCode=source_language,
                                        TargetLanguageCode=target_language)

    return response["TranslatedText"]

def send_back_response(prompt, message, channel):
    slack_token = utils.get_secret_value('slack-bot-token')
    slack_client = WebClient(token=slack_token)
    response = format_response(prompt, message)
    slack_response = slack_client.chat_postMessage(
        text = "J.A.R.V.I.S Translate",
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
            print(f"User:{prompt}.\nJ.A.R.V.I.S:{message}")
            send_back_response(prompt, ans, channel)
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
