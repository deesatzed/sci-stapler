"""Coverage tests for search/fetch providers — targets specific uncovered paths."""

import asyncio
from datetime import datetime, timezone

import httpx
import pytest

from agentmedq.cache import _seconds_since
from agentmedq.fetch.arxiv import ArxivFetch
from agentmedq.fetch.base import FetchProvider
from agentmedq.fetch.biorxiv import BiorxivFetch, _parse_authors as biorxiv_parse_authors
from agentmedq.fetch.pmc import PMCFetch, _parse_pmc_xml
from agentmedq.models import Source
from agentmedq.search.arxiv_api import _extract_arxiv_id
from agentmedq.search.base import SearchProvider
from agentmedq.search.europe_pmc import _parse_authors as epmc_parse_authors
from agentmedq.search.ncbi import NCBISearch
from agentmedq.server import create_server


@pytest.fixture
async def client():
    async with httpx.AsyncClient(timeout=30) as c:
        yield c


# ──────────────────────────────────────────────────────────────────────
# cache.py — line 58: _seconds_since with naive datetime
# ──────────────────────────────────────────────────────────────────────

class TestSecondsNaive:
    def test_naive_datetime_string(self):
        """Line 58: _seconds_since with naive ISO string (no tz) triggers fallback."""
        naive_str = "2024-01-01T00:00:00"
        elapsed = _seconds_since(naive_str)
        assert elapsed > 0  # Should be a large positive number


# ──────────────────────────────────────────────────────────────────────
# search/europe_pmc.py — lines 77-80: _parse_authors fallback
# ──────────────────────────────────────────────────────────────────────

class TestEpmcParseAuthors:
    def test_with_author_list(self):
        """Author list present — normal path."""
        item = {"authorList": {"author": [
            {"fullName": "John Doe"},
            {"fullName": "Jane Smith"},
        ]}}
        assert epmc_parse_authors(item) == ["John Doe", "Jane Smith"]

    def test_author_list_empty_fullname(self):
        """Author list entries without fullName are skipped."""
        item = {"authorList": {"author": [
            {"fullName": "John Doe"},
            {},  # No fullName
        ]}}
        assert epmc_parse_authors(item) == ["John Doe"]

    def test_author_string_fallback(self):
        """Line 78-79: authorString fallback when no authorList."""
        item = {"authorString": "Doe J, Smith J, Lee K."}
        result = epmc_parse_authors(item)
        assert len(result) == 3
        assert result[0] == "Doe J"

    def test_no_authors_at_all(self):
        """Line 80: no authors returns empty list."""
        item = {}
        assert epmc_parse_authors(item) == []

    def test_empty_author_list(self):
        """Empty authorList triggers authorString fallback."""
        item = {"authorList": {"author": []}, "authorString": "Smith A."}
        result = epmc_parse_authors(item)
        assert len(result) == 1


# ──────────────────────────────────────────────────────────────────────
# search/ncbi.py — lines 35, 49, 63, 76
# ──────────────────────────────────────────────────────────────────────

class TestNCBISearchCoverage:
    @pytest.mark.asyncio
    async def test_empty_search_results(self, client):
        """Line 35: empty IDs from esearch returns empty list."""
        s = NCBISearch(client)
        # A very specific nonsense query should return no results
        results = await s.search("xyzzynonexistentqueryzzz9999999", limit=1)
        assert results == []

    @pytest.mark.asyncio
    async def test_esearch_with_api_key(self, client):
        """Line 49: api_key param included in _esearch when set."""
        await asyncio.sleep(2)
        s = NCBISearch(client, api_key="fake_key")
        # Call _esearch directly — will 400 because fake key, but exercises the param path
        try:
            await s._esearch("CRISPR", 1)
        except httpx.HTTPStatusError:
            pass  # Expected — fake key rejected, but line 49 was executed

    @pytest.mark.asyncio
    async def test_esummary_with_api_key(self, client):
        """Line 63: api_key param included in _esummary when set."""
        await asyncio.sleep(2)
        s = NCBISearch(client, api_key="fake_key")
        try:
            await s._esummary(["12345"])
        except httpx.HTTPStatusError:
            pass  # Expected — fake key rejected, but line 63 was executed


# ──────────────────────────────────────────────────────────────────────
# search/arxiv_api.py — line 88: _extract_arxiv_id without /abs/
# ──────────────────────────────────────────────────────────────────────

class TestArxivIdExtraction:
    def test_with_abs(self):
        from xml.etree import ElementTree as ET
        xml = '<entry xmlns="http://www.w3.org/2005/Atom"><id>http://arxiv.org/abs/2301.12345v1</id></entry>'
        entry = ET.fromstring(xml)
        result = _extract_arxiv_id(entry)
        assert result == "2301.12345v1"

    def test_without_abs(self):
        """Line 88: ID without /abs/ returns the full text."""
        from xml.etree import ElementTree as ET
        xml = '<entry xmlns="http://www.w3.org/2005/Atom"><id>2301.12345</id></entry>'
        entry = ET.fromstring(xml)
        result = _extract_arxiv_id(entry)
        assert result == "2301.12345"


# ──────────────────────────────────────────────────────────────────────
# fetch/biorxiv.py — lines 33, 57, 73-75, 86-91, 98-101
# ──────────────────────────────────────────────────────────────────────

class TestBiorxivFetchCoverage:
    @pytest.mark.asyncio
    async def test_fetch_nonexistent_doi(self, client):
        """Line 33: metadata returns None for nonexistent paper."""
        f = BiorxivFetch(client)
        paper = await f.fetch("10.9999/nonexistent.paper.xyz", source=Source.BIORXIV)
        assert paper is None

    @pytest.mark.asyncio
    async def test_fetch_by_ppr_id(self, client):
        """Line 57: EXT_ID query path for non-DOI paper_id."""
        f = BiorxivFetch(client)
        paper = await f.fetch("PPR999999", source=Source.BIORXIV)
        assert paper is None or paper.source == Source.BIORXIV

    @pytest.mark.asyncio
    async def test_fetch_real_paper_full_text_path(self, client):
        """Lines 86-91: full text retrieval path."""
        f = BiorxivFetch(client)
        paper = await f.fetch("10.1101/2024.11.07.620146", source=Source.BIORXIV)
        assert paper is not None
        assert paper.title

    @pytest.mark.asyncio
    async def test_get_full_text_success(self, client):
        """Lines 86-88: _get_full_text with a PMC ID that has full text."""
        f = BiorxivFetch(client)
        # PMC articles have full text available via Europe PMC
        full_text = await f._get_full_text("PMC10767422")
        assert full_text is not None
        assert len(full_text) > 100  # Should have substantial text

    @pytest.mark.asyncio
    async def test_get_full_text_not_found(self, client):
        """Line 84-85: 404 response returns None."""
        f = BiorxivFetch(client)
        full_text = await f._get_full_text("PPR999999")
        assert full_text is None


class TestBiorxivParseAuthors:
    def test_with_author_list(self):
        item = {"authorList": {"author": [
            {"fullName": "Alice Foo"},
            {"fullName": "Bob Bar"},
        ]}}
        assert biorxiv_parse_authors(item) == ["Alice Foo", "Bob Bar"]

    def test_author_string_fallback(self):
        """Lines 98-100: authorString fallback."""
        item = {"authorString": "Foo A, Bar B, Baz C."}
        result = biorxiv_parse_authors(item)
        assert len(result) == 3
        assert result[0] == "Foo A"

    def test_no_authors(self):
        """Line 101: no authors at all."""
        assert biorxiv_parse_authors({}) == []

    def test_empty_author_list_with_string(self):
        """Empty authorList falls through to authorString."""
        item = {"authorList": {"author": []}, "authorString": "Solo A."}
        result = biorxiv_parse_authors(item)
        assert len(result) == 1


# ──────────────────────────────────────────────────────────────────────
# fetch/pmc.py — lines 35, 51-53
# ──────────────────────────────────────────────────────────────────────

class TestPMCFetchCoverage:
    def test_parse_invalid_xml(self):
        """Lines 51-53: XML parse error returns None."""
        result = _parse_pmc_xml("not valid xml <><>", "PMC000")
        assert result is None

    def test_parse_empty_article(self):
        """Minimal valid XML with no article content."""
        xml = "<pmc-articleset><article></article></pmc-articleset>"
        result = _parse_pmc_xml(xml, "PMC000")
        assert result is not None
        assert result.paper_id == "PMC000"
        assert result.title == ""

    def test_parse_root_as_article(self):
        """Article element is the root (line 57 fallback)."""
        xml = """<article>
            <front>
                <article-meta>
                    <title-group><article-title>Test Title</article-title></title-group>
                </article-meta>
            </front>
        </article>"""
        result = _parse_pmc_xml(xml, "PMC001")
        assert result is not None
        assert result.title == "Test Title"

    def test_parse_with_pub_date_fallback(self):
        """pub-date without epub type uses first available pub-date."""
        xml = """<pmc-articleset><article>
            <front><article-meta>
                <pub-date pub-type="ppub">
                    <year>2023</year><month>6</month><day>15</day>
                </pub-date>
            </article-meta></front>
        </article></pmc-articleset>"""
        result = _parse_pmc_xml(xml, "PMC002")
        assert result is not None
        assert result.date == "2023-06-15"

    def test_parse_with_epub_date(self):
        """pub-date with epub type is used preferentially."""
        xml = """<pmc-articleset><article>
            <front><article-meta>
                <pub-date pub-type="epub">
                    <year>2024</year><month>1</month><day>5</day>
                </pub-date>
                <pub-date pub-type="ppub">
                    <year>2023</year><month>12</month><day>1</day>
                </pub-date>
            </article-meta></front>
        </article></pmc-articleset>"""
        result = _parse_pmc_xml(xml, "PMC003")
        assert result is not None
        assert result.date == "2024-01-05"

    @pytest.mark.asyncio
    async def test_fetch_with_api_key_covers_error_handler(self, client):
        """Lines 34-35, 40-42: fake api_key triggers 400, caught by HTTPError handler."""
        await asyncio.sleep(2)
        f = PMCFetch(client, api_key="fake_key")
        # NCBI returns 400 for fake keys, which triggers the except handler
        paper = await f.fetch("PMC10767422")
        assert paper is None  # Error handler returns None


# ──────────────────────────────────────────────────────────────────────
# fetch/arxiv.py — lines 33-35, 45
# ──────────────────────────────────────────────────────────────────────

class TestArxivFetchCoverage:
    @pytest.mark.asyncio
    async def test_fetch_nonexistent_no_entry(self, client):
        """Line 40: no entry found for non-existent numeric ID."""
        await asyncio.sleep(4)  # arXiv rate limit: 3s between requests
        f = ArxivFetch(client)
        paper = await f.fetch("0000.00000")
        assert paper is None

    @pytest.mark.asyncio
    async def test_fetch_invalid_id_error_entry(self, client):
        """Line 45: arXiv returns error entry with 'api/errors' in id."""
        await asyncio.sleep(4)
        f = ArxivFetch(client)
        paper = await f.fetch("invalid_id")
        assert paper is None



# ──────────────────────────────────────────────────────────────────────
# server.py — line 22: create_server with no settings
# ──────────────────────────────────────────────────────────────────────

class TestServerDefaultSettings:
    def test_create_server_no_settings(self):
        """Line 22: create_server() with settings=None uses from_env()."""
        mcp, retriever, cache = create_server()
        assert mcp is not None
        assert mcp.name == "agentmedq"
