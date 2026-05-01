"""Europe PMC search provider for bioRxiv and medRxiv."""

from __future__ import annotations

import logging

import httpx

from ..models import SearchResult, Source

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"

_SOURCE_FILTERS = {
    Source.BIORXIV: '(SRC:PPR) (PUBLISHER:"bioRxiv")',
    Source.MEDRXIV: '(SRC:PPR) (PUBLISHER:"medRxiv")',
}


class EuropePMCSearch:
    """Search bioRxiv/medRxiv via the Europe PMC REST API."""

    def __init__(self, client: httpx.AsyncClient):
        self.client = client

    async def search(
        self,
        query: str,
        limit: int = 20,
        source: Source = Source.BIORXIV,
        **kwargs,
    ) -> list[SearchResult]:
        source_filter = _SOURCE_FILTERS.get(source)
        if source_filter is None:
            raise ValueError(f"EuropePMCSearch does not support source: {source}")

        full_query = f"{query} {source_filter}"
        params = {
            "query": full_query,
            "format": "json",
            "pageSize": min(limit, 25),
            "resultType": "core",
        }

        resp = await self.client.get(_BASE_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        results: list[SearchResult] = []
        for item in data.get("resultList", {}).get("result", []):
            authors = _parse_authors(item)
            doi = item.get("doi")
            paper_id = item.get("id", "")

            results.append(
                SearchResult(
                    paper_id=paper_id,
                    source=source,
                    title=item.get("title", ""),
                    authors=authors,
                    doi=doi,
                    date=item.get("firstPublicationDate"),
                    abstract=item.get("abstractText"),
                    journal=source.value,
                    url=f"https://doi.org/{doi}" if doi else None,
                )
            )

        return results[:limit]


def _parse_authors(item: dict) -> list[str]:
    author_list = item.get("authorList", {}).get("author", [])
    if author_list:
        return [a.get("fullName", "") for a in author_list if a.get("fullName")]
    author_str = item.get("authorString", "")
    if author_str:
        return [a.strip().rstrip(".") for a in author_str.split(",") if a.strip()]
    return []
