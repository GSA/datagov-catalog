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
  echo $VCAP_SERVICES | jq --raw-output --arg service_name "$service_name" ".[][] | select(.name == \$service_name) | ($path | if . == null then empty else . end)"
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

# sitemap S3 settings
export SITEMAP_AWS_REGION=$(vcap_get_service s3 .credentials.region)
export SITEMAP_AWS_ACCESS_KEY_ID=$(vcap_get_service s3 .credentials.access_key_id)
export SITEMAP_AWS_SECRET_ACCESS_KEY=$(vcap_get_service s3 .credentials.secret_access_key)
export SITEMAP_S3_BUCKET=$(vcap_get_service s3 .credentials.bucket)
export SITEMAP_S3_PREFIX=sitemap/
export SITEMAP_INDEX_KEY=sitemap.xml
export SITEMAP_BASE_URL=${SITE_URL}

# SMTP/SES settings for email sending
smtp_server=$(vcap_get_service smtp .credentials.smtp_server)
smtp_user=$(vcap_get_service smtp .credentials.smtp_user)
smtp_password=$(vcap_get_service smtp .credentials.smtp_password)

if [ -n "$smtp_server" ] && [ "$smtp_server" != "null" ]; then
  export SMTP_SERVER="$smtp_server"
  export SMTP_PORT=587
  export SMTP_USER="$smtp_user"
  export SMTP_PASSWORD="$smtp_password"
  export SMTP_STARTTLS="true"
  export SMTP_SENDER=noreply@$(vcap_get_service smtp .credentials.domain_arn | grep -o "ses-[[:alnum:]]\+.appmail.cloud.gov")
  echo "SMTP configured for email sending"
else
  echo "Warning: SMTP service not configured - contact form emails will not be sent"
fi

# Redis for rate limiting
redis_uri=$(vcap_get_service redis .credentials.uri)
if [ -n "$redis_uri" ] && [ "$redis_uri" != "null" ]; then
  export REDIS_URI="$redis_uri"
  echo "Redis configured for rate limiting"
else
  echo "Warning: Redis not configured - rate limiting will use in-memory storage (not suitable for multi-instance deployments)"
fi
