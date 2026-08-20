#!/usr/bin/env bash
set -euo pipefail

# Hash served static files after `make install-static`.
# Includes built output (assets/) plus JS/CSS served directly from source.
# Any of these dirs may be absent (git doesn't track empty dirs), so only
# pass the ones that actually exist to `find`.
dirs=()
for dir in app/static/assets app/static/js app/static/css; do
  [ -d "$dir" ] && dirs+=("$dir")
done

find "${dirs[@]}" -type f \
  | sort \
  | xargs sha256sum \
  | sha256sum \
  | awk '{print substr($1, 1, 7)}'
