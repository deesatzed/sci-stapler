"""MCP tool definitions for agentmedq."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from .cortex import get_mcp_cortex_capabilities
from .models import Source, SOURCE_REGISTRY
from .retriever import APIRetriever


async def tool_search_papers(retriever: APIRetriever, query: str, source: str, limit: int = 20) -> dict:
    """Core logic for search_papers tool."""
    try:
        src = Source(source.lower())
    except ValueError:
        valid = ", ".join(s.value for s in Source)
        return {"error": f"Invalid source '{source}'. Valid sources: {valid}"}

    limit = min(max(1, limit), 50)

    try:
        results = await retriever.search(query, src, limit=limit)
    except Exception as e:
        return {"error": f"Search failed: {e}"}

    return {
        "source": src.value,
        "query": query,
        "count": len(results),
        "results": [r.model_dump(mode="json", exclude_none=True) for r in results],
    }


async def tool_get_paper(retriever: APIRetriever, paper_id: str, source: str | None = None) -> dict:
    """Core logic for get_paper tool."""
    src = None
    if source:
        try:
            src = Source(source.lower())
        except ValueError:
            valid = ", ".join(s.value for s in Source)
            return {"error": f"Invalid source '{source}'. Valid sources: {valid}"}

    try:
        paper = await retriever.get_paper(paper_id, source=src)
    except Exception as e:
        return {"error": f"Fetch failed: {e}"}

    if paper is None:
        return {"error": f"Paper not found: {paper_id}"}

    return paper.model_dump(mode="json", exclude_none=True)


async def tool_lookup_paper(
    retriever: APIRetriever,
    doi: str | None = None,
    pmid: str | None = None,
    pmc_id: str | None = None,
) -> dict:
    """Core logic for lookup_paper tool."""
    if not any([doi, pmid, pmc_id]):
        return {"error": "Provide at least one of: doi, pmid, pmc_id"}

    try:
        paper = await retriever.lookup(doi=doi, pmid=pmid, pmc_id=pmc_id)
    except Exception as e:
        return {"error": f"Lookup failed: {e}"}

    if paper is None:
        identifier = doi or pmid or pmc_id
        return {"error": f"Paper not found for identifier: {identifier}"}

    return paper.model_dump(mode="json", exclude_none=True)


async def tool_search_abstracts(retriever: APIRetriever, query: str, limit: int = 20) -> dict:
    """Core logic for search_abstracts tool."""
    limit = min(max(1, limit), 50)

    try:
        results = await retriever.search(query, Source.OPENALEX, limit=limit)
    except Exception as e:
        return {"error": f"Search failed: {e}"}

    return {
        "source": "openalex",
        "query": query,
        "count": len(results),
        "note": "Abstract-only search. Use search_papers with a specific source for full text.",
        "results": [r.model_dump(mode="json", exclude_none=True) for r in results],
    }


async def tool_list_sources() -> dict:
    """Core logic for list_sources tool."""
    sources = []
    for info in SOURCE_REGISTRY.values():
        sources.append(info.model_dump(mode="json"))
    return {
        "sources": sources,
        "mcp_cortex_capabilities": get_mcp_cortex_capabilities(),
    }


def register_tools(mcp: FastMCP, retriever: APIRetriever) -> None:
    """Register all MCP tools on the server instance."""

    @mcp.tool(
        name="search_papers",
        description=(
            "Search for biomedical papers in a specific source. "
            "Sources: biorxiv, medrxiv, pmc, arxiv, openalex. "
            "Returns ranked results with title, authors, DOI, date, and abstract."
        ),
    )
    async def search_papers(query: str, source: str, limit: int = 20) -> dict:  # pragma: no cover
        """Search for papers in a specific biomedical literature source."""
        return await tool_search_papers(retriever, query, source, limit)

    @mcp.tool(
        name="get_paper",
        description=(
            "Retrieve full details of a specific paper by its ID. "
            "Returns metadata and full text when available. "
            "IDs: PMC1234567 (PMC), PPR123456 or DOI (bioRxiv/medRxiv), "
            "2301.12345 (arXiv), W1234567 (OpenAlex)."
        ),
    )
    async def get_paper(paper_id: str, source: str | None = None) -> dict:  # pragma: no cover
        """Retrieve a specific paper by its ID."""
        return await tool_get_paper(retriever, paper_id, source)

    @mcp.tool(
        name="lookup_paper",
        description=(
            "Find a paper by DOI, PMID, or PMC ID. "
            "Provide exactly one identifier. Returns full paper details."
        ),
    )
    async def lookup_paper(  # pragma: no cover
        doi: str | None = None, pmid: str | None = None, pmc_id: str | None = None
    ) -> dict:
        """Look up a paper by its identifier."""
        return await tool_lookup_paper(retriever, doi, pmid, pmc_id)

    @mcp.tool(
        name="search_abstracts",
        description=(
            "Fast abstract-only search across ~50M works via OpenAlex. "
            "Returns title, authors, DOI, date, and abstract. No full text. "
            "Best for broad literature surveys."
        ),
    )
    async def search_abstracts(query: str, limit: int = 20) -> dict:  # pragma: no cover
        """Search for paper abstracts across all indexed works."""
        return await tool_search_abstracts(retriever, query, limit)

    @mcp.tool(
        name="list_sources",
        description="List all available biomedical literature sources and their capabilities.",
    )
    async def list_sources() -> dict:  # pragma: no cover
        """List available data sources with their capabilities and coverage."""
        return await tool_list_sources()
