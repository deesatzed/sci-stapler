"""Integration tests for fetch providers (hit real APIs)."""

import httpx
import pytest

from agentmedq.models import Source
from agentmedq.fetch.pmc import PMCFetch, _element_text, _parse_pmc_xml
from agentmedq.fetch.arxiv import ArxivFetch
from agentmedq.fetch.biorxiv import BiorxivFetch, _xml_to_text


@pytest.fixture
async def client():
    async with httpx.AsyncClient() as c:
        yield c


class TestPMCFetch:
    @pytest.mark.asyncio
    async def test_fetch_known_paper(self, client):
        f = PMCFetch(client)
        paper = await f.fetch("PMC10767422")
        assert paper is not None
        assert paper.source == Source.PMC
        assert paper.title
        assert len(paper.authors) > 0
        assert paper.full_text and len(paper.full_text) > 100

    @pytest.mark.asyncio
    async def test_fetch_invalid_id(self, client):
        f = PMCFetch(client)
        paper = await f.fetch("PMC999999999")
        # May return None or empty paper depending on NCBI response
        if paper is not None:
            assert paper.title == "" or paper.full_text is None


class TestArxivFetch:
    @pytest.mark.asyncio
    async def test_fetch_known_paper(self, client):
        import asyncio
        await asyncio.sleep(4)  # arXiv rate limit: 3s between requests
        f = ArxivFetch(client)
        paper = await f.fetch("2301.08745")
        assert paper is not None
        assert paper.source == Source.ARXIV
        assert paper.title
        assert paper.abstract
        assert paper.full_text is None  # No full text in v1

    @pytest.mark.asyncio
    async def test_fetch_with_version(self, client):
        import asyncio
        await asyncio.sleep(4)
        f = ArxivFetch(client)
        paper = await f.fetch("2301.08745v1")
        assert paper is not None

    @pytest.mark.asyncio
    async def test_fetch_invalid_id(self, client):
        import asyncio
        await asyncio.sleep(4)
        f = ArxivFetch(client)
        paper = await f.fetch("0000.00000")
        assert paper is None


class TestBiorxivFetch:
    @pytest.mark.asyncio
    async def test_fetch_by_doi(self, client):
        f = BiorxivFetch(client)
        paper = await f.fetch("10.1101/2024.11.07.620146", source=Source.BIORXIV)
        assert paper is not None
        assert paper.source == Source.BIORXIV
        assert paper.title
        assert len(paper.authors) > 0


class TestXmlToText:
    def test_basic(self):
        xml = "<root><p>Hello</p><p>World</p></root>"
        text = _xml_to_text(xml)
        assert "Hello" in text
        assert "World" in text

    def test_empty(self):
        assert _xml_to_text("") == ""

    def test_nested_tags(self):
        xml = "<root><p>A <b>bold</b> word</p></root>"
        text = _xml_to_text(xml)
        assert "bold" in text


class TestElementText:
    def test_basic(self):
        from xml.etree import ElementTree as ET
        el = ET.fromstring("<p>Hello <b>world</b></p>")
        assert _element_text(el) == "Hello world"
