"""A per-player limit on recognitions, so a public address cannot be used to spend the model budget.

In memory: the public server runs as at most one instance, and a restart forgetting
the counts only ever makes the limit more generous for a moment, never stricter.
"""

from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Callable

MINUTE = 60.0
DAY = 24 * 60 * 60.0


class RateLimiter:
    def __init__(self, per_minute: int, per_day: int, clock: Callable[[], float] = time.monotonic):
        self.per_minute = per_minute
        self.per_day = per_day
        self.clock = clock
        self._seen: dict[str, deque[float]] = defaultdict(deque)

    def allow(self, client: str) -> bool:
        """Record one request for this client if it is within both limits."""
        now = self.clock()
        seen = self._seen[client]
        while seen and now - seen[0] >= DAY:
            seen.popleft()
        last_minute = sum(1 for t in seen if now - t < MINUTE)
        if last_minute >= self.per_minute or len(seen) >= self.per_day:
            return False
        seen.append(now)
        return True


def client_id(forwarded_for: str | None, peer: str | None) -> str:
    """The player's address: Cloud Run puts it first in X-Forwarded-For."""
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return peer or "unknown"
