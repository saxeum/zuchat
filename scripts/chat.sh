#!/usr/bin/env bash
#
# Chat with the app over HTTP and print the reply.
#
#   ./scripts/chat.sh "hello"
#   APP_URL=http://127.0.0.1:8000 ./scripts/chat.sh "hello"
#
# Exits non-zero on a non-2xx response, so it doubles as a smoke test.
set -euo pipefail

URL="${APP_URL:-http://127.0.0.1:8000}"
MESSAGE="${1:-hello}"

# JSON-encode the message so quotes/newlines in it can't break the request.
BODY="$(python3 -c 'import json, sys; print(json.dumps({"message": sys.argv[1]}))' "$MESSAGE")"

if ! RESPONSE="$(curl -sS -f -X POST "$URL/chat" \
  -H 'Content-Type: application/json' -d "$BODY")"; then
  echo "error: nothing answering at $URL/chat" >&2
  [ -n "${HINT:-}" ] && echo "hint:  $HINT" >&2
  echo "       (check what is listening: ss -ltn | grep ':800[01]')" >&2
  exit 1
fi

printf '%s' "$RESPONSE" \
  | python3 -c 'import json, sys; print(json.load(sys.stdin)["reply"])'
