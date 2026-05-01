"""Tests for rate limiter."""

import asyncio
import time

import pytest

from agentmedq.rate_limiter import RateLimiter, TokenBucket


class TestTokenBucket:
    @pytest.mark.asyncio
    async def test_immediate_acquire(self):
        bucket = TokenBucket(rate=10.0)
        start = time.monotonic()
        await bucket.acquire()
        elapsed = time.monotonic() - start
        assert elapsed < 0.1

    @pytest.mark.asyncio
    async def test_rate_limiting(self):
        bucket = TokenBucket(rate=2.0, burst=2)
        start = time.monotonic()
        for _ in range(4):
            await bucket.acquire()
        elapsed = time.monotonic() - start
        assert elapsed >= 0.5  # 4 requests at 2/s with burst=2

    @pytest.mark.asyncio
    async def test_burst(self):
        bucket = TokenBucket(rate=1.0, burst=3)
        start = time.monotonic()
        for _ in range(3):
            await bucket.acquire()
        elapsed = time.monotonic() - start
        assert elapsed < 0.1  # Burst of 3 should be immediate


class TestRateLimiter:
    @pytest.mark.asyncio
    async def test_unknown_endpoint_passthrough(self):
        rl = RateLimiter({"known": 1.0})
        start = time.monotonic()
        await rl.acquire("unknown")  # Should not block
        elapsed = time.monotonic() - start
        assert elapsed < 0.05

    @pytest.mark.asyncio
    async def test_multiple_endpoints_independent(self):
        rl = RateLimiter({"a": 1.0, "b": 1.0})
        start = time.monotonic()
        await rl.acquire("a")
        await rl.acquire("b")
        elapsed = time.monotonic() - start
        assert elapsed < 0.1  # Independent endpoints
