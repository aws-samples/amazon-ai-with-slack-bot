import requests
import json
import boto3
from slack_sdk import WebClient
import base64

import sys
sys.path.append('/opt/python/libs')
import utils

ddb_table = boto3.resource('dynamodb').Table("Slack-Bot-Image")

# Formatted message
def format_response(image_urls, prompt):
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
			"text": {
				"type": "mrkdwn",
				"text": f"*Prompt*: {prompt}"
			}
		},
    ]
    for image_url in image_urls:
        image_block = {
            "type": "image",
            "image_url": image_url,
            "alt_text": "aigc_image"
        }
        msg.append(image_block)
    return msg

def send_back_response(image_urls, prompt, channel):
    slack_token = utils.get_secret_value('slack-bot-token')
    slack_client = WebClient(token=slack_token)
    response = format_response(image_urls, prompt)
    print("channel", channel)
    print("response", response)
    slack_response = slack_client.chat_postMessage(
        text = "J.A.R.V.I.S",
        channel = channel,
        blocks = response
    )

def lambda_handler(event, context):
    s3_client = boto3.client("s3")

    for record in event["Records"]:
        bucket = record["s3"]["bucket"]["name"]
        image_key = record["s3"]["object"]["key"]
        channel = ddb_table.get_item(Key={'object_key': image_key})["Item"]["channel"]
        image_content = json.loads(s3_client.get_object(Bucket=bucket, Key=image_key)["Body"].read())

        image_urls = []
        image_prefix = image_key.replace(".out", "")
        prompt = image_content["parameters"]["prompt"]
        print("prompt: ", prompt)
        for i in range(len(image_content["images"])):
            with open("/tmp/tmp.png", "wb") as image:
                image.write(base64.decodebytes(image_content["images"][i].encode('ascii')))
            upload_file_key = f"{image_prefix}_{i}.png"
            s3_client.upload_file("/tmp/tmp.png", bucket, upload_file_key)
            print(f"Upload file: {upload_file_key}")
            image_urls.append(f"https://d2hfi0x3wzw6aa.cloudfront.net/{upload_file_key}")

        s3_client.delete_object(Bucket=bucket, Key=image_key)
        print(f"Delete origin file: {image_key}")
        send_back_response(image_urls, prompt, channel)
        print(f"Images sent successfully")
        return {
            'statusCode': 200,
            'body': "ImageResponse Finished"
        }

