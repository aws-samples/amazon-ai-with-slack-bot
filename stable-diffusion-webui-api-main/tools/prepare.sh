#!/bin/bash
if [ "$#" -ne 1 ]; then
    echo "usage: $0 [region]"
    exit 1
fi

if [ -f "./s5cmd" ];
    echo "Please ref to https://github.com/peak/s5cmd and install s5cmd and run again"
fi

echo "Please make sure that you have already put model.tar.gz into assets directory and SD checkpoints (.ckpt) into models directory, please refer to Prepare SD models at https://docs.ai.examples.pro/stable-diffusion-webui/"

userid=$(aws sts get-caller-identity | jq -r .Account)
region=$1
aws s3 mb s3://sagemaker-${region}-${userid} --region ${region}
echo "Uploading assets/model.tar.gz to s3://sagemaker-${region}-${userid}/stable-diffusion-webui/assets/"
AWS_REGION=${region} ./s5cmd cp assets/model.tar.gz s3://sagemaker-${region}-${userid}/stable-diffusion-webui/assets/
echo "Uploading models/ to s3://sagemaker-${region}-${userid}/stable-diffusion-webui/models/"
AWS_REGION=${region} ./s5cmd cp models/ s3://sagemaker-${region}-${userid}/stable-diffusion-webui/models/