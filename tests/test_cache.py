"""Tests for SQLite cache."""

import asyncio
from datetime import datetime, timezone, timedelta

import pytest

from agentmedq.cache import Cache, _query_hash, _seconds_since, _now_iso
from agentmedq.models import Paper, SearchResult, Source


@pytest.fixture
async def cache():
    c = Cache(":memory:", search_ttl=86400, paper_ttl=2592000)
    await c.init_db()
    yield c
    await c.close()


class TestCacheHelpers:
    def test_query_hash_deterministic(self):
        h1 = _query_hash("CRISPR", "pmc", 20)
        h2 = _query_hash("CRISPR", "pmc", 20)
        assert h1 == h2

    def test_query_hash_different_inputs(self):
        h1 = _query_hash("CRISPR", "pmc", 20)
        h2 = _query_hash("CRISPR", "biorxiv", 20)
        assert h1 != h2

    def test_query_hash_case_insensitive(self):
        h1 = _query_hash("CRISPR", "pmc", 20)
        h2 = _query_hash("crispr", "pmc", 20)
        assert h1 == h2

    def test_now_iso(self):
        iso = _now_iso()
        dt = datetime.fromisoformat(iso)
        assert dt.tzinfo is not None

    def test_seconds_since(self):
        past = (datetime.now(timezone.utc) - timedelta(seconds=10)).isoformat()
        elapsed = _seconds_since(past)
        assert 9 < elapsed < 12


class TestSearchCache:
    @pytest.mark.asyncio
    async def test_put_and_get(self, cache):
        results = [
            SearchResult(paper_id="PMC123", source=Source.PMC, title="Test Paper"),
        ]
        await cache.put_search("CRISPR", "pmc", 20, results)
        cached = await cache.get_search("CRISPR", "pmc", 20)
        assert cached is not None
        assert len(cached) == 1
        assert cached[0].title == "Test Paper"

    @pytest.mark.asyncio
    async def test_cache_miss(self, cache):
        result = await cache.get_search("nonexistent", "pmc", 20)
        assert result is None

    @pytest.mark.asyncio
    async def test_ttl_expiry(self):
        c = Cache(":memory:", search_ttl=0, paper_ttl=0)  # Immediate expiry
        await c.init_db()
        results = [SearchResult(paper_id="PMC123", source=Source.PMC, title="Test")]
        await c.put_search("test", "pmc", 20, results)
        await asyncio.sleep(0.01)
        cached = await c.get_search("test", "pmc", 20)
        assert cached is None
        await c.close()

    @pytest.mark.asyncio
    async def test_replace_existing(self, cache):
        r1 = [SearchResult(paper_id="PMC1", source=Source.PMC, title="First")]
        r2 = [SearchResult(paper_id="PMC2", source=Source.PMC, title="Second")]
        await cache.put_search("query", "pmc", 20, r1)
        await cache.put_search("query", "pmc", 20, r2)
        cached = await cache.get_search("query", "pmc", 20)
        assert cached[0].title == "Second"


class TestPaperCache:
    @pytest.mark.asyncio
    async def test_put_and_get(self, cache):
        paper = Paper(
            paper_id="PMC123",
            source=Source.PMC,
            title="Test Paper",
            authors=["A. Author"],
            doi="10.1234/test",
            full_text="Full text here",
        )
        await cache.put_paper(paper)
        cached = await cache.get_paper("PMC123")
        assert cached is not None
        assert cached.title == "Test Paper"
        assert cached.doi == "10.1234/test"
        assert cached.full_text == "Full text here"
        assert cached.cached_at is not None

    @pytest.mark.asyncio
    async def test_cache_miss(self, cache):
        result = await cache.get_paper("nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_doi(self, cache):
        paper = Paper(
            paper_id="PMC123",
            source=Source.PMC,
            title="Test",
            doi="10.1234/test",
        )
        await cache.put_paper(paper)
        cached = await cache.get_paper_by_doi("10.1234/test")
        assert cached is not None
        assert cached.paper_id == "PMC123"

    @pytest.mark.asyncio
    async def test_doi_miss(self, cache):
        result = await cache.get_paper_by_doi("10.9999/nonexistent")
        assert result is None

    @pytest.mark.asyncio
    async def test_paper_without_optional_fields(self, cache):
        paper = Paper(paper_id="PMC456", source=Source.PMC, title="Minimal")
        await cache.put_paper(paper)
        cached = await cache.get_paper("PMC456")
        assert cached is not None
        assert cached.authors == []
        assert cached.full_text is None

    @pytest.mark.asyncio
    async def test_paper_ttl_expiry(self):
        c = Cache(":memory:", search_ttl=86400, paper_ttl=0)
        await c.init_db()
        paper = Paper(paper_id="PMC789", source=Source.PMC, title="Expired")
        await c.put_paper(paper)
        await asyncio.sleep(0.01)
        cached = await c.get_paper("PMC789")
        assert cached is None
        await c.close()


class TestCacheInit:
    @pytest.mark.asyncio
    async def test_uninitialized_raises(self):
        c = Cache(":memory:")
        with pytest.raises(RuntimeError, match="not initialized"):
            _ = c.db

    @pytest.mark.asyncio
    async def test_double_close(self):
        c = Cache(":memory:")
        await c.init_db()
        await c.close()
        await c.close()  # Should not raise
