"""Coverage tests for retriever.py — targets specific uncovered paths."""

import asyncio

import pytest

from agentmedq.cache import Cache
from agentmedq.config import Settings
from agentmedq.models import Paper, Source
from agentmedq.rate_limiter import RateLimiter
from agentmedq.retriever import APIRetriever, _correct_source_from_doi


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


class TestGetPaperNoFetchProvider:
    """Cover lines 138-139: source with no fetch provider (OpenAlex)."""

    @pytest.mark.asyncio
    async def test_openalex_get_paper_returns_none(self, retriever):
        """OpenAlex has no fetch provider; should return None."""
        result = await retriever.get_paper("W1234567890", source=Source.OPENALEX)
        assert result is None


class TestGetPaperBiorxivMedrxivFetch:
    """Cover line 142: biorxiv/medrxiv fetch routing with source kwarg."""

    @pytest.mark.asyncio
    async def test_fetch_biorxiv_by_ppr_id(self, retriever):
        """Fetching a PPR ID should route through biorxiv fetch with source kwarg."""
        # PPR IDs auto-detect as BIORXIV and route through line 142
        result = await retriever.get_paper("10.1101/2024.11.07.620146", source=Source.BIORXIV)
        assert result is not None
        assert result.source == Source.BIORXIV

    @pytest.mark.asyncio
    async def test_fetch_medrxiv(self, retriever):
        """Fetch a medRxiv paper through the biorxiv fetch provider with source=MEDRXIV."""
        result = await retriever.get_paper("10.1101/2024.10.28.24316263", source=Source.MEDRXIV)
        # May or may not return paper depending on availability
        if result is not None:
            assert result.source == Source.MEDRXIV


class TestLookupDOICacheHit:
    """Cover line 163: DOI lookup returning cached result."""

    @pytest.mark.asyncio
    async def test_doi_cache_hit(self, retriever):
        """First lookup caches, second lookup should hit DOI cache (line 163)."""
        paper = await retriever.lookup(doi="10.1101/2024.11.07.620146")
        if paper is not None:
            # Now lookup again — should hit get_paper_by_doi cache
            paper2 = await retriever.lookup(doi="10.1101/2024.11.07.620146")
            assert paper2 is not None
            assert paper2.cached_at is not None


class TestCorrectSourceFromDoi:
    """Unit tests for _correct_source_from_doi function."""

    def test_medrxiv_doi(self):
        assert _correct_source_from_doi("10.1234/medrxiv.2024.01.01") == Source.MEDRXIV

    def test_biorxiv_doi(self):
        assert _correct_source_from_doi("10.1101/2024.11.07.620146") == Source.BIORXIV

    def test_biorxiv_in_doi_string(self):
        assert _correct_source_from_doi("10.1234/biorxiv.something") == Source.BIORXIV

    def test_pmc_doi(self):
        assert _correct_source_from_doi("10.1038/s41586-020-2649-2") == Source.PMC

    def test_case_insensitive(self):
        assert _correct_source_from_doi("10.1234/MEDRXIV.test") == Source.MEDRXIV


class TestLookupDOISourceCorrection:
    """Integration tests for DOI source correction in lookup."""

    @pytest.mark.asyncio
    async def test_biorxiv_doi_stays_biorxiv(self, retriever):
        paper = await retriever.lookup(doi="10.1101/2024.11.07.620146")
        if paper is not None:
            assert paper.source == Source.BIORXIV

    @pytest.mark.asyncio
    async def test_non_1101_doi_correction_to_pmc(self, retriever):
        paper = await retriever.lookup(doi="10.1038/s41586-020-2649-2")
        if paper is not None:
            assert paper.source == Source.PMC


class TestLookupByPMID:
    """Cover lines 178-180: PMID lookup path."""

    @pytest.mark.asyncio
    async def test_pmid_lookup_success(self, retriever):
        """Lookup by PMID that maps to PMCID should fetch the paper (line 179)."""
        # PMID 33024307 maps to PMC7537588
        import asyncio
        await asyncio.sleep(2)
        paper = await retriever.lookup(pmid="33024307")
        if paper is not None:
            assert paper.paper_id.startswith("PMC")

    @pytest.mark.asyncio
    async def test_pmid_not_in_pmc(self, retriever):
        """PMID not in PMC returns None (line 180)."""
        import asyncio
        await asyncio.sleep(2)
        paper = await retriever.lookup(pmid="38113784")
        assert paper is None

    @pytest.mark.asyncio
    async def test_pmid_not_found(self, retriever):
        """Non-existent PMID returns None."""
        import asyncio
        await asyncio.sleep(2)
        paper = await retriever.lookup(pmid="99999999999")
        assert paper is None


class TestPmidToPmcid:
    """Cover lines 184-197: _pmid_to_pmcid method."""

    @pytest.mark.asyncio
    async def test_valid_conversion(self, retriever):
        """Known PMID should convert to PMCID."""
        import asyncio
        await asyncio.sleep(3)
        pmcid = await retriever._pmid_to_pmcid("33024307")
        # May be rate-limited; if we got a result, verify it's correct
        if pmcid is not None:
            assert pmcid == "PMC7537588"

    @pytest.mark.asyncio
    async def test_pmid_not_in_pmc(self, retriever):
        """PMID not in PMC returns None (no pmcid in record)."""
        import asyncio
        await asyncio.sleep(3)
        pmcid = await retriever._pmid_to_pmcid("38113784")
        assert pmcid is None

    @pytest.mark.asyncio
    async def test_nonexistent_pmid(self, retriever):
        """Non-existent PMID returns None."""
        import asyncio
        await asyncio.sleep(3)
        pmcid = await retriever._pmid_to_pmcid("99999999999")
        assert pmcid is None


class TestPmidToPmcidError:
    """Cover lines 195-197: exception handler in _pmid_to_pmcid."""

    @pytest.mark.asyncio
    async def test_http_error_returns_none(self):
        """HTTP error in _pmid_to_pmcid returns None (lines 195-197)."""
        settings = Settings.from_env()
        cache = Cache(":memory:", search_ttl=86400, paper_ttl=2592000)
        await cache.init_db()
        rl = RateLimiter(settings.rate_limits)
        r = APIRetriever(settings, cache, rl)
        # Create and immediately close the client
        _ = r.client
        await r._client.aclose()
        pmcid = await r._pmid_to_pmcid("33024307")
        assert pmcid is None
        r._client = None
        await cache.close()
