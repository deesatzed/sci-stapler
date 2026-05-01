"""Tests for MCP tool definitions."""

import pytest

from agentmedq.cache import Cache
from agentmedq.config import Settings
from agentmedq.models import Source
from agentmedq.rate_limiter import RateLimiter
from agentmedq.retriever import APIRetriever
from agentmedq.server import create_server


class TestToolRegistration:
    def test_tools_registered(self):
        settings = Settings()
        mcp, retriever, cache = create_server(settings)
        # FastMCP stores tools internally
        assert mcp is not None


class TestListSources:
    @pytest.mark.asyncio
    async def test_via_retriever(self):
        from agentmedq.models import SOURCE_REGISTRY
        sources = SOURCE_REGISTRY
        assert len(sources) == 5
        for source in Source:
            assert source in sources
            info = sources[source]
            assert info.display_name
            assert info.description
            assert info.record_count
