#!/usr/bin/env bash
# Verifies the frontend proxy: header allowlist, forged identity headers, health, SPA fallback.
# Usage: proxy-test/run.sh [image]   (default image: dh-frontend:dev)
set -euo pipefail
IMAGE="${1:-dh-frontend:dev}"
DIR="$(cd "$(dirname "$0")" && pwd)"
NET="dh-proxy-test-$$"
fail=0

cleanup() { docker rm -f "$NET-up" "$NET-strip" "$NET-trust" >/dev/null 2>&1 || true; docker network rm "$NET" >/dev/null 2>&1 || true; }
trap cleanup EXIT

check() { # description, condition-result
  if [ "$2" = "ok" ]; then echo "PASS  $1"; else echo "FAIL  $1"; fail=1; fi
}

docker network create "$NET" >/dev/null
docker run -d --name "$NET-up" --network "$NET" -v "$DIR/echo_upstream.py:/echo.py:ro" \
  python:3.12-alpine python /echo.py >/dev/null

start_frontend() { # name, trust, host-port
  docker run -d --name "$1" --network "$NET" -p "127.0.0.1:$3:3000" \
    -e API_UPSTREAM="http://$NET-up:8000" -e TRUST_EASY_AUTH_HEADERS="$2" "$IMAGE" >/dev/null
}
start_frontend "$NET-strip" false 13001
start_frontend "$NET-trust" True 13002

wait_for() { for _ in $(seq 1 40); do curl -fs "http://127.0.0.1:$1/healthz" >/dev/null 2>&1 && return 0; sleep 0.5; done; return 1; }
wait_for 13001 && wait_for 13002 || { echo "frontend did not start"; docker logs "$NET-strip" | tail; exit 1; }

hdr() { python3 -c "import json,sys; d=json.load(sys.stdin); print(d['headers'].get(sys.argv[1], '<absent>'))" "$1"; }
FORGED=(-H "X-MS-CLIENT-PRINCIPAL: forged" -H "X-MS-CLIENT-PRINCIPAL-ID: attacker" -H "X-MS-CLIENT-PRINCIPAL-NAME: admin@example.test" -H "X-MS-CLIENT-PRINCIPAL-IDP: google")
OTHER=(-H "Cookie: session=secret" -H "Authorization: Bearer secret" -H "X-Forwarded-For: 6.6.6.6" -H "X-Custom: leak")

# --- trust=false: forged identity headers never reach the API
R=$(curl -fs "${FORGED[@]}" "${OTHER[@]}" "http://127.0.0.1:13001/api/technical/me")
check "strip mode: forged X-MS-CLIENT-PRINCIPAL dropped" "$([ "$(echo "$R" | hdr x-ms-client-principal)" = "<absent>" ] && echo ok)"
check "strip mode: forged principal id/name/idp dropped" "$([ "$(echo "$R" | hdr x-ms-client-principal-id)$(echo "$R" | hdr x-ms-client-principal-name)$(echo "$R" | hdr x-ms-client-principal-idp)" = "<absent><absent><absent>" ] && echo ok)"

# --- both modes: nothing outside the allowlist is forwarded
for port in 13001 13002; do
  R=$(curl -fs "${FORGED[@]}" "${OTHER[@]}" "http://127.0.0.1:$port/api/technical/me")
  leaked=$(echo "$R" | python3 -c "import json,sys; h=json.load(sys.stdin)['headers']; print(','.join(k for k in ('cookie','authorization','x-forwarded-for','x-custom') if k in h))")
  check "port $port: cookie/authorization/custom headers not forwarded" "$([ -z "$leaked" ] && echo ok)"
done

# --- trust=true: Easy Auth headers (set by Easy Auth at the edge in Azure) pass through
R=$(curl -fs "${FORGED[@]}" "http://127.0.0.1:13002/api/technical/me")
check "trust mode: identity headers forwarded" "$([ "$(echo "$R" | hdr x-ms-client-principal-id)" = "attacker" ] && echo ok)"

# --- path and method preserved, Host is the upstream, body passes
R=$(curl -fs -X POST -H "Content-Type: application/json" -d '{"a":1}' "http://127.0.0.1:13001/api/technical/check?x=1")
check "path and query preserved" "$([ "$(echo "$R" | python3 -c "import json,sys; print(json.load(sys.stdin)['path'])")" = "/api/technical/check?x=1" ] && echo ok)"
check "Host header is the upstream host" "$([ "$(echo "$R" | hdr host)" = "$NET-up:8000" ] && echo ok)"
check "request body forwarded" "$([ "$(echo "$R" | python3 -c "import json,sys; print(json.load(sys.stdin)['body'])")" = '{"a":1}' ] && echo ok)"

# --- health and SPA
check "health endpoint answers ok" "$([ "$(curl -fs http://127.0.0.1:13001/healthz)" = "ok" ] && echo ok)"
check "SPA served at /" "$(curl -fs http://127.0.0.1:13001/ | grep -q '<div id="root">' && echo ok)"
check "SPA fallback for client routes" "$(curl -fs http://127.0.0.1:13001/some/route | grep -q '<div id="root">' && echo ok)"
check "/healthz is not proxied to the API" "$(curl -fs http://127.0.0.1:13001/healthz | grep -qv path && echo ok)"

exit $fail
