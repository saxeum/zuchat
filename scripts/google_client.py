#!/usr/bin/env python3
"""Print one field from a Google OAuth client JSON (the file the console downloads).

    ./scripts/google_client.py id     ~/.config/zuchat/google-oauth.json
    ./scripts/google_client.py secret ~/.config/zuchat/google-oauth.json

Supports both the "web" and "installed" wrappers.
"""

import json
import sys
from pathlib import Path

FIELDS = {"id": "client_id", "secret": "client_secret"}


def main() -> int:
    if len(sys.argv) != 3 or sys.argv[1] not in FIELDS:  # noqa: PLR2004
        sys.stderr.write(__doc__ or "")
        return 2
    try:
        data = json.loads(Path(sys.argv[2]).read_text())
    except (OSError, ValueError):
        return 1
    payload = data.get("web") or data.get("installed") or data
    sys.stdout.write(payload.get(FIELDS[sys.argv[1]], ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
