#!/bin/bash

set -o errexit
set -o pipefail

function vcap_get_service () {
  local path name
  name="$1"
  path="$2"
  service_name=${APP_NAME}-${name}
  if [ "$name" = "db" ]; then
    service_name=datagov-harvest-db
  fi
  echo $VCAP_SERVICES | jq --raw-output --arg service_name "$service_name" ".[][] | select(.name == \$service_name) | $path"
}

export APP_NAME=$(echo $VCAP_APPLICATION | jq -r '.application_name')

# FLASK SECRET KEY
flask_secret=$(vcap_get_service secrets .credentials.FLASK_SECRET_KEY)
if [ -z "$flask_secret" ] || [ "$flask_secret" = "null" ]; then
  echo "FLASK_SECRET_KEY is not found in secrets" >&2
  exit 1
fi
export FLASK_SECRET_KEY="$flask_secret"

# POSTGRES DB CREDS
export URI=$(vcap_get_service db .credentials.replica_uri)
export DATABASE_URI=$(echo $URI | sed 's/postgres:\/\//postgresql+psycopg:\/\//g')

# Opensearch host and credentials
export OPENSEARCH_HOST=$(vcap_get_service opensearch .credentials.host)
export OPENSEARCH_ACCESS_KEY=$(vcap_get_service opensearch .credentials.access_key)
export OPENSEARCH_SECRET_KEY=$(vcap_get_service opensearch .credentials.secret_key)

# New Relic
export NEW_RELIC_LICENSE_KEY=$(vcap_get_service secrets .credentials.NEW_RELIC_LICENSE_KEY)

echo "Setting CA Bundle.."
export REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
export SSL_CERT_FILE=/etc/ssl/certs/ca-certificates.crt

# egress proxy
echo "Setting up egress proxy.."
if [ -z ${proxy_url+x} ]; then
  echo "Egress proxy is not connected."
else
  echo "Egress proxy is enabled, excluding internal domains.."
  export no_proxy=".apps.internal"
  export http_proxy=$proxy_url
  export https_proxy=$proxy_url
fi
