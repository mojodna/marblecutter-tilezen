#!/usr/bin/env bash

input=$1

set -eo pipefail

# TODO figure this out from the path of this file
export PATH=/var/task/bin:$PATH
export PYTHONPATH=/var/task/.local/lib/python2.7/site-packages:/var/runtime

function update_aws_credentials() {
  set +u

  # attempt to load credentials from an IAM profile if none were provided
  if [[ -z "$AWS_ACCESS_KEY_ID"  || -z "$AWS_SECRET_ACCESS_KEY" ]]; then
    set +e

    local role=$(curl -sf --connect-timeout 1 http://169.254.169.254/latest/meta-data/iam/security-credentials/)
    local credentials=$(curl -sf --connect-timeout 1 http://169.254.169.254/latest/meta-data/iam/security-credentials/${role})
    export AWS_ACCESS_KEY_ID=$(jq -r .AccessKeyId <<< $credentials)
    export AWS_SECRET_ACCESS_KEY=$(jq -r .SecretAccessKey <<< $credentials)
    export AWS_SESSION_TOKEN=$(jq -r .Token <<< $credentials)

    set -e
  fi

  set -e
}

update_aws_credentials

# update input path for GDAL now that rasterio has read it
if [[ $input =~ "http://" ]] || [[ $input =~ "https://" ]]; then
  gdal_input="/vsicurl/$input"
elif [[ $input =~ "s3://" ]]; then
  gdal_input=$(sed 's|s3://\([^/]*\)/|/vsis3/\1/|' <<< $input)
fi

info=$(rio info $input)
resolution=$(get_resolution.py $input)
small=$(mktemp --tmpdir --suffix=".tif")

# resample using 'average' so that rescaled pixels containing _some_ values
# don't end up as NODATA (better than sampling with rio shapes for this reason)
gdalwarp \
  -q \
  -r average \
  -ts $[$(jq -r .width <<< $info) / 100] $[$(jq -r .height <<< $info) / 100] \
  -srcnodata $(jq -r .nodata <<< $info) \
  -ovr NONE \
  $gdal_input $small

rio shapes --mask --as-mask --precision 6 ${small} | \
  build_metadata.py \
    --meta \
      dimensions=$(jq -c '.shape | reverse' <<< $info) \
      bands=$(jq -c .count <<< $info) \
      dtype=$(jq -c .dtype <<< $info) \
      crs="$(jq -c .crs <<< $info)" \
      colorinterp=$(jq -c .colorinterp <<< $info) \
      resolution=$(jq -c .res <<< $info) \
      resolution_in_meters=${resolution}

rm -f ${small}
