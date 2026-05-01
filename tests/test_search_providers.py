"""Integration tests for search providers (hit real APIs)."""

import asyncio

import httpx
import pytest

from agentmedq.models import Source
from agentmedq.search.europe_pmc import EuropePMCSearch
from agentmedq.search.ncbi import NCBISearch
from agentmedq.search.arxiv_api import ArxivSearch
from agentmedq.search.openalex import OpenAlexSearch


@pytest.fixture
async def client():
    async with httpx.AsyncClient() as c:
        yield c


class TestEuropePMCSearch:
    @pytest.mark.asyncio
    async def test_search_biorxiv(self, client):
        s = EuropePMCSearch(client)
        results = await s.search("CRISPR", limit=3, source=Source.BIORXIV)
        assert len(results) > 0
        assert results[0].source == Source.BIORXIV
        assert results[0].title

    @pytest.mark.asyncio
    async def test_search_medrxiv(self, client):
        s = EuropePMCSearch(client)
        results = await s.search("COVID", limit=3, source=Source.MEDRXIV)
        assert len(results) > 0
        assert results[0].source == Source.MEDRXIV

    @pytest.mark.asyncio
    async def test_invalid_source(self, client):
        s = EuropePMCSearch(client)
        with pytest.raises(ValueError):
            await s.search("test", source=Source.PMC)

    @pytest.mark.asyncio
    async def test_limit_respected(self, client):
        s = EuropePMCSearch(client)
        results = await s.search("gene", limit=2, source=Source.BIORXIV)
        assert len(results) <= 2


class TestNCBISearch:
    @pytest.mark.asyncio
    async def test_search_pmc(self, client):
        s = NCBISearch(client)
        results = await s.search("CRISPR", limit=3)
        assert len(results) > 0
        assert results[0].source == Source.PMC
        assert results[0].paper_id.startswith("PMC")

    @pytest.mark.asyncio
    async def test_has_metadata(self, client):
        await asyncio.sleep(1)  # NCBI rate limit: 3 req/s without API key
        s = NCBISearch(client)
        results = await s.search("cancer immunotherapy", limit=1)
        assert len(results) == 1
        r = results[0]
        assert r.title
        assert r.paper_id


class TestArxivSearch:
    @pytest.mark.asyncio
    async def test_search(self, client):
        s = ArxivSearch(client)
        results = await s.search("attention mechanism", limit=3)
        assert len(results) > 0
        assert results[0].source == Source.ARXIV
        assert results[0].abstract

    @pytest.mark.asyncio
    async def test_has_authors(self, client):
        s = ArxivSearch(client)
        results = await s.search("deep learning", limit=1)
        assert len(results) == 1
        assert len(results[0].authors) > 0


class TestOpenAlexSearch:
    @pytest.mark.asyncio
    async def test_search(self, client):
        s = OpenAlexSearch(client)
        results = await s.search("GLP-1 receptor", limit=3)
        assert len(results) > 0
        assert results[0].source == Source.OPENALEX

    @pytest.mark.asyncio
    async def test_has_doi(self, client):
        s = OpenAlexSearch(client)
        results = await s.search("protein folding", limit=5)
        # At least some should have DOIs
        has_doi = any(r.doi for r in results)
        assert has_doi

    @pytest.mark.asyncio
    async def test_with_email(self, client):
        s = OpenAlexSearch(client, email="test@example.com")
        results = await s.search("vaccine", limit=2)
        assert len(results) > 0
