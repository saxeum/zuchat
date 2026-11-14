#!/usr/bin/env bash
#
# End-to-end check of a running app: send a chat message, expect a given word.
#
#   APP_URL=http://127.0.0.1:8000 ./scripts/smoke.sh   # local `make dev`
#   APP_URL=http://127.0.0.1:8001 ./scripts/smoke.sh   # container
set -euo pipefail

URL="${APP_URL:?APP_URL must be set}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

REPLY="$(APP_URL="$URL" "$HERE/chat.sh" 'Reply with exactly: pong')"
echo "url:   $URL"
echo "reply: $REPLY"

case "$REPLY" in
  *[pP][oO][nN][gG]*) echo "PASS" ;;
  *) echo "FAIL: reply did not contain 'pong'" >&2; exit 1 ;;
esac
