#!/usr/bin/env bash

source_bucket=$1
source_prefix=$2
target_bucket=$3

aws s3api list-objects-v2 --bucket $source_bucket --prefix $source_prefix --delimiter / --request-payer requester | jq -r '.Contents[].Key' | parallel --retries 10 --no-notice -P 200% --eta aws s3api copy-object --request-payer requester --copy-source $source_bucket/{} --key $source_bucket/{} --bucket $target_bucket
