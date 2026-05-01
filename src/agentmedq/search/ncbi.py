"""NCBI E-utilities search provider for PubMed Central."""

from __future__ import annotations

import logging
from xml.etree import ElementTree as ET

import httpx

from ..models import SearchResult, Source

logger = logging.getLogger(__name__)

_ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
_ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
_EFETCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


class NCBISearch:
    """Search PubMed Central via NCBI E-utilities (esearch + esummary)."""

    def __init__(self, client: httpx.AsyncClient, api_key: str | None = None):
        self.client = client
        self.api_key = api_key

    async def search(
        self,
        query: str,
        limit: int = 20,
        **kwargs,
    ) -> list[SearchResult]:
        # Step 1: esearch to get PMC IDs
        ids = await self._esearch(query, limit)
        if not ids:
            return []

        # Step 2: esummary to get metadata
        return await self._esummary(ids)

    async def _esearch(self, query: str, limit: int) -> list[str]:
        params: dict = {
            "db": "pmc",
            "term": query,
            "retmax": min(limit, 100),
            "retmode": "json",
            "sort": "relevance",
        }
        if self.api_key:
            params["api_key"] = self.api_key

        resp = await self.client.get(_ESEARCH_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        return data.get("esearchresult", {}).get("idlist", [])

    async def _esummary(self, ids: list[str]) -> list[SearchResult]:
        params: dict = {
            "db": "pmc",
            "id": ",".join(ids),
            "retmode": "json",
        }
        if self.api_key:
            params["api_key"] = self.api_key

        resp = await self.client.get(_ESUMMARY_URL, params=params, timeout=30)
        resp.raise_for_status()
        data = resp.json()

        results: list[SearchResult] = []
        result_data = data.get("result", {})
        uid_list = result_data.get("uids", [])

        for uid in uid_list:
            item = result_data.get(uid)
            if not item:  # pragma: no cover
                continue

            authors = []
            for a in item.get("authors", []):
                name = a.get("name", "")
                if name:
                    authors.append(name)

            doi_list = item.get("articleids", [])
            doi = None
            for aid in doi_list:
                if aid.get("idtype") == "doi":
                    doi = aid.get("value")
                    break

            pmc_id = f"PMC{uid}"
            pub_date = item.get("pubdate", item.get("epubdate", ""))

            results.append(
                SearchResult(
                    paper_id=pmc_id,
                    source=Source.PMC,
                    title=item.get("title", ""),
                    authors=authors,
                    doi=doi,
                    date=pub_date,
                    abstract=None,  # esummary doesn't return abstracts; fetched on demand
                    journal=item.get("fulljournalname", item.get("source", "")),
                    url=f"https://www.ncbi.nlm.nih.gov/pmc/articles/{pmc_id}/",
                )
            )

        return results
