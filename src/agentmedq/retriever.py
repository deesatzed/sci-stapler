"""Retriever protocol and API implementation."""

from __future__ import annotations

import logging
from typing import Protocol

import httpx

from .cache import Cache
from .config import Settings
from .fetch.arxiv import ArxivFetch
from .fetch.biorxiv import BiorxivFetch
from .fetch.pmc import PMCFetch
from .models import Paper, SearchResult, Source
from .rate_limiter import RateLimiter
from .search.arxiv_api import ArxivSearch
from .search.europe_pmc import EuropePMCSearch
from .search.ncbi import NCBISearch
from .search.openalex import OpenAlexSearch

logger = logging.getLogger(__name__)


class Retriever(Protocol):  # pragma: no cover
    """Abstract retriever interface. Swap-point for cam-rag-platform integration."""

    async def search(self, query: str, source: Source, limit: int = 20) -> list[SearchResult]: ...
    async def get_paper(self, paper_id: str, source: Source | None = None) -> Paper | None: ...
    async def lookup(
        self, doi: str | None = None, pmid: str | None = None, pmc_id: str | None = None
    ) -> Paper | None: ...


class APIRetriever:
    """v1 Retriever: queries upstream APIs with caching and rate limiting."""

    def __init__(self, settings: Settings, cache: Cache, rate_limiter: RateLimiter):
        self.settings = settings
        self.cache = cache
        self.rate_limiter = rate_limiter
        self._client: httpx.AsyncClient | None = None

        # Providers initialized lazily after client is created
        self._search_providers: dict[Source, object] | None = None
        self._fetch_providers: dict[Source, object] | None = None

    @property
    def client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=30,
                follow_redirects=True,
                headers={"User-Agent": "agentmedq/0.1.0"},
            )
        return self._client

    def _get_search_providers(self) -> dict:
        if self._search_providers is None:
            europe_pmc = EuropePMCSearch(self.client)
            self._search_providers = {
                Source.BIORXIV: europe_pmc,
                Source.MEDRXIV: europe_pmc,
                Source.PMC: NCBISearch(self.client, api_key=self.settings.ncbi_api_key),
                Source.ARXIV: ArxivSearch(self.client),
                Source.OPENALEX: OpenAlexSearch(self.client, email=self.settings.openalex_email),
            }
        return self._search_providers

    def _get_fetch_providers(self) -> dict:
        if self._fetch_providers is None:
            biorxiv_fetch = BiorxivFetch(self.client)
            self._fetch_providers = {
                Source.BIORXIV: biorxiv_fetch,
                Source.MEDRXIV: biorxiv_fetch,
                Source.PMC: PMCFetch(self.client, api_key=self.settings.ncbi_api_key),
                Source.ARXIV: ArxivFetch(self.client),
            }
        return self._fetch_providers

    def _rate_limit_key(self, source: Source) -> str:
        return {
            Source.BIORXIV: "europe_pmc",
            Source.MEDRXIV: "europe_pmc",
            Source.PMC: "ncbi",
            Source.ARXIV: "arxiv",
            Source.OPENALEX: "openalex",
        }[source]

    async def search(self, query: str, source: Source, limit: int = 20) -> list[SearchResult]:
        """Search for papers. Checks cache first, then queries upstream API."""
        # Check cache
        cached = await self.cache.get_search(query, source.value, limit)
        if cached is not None:
            logger.info("Cache hit for search: %s (source=%s)", query[:50], source.value)
            return cached

        # Rate limit
        await self.rate_limiter.acquire(self._rate_limit_key(source))

        # Query upstream
        providers = self._get_search_providers()
        provider = providers[source]

        if source in (Source.BIORXIV, Source.MEDRXIV):
            results = await provider.search(query, limit=limit, source=source)
        else:
            results = await provider.search(query, limit=limit)

        # Cache results
        if results:
            await self.cache.put_search(query, source.value, limit, results)

        return results

    async def get_paper(self, paper_id: str, source: Source | None = None) -> Paper | None:
        """Get full paper details. Checks cache, then fetches from upstream."""
        # Try cache
        cached = await self.cache.get_paper(paper_id)
        if cached is not None:
            logger.info("Cache hit for paper: %s", paper_id)
            return cached

        # Detect source from ID if not provided
        if source is None:
            source = _detect_source(paper_id)
            if source is None:
                logger.warning("Cannot detect source for paper_id: %s", paper_id)
                return None

        # Rate limit
        await self.rate_limiter.acquire(self._rate_limit_key(source))

        # Fetch
        providers = self._get_fetch_providers()
        provider = providers.get(source)
        if provider is None:
            logger.warning("No fetch provider for source: %s", source.value)
            return None

        if source in (Source.BIORXIV, Source.MEDRXIV):
            paper = await provider.fetch(paper_id, source=source)
        else:
            paper = await provider.fetch(paper_id)

        # Cache
        if paper is not None:
            await self.cache.put_paper(paper)

        return paper

    async def lookup(
        self, doi: str | None = None, pmid: str | None = None, pmc_id: str | None = None
    ) -> Paper | None:
        """Look up a paper by DOI, PMID, or PMC ID."""
        if pmc_id:
            return await self.get_paper(pmc_id, source=Source.PMC)

        if doi:
            # Check cache by DOI
            cached = await self.cache.get_paper_by_doi(doi)
            if cached is not None:
                return cached

            # Try to find via Europe PMC (it covers most sources)
            await self.rate_limiter.acquire("europe_pmc")
            fetch = BiorxivFetch(self.client)
            paper = await fetch.fetch(doi, source=Source.BIORXIV)
            if paper is not None:
                paper.source = _correct_source_from_doi(doi)
                await self.cache.put_paper(paper)
            return paper

        if pmid:
            # Convert PMID to PMC ID via E-utilities link
            await self.rate_limiter.acquire("ncbi")
            pmc_id_found = await self._pmid_to_pmcid(pmid)
            if pmc_id_found:
                return await self.get_paper(pmc_id_found, source=Source.PMC)
            return None

        return None

    async def _pmid_to_pmcid(self, pmid: str) -> str | None:
        """Convert PMID to PMC ID via NCBI ID converter."""
        url = "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/"
        params = {"ids": pmid, "format": "json"}
        try:
            resp = await self.client.get(url, params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
            records = data.get("records", [])
            if records:
                return records[0].get("pmcid")
        except Exception as e:
            logger.warning("Failed to convert PMID %s to PMCID: %s", pmid, e)
        return None

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None


def _correct_source_from_doi(doi: str) -> Source:
    """Correct source attribution based on DOI prefix."""
    doi_lower = doi.lower()
    if "medrxiv" in doi_lower:
        return Source.MEDRXIV
    if "biorxiv" in doi_lower or "10.1101" in doi:
        return Source.BIORXIV
    return Source.PMC


def _detect_source(paper_id: str) -> Source | None:
    """Detect source from paper ID format."""
    pid = paper_id.upper()
    if pid.startswith("PMC"):
        return Source.PMC
    if pid.startswith("PPR"):
        return Source.BIORXIV  # Europe PMC preprint ID; could be either
    if "10.1101/" in paper_id:
        return Source.BIORXIV
    # arXiv IDs look like YYMM.NNNNN
    if "." in paper_id and paper_id.replace(".", "").replace("v", "").isdigit():
        return Source.ARXIV
    if paper_id.startswith("W"):
        return Source.OPENALEX
    return None
