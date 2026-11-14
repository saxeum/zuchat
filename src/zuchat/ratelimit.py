"""Per-client token bucket. One task, so in-process state is enough."""

from __future__ import annotations

import time
from collections import defaultdict, deque

LIMIT = 20
WINDOW_SECONDS = 60

_hits: dict[str, deque[float]] = defaultdict(deque)


def allow(key: str) -> bool:
    """Record a hit for key; return False when the window is full."""
    now = time.monotonic()
    hits = _hits[key]
    while hits and now - hits[0] > WINDOW_SECONDS:
        hits.popleft()
    if len(hits) >= LIMIT:
        return False
    hits.append(now)
    return True
