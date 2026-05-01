"""Tests for data models."""

import pytest
from pydantic import ValidationError

from agentmedq.models import (
    Paper,
    SearchResult,
    Source,
    SourceCapabilities,
    SourceInfo,
    SOURCE_REGISTRY,
)


class TestSource:
    def test_all_sources_exist(self):
        assert len(Source) == 5

    def test_source_values(self):
        assert Source.BIORXIV.value == "biorxiv"
        assert Source.MEDRXIV.value == "medrxiv"
        assert Source.PMC.value == "pmc"
        assert Source.ARXIV.value == "arxiv"
        assert Source.OPENALEX.value == "openalex"

    def test_source_from_string(self):
        assert Source("biorxiv") == Source.BIORXIV


class TestSearchResult:
    def test_minimal(self):
        r = SearchResult(paper_id="PMC123", source=Source.PMC, title="Test")
        assert r.paper_id == "PMC123"
        assert r.authors == []
        assert r.doi is None

    def test_full(self):
        r = SearchResult(
            paper_id="PMC123",
            source=Source.PMC,
            title="Test Paper",
            authors=["A. Author", "B. Coauthor"],
            doi="10.1234/test",
            date="2024-01-01",
            abstract="Abstract text",
            journal="Nature",
            url="https://doi.org/10.1234/test",
            score=0.95,
        )
        assert len(r.authors) == 2
        assert r.score == 0.95

    def test_json_serialization(self):
        r = SearchResult(paper_id="PMC123", source=Source.PMC, title="Test")
        data = r.model_dump(mode="json")
        assert data["source"] == "pmc"
        assert data["paper_id"] == "PMC123"

    def test_missing_required_field(self):
        with pytest.raises(ValidationError):
            SearchResult(source=Source.PMC, title="Test")  # missing paper_id


class TestPaper:
    def test_minimal(self):
        p = Paper(paper_id="PMC123", source=Source.PMC, title="Test")
        assert p.full_text is None
        assert p.metadata is None

    def test_with_full_text(self):
        p = Paper(
            paper_id="PMC123",
            source=Source.PMC,
            title="Test",
            full_text="Full text content here",
        )
        assert p.full_text == "Full text content here"

    def test_json_round_trip(self):
        p = Paper(
            paper_id="PMC123",
            source=Source.PMC,
            title="Test Paper",
            authors=["Author"],
            doi="10.1234/test",
        )
        data = p.model_dump(mode="json")
        p2 = Paper.model_validate(data)
        assert p2.paper_id == p.paper_id
        assert p2.doi == p.doi


class TestSourceRegistry:
    def test_all_sources_registered(self):
        for source in Source:
            assert source in SOURCE_REGISTRY

    def test_source_info_fields(self):
        info = SOURCE_REGISTRY[Source.PMC]
        assert info.display_name == "PubMed Central (PMC)"
        assert info.capabilities.full_text is True
        assert info.capabilities.keyword_search is True

    def test_arxiv_no_full_text(self):
        info = SOURCE_REGISTRY[Source.ARXIV]
        assert info.capabilities.full_text is False

    def test_openalex_no_full_text(self):
        info = SOURCE_REGISTRY[Source.OPENALEX]
        assert info.capabilities.full_text is False
