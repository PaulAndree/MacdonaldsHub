#!/bin/sh
set -eu
trust="$(printf '%s' "${TRUST_EASY_AUTH_HEADERS:-false}" | tr '[:upper:]' '[:lower:]')"
if [ "$trust" = "true" ]; then
  cp /etc/nginx/identity-available/identity-forward.conf /etc/nginx/identity/headers.conf
  echo "identity headers: forwarded (Easy Auth trusted)"
else
  cp /etc/nginx/identity-available/identity-strip.conf /etc/nginx/identity/headers.conf
  echo "identity headers: stripped"
fi
