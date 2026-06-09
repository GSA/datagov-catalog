#!/bin/bash

set -o errexit
set -o pipefail

function vcap_get_service () {
  local path name service_name
  name="$1"
  path="$2"
  service_name=${APP_NAME}-${name}
  if [ "$name" = "db" ]; then
    service_name=datagov-harvest-db
  fi
  echo "$VCAP_SERVICES" | jq --raw-output --arg service_name "$service_name" ".[][] | select(.name == \$service_name) | $path"
}

function require_vcap_value () {
  local service="$1"
  local credential_path="$2"
  local label="$3"
  local _val

  _val=$(vcap_get_service "$service" "$credential_path")
  if [ "$_val" = "null" ] || [ -z "$_val" ]; then
    echo "ERROR: ${label} not found in VCAP_SERVICES. Aborting startup." >&2
    exit 1
  fi
  printf '%s' "$_val"
}

function require_vcap_secret () {
  local service="$1"
  local credential_path="$2"
  local env_var="$3"
  local label="${4:-$env_var}"
  local _val

  _val=$(require_vcap_value "$service" "$credential_path" "$label")
  printf -v "$env_var" '%s' "$_val"
  export "$env_var"
}

export APP_NAME=$(echo "$VCAP_APPLICATION" | jq -r '.application_name')

# FLASK SECRET KEY
require_vcap_secret secrets .credentials.FLASK_SECRET_KEY FLASK_SECRET_KEY

# POSTGRES DB CREDS
require_vcap_secret db .credentials.replica_uri URI DATABASE_URI
export DATABASE_URI=$(echo "$URI" | sed 's/postgres:\/\//postgresql+psycopg:\/\//g')

# Opensearch host and credentials
export OPENSEARCH_HOST=$(vcap_get_service opensearch .credentials.host)
require_vcap_secret opensearch .credentials.access_key OPENSEARCH_ACCESS_KEY
require_vcap_secret opensearch .credentials.secret_key OPENSEARCH_SECRET_KEY

# New Relic
require_vcap_secret secrets .credentials.NEW_RELIC_LICENSE_KEY NEW_RELIC_LICENSE_KEY

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

# sitemap S3 settings
export SITEMAP_AWS_REGION=$(vcap_get_service s3 .credentials.region)
require_vcap_secret s3 .credentials.access_key_id SITEMAP_AWS_ACCESS_KEY_ID
require_vcap_secret s3 .credentials.secret_access_key SITEMAP_AWS_SECRET_ACCESS_KEY
export SITEMAP_S3_BUCKET=$(vcap_get_service s3 .credentials.bucket)
export SITEMAP_S3_PREFIX=sitemap/
export SITEMAP_INDEX_KEY=sitemap.xml
export SITEMAP_BASE_URL=${SITE_URL}
