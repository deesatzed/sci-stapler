"""Unit tests for tool standalone functions (tools.py)."""

import pytest

from agentmedq.cache import Cache
from agentmedq.config import Settings
from agentmedq.models import Source
from agentmedq.rate_limiter import RateLimiter
from agentmedq.retriever import APIRetriever
from agentmedq.tools import (
    tool_get_paper,
    tool_list_sources,
    tool_lookup_paper,
    tool_search_abstracts,
    tool_search_papers,
)


@pytest.fixture
async def retriever():
    settings = Settings.from_env()
    cache = Cache(":memory:", search_ttl=86400, paper_ttl=2592000)
    await cache.init_db()
    rl = RateLimiter(settings.rate_limits)
    r = APIRetriever(settings, cache, rl)
    yield r
    await r.close()
    await cache.close()


@pytest.fixture
async def broken_retriever():
    """Retriever with a closed client — all HTTP calls will raise."""
    settings = Settings.from_env()
    cache = Cache(":memory:", search_ttl=86400, paper_ttl=2592000)
    await cache.init_db()
    rl = RateLimiter(settings.rate_limits)
    r = APIRetriever(settings, cache, rl)
    # Create and immediately close the client so any HTTP call fails
    _ = r.client
    await r._client.aclose()
    yield r
    # Already closed, but reset internal state for cleanup
    r._client = None
    await cache.close()


class TestToolSearchPapers:
    @pytest.mark.asyncio
    async def test_valid_search(self, retriever):
        result = await tool_search_papers(retriever, "protein folding", "openalex", limit=3)
        assert "error" not in result
        assert result["source"] == "openalex"
        assert result["query"] == "protein folding"
        assert result["count"] >= 0
        assert isinstance(result["results"], list)

    @pytest.mark.asyncio
    async def test_invalid_source(self, retriever):
        result = await tool_search_papers(retriever, "test", "invalid_source")
        assert "error" in result
        assert "Invalid source" in result["error"]
        assert "invalid_source" in result["error"]

    @pytest.mark.asyncio
    async def test_limit_clamped_high(self, retriever):
        result = await tool_search_papers(retriever, "protein", "openalex", limit=100)
        # limit gets clamped to 50
        assert "error" not in result

    @pytest.mark.asyncio
    async def test_limit_clamped_low(self, retriever):
        result = await tool_search_papers(retriever, "protein", "openalex", limit=0)
        # limit gets clamped to 1
        assert "error" not in result

    @pytest.mark.asyncio
    async def test_case_insensitive_source(self, retriever):
        result = await tool_search_papers(retriever, "CRISPR", "OPENALEX", limit=2)
        assert "error" not in result
        assert result["source"] == "openalex"

    @pytest.mark.asyncio
    async def test_results_serialized(self, retriever):
        result = await tool_search_papers(retriever, "vaccine", "openalex", limit=2)
        if result["count"] > 0:
            r = result["results"][0]
            assert "paper_id" in r
            assert "source" in r
            assert "title" in r


class TestToolGetPaper:
    @pytest.mark.asyncio
    async def test_valid_paper(self, retriever):
        result = await tool_get_paper(retriever, "PMC10767422", source="pmc")
        assert "error" not in result
        assert result["paper_id"] == "PMC10767422"

    @pytest.mark.asyncio
    async def test_invalid_source(self, retriever):
        result = await tool_get_paper(retriever, "PMC123", source="bad_source")
        assert "error" in result
        assert "Invalid source" in result["error"]

    @pytest.mark.asyncio
    async def test_paper_not_found(self, retriever):
        result = await tool_get_paper(retriever, "unknown_id_xyz_999")
        assert "error" in result
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_no_source_auto_detect(self, retriever):
        result = await tool_get_paper(retriever, "PMC10767422")
        assert "error" not in result

    @pytest.mark.asyncio
    async def test_source_none_passed(self, retriever):
        result = await tool_get_paper(retriever, "PMC10767422", source=None)
        assert "error" not in result


class TestToolLookupPaper:
    @pytest.mark.asyncio
    async def test_no_identifiers(self, retriever):
        result = await tool_lookup_paper(retriever)
        assert "error" in result
        assert "at least one" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_by_pmc_id(self, retriever):
        result = await tool_lookup_paper(retriever, pmc_id="PMC10767422")
        if "error" not in result:
            assert result["paper_id"] == "PMC10767422"

    @pytest.mark.asyncio
    async def test_by_doi(self, retriever):
        result = await tool_lookup_paper(retriever, doi="10.1101/2024.11.07.620146")
        assert "error" not in result

    @pytest.mark.asyncio
    async def test_not_found(self, retriever):
        result = await tool_lookup_paper(retriever, doi="10.9999/nonexistent.paper.xyz")
        assert "error" in result
        assert "not found" in result["error"].lower()


class TestToolSearchAbstracts:
    @pytest.mark.asyncio
    async def test_valid_search(self, retriever):
        result = await tool_search_abstracts(retriever, "GLP-1 receptor", limit=3)
        assert "error" not in result
        assert result["source"] == "openalex"
        assert "note" in result
        assert isinstance(result["results"], list)

    @pytest.mark.asyncio
    async def test_limit_clamped_high(self, retriever):
        result = await tool_search_abstracts(retriever, "test", limit=100)
        assert "error" not in result

    @pytest.mark.asyncio
    async def test_limit_clamped_low(self, retriever):
        result = await tool_search_abstracts(retriever, "test", limit=-5)
        assert "error" not in result


class TestToolListSources:
    @pytest.mark.asyncio
    async def test_returns_all_sources(self):
        result = await tool_list_sources()
        assert "sources" in result
        assert len(result["sources"]) == 5
        names = {s["name"] for s in result["sources"]}
        for src in Source:
            assert src.value in names

    @pytest.mark.asyncio
    async def test_source_fields(self):
        result = await tool_list_sources()
        for s in result["sources"]:
            assert "name" in s
            assert "display_name" in s
            assert "description" in s
            assert "capabilities" in s


class TestToolSearchPapersError:
    """Test exception handling in tool_search_papers (lines 23-24)."""

    @pytest.mark.asyncio
    async def test_search_exception_returns_error(self, broken_retriever):
        result = await tool_search_papers(broken_retriever, "test", "openalex", limit=1)
        assert "error" in result
        assert "Search failed" in result["error"]


class TestToolGetPaperError:
    """Test exception handling in tool_get_paper (lines 46-47)."""

    @pytest.mark.asyncio
    async def test_fetch_exception_returns_error(self, broken_retriever):
        result = await tool_get_paper(broken_retriever, "PMC10767422", source="pmc")
        assert "error" in result
        assert "Fetch failed" in result["error"]


class TestToolLookupPaperError:
    """Test exception handling in tool_lookup_paper (lines 67-68)."""

    @pytest.mark.asyncio
    async def test_lookup_exception_returns_error(self, broken_retriever):
        result = await tool_lookup_paper(broken_retriever, doi="10.1101/2024.11.07.620146")
        assert "error" in result
        assert "Lookup failed" in result["error"]


class TestToolSearchAbstractsError:
    """Test exception handling in tool_search_abstracts (lines 83-84)."""

    @pytest.mark.asyncio
    async def test_search_exception_returns_error(self, broken_retriever):
        result = await tool_search_abstracts(broken_retriever, "test", limit=1)
        assert "error" in result
        assert "Search failed" in result["error"]
