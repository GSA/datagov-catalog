#!/usr/bin/env bash
set -euo pipefail

# Hash served static files after `make install-static`.
# Includes built output (assets/) plus JS/CSS served directly from source.
# Output length/format must stay in sync with DEPLOY_ASSET_VERSION_PATTERN
# in app/static_assets.py (7 lowercase hex chars).
find app/static/assets app/static/js app/static/css -type f \
  | sort \
  | xargs sha256sum \
  | sha256sum \
  | awk '{print substr($1, 1, 7)}'
