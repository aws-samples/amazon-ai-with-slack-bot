#!/bin/bash
set -v
set -e

if [ -z "$2" or -z "$3"] ; then
    echo "Usage: ./secretmanager.sh <secret-id> <region> <get|rotate>"
    exit 1
fi

if [ "$3" != "get" -a "$3" != "rotate" ] ; then
    echo "Usage: ./secretmanager.sh <secret-id> <region> <get|rotate> "
    exit 1
fi

secret_id=$1
region=$2
option=$3

if [ $option == "get" ]; then
secret_value=$(aws secretsmanager get-secret-value --secret-id $secret_id --region $region | jq --raw-output .SecretString)
echo $secret_value
elif [ $option == 'rotate']; then
aws secretsmanager rotate-secret --secret-id $secret_id --region $region
fi