"""Request limiting for the endpoints that spend DeepSeek credits.

One ECS task serves the app, so the counts live in this process: no Redis, no
shared state. Both limits are sliding windows, and setting one to 0 disables it.
"""

import os
import threading
import time
from collections import deque
from collections.abc import Callable  # noqa: TC003 - used at runtime
from dataclasses import dataclass
from functools import lru_cache

WINDOW_SECONDS = 60.0
DEFAULT_PER_USER = 10
DEFAULT_EVERYONE = 60

# The key for the shared budget. No email can collide with it.
EVERYONE = "everyone"


class Limiter:
    """Allow at most `limit` hits per `window` seconds for each key."""

    def __init__(
        self,
        limit: int,
        window: float = WINDOW_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Set the ceiling; `clock` is injectable so tests can move time."""
        self.limit = limit
        self.window = window
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()
        self._pruned = clock()

    def retry_after(self, key: str) -> float:
        """Count a hit for `key`; return seconds to wait, or 0.0 if allowed."""
        if self.limit <= 0:
            return 0.0
        now = self._clock()
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and now - hits[0] >= self.window:
                hits.popleft()
            if len(hits) >= self.limit:
                # The oldest hit frees the next slot when its window ends.
                return max(hits[0] + self.window - now, 0.0)
            hits.append(now)
            self._prune(now)
            return 0.0

    def _prune(self, now: float) -> None:
        """Forget idle keys once per window, so the dict cannot grow forever."""
        if now - self._pruned < self.window:
            return
        self._pruned = now
        stale = [
            key
            for key, hits in self._hits.items()
            if not hits or now - hits[-1] >= self.window
        ]
        for key in stale:
            del self._hits[key]


@dataclass(frozen=True)
class Limits:
    """One bucket per signed-in user, and one shared by everyone."""

    per_user: Limiter
    everyone: Limiter


def _limit_from_env(name: str, default: int) -> int:
    raw = os.environ.get(name, "").strip()
    return int(raw) if raw else default


@lru_cache
def get_limits() -> Limits:
    """Return the process-wide limits, reading the environment once.

    A non-numeric value raises here, so a typo fails at startup rather than on
    the first chat request.
    """
    return Limits(
        per_user=Limiter(_limit_from_env("RATE_LIMIT_PER_MINUTE", DEFAULT_PER_USER)),
        everyone=Limiter(
            _limit_from_env("RATE_LIMIT_GLOBAL_PER_MINUTE", DEFAULT_EVERYONE),
        ),
    )
