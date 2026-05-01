"""Async token-bucket rate limiter per API endpoint."""

from __future__ import annotations

import asyncio
import time


class TokenBucket:
    """Token bucket rate limiter for a single endpoint."""

    def __init__(self, rate: float, burst: int | None = None):
        self.rate = rate  # tokens per second
        self.burst = burst or max(1, int(rate))
        self.tokens = float(self.burst)
        self.last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.burst, self.tokens + elapsed * self.rate)
        self.last_refill = now

    async def acquire(self) -> None:
        """Wait until a token is available, then consume it."""
        async with self._lock:
            self._refill()
            if self.tokens >= 1.0:
                self.tokens -= 1.0
                return

            wait = (1.0 - self.tokens) / self.rate
            await asyncio.sleep(wait)
            self._refill()
            self.tokens -= 1.0


class RateLimiter:
    """Manages rate limiters for multiple API endpoints."""

    def __init__(self, rate_limits: dict[str, float]):
        self._buckets: dict[str, TokenBucket] = {}
        for name, rate in rate_limits.items():
            self._buckets[name] = TokenBucket(rate=rate)

    async def acquire(self, endpoint: str) -> None:
        """Wait for rate limit clearance on the given endpoint."""
        bucket = self._buckets.get(endpoint)
        if bucket is None:
            return  # No rate limit configured for this endpoint
        await bucket.acquire()
