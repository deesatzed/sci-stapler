"""agentmedq MCP server — stdio and HTTP/SSE transports."""

from __future__ import annotations

import asyncio
import logging
import sys

from mcp.server.fastmcp import FastMCP

from .cache import Cache
from .config import Settings
from .rate_limiter import RateLimiter
from .retriever import APIRetriever
from .tools import register_tools

logger = logging.getLogger(__name__)


def create_server(settings: Settings | None = None) -> tuple[FastMCP, APIRetriever, Cache]:
    """Create and configure the MCP server with all tools."""
    if settings is None:
        settings = Settings.from_env()

    mcp = FastMCP(
        name="agentmedq",
        instructions=(
            "Biomedical literature search server. "
            "Search bioRxiv, medRxiv, PubMed Central, arXiv, and OpenAlex. "
            "Use search_papers for source-specific search, "
            "search_abstracts for broad surveys, "
            "get_paper for full text retrieval, "
            "lookup_paper to find papers by DOI/PMID/PMCID, "
            "and list_sources to see available databases."
        ),
        host=settings.host,
        port=settings.port,
    )

    cache = Cache(
        db_path=settings.db_full_path,
        search_ttl=settings.search_cache_ttl,
        paper_ttl=settings.paper_cache_ttl,
    )

    rate_limiter = RateLimiter(settings.rate_limits)
    retriever = APIRetriever(settings, cache, rate_limiter)

    register_tools(mcp, retriever)

    return mcp, retriever, cache


def main() -> None:  # pragma: no cover
    """Entry point for running the server.

    Usage:
        agentmedq              # stdio transport (default, for MCP clients)
        agentmedq --sse        # HTTP/SSE transport on configured host:port
    """
    transport = "stdio"
    if "--sse" in sys.argv:
        transport = "sse"

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    settings = Settings.from_env()
    mcp, retriever, cache = create_server(settings)

    async def init():
        await cache.init_db()
        logger.info("Cache initialized at %s", cache.db_path)

    asyncio.run(init())

    if transport == "sse":
        logger.info("Starting agentmedq MCP server on %s:%s (SSE)", settings.host, settings.port)
    else:
        logger.info("Starting agentmedq MCP server (stdio)")

    mcp.run(transport=transport)


if __name__ == "__main__":  # pragma: no cover
    main()
