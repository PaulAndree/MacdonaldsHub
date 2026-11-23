#!/usr/bin/env bash
# End-to-end check of the standard frontend image against the real API, through the same proxy the
# browser uses (change 2, task 7.2). It needs the compose stack running and a CLEAN database:
#   docker compose up --build -d --wait && scripts/smoke-real-api.sh
# It imports docs/samples/xlsx/incidencias.xlsx, reviews it, confirms it, and checks what the
# approved walkthroughs rely on. Nothing is sent: the emails stay pending.
set -euo pipefail

BASE="${BASE:-http://localhost:3000}"
MAILPIT="${MAILPIT:-http://localhost:8025}"
SAMPLE="$(dirname "$0")/../docs/samples/xlsx/incidencias.xlsx"
JQ="${JQ:-jq}"

pass() { printf '  ok  %s\n' "$1"; }
fail() { printf 'FAIL  %s\n' "$1" >&2; exit 1; }
expect() { # expect <description> <actual> <expected>
  [ "$2" = "$3" ] && pass "$1" || fail "$1 (got '$2', expected '$3')"
}
api() { curl -fsS "$@"; }

echo "1. The standard build is served, with no example data"
html="$(api "$BASE/")"
echo "$html" | grep -q '<div id="root">' && pass "the SPA is served" || fail "the SPA is not served"
assets="$(echo "$html" | grep -oE '/assets/[^"]+\.js' | sort -u)"
[ -n "$assets" ] || fail "no script found in the page"
for asset in $assets; do
  if api "$BASE$asset" | grep -qE 'Escenario de ejemplo|dh-example-scenario|example\.invalid'; then
    fail "example marker found in $asset"
  fi
done
pass "no example marker in the scripts"
# The proxy answers unknown paths with the page itself, so check what comes back, not the status.
if curl -s "$BASE/mockServiceWorker.js" | grep -q 'Mock Service Worker'; then
  fail "the mock service worker is served"
fi
pass "no mock service worker is served"

echo "2. Session"
session="$(api "$BASE/api/session")"
expect "role" "$(echo "$session" | $JQ -r .role)" "administrator"
expect "permissions" "$(echo "$session" | $JQ -r '.permissions | length')" "6"

echo "3. Upload, preparation and review"
size="$(wc -c < "$SAMPLE" | tr -d ' ')"
created="$(api -X POST "$BASE/api/batches" -H 'Content-Type: application/json' \
  -d "{\"fileName\":\"incidencias.xlsx\",\"sizeBytes\":$size}")"
batch="$(echo "$created" | $JQ -r .batch.id)"
expect "state after registering" "$(echo "$created" | $JQ -r .batch.state)" "uploaded"
url="$(echo "$created" | $JQ -r .upload.url)"
curl -fsS -X PUT "$url" -H 'x-ms-blob-type: BlockBlob' -H 'If-None-Match: *' --data-binary "@$SAMPLE" >/dev/null
pass "the file reached storage directly"
expect "state after the upload" "$(api -X POST "$BASE/api/batches/$batch/uploaded" | $JQ -r .state)" "processing"
state=""
for _ in $(seq 1 40); do
  state="$(api "$BASE/api/batches/$batch" | $JQ -r .state)"
  [ "$state" = "in_review" ] && break
  sleep 2
done
expect "the worker prepared it" "$state" "in_review"
rows="$(api "$BASE/api/batches/$batch/rows?pageSize=200")"
expect "rows" "$(echo "$rows" | $JQ -r .total)" "18"
expect "classes" "$(echo "$rows" | $JQ -c .totalsByClass)" '{"new":8,"duplicate":2,"conflict":2,"error":6}'
expect "no incident exists before confirming" "$(api "$BASE/api/incidents" | $JQ -r .total)" "0"
api "$BASE/api/batches/$batch/excluded-report" -o /tmp/excluded-report.xlsx
[ -s /tmp/excluded-report.xlsx ] && pass "the excluded-rows report downloads" || fail "empty report"

echo "4. Confirmation, once"
version="$(api "$BASE/api/batches/$batch" | $JQ -r .reviewedVersion)"
summary="$(api "$BASE/api/batches/$batch/confirmation-summary")"
expect "emails to generate" "$(echo "$summary" | $JQ -r .emailsToGenerate)" "7"
result="$(api -X POST "$BASE/api/batches/$batch/confirm" -H 'Content-Type: application/json' \
  -d "{\"reviewedVersion\":\"$version\"}")"
expect "created incidents" "$(echo "$result" | $JQ -r .createdIncidents)" "8"
expect "pending emails" "$(echo "$result" | $JQ -r .pendingEmails)" "7"
again="$(api -X POST "$BASE/api/batches/$batch/confirm" -H 'Content-Type: application/json' \
  -d "{\"reviewedVersion\":\"$version\"}")"
expect "a repeated confirmation returns the stored result" "$(echo "$again" | $JQ -r .alreadyConfirmed)" "true"
expect "incidents after confirming" "$(api "$BASE/api/incidents" | $JQ -r .total)" "8"

echo "5. Nothing is sent"
if curl -fsS "$MAILPIT/api/v1/messages" >/tmp/mailpit.json 2>/dev/null; then
  expect "messages captured" "$($JQ -r .total /tmp/mailpit.json)" "0"
else
  echo "  --  mail capture not reachable, skipped"
fi

echo "6. Incidents, manual entry and the dashboard"
glovo="$(api "$BASE/api/incidents?provider=glovo" | $JQ -r '.items[0].id')"
expect "claim a Glovo incident" \
  "$(api -X POST "$BASE/api/incidents/$glovo/claim" -H 'Content-Type: application/json' -d '{"claimDate":"2026-11-21"}' | $JQ -r .status)" "claimed"
entry='{"provider":"uber eats","orderId":"UE-SMOKE-1","incidentDate":"2026-11-21","incidentTime":null,"branch":null,"claimAmount":"18.75","providerCosts":null,"total":null,"description":null}'
expect "a new manual entry is new" "$(api -X POST "$BASE/api/incidents/manual/check" -H 'Content-Type: application/json' -d "$entry" | $JQ -r .outcome)" "new"
expect "it is saved with its email pending" \
  "$(api -X POST "$BASE/api/incidents/manual" -H 'Content-Type: application/json' -d "$entry" | $JQ -r .status)" "pending_send"
expect "the same key is refused" \
  "$(curl -s -o /dev/null -w '%{http_code}' -X POST "$BASE/api/incidents/manual" -H 'Content-Type: application/json' -d "$entry")" "409"
metrics="$(api "$BASE/api/metrics")"
expect "criteria are approved" "$(echo "$metrics" | $JQ -r .criteria.status)" "approved"
expect "claim date by default" "$(echo "$metrics" | $JQ -r .dateKind)" "claim"
expect "one pending claim" "$(echo "$metrics" | $JQ -r '.pendingClaims | length')" "1"

echo "7. Cerrar sesión discards nothing when nothing is pending"
expect "discarded" "$(api -X POST "$BASE/api/batches/discard-unconfirmed" | $JQ -r .discarded)" "0"

echo
echo "All checks passed against the real API."
