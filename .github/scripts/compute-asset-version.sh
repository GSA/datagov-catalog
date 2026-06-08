#!/usr/bin/env bash
set -euo pipefail

# Hash served static files after `make install-static`.
# Includes built output (assets/) plus JS/CSS served directly from source.
find app/static/assets app/static/js app/static/css -type f \
  | sort \
  | xargs sha256sum \
  | sha256sum \
  | awk '{print substr($1, 1, 7)}'
