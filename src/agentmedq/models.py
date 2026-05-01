"""Data models for agentmedq."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class Source(str, Enum):
    """Available literature sources."""

    BIORXIV = "biorxiv"
    MEDRXIV = "medrxiv"
    PMC = "pmc"
    ARXIV = "arxiv"
    OPENALEX = "openalex"


class SourceCapabilities(BaseModel):
    """What a source supports."""

    keyword_search: bool = True
    full_text: bool = False
    abstract: bool = True


class SourceInfo(BaseModel):
    """Information about a literature source."""

    name: Source
    display_name: str
    description: str
    record_count: str
    coverage: str
    capabilities: SourceCapabilities
    search_api: str = Field(description="API used for searching this source")


class SearchResult(BaseModel):
    """A single search result."""

    paper_id: str = Field(description="Source-specific paper identifier")
    source: Source
    title: str
    authors: list[str] = Field(default_factory=list)
    doi: str | None = None
    date: str | None = None
    abstract: str | None = None
    journal: str | None = None
    url: str | None = None
    score: float | None = Field(default=None, description="Relevance score if available")


class Paper(BaseModel):
    """Full paper details with optional full text."""

    paper_id: str
    source: Source
    title: str
    authors: list[str] = Field(default_factory=list)
    doi: str | None = None
    date: str | None = None
    abstract: str | None = None
    journal: str | None = None
    url: str | None = None
    full_text: str | None = Field(default=None, description="Full text content if available")
    metadata: dict | None = Field(default=None, description="Source-specific metadata")
    cached_at: datetime | None = Field(default=None, description="When this was cached locally")


# Source registry with static info
SOURCE_REGISTRY: dict[Source, SourceInfo] = {
    Source.BIORXIV: SourceInfo(
        name=Source.BIORXIV,
        display_name="bioRxiv",
        description="Preprint server for the biological sciences, operated by Cold Spring Harbor Laboratory.",
        record_count="~400K",
        coverage="2013-present",
        capabilities=SourceCapabilities(keyword_search=True, full_text=True, abstract=True),
        search_api="Europe PMC",
    ),
    Source.MEDRXIV: SourceInfo(
        name=Source.MEDRXIV,
        display_name="medRxiv",
        description="Preprint server for the health and clinical sciences.",
        record_count="~100K",
        coverage="2019-present",
        capabilities=SourceCapabilities(keyword_search=True, full_text=True, abstract=True),
        search_api="Europe PMC",
    ),
    Source.PMC: SourceInfo(
        name=Source.PMC,
        display_name="PubMed Central (PMC)",
        description="Open-access papers from top journals including Nature, Science, Cell, NEJM, The Lancet.",
        record_count="~7.5M",
        coverage="All years",
        capabilities=SourceCapabilities(keyword_search=True, full_text=True, abstract=True),
        search_api="NCBI E-utilities",
    ),
    Source.ARXIV: SourceInfo(
        name=Source.ARXIV,
        display_name="arXiv",
        description="Preprint server for all scientific categories. Abstract only in v1 (PDF parsing deferred).",
        record_count="~3.0M",
        coverage="1991-present",
        capabilities=SourceCapabilities(keyword_search=True, full_text=False, abstract=True),
        search_api="arXiv API",
    ),
    Source.OPENALEX: SourceInfo(
        name=Source.OPENALEX,
        display_name="OpenAlex",
        description="Title and abstract search across ~50M works. Useful for broad literature surveys.",
        record_count="~50M",
        coverage="All years",
        capabilities=SourceCapabilities(keyword_search=True, full_text=False, abstract=True),
        search_api="OpenAlex API",
    ),
}
