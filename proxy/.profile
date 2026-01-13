#!/bin/bash

set -o errexit
set -o pipefail

function vcap_get_service () {
    local path name
    name="$1"
    path="$2"
    service_name=datagov-catalog-${name}
    echo "$VCAP_SERVICES" | jq --raw-output --arg service_name "$service_name" ".[][] | select(.name == \$service_name) | $path"
}

export APP_NAME=$(echo "$VCAP_APPLICATION" | jq -r '.application_name')
export SPACE_NAME=$(echo "$VCAP_APPLICATION" | jq -r '.space_name')

echo "Setting up proxy in $APP_NAME on $SPACE_NAME"

# sitemap config 
export S3_URL=$(vcap_get_service s3 .credentials.endpoint)
export S3_BUCKET=$(vcap_get_service s3 .credentials.bucket)

# basic auth
echo "Setting basic auth username and password"
PROXY_USER=$(vcap_get_service secrets .credentials.PROXY_USER)
PROXY_PASSWORD=$(openssl passwd -apr1 "$(vcap_get_service secrets .credentials.PROXY_PASSWORD)")
echo "$PROXY_USER:$PROXY_PASSWORD" > ${HOME}/etc/nginx/.htpasswd