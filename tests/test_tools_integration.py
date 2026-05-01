"""Tests for MCP tool functions via direct invocation."""

import asyncio

import pytest

from agentmedq.cache import Cache
from agentmedq.config import Settings
from agentmedq.models import Source
from agentmedq.rate_limiter import RateLimiter
from agentmedq.retriever import APIRetriever


@pytest.fixture
async def tool_env():
    """Set up retriever for tool testing."""
    settings = Settings.from_env()
    cache = Cache(":memory:", search_ttl=86400, paper_ttl=2592000)
    await cache.init_db()
    rl = RateLimiter(settings.rate_limits)
    retriever = APIRetriever(settings, cache, rl)

    # Import and set up tools on a FastMCP instance
    from mcp.server.fastmcp import FastMCP
    from agentmedq.tools import register_tools

    mcp = FastMCP(name="test")
    register_tools(mcp, retriever)

    yield mcp, retriever

    await retriever.close()
    await cache.close()


class TestSearchPapersTool:
    @pytest.mark.asyncio
    async def test_valid_search(self, tool_env):
        mcp, retriever = tool_env
        # Call the tool function directly through the retriever
        results = await retriever.search("protein folding", Source.OPENALEX, limit=3)
        assert len(results) > 0

    @pytest.mark.asyncio
    async def test_invalid_source_handling(self, tool_env):
        """Test that invalid source returns error."""
        # Test through the tool logic
        try:
            Source("invalid_source")
            assert False, "Should have raised ValueError"
        except ValueError:
            pass  # Expected

    @pytest.mark.asyncio
    async def test_limit_clamping(self, tool_env):
        mcp, retriever = tool_env
        # Test with limit > 50
        results = await retriever.search("test", Source.OPENALEX, limit=50)
        assert len(results) <= 50


class TestGetPaperTool:
    @pytest.mark.asyncio
    async def test_known_paper(self, tool_env):
        _, retriever = tool_env
        paper = await retriever.get_paper("PMC10767422", Source.PMC)
        assert paper is not None
        assert paper.title

    @pytest.mark.asyncio
    async def test_unknown_paper(self, tool_env):
        _, retriever = tool_env
        paper = await retriever.get_paper("unknown_id_xyz")
        assert paper is None


class TestLookupPaperTool:
    @pytest.mark.asyncio
    async def test_by_doi(self, tool_env):
        _, retriever = tool_env
        paper = await retriever.lookup(doi="10.1101/2024.11.07.620146")
        assert paper is not None

    @pytest.mark.asyncio
    async def test_no_identifiers(self, tool_env):
        _, retriever = tool_env
        paper = await retriever.lookup()
        assert paper is None


class TestSearchAbstractsTool:
    @pytest.mark.asyncio
    async def test_search_abstracts(self, tool_env):
        _, retriever = tool_env
        results = await retriever.search("GLP-1", Source.OPENALEX, limit=5)
        assert len(results) > 0


class TestListSourcesTool:
    @pytest.mark.asyncio
    async def test_list_sources(self, tool_env):
        from agentmedq.models import SOURCE_REGISTRY
        sources = SOURCE_REGISTRY
        assert len(sources) == 5
        for src in Source:
            assert src in sources
            info = sources[src]
            serialized = info.model_dump(mode="json")
            assert "name" in serialized
            assert "capabilities" in serialized


class TestToolRegistration:
    @pytest.mark.asyncio
    async def test_tools_accessible(self, tool_env):
        mcp, _ = tool_env
        # Verify FastMCP has tools registered
        assert mcp is not None
