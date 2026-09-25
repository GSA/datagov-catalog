#!/bin/bash

set -o errexit
set -o pipefail

function vcap_get_service () {
    local path name
    name="$1"
    path="$2"
    service_name=datagov-catalog-${name}
    echo "$VCAP_SERVICES" | jq --raw-output --arg service_name "$service_name" ".[][] | select(.name == \$service_name) | ($path | if . == null then empty else . end)"
}

export APP_NAME=$(echo "$VCAP_APPLICATION" | jq -r '.application_name')
export SPACE_NAME=$(echo "$VCAP_APPLICATION" | jq -r '.space_name')

echo "Setting up proxy in $APP_NAME on $SPACE_NAME"

# Convert the human-readable CIDR list into the address/value format required
# by nginx's geo include directive.
ALLOWLIST_SOURCE=${HOME}/ip-allow-list.txt
ALLOWLIST_CONFIG=${HOME}/etc/nginx/ip-allow-list.conf
if ! awk '
    /^[[:space:]]*#/ || NF == 0 { next }
    NF != 1 { exit 1 }
    { print $1 " 1;" }
' "$ALLOWLIST_SOURCE" > "$ALLOWLIST_CONFIG"; then
    echo "Invalid entry in $ALLOWLIST_SOURCE" >&2
    exit 1
fi

# sitemap config
export S3_URL=$(vcap_get_service s3 .credentials.endpoint)
export S3_BUCKET=$(vcap_get_service s3 .credentials.bucket)

# basic auth
echo "Setting basic auth username and password"
PROXY_USER=$(vcap_get_service secrets .credentials.PROXY_USER)
PROXY_PASSWORD=$(openssl passwd -apr1 "$(vcap_get_service secrets .credentials.PROXY_PASSWORD)")
echo "$PROXY_USER:$PROXY_PASSWORD" > ${HOME}/etc/nginx/.htpasswd

PROXY_USER_CLIENT=$(vcap_get_service secrets .credentials.PROXY_USER_CLIENT)
PROXY_PASSWORD_CLIENT_RAW=$(vcap_get_service secrets .credentials.PROXY_PASSWORD_CLIENT)
if [[ -n "$PROXY_USER_CLIENT" && -n "$PROXY_PASSWORD_CLIENT_RAW" ]]; then
    PROXY_PASSWORD_CLIENT=$(openssl passwd -apr1 "$PROXY_PASSWORD_CLIENT_RAW")
    echo "$PROXY_USER_CLIENT:$PROXY_PASSWORD_CLIENT" >> ${HOME}/etc/nginx/.htpasswd
else
    echo "Optional client proxy credentials are not configured"
fi
