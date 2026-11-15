"""Controls on what a caller may spend.

Three different kinds of abuse, three kinds of counter:

* request rate bounds bursts (a script hammering the endpoint),
* concurrency bounds fan-out (many parallel streams from one account),
* token budgets bound the bill, which is the one that actually matters for an
  LLM: one long prompt can cost more than hundreds of short ones.

One ECS task serves the app, so the counts live in this process: no Redis, no
shared state. Every control is a sliding window or a running total, and a limit
of 0 disables it.
"""

import threading
import time
from collections import deque
from collections.abc import Callable  # noqa: TC003 - used at runtime
from dataclasses import dataclass
from functools import lru_cache

from zuchat.config import get_settings

WINDOW_SECONDS = 60.0
DAY_SECONDS = 86400.0

# A stream that never closed (client vanished, generator never finalised) must
# not lock the user out forever, so a hold older than this is ignored.
STALE_SECONDS = 300.0

# The key for the shared budget. No email can collide with it.
EVERYONE = "everyone"

# DeepSeek bills tokens; this is only a fallback for a reply that ended without
# a usage frame. Four characters per token is the usual English rule of thumb.
CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    """Approximate a token count for text the provider did not measure."""
    return len(text) // CHARS_PER_TOKEN + 1 if text else 0


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

    def hit(self, key: str) -> float:
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


class Gate:
    """Allow at most `limit` simultaneous holders for each key."""

    def __init__(
        self,
        limit: int,
        stale_after: float = STALE_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        """Set the ceiling; `stale_after` releases holds that never came back."""
        self.limit = limit
        self.stale_after = stale_after
        self._clock = clock
        self._held: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def acquire(self, key: str) -> bool:
        """Take a slot for `key`; False when it is already at the ceiling."""
        if self.limit <= 0:
            return True
        now = self._clock()
        with self._lock:
            held = self._held.setdefault(key, deque())
            while held and now - held[0] >= self.stale_after:
                held.popleft()
            if len(held) >= self.limit:
                return False
            held.append(now)
            return True

    def release(self, key: str) -> None:
        """Give a slot back; a no-op when the hold already expired."""
        with self._lock:
            held = self._held.get(key)
            if held:
                held.popleft()


class Budget:
    """Track units spent per key in a fixed window (a UTC day by default)."""

    def __init__(
        self,
        limit: int,
        window: float = DAY_SECONDS,
        clock: Callable[[], float] = time.time,
    ) -> None:
        """Set the ceiling; spend is summed per window bucket."""
        self.limit = limit
        self.window = window
        self._clock = clock
        self._spent: dict[str, tuple[int, int]] = {}
        self._lock = threading.Lock()
        self._pruned = int(clock() // window)

    def retry_after(self, key: str) -> float:
        """Return 0.0 while `key` has room, else seconds until the window rolls."""
        if self.limit <= 0:
            return 0.0
        now = self._clock()
        with self._lock:
            bucket, spent = self._current(key, now)
        if spent < self.limit:
            return 0.0
        return max((bucket + 1) * self.window - now, 0.0)

    def add(self, key: str, units: int) -> None:
        """Record spend; a single reply may overshoot the ceiling slightly."""
        if self.limit <= 0 or units <= 0:
            return
        now = self._clock()
        with self._lock:
            bucket, spent = self._current(key, now)
            self._spent[key] = (bucket, spent + units)
            self._prune(bucket)

    def spent(self, key: str) -> int:
        """Units spent by `key` in the current window."""
        with self._lock:
            return self._current(key, self._clock())[1]

    def _current(self, key: str, now: float) -> tuple[int, int]:
        bucket = int(now // self.window)
        stored = self._spent.get(key)
        if stored is None or stored[0] != bucket:
            return bucket, 0
        return stored

    def _prune(self, bucket: int) -> None:
        """Forget previous windows once per window, so the dict cannot grow."""
        if bucket <= self._pruned:
            return
        self._pruned = bucket
        stale = [key for key, (seen, _) in self._spent.items() if seen < bucket]
        for key in stale:
            del self._spent[key]


@dataclass(frozen=True)
class Limits:
    """Everything that bounds one chat request, built from the settings."""

    per_user: Limiter
    everyone: Limiter
    in_flight: Gate
    tokens_per_user: Budget
    tokens_everyone: Budget
    max_output_tokens: int


@lru_cache
def get_limits() -> Limits:
    """Return the process-wide limits, built from the validated settings."""
    settings = get_settings()
    return Limits(
        per_user=Limiter(settings.rate_limit_per_minute),
        everyone=Limiter(settings.rate_limit_global_per_minute),
        in_flight=Gate(settings.max_concurrent_per_user),
        tokens_per_user=Budget(settings.token_budget_per_day),
        tokens_everyone=Budget(settings.token_budget_global_per_day),
        max_output_tokens=settings.max_output_tokens,
    )


def record(email: str, tokens: int) -> None:
    """Charge measured (or estimated) tokens to the user and to everyone."""
    limits = get_limits()
    limits.tokens_per_user.add(email, tokens)
    limits.tokens_everyone.add(EVERYONE, tokens)
